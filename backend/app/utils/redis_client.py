"""Redis client for caching and pub/sub."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as redis
from redis.asyncio import ConnectionPool, Redis

from app.config import get_settings

settings = get_settings()

# Global Redis connection pool and client instance
redis_pool: ConnectionPool | None = None
redis_client: Redis | None = None


async def init_redis() -> Redis:
    """Initialize Redis connection with connection pool for 300-500 concurrent users."""
    global redis_pool, redis_client

    # Create connection pool with enhanced settings
    redis_pool = ConnectionPool.from_url(
        settings.redis_url,
        max_connections=settings.redis_max_connections,
        socket_timeout=settings.redis_socket_timeout,
        socket_connect_timeout=settings.redis_socket_connect_timeout,
        retry_on_timeout=True,
        health_check_interval=settings.redis_health_check_interval,
        encoding="utf-8",
        decode_responses=True,
    )

    # Create Redis client with the connection pool
    redis_client = Redis(connection_pool=redis_pool)

    # Test connection
    await redis_client.ping()
    return redis_client


async def close_redis() -> None:
    """Close Redis connection and pool."""
    global redis_pool, redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None
    if redis_pool:
        await redis_pool.disconnect()
        redis_pool = None


async def get_redis() -> AsyncGenerator[Redis, None]:
    """Dependency for getting Redis client.

    Usage:
        @app.get("/cache")
        async def get_cache(redis: Redis = Depends(get_redis)):
            ...
    """
    if redis_client is None:
        await init_redis()
    yield redis_client  # type: ignore


@asynccontextmanager
async def get_redis_context() -> AsyncGenerator[Redis, None]:
    """Context manager for getting Redis client.

    Usage:
        async with get_redis_context() as redis:
            await redis.set("key", "value")
    """
    if redis_client is None:
        await init_redis()
    yield redis_client  # type: ignore


class RedisService:
    """Redis service for common operations."""

    def __init__(self, client: Redis):
        self.client = client

    # Session management
    async def set_session(self, user_id: str, session_data: dict[str, Any]) -> None:
        """Store user session."""
        import json

        key = f"session:{user_id}"
        await self.client.setex(
            key,
            settings.redis_session_ttl,
            json.dumps(session_data),
        )

    async def get_session(self, user_id: str) -> dict[str, Any] | None:
        """Get user session."""
        import json

        key = f"session:{user_id}"
        data = await self.client.get(key)
        if data:
            return json.loads(data)
        return None

    async def delete_session(self, user_id: str) -> None:
        """Delete user session."""
        key = f"session:{user_id}"
        await self.client.delete(key)

    # Idempotency key management
    async def check_and_set_idempotency(
        self,
        table_id: str,
        user_id: str,
        request_id: str,
        ttl: int = 300,
    ) -> bool:
        """Check and set idempotency key.

        Returns True if this is a new request, False if duplicate.
        """
        key = f"idempotency:{table_id}:{user_id}:{request_id}"
        # SET NX returns True if key was set (new request)
        result = await self.client.set(key, "1", nx=True, ex=ttl)
        return result is not None

    async def get_idempotency_result(
        self,
        table_id: str,
        user_id: str,
        request_id: str,
    ) -> str | None:
        """Get cached result for idempotent request."""
        key = f"idempotency_result:{table_id}:{user_id}:{request_id}"
        return await self.client.get(key)

    async def set_idempotency_result(
        self,
        table_id: str,
        user_id: str,
        request_id: str,
        result: str,
        ttl: int = 300,
    ) -> None:
        """Cache result for idempotent request."""
        key = f"idempotency_result:{table_id}:{user_id}:{request_id}"
        await self.client.setex(key, ttl, result)

    # Pub/Sub for table events
    async def publish_table_event(self, table_id: str, event: str) -> None:
        """Publish event to table channel."""
        channel = f"table:{table_id}"
        await self.client.publish(channel, event)

    async def subscribe_table(self, table_id: str):
        """Subscribe to table channel."""
        pubsub = self.client.pubsub()
        await pubsub.subscribe(f"table:{table_id}")
        return pubsub

    # Rate limiting
    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window: int,
    ) -> tuple[bool, int]:
        """Check rate limit using sliding window.

        Returns (allowed, remaining).
        """
        import time

        now = int(time.time())
        window_start = now - window

        pipe = self.client.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window)
        results = await pipe.execute()

        count = results[2]
        allowed = count <= limit
        remaining = max(0, limit - count)

        return allowed, remaining

    # ========================================
    # Bot Detection: 타이밍 데이터 저장 (Phase 2.2)
    # ========================================

    async def record_turn_start(
        self,
        room_id: str,
        user_id: str,
        ttl: int = 60,
    ) -> None:
        """턴 시작 시간을 Redis에 저장.

        Args:
            room_id: 방 ID
            user_id: 사용자 ID
            ttl: 만료 시간 (초), 기본 60초
        """
        from datetime import datetime, timezone

        key = f"game:turn:{room_id}:{user_id}"
        now = datetime.now(timezone.utc).isoformat()
        await self.client.setex(key, ttl, now)

    async def get_turn_start(
        self,
        room_id: str,
        user_id: str,
    ) -> str | None:
        """턴 시작 시간 조회.

        Returns:
            ISO 형식 시작 시간 또는 None
        """
        key = f"game:turn:{room_id}:{user_id}"
        return await self.client.get(key)

    async def delete_turn_start(
        self,
        room_id: str,
        user_id: str,
    ) -> None:
        """턴 시작 시간 삭제."""
        key = f"game:turn:{room_id}:{user_id}"
        await self.client.delete(key)

    async def save_response_time(
        self,
        user_id: str,
        response_time_ms: int,
        ttl: int = 604800,  # 7일
    ) -> None:
        """응답 시간을 Redis SORTED SET에 저장.

        Args:
            user_id: 사용자 ID
            response_time_ms: 응답 시간 (밀리초)
            ttl: 만료 시간 (초), 기본 7일
        """
        import time

        key = f"stats:response_times:{user_id}"
        now_ms = int(time.time() * 1000)

        # SORTED SET에 저장 (score: timestamp, member: response_time)
        # member를 unique하게 하기 위해 timestamp 포함
        member = f"{response_time_ms}:{now_ms}"
        await self.client.zadd(key, {member: now_ms})
        await self.client.expire(key, ttl)

        # 최근 1000개만 유지
        await self.client.zremrangebyrank(key, 0, -1001)

    async def get_response_times(
        self,
        user_id: str,
        since_hours: int = 24,
    ) -> list[int]:
        """최근 응답 시간 목록 조회.

        Args:
            user_id: 사용자 ID
            since_hours: 조회 시간 범위 (시간)

        Returns:
            응답 시간 목록 (밀리초)
        """
        import time

        key = f"stats:response_times:{user_id}"
        now_ms = int(time.time() * 1000)
        since_ms = now_ms - (since_hours * 3600 * 1000)

        # 시간 범위 내 데이터 조회
        members = await self.client.zrangebyscore(key, since_ms, now_ms)

        # member 형식: "response_time:timestamp"
        response_times = []
        for member in members:
            try:
                response_time = int(member.split(":")[0])
                response_times.append(response_time)
            except (ValueError, IndexError):
                continue

        return response_times

    async def save_action_pattern(
        self,
        user_id: str,
        action_type: str,
        ttl: int = 86400,  # 24시간
    ) -> None:
        """액션 패턴을 Redis HASH에 저장.

        Args:
            user_id: 사용자 ID
            action_type: 액션 유형 (fold, check, call, raise, bet)
            ttl: 만료 시간 (초), 기본 24시간
        """
        key = f"stats:action_pattern:{user_id}"

        # 액션 카운트 증가
        await self.client.hincrby(key, action_type, 1)
        await self.client.hincrby(key, "total", 1)
        await self.client.expire(key, ttl)

    async def get_action_pattern(
        self,
        user_id: str,
    ) -> dict[str, int]:
        """액션 패턴 조회.

        Returns:
            액션별 카운트 딕셔너리
        """
        key = f"stats:action_pattern:{user_id}"
        data = await self.client.hgetall(key)

        return {k: int(v) for k, v in data.items()}

    async def clear_action_pattern(
        self,
        user_id: str,
    ) -> None:
        """액션 패턴 초기화."""
        key = f"stats:action_pattern:{user_id}"
        await self.client.delete(key)

    # ========================================
    # Waitlist Management (Phase 4.1)
    # ========================================

    async def add_to_waitlist(
        self,
        room_id: str,
        user_id: str,
        buy_in: int,
        ttl: int = 1800,  # 30분
    ) -> dict[str, Any]:
        """대기열에 사용자 추가.

        Redis 구조:
        - waitlist:{room_id} (ZSET): user_id를 member로, timestamp를 score로 저장
        - waitlist:detail:{room_id}:{user_id} (STRING/JSON): 상세 정보

        Args:
            room_id: 방 ID
            user_id: 사용자 ID
            buy_in: 바이인 금액
            ttl: 대기 만료 시간 (초), 기본 30분

        Returns:
            {"position": int, "joined_at": str}
        """
        import json
        import time
        from datetime import datetime, timezone

        waitlist_key = f"waitlist:{room_id}"
        detail_key = f"waitlist:detail:{room_id}:{user_id}"
        now = datetime.now(timezone.utc)
        score = time.time()

        # 이미 대기열에 있는지 확인
        existing_score = await self.client.zscore(waitlist_key, user_id)
        if existing_score is not None:
            # 이미 대기 중이면 현재 위치 반환
            position = await self.client.zrank(waitlist_key, user_id)
            detail_json = await self.client.get(detail_key)
            detail = json.loads(detail_json) if detail_json else {}
            return {
                "position": position + 1 if position is not None else 1,
                "joined_at": detail.get("joined_at", now.isoformat()),
                "already_waiting": True,
            }

        # 대기열에 추가 (ZSET)
        await self.client.zadd(waitlist_key, {user_id: score})
        await self.client.expire(waitlist_key, ttl + 60)  # 여유분 추가

        # 상세 정보 저장
        detail = {
            "user_id": user_id,
            "buy_in": buy_in,
            "joined_at": now.isoformat(),
        }
        await self.client.setex(detail_key, ttl, json.dumps(detail))

        # 대기열 위치 계산
        position = await self.client.zrank(waitlist_key, user_id)

        return {
            "position": position + 1 if position is not None else 1,
            "joined_at": now.isoformat(),
            "already_waiting": False,
        }

    async def remove_from_waitlist(
        self,
        room_id: str,
        user_id: str,
    ) -> bool:
        """대기열에서 사용자 제거.

        Args:
            room_id: 방 ID
            user_id: 사용자 ID

        Returns:
            제거 성공 여부
        """
        waitlist_key = f"waitlist:{room_id}"
        detail_key = f"waitlist:detail:{room_id}:{user_id}"

        # ZSET에서 제거
        removed = await self.client.zrem(waitlist_key, user_id)

        # 상세 정보 삭제
        await self.client.delete(detail_key)

        return removed > 0

    async def get_waitlist(
        self,
        room_id: str,
    ) -> list[dict[str, Any]]:
        """대기열 목록 조회.

        Args:
            room_id: 방 ID

        Returns:
            대기 중인 사용자 목록 (순서대로)
        """
        import json

        waitlist_key = f"waitlist:{room_id}"

        # ZSET에서 순서대로 조회
        members = await self.client.zrange(waitlist_key, 0, -1)

        result = []
        for i, user_id in enumerate(members):
            detail_key = f"waitlist:detail:{room_id}:{user_id}"
            detail_json = await self.client.get(detail_key)

            if detail_json:
                detail = json.loads(detail_json)
                detail["position"] = i + 1
                result.append(detail)
            else:
                # 상세 정보가 만료되었으면 ZSET에서도 제거
                await self.client.zrem(waitlist_key, user_id)

        return result

    async def get_waitlist_position(
        self,
        room_id: str,
        user_id: str,
    ) -> int | None:
        """대기열에서 사용자의 위치 조회.

        Args:
            room_id: 방 ID
            user_id: 사용자 ID

        Returns:
            위치 (1부터 시작) 또는 None (대기열에 없음)
        """
        waitlist_key = f"waitlist:{room_id}"
        rank = await self.client.zrank(waitlist_key, user_id)

        return rank + 1 if rank is not None else None

    async def get_first_in_waitlist(
        self,
        room_id: str,
    ) -> dict[str, Any] | None:
        """대기열에서 첫 번째 사용자 정보 조회.

        Args:
            room_id: 방 ID

        Returns:
            첫 번째 대기자 정보 또는 None
        """
        import json

        waitlist_key = f"waitlist:{room_id}"

        # ZSET에서 첫 번째 멤버 조회
        members = await self.client.zrange(waitlist_key, 0, 0)

        if not members:
            return None

        user_id = members[0]
        detail_key = f"waitlist:detail:{room_id}:{user_id}"
        detail_json = await self.client.get(detail_key)

        if detail_json:
            detail = json.loads(detail_json)
            detail["position"] = 1
            return detail

        # 상세 정보가 만료되었으면 제거하고 다음 사람 확인
        await self.client.zrem(waitlist_key, user_id)
        return await self.get_first_in_waitlist(room_id)

    async def get_waitlist_count(
        self,
        room_id: str,
    ) -> int:
        """대기열 인원 수 조회.

        Args:
            room_id: 방 ID

        Returns:
            대기 중인 인원 수
        """
        waitlist_key = f"waitlist:{room_id}"
        return await self.client.zcard(waitlist_key)

    async def get_waitlist_detail(
        self,
        room_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        """대기열 상세 정보 조회.

        Args:
            room_id: 방 ID
            user_id: 사용자 ID

        Returns:
            상세 정보 또는 None
        """
        import json

        detail_key = f"waitlist:detail:{room_id}:{user_id}"
        detail_json = await self.client.get(detail_key)

        if detail_json:
            detail = json.loads(detail_json)
            position = await self.get_waitlist_position(room_id, user_id)
            detail["position"] = position
            return detail

        return None
