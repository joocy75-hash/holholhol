"""Integration test fixtures for end-to-end game flow testing.

This module provides fixtures that test the full stack:
- Database (PostgreSQL)
- Redis (pub/sub, caching)
- FastAPI application
- WebSocket connections
- Game engine
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import Settings, get_settings
from app.models.base import Base
from app.models.user import User, UserStatus
from app.utils.db import get_db
from app.utils.security import create_token_pair, generate_session_id, hash_password


# =============================================================================
# Test Configuration
# =============================================================================

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/pokerkit_test"
)


def get_integration_test_settings() -> Settings:
    """Get settings for integration tests."""
    return Settings(
        app_env="test",
        app_debug=True,
        database_url=TEST_DATABASE_URL,
        jwt_secret_key="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6",
        jwt_access_token_expire_minutes=60,
        jwt_refresh_token_expire_days=7,
        redis_url="redis://localhost:6379/1",  # Use DB 1 for tests
        serialization_hmac_key="x1y2z3a4b5c6d7e8f9g0h1i2j3k4l5m6n7o8p9q0r1s2t3u4v5w6",
    )


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def integration_engine():
    """Create database engine for integration tests."""
    settings = get_integration_test_settings()
    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        echo=False,
        future=True,
    )

    # Import all models
    from app.models import user, room, table, hand, audit  # noqa: F401

    # Create fresh tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def integration_db(integration_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for integration tests."""
    async_session_factory = async_sessionmaker(
        bind=integration_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with async_session_factory() as session:
        yield session
        await session.rollback()


# =============================================================================
# Application Fixtures
# =============================================================================


@pytest_asyncio.fixture(scope="function")
async def integration_app(integration_db: AsyncSession):
    """Create full FastAPI application for integration tests."""
    from app.main import app
    from app.config import get_settings

    # Override settings
    app.dependency_overrides[get_settings] = get_integration_test_settings

    # Override database
    async def override_get_db():
        yield integration_db

    app.dependency_overrides[get_db] = override_get_db

    yield app

    # Clear overrides
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def integration_client(integration_app) -> AsyncGenerator[AsyncClient, None]:
    """Create HTTP client for integration tests."""
    transport = ASGITransport(app=integration_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# =============================================================================
# User Fixtures
# =============================================================================


@pytest_asyncio.fixture(scope="function")
async def player1(integration_db: AsyncSession) -> dict[str, Any]:
    """Create first test player."""
    user = User(
        id=str(uuid4()),
        email="player1@test.com",
        password_hash=hash_password("Player1Pass123"),
        nickname="Player1",
        status=UserStatus.ACTIVE.value,
        total_hands=0,
        total_winnings=0,
    )
    integration_db.add(user)
    await integration_db.commit()
    await integration_db.refresh(user)

    session_id = generate_session_id()
    tokens = create_token_pair(user.id, session_id)

    return {
        "user": user,
        "tokens": tokens,
        "headers": {"Authorization": f"Bearer {tokens['access_token']}"},
    }


@pytest_asyncio.fixture(scope="function")
async def player2(integration_db: AsyncSession) -> dict[str, Any]:
    """Create second test player."""
    user = User(
        id=str(uuid4()),
        email="player2@test.com",
        password_hash=hash_password("Player2Pass123"),
        nickname="Player2",
        status=UserStatus.ACTIVE.value,
        total_hands=0,
        total_winnings=0,
    )
    integration_db.add(user)
    await integration_db.commit()
    await integration_db.refresh(user)

    session_id = generate_session_id()
    tokens = create_token_pair(user.id, session_id)

    return {
        "user": user,
        "tokens": tokens,
        "headers": {"Authorization": f"Bearer {tokens['access_token']}"},
    }


@pytest_asyncio.fixture(scope="function")
async def player3(integration_db: AsyncSession) -> dict[str, Any]:
    """Create third test player."""
    user = User(
        id=str(uuid4()),
        email="player3@test.com",
        password_hash=hash_password("Player3Pass123"),
        nickname="Player3",
        status=UserStatus.ACTIVE.value,
        total_hands=0,
        total_winnings=0,
    )
    integration_db.add(user)
    await integration_db.commit()
    await integration_db.refresh(user)

    session_id = generate_session_id()
    tokens = create_token_pair(user.id, session_id)

    return {
        "user": user,
        "tokens": tokens,
        "headers": {"Authorization": f"Bearer {tokens['access_token']}"},
    }


# =============================================================================
# Room & Table Fixtures
# =============================================================================


@pytest_asyncio.fixture(scope="function")
async def game_room(
    integration_db: AsyncSession,
    integration_client: AsyncClient,
    player1: dict[str, Any],
) -> dict[str, Any]:
    """Create a game room for testing."""
    room_data = {
        "name": "Integration Test Room",
        "description": "Room for integration testing",
        "maxSeats": 6,
        "smallBlind": 10,
        "bigBlind": 20,
        "buyInMin": 400,
        "buyInMax": 2000,
        "isPrivate": False,
    }

    response = await integration_client.post(
        "/api/v1/rooms",
        json=room_data,
        headers=player1["headers"],
    )

    assert response.status_code == 201, f"Failed to create room: {response.text}"
    data = response.json()

    return {
        "room_id": data["data"]["id"],
        "table_id": data["data"].get("tableId"),
        "config": room_data,
    }


# =============================================================================
# Helper Functions
# =============================================================================


async def register_user(
    client: AsyncClient,
    email: str,
    password: str,
    nickname: str,
) -> dict[str, Any]:
    """Register a new user and return tokens."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "nickname": nickname,
        },
    )
    assert response.status_code == 201, f"Registration failed: {response.text}"
    return response.json()["data"]


async def login_user(
    client: AsyncClient,
    email: str,
    password: str,
) -> dict[str, Any]:
    """Login and return tokens."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["data"]


async def create_room(
    client: AsyncClient,
    headers: dict[str, str],
    name: str = "Test Room",
    small_blind: int = 10,
    big_blind: int = 20,
    max_seats: int = 6,
) -> dict[str, Any]:
    """Create a room and return room data."""
    response = await client.post(
        "/api/v1/rooms",
        json={
            "name": name,
            "maxSeats": max_seats,
            "smallBlind": small_blind,
            "bigBlind": big_blind,
            "buyInMin": small_blind * 40,
            "buyInMax": small_blind * 200,
            "isPrivate": False,
        },
        headers=headers,
    )
    assert response.status_code == 201, f"Room creation failed: {response.text}"
    return response.json()["data"]


async def join_room(
    client: AsyncClient,
    headers: dict[str, str],
    room_id: str,
    buy_in: int,
    password: str | None = None,
) -> dict[str, Any]:
    """Join a room."""
    data = {"buyIn": buy_in}
    if password:
        data["password"] = password

    response = await client.post(
        f"/api/v1/rooms/{room_id}/join",
        json=data,
        headers=headers,
    )
    assert response.status_code == 200, f"Join failed: {response.text}"
    return response.json()["data"]


async def leave_room(
    client: AsyncClient,
    headers: dict[str, str],
    room_id: str,
) -> dict[str, Any]:
    """Leave a room."""
    response = await client.post(
        f"/api/v1/rooms/{room_id}/leave",
        headers=headers,
    )
    return response.json()
