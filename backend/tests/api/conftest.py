"""Test fixtures for API integration tests."""

import asyncio
import os
from collections.abc import AsyncGenerator
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
# Test Settings
# =============================================================================

# Use environment variable or default test database URL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/pokerkit_test"
)


def get_test_settings() -> Settings:
    """Get test-specific settings."""
    return Settings(
        app_env="test",
        app_debug=False,
        database_url=TEST_DATABASE_URL,
        jwt_secret_key="test-secret-key-for-testing-only",
        jwt_access_token_expire_minutes=30,
        jwt_refresh_token_expire_days=7,
    )


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create a test database engine with fresh tables for each test."""
    settings = get_test_settings()
    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        echo=False,
        future=True,
    )

    # Import all models to ensure they're registered with Base
    from app.models import user, room, table, hand, audit  # noqa: F401

    # Drop and recreate all tables for clean state
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session.

    This fixture mimics the behavior of the actual get_db() dependency:
    - autoflush=True to ensure pending changes are visible within the same session
    - commit() after yield to persist changes (matching production behavior)
    - rollback() on exception to ensure clean state
    """
    async_session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=True,  # Changed: Enable autoflush for better consistency
    )

    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()  # Changed: Commit changes like production
        except Exception:
            await session.rollback()
            raise


# =============================================================================
# FastAPI App & Client Fixtures
# =============================================================================


@pytest_asyncio.fixture(scope="function")
async def test_app(test_db: AsyncSession):
    """Create a test FastAPI application."""
    from fastapi import FastAPI
    from app.api.auth import router as auth_router
    from app.api.rooms import router as rooms_router
    from app.api.users import router as users_router
    from app.config import get_settings

    app = FastAPI(title="Test App")

    # Override settings
    app.dependency_overrides[get_settings] = get_test_settings

    # Override database dependency to match production behavior
    async def override_get_db():
        """Override that commits after each request like production get_db()."""
        try:
            yield test_db
            await test_db.commit()  # Commit after request completes
        except Exception:
            await test_db.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db

    # Include routers
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(rooms_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")

    yield app


@pytest_asyncio.fixture(scope="function")
async def test_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# =============================================================================
# User & Auth Fixtures
# =============================================================================


@pytest_asyncio.fixture(scope="function")
async def test_user(test_db: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=str(uuid4()),
        email="test@example.com",
        password_hash=hash_password("TestPass123"),
        nickname="testuser",
        status=UserStatus.ACTIVE.value,
        total_hands=0,
        total_winnings=0,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def test_user2(test_db: AsyncSession) -> User:
    """Create a second test user."""
    user = User(
        id=str(uuid4()),
        email="test2@example.com",
        password_hash=hash_password("TestPass123"),
        nickname="testuser2",
        status=UserStatus.ACTIVE.value,
        total_hands=0,
        total_winnings=0,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def inactive_user(test_db: AsyncSession) -> User:
    """Create an inactive test user."""
    user = User(
        id=str(uuid4()),
        email="inactive@example.com",
        password_hash=hash_password("TestPass123"),
        nickname="inactiveuser",
        status=UserStatus.SUSPENDED.value,
        total_hands=0,
        total_winnings=0,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict[str, str]:
    """Create authorization headers with a valid access token."""
    session_id = generate_session_id()
    tokens = create_token_pair(test_user.id, session_id)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def auth_headers_user2(test_user2: User) -> dict[str, str]:
    """Create authorization headers for the second test user."""
    session_id = generate_session_id()
    tokens = create_token_pair(test_user2.id, session_id)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def invalid_auth_headers() -> dict[str, str]:
    """Create authorization headers with an invalid token."""
    return {"Authorization": "Bearer invalid-token-12345"}


# =============================================================================
# Room Fixtures
# =============================================================================


@pytest_asyncio.fixture(scope="function")
async def test_room(test_db: AsyncSession, test_user: User):
    """Create a test room."""
    from app.models.room import Room, RoomStatus
    from app.models.table import Table

    room = Room(
        id=str(uuid4()),
        name="Test Room",
        description="A test room for testing",
        owner_id=test_user.id,
        config={
            "max_seats": 6,
            "small_blind": 10,
            "big_blind": 20,
            "buy_in_min": 400,
            "buy_in_max": 2000,
            "turn_timeout": 30,
            "is_private": False,
            "password_hash": None,
        },
        status=RoomStatus.WAITING.value,
        current_players=0,
    )
    test_db.add(room)
    await test_db.flush()

    # Create associated table
    table = Table(
        id=str(uuid4()),
        room_id=room.id,
        status="waiting",
        dealer_position=0,
        state_version=0,
        seats={},
    )
    test_db.add(table)
    await test_db.commit()
    await test_db.refresh(room)

    return room


@pytest_asyncio.fixture(scope="function")
async def private_room(test_db: AsyncSession, test_user: User):
    """Create a private test room with password."""
    from app.models.room import Room, RoomStatus
    from app.models.table import Table

    room = Room(
        id=str(uuid4()),
        name="Private Room",
        description="A private test room",
        owner_id=test_user.id,
        config={
            "max_seats": 6,
            "small_blind": 10,
            "big_blind": 20,
            "buy_in_min": 400,
            "buy_in_max": 2000,
            "turn_timeout": 30,
            "is_private": True,
            "password_hash": hash_password("roompass"),
        },
        status=RoomStatus.WAITING.value,
        current_players=0,
    )
    test_db.add(room)
    await test_db.flush()

    table = Table(
        id=str(uuid4()),
        room_id=room.id,
        status="waiting",
        dealer_position=0,
        state_version=0,
        seats={},
    )
    test_db.add(table)
    await test_db.commit()
    await test_db.refresh(room)

    return room


# =============================================================================
# Helper Functions
# =============================================================================


def make_register_data(
    email: str = "new@example.com",
    password: str = "NewPass123",
    nickname: str = "newuser",
) -> dict[str, str]:
    """Create registration request data."""
    return {
        "email": email,
        "password": password,
        "nickname": nickname,
    }


def make_login_data(
    email: str = "test@example.com",
    password: str = "TestPass123",
) -> dict[str, str]:
    """Create login request data."""
    return {
        "email": email,
        "password": password,
    }


def make_room_data(
    name: str = "New Room",
    description: str | None = "A new room",
    max_seats: int = 6,
    small_blind: int = 10,
    big_blind: int = 20,
    buy_in_min: int = 400,
    buy_in_max: int = 2000,
    is_private: bool = False,
    password: str | None = None,
) -> dict[str, Any]:
    """Create room creation request data."""
    data = {
        "name": name,
        "description": description,
        "maxSeats": max_seats,
        "smallBlind": small_blind,
        "bigBlind": big_blind,
        "buyInMin": buy_in_min,
        "buyInMax": buy_in_max,
        "isPrivate": is_private,
    }
    if password:
        data["password"] = password
    return data
