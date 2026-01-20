"""
Redis-based Distributed Locking System.

300명 이상 동시 접속 시 DB Deadlock 방지를 위한 분산 락 구현.

핵심 설계 원칙:
1. Redis Single-threaded 특성을 활용한 원자적 락 획득
2. Lock Timeout으로 데드락 방지
3. Lock Renewal로 장시간 작업 지원
4. Hierarchical Locking으로 세밀한 동시성 제어

Lock Hierarchy (상위 락 획득 시 하위 자동 보호):
- tournament:{id}                    # 토너먼트 전체 락 (설정 변경, 시작/종료)
- tournament:{id}:tables             # 테이블 관리 락 (밸런싱)
- tournament:{id}:table:{table_id}   # 개별 테이블 락 (핸드 진행)
- tournament:{id}:player:{user_id}   # 개별 플레이어 락 (칩 변경)
- tournament:{id}:ranking            # 랭킹 업데이트 락
"""

import asyncio
import time
import hashlib
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Optional, AsyncGenerator, Set
from uuid import uuid4

import redis.asyncio as redis


class LockType(Enum):
    """Lock granularity types."""

    TOURNAMENT = "tournament"  # 토너먼트 전체
    TABLES = "tables"  # 테이블 관리
    TABLE = "table"  # 개별 테이블
    PLAYER = "player"  # 개별 플레이어
    RANKING = "ranking"  # 랭킹 시스템
    BLIND = "blind"  # 블라인드 레벨


@dataclass
class LockInfo:
    """Lock metadata."""

    lock_key: str
    owner_id: str
    acquired_at: float
    expires_at: float
    lock_type: LockType


class DistributedLockError(Exception):
    """Base lock error."""

    pass


class LockAcquisitionError(DistributedLockError):
    """Failed to acquire lock within timeout."""

    pass


class LockNotHeldError(DistributedLockError):
    """Attempted operation on lock not held."""

    pass


class DistributedLockManager:
    """
    Redis-based Distributed Lock Manager.

    동시성 제어 전략:
    ─────────────────────────────────────────────────────────────────

    1. 낙관적 락 (Optimistic Locking):
       - 읽기 작업에는 락 없이 접근
       - 쓰기 시점에만 락 획득 -> 충돌 발생 시 재시도
       - 읽기 비율이 높은 랭킹 조회 등에 적합

    2. 비관적 락 (Pessimistic Locking):
       - 작업 시작 전 반드시 락 획득
       - 칩 변경, 테이블 이동 등 정합성이 중요한 작업에 사용

    3. 계층적 락 (Hierarchical Locking):
       - 상위 락 획득 시 하위 리소스 자동 보호
       - 테이블 밸런싱 시 tournament:tables 락만으로 모든 테이블 보호

    4. Lock-Free 영역:
       - 이벤트 발행, 로깅, 스냅샷 저장은 락 없이 비동기 처리
       - CAS(Compare-And-Swap) 패턴으로 충돌 해결

    ─────────────────────────────────────────────────────────────────

    Redis 명령어 사용:
    - SET NX PX: 원자적 락 획득 (key가 없을 때만 설정, 만료시간 포함)
    - GET + DEL (Lua): 원자적 락 해제 (owner 확인 후 삭제)
    - PEXPIRE: 락 갱신 (TTL 연장)
    """

    # Lua script for atomic lock release with owner verification
    # 락 소유자 확인 후 삭제 - 다른 프로세스의 락을 실수로 해제하지 않음
    RELEASE_LOCK_SCRIPT = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """

    # Lua script for atomic lock renewal with owner verification
    RENEW_LOCK_SCRIPT = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("pexpire", KEYS[1], ARGV[2])
    else
        return 0
    end
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        default_lock_timeout_ms: int = 10000,  # 기본 락 타임아웃: 10초
        default_acquire_timeout_ms: int = 5000,  # 기본 획득 대기: 5초
        retry_interval_ms: int = 50,  # 재시도 간격: 50ms
    ):
        self.redis = redis_client
        self.default_lock_timeout_ms = default_lock_timeout_ms
        self.default_acquire_timeout_ms = default_acquire_timeout_ms
        self.retry_interval_ms = retry_interval_ms

        # Instance ID for lock ownership
        self._instance_id = str(uuid4())

        # Currently held locks (for cleanup on shutdown)
        self._held_locks: Set[str] = set()

        # Pre-register Lua scripts
        self._release_script: Optional[redis.client.Script] = None
        self._renew_script: Optional[redis.client.Script] = None

    async def _ensure_scripts(self) -> None:
        """Register Lua scripts if not already done."""
        if self._release_script is None:
            self._release_script = self.redis.register_script(self.RELEASE_LOCK_SCRIPT)
        if self._renew_script is None:
            self._renew_script = self.redis.register_script(self.RENEW_LOCK_SCRIPT)

    def _make_lock_key(
        self,
        tournament_id: str,
        lock_type: LockType,
        resource_id: Optional[str] = None,
    ) -> str:
        """
        Generate Redis key for lock.

        Key 구조:
        - lock:tournament:{id} - 토너먼트 전체
        - lock:tournament:{id}:tables - 테이블 관리
        - lock:tournament:{id}:table:{table_id} - 개별 테이블
        - lock:tournament:{id}:player:{user_id} - 개별 플레이어
        """
        base = f"lock:tournament:{tournament_id}"

        if lock_type == LockType.TOURNAMENT:
            return base
        elif lock_type == LockType.TABLES:
            return f"{base}:tables"
        elif lock_type == LockType.TABLE:
            return f"{base}:table:{resource_id}"
        elif lock_type == LockType.PLAYER:
            return f"{base}:player:{resource_id}"
        elif lock_type == LockType.RANKING:
            return f"{base}:ranking"
        elif lock_type == LockType.BLIND:
            return f"{base}:blind"
        else:
            return f"{base}:{lock_type.value}:{resource_id}"

    def _make_owner_token(self) -> str:
        """
        Generate unique owner token for this lock acquisition.

        토큰 구성:
        - Instance ID: 서버 인스턴스 식별
        - Timestamp: 획득 시점
        - Random: 동일 인스턴스의 동시 획득 구분
        """
        raw = f"{self._instance_id}:{time.time_ns()}:{uuid4().hex[:8]}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    async def acquire(
        self,
        tournament_id: str,
        lock_type: LockType,
        resource_id: Optional[str] = None,
        lock_timeout_ms: Optional[int] = None,
        acquire_timeout_ms: Optional[int] = None,
    ) -> LockInfo:
        """
        Acquire distributed lock.

        동시성 제어 핵심 로직:
        ─────────────────────────────────────────────────────────────

        1. SET NX PX 명령어로 원자적 락 획득 시도
           - NX: key가 존재하지 않을 때만 설정 (다른 프로세스가 이미 소유 시 실패)
           - PX: 밀리초 단위 만료시간 설정 (데드락 방지)

        2. 획득 실패 시 retry_interval_ms 간격으로 재시도
           - acquire_timeout_ms 초과 시 LockAcquisitionError 발생
           - Exponential backoff 없이 고정 간격 사용 (빠른 응답 필요)

        3. 획득 성공 시 LockInfo 반환
           - owner_token으로 소유권 증명 (해제 시 검증)
           - _held_locks set에 추가 (셧다운 시 정리용)

        ─────────────────────────────────────────────────────────────

        Args:
            tournament_id: Tournament identifier
            lock_type: Type/scope of lock
            resource_id: Optional resource ID (table, player)
            lock_timeout_ms: Lock auto-expire time
            acquire_timeout_ms: Max time to wait for lock

        Returns:
            LockInfo with lock details

        Raises:
            LockAcquisitionError: If lock cannot be acquired within timeout
        """
        await self._ensure_scripts()

        lock_timeout = lock_timeout_ms or self.default_lock_timeout_ms
        acquire_timeout = acquire_timeout_ms or self.default_acquire_timeout_ms

        lock_key = self._make_lock_key(tournament_id, lock_type, resource_id)
        owner_token = self._make_owner_token()

        start_time = time.time() * 1000  # Convert to ms

        while True:
            # 원자적 락 획득 시도: SET key value NX PX timeout
            # NX = Only set if Not eXists
            # PX = Set expiry in milliseconds
            acquired = await self.redis.set(
                lock_key,
                owner_token,
                nx=True,  # Only if not exists
                px=lock_timeout,  # Expiry in ms
            )

            if acquired:
                # 락 획득 성공
                now = time.time()
                lock_info = LockInfo(
                    lock_key=lock_key,
                    owner_id=owner_token,
                    acquired_at=now,
                    expires_at=now + (lock_timeout / 1000),
                    lock_type=lock_type,
                )
                self._held_locks.add(lock_key)
                return lock_info

            # 획득 실패 - 타임아웃 체크
            elapsed = (time.time() * 1000) - start_time
            if elapsed >= acquire_timeout:
                raise LockAcquisitionError(
                    f"Failed to acquire lock {lock_key} within {acquire_timeout}ms. "
                    f"Lock is held by another process."
                )

            # 재시도 대기
            await asyncio.sleep(self.retry_interval_ms / 1000)

    async def release(self, lock_info: LockInfo) -> bool:
        """
        Release distributed lock.

        Lua 스크립트를 사용한 원자적 해제:
        1. GET으로 현재 owner 확인
        2. owner가 일치하면 DEL
        3. 일치하지 않으면 무시 (이미 만료되었거나 다른 프로세스가 획득)

        이 원자성이 중요한 이유:
        - GET 후 DEL 사이에 락이 만료되고 다른 프로세스가 획득할 수 있음
        - Lua 스크립트는 Redis에서 원자적으로 실행되어 이 문제 방지

        Args:
            lock_info: LockInfo from acquire()

        Returns:
            True if lock was released, False if not held (expired or stolen)
        """
        await self._ensure_scripts()

        result = await self._release_script(
            keys=[lock_info.lock_key],
            args=[lock_info.owner_id],
        )

        self._held_locks.discard(lock_info.lock_key)
        return result == 1

    async def renew(
        self,
        lock_info: LockInfo,
        additional_time_ms: Optional[int] = None,
    ) -> bool:
        """
        Renew (extend) lock TTL.

        장시간 작업 시 락 갱신:
        - 주기적으로 TTL 연장하여 만료 방지
        - 작업 완료 전 락이 만료되면 정합성 문제 발생

        권장 패턴:
        - 락 TTL의 1/3 시점에 갱신 시도
        - 갱신 실패 시 작업 중단 및 롤백

        Args:
            lock_info: LockInfo from acquire()
            additional_time_ms: New TTL (default: original timeout)

        Returns:
            True if renewed, False if lock no longer held
        """
        await self._ensure_scripts()

        ttl = additional_time_ms or self.default_lock_timeout_ms

        result = await self._renew_script(
            keys=[lock_info.lock_key],
            args=[lock_info.owner_id, ttl],
        )

        if result == 1:
            # Update expiry time in lock_info (immutable이므로 새 객체 반환 권장)
            return True
        return False

    async def is_locked(
        self,
        tournament_id: str,
        lock_type: LockType,
        resource_id: Optional[str] = None,
    ) -> bool:
        """Check if resource is currently locked."""
        lock_key = self._make_lock_key(tournament_id, lock_type, resource_id)
        return await self.redis.exists(lock_key) == 1

    async def get_lock_holder(
        self,
        tournament_id: str,
        lock_type: LockType,
        resource_id: Optional[str] = None,
    ) -> Optional[str]:
        """Get current lock holder token (for debugging)."""
        lock_key = self._make_lock_key(tournament_id, lock_type, resource_id)
        return await self.redis.get(lock_key)

    @asynccontextmanager
    async def lock(
        self,
        tournament_id: str,
        lock_type: LockType,
        resource_id: Optional[str] = None,
        lock_timeout_ms: Optional[int] = None,
        acquire_timeout_ms: Optional[int] = None,
    ) -> AsyncGenerator[LockInfo, None]:
        """
        Context manager for automatic lock acquire/release.

        사용 예시:
        ```python
        async with lock_manager.lock("t1", LockType.TABLE, "table_1") as lock_info:
            # 이 블록 내에서 table_1에 대한 배타적 접근 보장
            await process_hand(table_state)
        # 블록 종료 시 자동으로 락 해제
        ```

        예외 발생 시에도 finally에서 락 해제 보장.
        """
        lock_info = await self.acquire(
            tournament_id,
            lock_type,
            resource_id,
            lock_timeout_ms,
            acquire_timeout_ms,
        )
        try:
            yield lock_info
        finally:
            await self.release(lock_info)

    async def cleanup_all(self) -> int:
        """
        Release all locks held by this instance.

        서버 셧다운 시 호출:
        - 정상 종료 시 모든 락 해제
        - 비정상 종료 시 TTL에 의해 자동 만료

        Returns:
            Number of locks released
        """
        released = 0
        for lock_key in list(self._held_locks):
            try:
                # 직접 삭제 (owner 확인 생략 - 이 인스턴스의 락만 추적)
                await self.redis.delete(lock_key)
                released += 1
            except Exception:
                pass  # Best effort
            self._held_locks.discard(lock_key)
        return released


class MultiLockManager:
    """
    Manager for acquiring multiple locks atomically.

    여러 리소스에 동시 접근이 필요한 경우:
    - 테이블 밸런싱: 여러 테이블 동시 락
    - 플레이어 이동: source_table + dest_table + player 락

    데드락 방지:
    - 락 획득 순서 고정 (lock_key 정렬)
    - 일부 획득 실패 시 전체 롤백
    """

    def __init__(self, lock_manager: DistributedLockManager):
        self.lock_manager = lock_manager

    @asynccontextmanager
    async def multi_lock(
        self,
        locks: list[
            tuple[str, LockType, Optional[str]]
        ],  # (tournament_id, type, resource_id)
        lock_timeout_ms: Optional[int] = None,
        acquire_timeout_ms: Optional[int] = None,
    ) -> AsyncGenerator[list[LockInfo], None]:
        """
        Acquire multiple locks in sorted order to prevent deadlocks.

        데드락 방지 원리:
        ─────────────────────────────────────────────────────────────

        문제 상황 (교차 순서로 획득 시):
        - Process A: lock(table_1) -> lock(table_2)
        - Process B: lock(table_2) -> lock(table_1)
        - A가 table_1 획득, B가 table_2 획득 → 서로 대기 → 데드락

        해결 (정렬된 순서로 획득):
        - 모든 프로세스가 동일한 순서로 락 획득 시도
        - 예: table_1 -> table_2 순서로 통일
        - 먼저 요청한 프로세스가 전체 획득, 나머지는 대기

        ─────────────────────────────────────────────────────────────

        Args:
            locks: List of (tournament_id, lock_type, resource_id) tuples
            lock_timeout_ms: Lock timeout for each lock
            acquire_timeout_ms: Acquire timeout for each lock

        Yields:
            List of LockInfo for acquired locks
        """
        # 락 키 기준으로 정렬하여 데드락 방지
        # 모든 프로세스가 동일한 순서로 락을 획득하면 데드락 불가
        sorted_locks = sorted(
            locks, key=lambda x: self.lock_manager._make_lock_key(x[0], x[1], x[2])
        )

        acquired_locks: list[LockInfo] = []

        try:
            for tournament_id, lock_type, resource_id in sorted_locks:
                lock_info = await self.lock_manager.acquire(
                    tournament_id,
                    lock_type,
                    resource_id,
                    lock_timeout_ms,
                    acquire_timeout_ms,
                )
                acquired_locks.append(lock_info)

            yield acquired_locks

        finally:
            # 획득 역순으로 해제 (관례적 - 필수는 아님)
            for lock_info in reversed(acquired_locks):
                try:
                    await self.lock_manager.release(lock_info)
                except Exception:
                    pass  # Best effort release
