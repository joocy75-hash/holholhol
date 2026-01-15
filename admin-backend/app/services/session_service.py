import json
from datetime import datetime, timedelta
from typing import Optional
import redis.asyncio as redis

from app.config import get_settings

settings = get_settings()

SESSION_PREFIX = "admin_session:"
SESSION_TIMEOUT = timedelta(minutes=30)


class SessionService:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def create_session(
        self,
        user_id: str,
        token: str,
        ip_address: str,
        user_agent: str,
    ) -> str:
        """Create a new session"""
        session_key = f"{SESSION_PREFIX}{token}"
        session_data = {
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
        }
        await self.redis.setex(
            session_key,
            SESSION_TIMEOUT,
            json.dumps(session_data),
        )
        return token

    async def get_session(self, token: str) -> Optional[dict]:
        """Get session data"""
        session_key = f"{SESSION_PREFIX}{token}"
        data = await self.redis.get(session_key)
        if not data:
            return None
        return json.loads(data)

    async def refresh_session(self, token: str) -> bool:
        """Refresh session timeout (called on activity)"""
        session_key = f"{SESSION_PREFIX}{token}"
        data = await self.redis.get(session_key)
        if not data:
            return False

        session_data = json.loads(data)
        session_data["last_activity"] = datetime.utcnow().isoformat()

        await self.redis.setex(
            session_key,
            SESSION_TIMEOUT,
            json.dumps(session_data),
        )
        return True

    async def invalidate_session(self, token: str) -> bool:
        """Invalidate a session (logout)"""
        session_key = f"{SESSION_PREFIX}{token}"
        result = await self.redis.delete(session_key)
        return result > 0

    async def invalidate_all_user_sessions(self, user_id: str) -> int:
        """Invalidate all sessions for a user"""
        pattern = f"{SESSION_PREFIX}*"
        count = 0
        async for key in self.redis.scan_iter(match=pattern):
            data = await self.redis.get(key)
            if data:
                session_data = json.loads(data)
                if session_data.get("user_id") == user_id:
                    await self.redis.delete(key)
                    count += 1
        return count

    async def get_user_sessions(self, user_id: str) -> list[dict]:
        """Get all active sessions for a user"""
        pattern = f"{SESSION_PREFIX}*"
        sessions = []
        async for key in self.redis.scan_iter(match=pattern):
            data = await self.redis.get(key)
            if data:
                session_data = json.loads(data)
                if session_data.get("user_id") == user_id:
                    session_data["token"] = key.decode().replace(SESSION_PREFIX, "")
                    sessions.append(session_data)
        return sessions

    async def is_session_valid(self, token: str) -> bool:
        """Check if session is valid"""
        session = await self.get_session(token)
        return session is not None


async def get_redis_client() -> redis.Redis:
    """Get Redis client"""
    return redis.from_url(settings.redis_url, decode_responses=True)


async def get_session_service() -> SessionService:
    """Get session service"""
    client = await get_redis_client()
    return SessionService(client)
