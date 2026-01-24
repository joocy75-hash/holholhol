"""Worker health management for multi-instance WebSocket support.

Phase 2.7: 워커 간 장애 복구 - 워커 상태 모니터링 및 연결 정리
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# Constants
WORKER_HEARTBEAT_INTERVAL = 5  # 워커 heartbeat 주기 (초)
WORKER_TTL = 30  # 워커 상태 TTL (초)
WORKER_CLEANUP_INTERVAL = 10  # 죽은 워커 정리 주기 (초)


class WorkerHealthManager:
    """워커 상태 관리 및 장애 복구.

    각 워커 인스턴스는:
    1. 주기적으로 heartbeat를 Redis에 등록 (TTL 30초)
    2. 다른 워커의 상태를 모니터링
    3. 죽은 워커의 연결 정보를 정리
    """

    def __init__(self, redis: Redis, instance_id: str):
        self.redis = redis
        self.instance_id = instance_id
        self._running = False
        self._heartbeat_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None
        self._on_worker_dead_callback: callable | None = None

    async def start(self, on_worker_dead: callable | None = None) -> None:
        """워커 헬스 매니저 시작.

        Args:
            on_worker_dead: 죽은 워커 발견 시 호출할 콜백 함수
        """
        if self._running:
            return

        self._running = True
        self._on_worker_dead_callback = on_worker_dead

        # 워커 등록
        await self._register_worker()

        # Heartbeat 태스크 시작
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # 클린업 태스크 시작
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info(f"WorkerHealthManager started (instance: {self.instance_id})")

    async def stop(self) -> None:
        """워커 헬스 매니저 중지."""
        self._running = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # 워커 등록 해제
        await self._unregister_worker()

        logger.info(f"WorkerHealthManager stopped (instance: {self.instance_id})")

    async def _register_worker(self) -> None:
        """Redis에 워커 등록."""
        await self.redis.hset(
            "ws:workers",
            self.instance_id,
            json.dumps({
                "started_at": datetime.now(timezone.utc).isoformat(),
                "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                "connection_count": 0,
            }),
        )
        # TTL 설정
        await self.redis.setex(
            f"ws:worker:{self.instance_id}:alive",
            WORKER_TTL,
            datetime.now(timezone.utc).isoformat(),
        )
        logger.debug(f"Worker {self.instance_id} registered")

    async def _unregister_worker(self) -> None:
        """Redis에서 워커 등록 해제."""
        await self.redis.hdel("ws:workers", self.instance_id)
        await self.redis.delete(f"ws:worker:{self.instance_id}:alive")
        logger.debug(f"Worker {self.instance_id} unregistered")

    async def _heartbeat_loop(self) -> None:
        """주기적으로 heartbeat 전송."""
        while self._running:
            try:
                await self._send_heartbeat()
                await asyncio.sleep(WORKER_HEARTBEAT_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(1)

    async def _send_heartbeat(self) -> None:
        """Heartbeat 전송 및 TTL 갱신."""
        now = datetime.now(timezone.utc).isoformat()

        # 워커 정보 업데이트
        await self.redis.hset(
            "ws:workers",
            self.instance_id,
            json.dumps({
                "last_heartbeat": now,
                "connection_count": await self._get_connection_count(),
            }),
        )

        # TTL 갱신
        await self.redis.setex(
            f"ws:worker:{self.instance_id}:alive",
            WORKER_TTL,
            now,
        )

    async def _get_connection_count(self) -> int:
        """현재 워커의 연결 수 조회."""
        # Redis에서 이 인스턴스의 연결 수를 카운트
        count = 0
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(
                cursor,
                match="ws:connections:*",
                count=100,
            )
            for key in keys:
                connections = await self.redis.hgetall(key)
                for conn_data in connections.values():
                    try:
                        data = json.loads(conn_data)
                        if data.get("instance") == self.instance_id:
                            count += 1
                    except (json.JSONDecodeError, TypeError):
                        pass
            if cursor == 0:
                break
        return count

    async def _cleanup_loop(self) -> None:
        """주기적으로 죽은 워커 정리."""
        while self._running:
            try:
                await asyncio.sleep(WORKER_CLEANUP_INTERVAL)
                await self._cleanup_dead_workers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    async def _cleanup_dead_workers(self) -> None:
        """죽은 워커의 연결 정보 정리."""
        workers = await self.redis.hgetall("ws:workers")

        for worker_id, worker_data in workers.items():
            if worker_id == self.instance_id:
                continue

            # alive 키 확인 (TTL 만료 여부)
            alive = await self.redis.get(f"ws:worker:{worker_id}:alive")
            if alive is None:
                logger.warning(f"Dead worker detected: {worker_id}")
                await self._cleanup_worker_connections(worker_id)

                # 워커 정보 삭제
                await self.redis.hdel("ws:workers", worker_id)

                # 콜백 호출
                if self._on_worker_dead_callback:
                    try:
                        await self._on_worker_dead_callback(worker_id)
                    except Exception as e:
                        logger.error(f"Error in on_worker_dead callback: {e}")

    async def _cleanup_worker_connections(self, worker_id: str) -> None:
        """특정 워커의 연결 정보 정리."""
        cleaned_count = 0

        # 모든 사용자의 연결 정보 스캔
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(
                cursor,
                match="ws:connections:*",
                count=100,
            )
            for key in keys:
                connections = await self.redis.hgetall(key)
                for conn_id, conn_data in connections.items():
                    try:
                        data = json.loads(conn_data)
                        if data.get("instance") == worker_id:
                            await self.redis.hdel(key, conn_id)
                            cleaned_count += 1
                    except (json.JSONDecodeError, TypeError):
                        pass
            if cursor == 0:
                break

        # 채널 구독 정보 정리
        channel_cursor = 0
        while True:
            channel_cursor, keys = await self.redis.scan(
                channel_cursor,
                match="ws:channel:*",
                count=100,
            )
            for key in keys:
                members = await self.redis.smembers(key)
                for member in members:
                    if member.startswith(f"{worker_id}:"):
                        await self.redis.srem(key, member)
            if channel_cursor == 0:
                break

        logger.info(f"Cleaned up {cleaned_count} connections from dead worker {worker_id}")

    async def get_all_workers(self) -> dict[str, Any]:
        """모든 워커 상태 조회."""
        workers = await self.redis.hgetall("ws:workers")
        result = {}

        for worker_id, worker_data in workers.items():
            try:
                data = json.loads(worker_data)
                alive = await self.redis.get(f"ws:worker:{worker_id}:alive")
                data["alive"] = alive is not None
                data["is_self"] = worker_id == self.instance_id
                result[worker_id] = data
            except (json.JSONDecodeError, TypeError):
                pass

        return result

    async def get_total_connection_count(self) -> int:
        """전체 인스턴스의 총 연결 수 조회."""
        workers = await self.get_all_workers()
        total = 0
        for worker_data in workers.values():
            if worker_data.get("alive"):
                total += worker_data.get("connection_count", 0)
        return total
