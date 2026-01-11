"""WebSocket test fixtures and utilities."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.models.base import Base
from app.ws.connection import WebSocketConnection, ConnectionState
from app.ws.events import EventType
from app.ws.manager import ConnectionManager
from app.ws.messages import MessageEnvelope

settings = get_settings()


# =============================================================================
# Test Token Generation
# =============================================================================


def create_test_token(
    user_id: str,
    session_id: str | None = None,
    expired: bool = False,
) -> str:
    """Create a test JWT token."""
    now = datetime.now(timezone.utc)

    if expired:
        expire = now - timedelta(hours=1)
    else:
        expire = now + timedelta(hours=1)

    payload = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": expire,
    }

    if session_id:
        payload["sid"] = session_id

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


# =============================================================================
# Mock Classes
# =============================================================================


class MockWebSocket:
    """Mock WebSocket for testing."""

    def __init__(self):
        self.accepted = False
        self.closed = False
        self.close_code = None
        self.close_reason = None
        self.sent_messages: list[dict[str, Any]] = []
        self.receive_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def accept(self) -> None:
        self.accepted = True

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True
        self.close_code = code
        self.close_reason = reason

    async def send_json(self, data: dict[str, Any]) -> None:
        if self.closed:
            raise RuntimeError("WebSocket closed")
        self.sent_messages.append(data)

    async def receive_json(self) -> dict[str, Any]:
        if self.closed:
            raise RuntimeError("WebSocket closed")
        return await self.receive_queue.get()

    def add_message(self, message: dict[str, Any]) -> None:
        """Add message to receive queue."""
        self.receive_queue.put_nowait(message)


class MockRedis:
    """Mock Redis client for testing."""

    def __init__(self):
        self._data: dict[str, Any] = {}
        self._sets: dict[str, set[str]] = {}
        self._hashes: dict[str, dict[str, str]] = {}
        self._lists: dict[str, list[str]] = {}
        self._pubsub_channels: dict[str, list[Any]] = {}

    async def ping(self) -> bool:
        return True

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def set(
        self,
        key: str,
        value: str,
        nx: bool = False,
        ex: int | None = None,
    ) -> bool | None:
        if nx and key in self._data:
            return None
        self._data[key] = value
        return True

    async def setex(self, key: str, seconds: int, value: str) -> bool:
        self._data[key] = value
        return True

    async def delete(self, key: str) -> int:
        if key in self._data:
            del self._data[key]
            return 1
        return 0

    async def hset(self, name: str, key: str, value: str) -> int:
        if name not in self._hashes:
            self._hashes[name] = {}
        self._hashes[name][key] = value
        return 1

    async def hget(self, name: str, key: str) -> str | None:
        return self._hashes.get(name, {}).get(key)

    async def hdel(self, name: str, key: str) -> int:
        if name in self._hashes and key in self._hashes[name]:
            del self._hashes[name][key]
            return 1
        return 0

    async def sadd(self, name: str, value: str) -> int:
        if name not in self._sets:
            self._sets[name] = set()
        self._sets[name].add(value)
        return 1

    async def srem(self, name: str, value: str) -> int:
        if name in self._sets and value in self._sets[name]:
            self._sets[name].remove(value)
            return 1
        return 0

    async def smembers(self, name: str) -> set[str]:
        return self._sets.get(name, set())

    async def lpush(self, key: str, value: str) -> int:
        if key not in self._lists:
            self._lists[key] = []
        self._lists[key].insert(0, value)
        return len(self._lists[key])

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        items = self._lists.get(key, [])
        if end < 0:
            end = len(items) + end + 1
        else:
            end = end + 1
        return items[start:end]

    async def ltrim(self, key: str, start: int, end: int) -> bool:
        if key in self._lists:
            items = self._lists[key]
            if end < 0:
                end = len(items) + end + 1
            else:
                end = end + 1
            self._lists[key] = items[start:end]
        return True

    async def expire(self, key: str, seconds: int) -> bool:
        return True

    async def publish(self, channel: str, message: str) -> int:
        return 1

    def pubsub(self):
        return MockPubSub()


class MockPubSub:
    """Mock Redis pub/sub."""

    def __init__(self):
        self._subscribed: set[str] = set()

    async def psubscribe(self, pattern: str) -> None:
        self._subscribed.add(pattern)

    async def punsubscribe(self, pattern: str) -> None:
        self._subscribed.discard(pattern)

    async def close(self) -> None:
        pass

    async def get_message(
        self,
        ignore_subscribe_messages: bool = True,
        timeout: float = 1.0,
    ) -> dict[str, Any] | None:
        await asyncio.sleep(0.01)  # Simulate async
        return None


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_redis() -> MockRedis:
    """Create a mock Redis client."""
    return MockRedis()


@pytest.fixture
def mock_websocket() -> MockWebSocket:
    """Create a mock WebSocket."""
    return MockWebSocket()


@pytest_asyncio.fixture
async def connection_manager(mock_redis: MockRedis) -> AsyncGenerator[ConnectionManager, None]:
    """Create a connection manager with mock Redis."""
    manager = ConnectionManager(mock_redis)
    await manager.start()
    yield manager
    await manager.stop()


@pytest.fixture
def test_user_id() -> str:
    """Generate a test user ID."""
    return str(uuid4())


@pytest.fixture
def test_token(test_user_id: str) -> str:
    """Generate a test JWT token."""
    return create_test_token(test_user_id)


@pytest_asyncio.fixture
async def test_connection(
    mock_websocket: MockWebSocket,
    test_user_id: str,
) -> WebSocketConnection:
    """Create a test WebSocket connection."""
    return WebSocketConnection(
        websocket=mock_websocket,
        user_id=test_user_id,
        session_id=str(uuid4()),
        connection_id=str(uuid4()),
        connected_at=datetime.utcnow(),
    )


# =============================================================================
# Helper Functions
# =============================================================================


def create_ping_message(
    request_id: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Create a PING message."""
    return MessageEnvelope.create(
        event_type=EventType.PING,
        payload={},
        request_id=request_id,
        trace_id=trace_id,
    ).to_dict()


def create_subscribe_lobby_message(
    request_id: str | None = None,
) -> dict[str, Any]:
    """Create a SUBSCRIBE_LOBBY message."""
    return MessageEnvelope.create(
        event_type=EventType.SUBSCRIBE_LOBBY,
        payload={},
        request_id=request_id,
    ).to_dict()


def create_subscribe_table_message(
    table_id: str,
    mode: str = "player",
    request_id: str | None = None,
) -> dict[str, Any]:
    """Create a SUBSCRIBE_TABLE message."""
    return MessageEnvelope.create(
        event_type=EventType.SUBSCRIBE_TABLE,
        payload={
            "tableId": table_id,
            "mode": mode,
        },
        request_id=request_id,
    ).to_dict()


def create_action_message(
    table_id: str,
    action_type: str,
    amount: int | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Create an ACTION_REQUEST message."""
    payload = {
        "tableId": table_id,
        "actionType": action_type,
    }
    if amount is not None:
        payload["amount"] = amount

    return MessageEnvelope.create(
        event_type=EventType.ACTION_REQUEST,
        payload=payload,
        request_id=request_id,
    ).to_dict()
