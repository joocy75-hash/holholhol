"""Redis client for caching and pub/sub."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as redis
from redis.asyncio import Redis

from app.config import get_settings

settings = get_settings()

# Global Redis client instance
redis_client: Redis | None = None


async def init_redis() -> Redis:
    """Initialize Redis connection."""
    global redis_client
    redis_client = redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    # Test connection
    await redis_client.ping()
    return redis_client


async def close_redis() -> None:
    """Close Redis connection."""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None


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
