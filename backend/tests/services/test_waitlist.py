"""Unit tests for Waitlist functionality (Phase 4.1).

Tests:
- Redis waitlist operations
- RoomService waitlist methods
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest_asyncio

from app.services.room import RoomService, RoomError
from app.models.room import RoomStatus


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock()
    return db


@pytest.fixture
def room_service(mock_db):
    """Create RoomService with mock db."""
    return RoomService(mock_db)


def create_mock_room(
    room_id: str | None = None,
    status: str = RoomStatus.WAITING.value,
    current_players: int = 6,  # Full by default for waitlist tests
    max_seats: int = 6,
    buy_in_min: int = 400,
    buy_in_max: int = 2000,
    tables: list | None = None,
) -> MagicMock:
    """Create a mock Room object."""
    room = MagicMock()
    room.id = room_id or str(uuid4())
    room.status = status
    room.current_players = current_players
    room.max_seats = max_seats
    room.config = {
        "max_seats": max_seats,
        "buy_in_min": buy_in_min,
        "buy_in_max": buy_in_max,
    }
    room.is_full = current_players >= max_seats
    room.tables = tables or []
    return room


def create_mock_table(
    table_id: str | None = None,
    room_id: str | None = None,
    seats: dict | None = None,
) -> MagicMock:
    """Create a mock Table object."""
    table = MagicMock()
    table.id = table_id or str(uuid4())
    table.room_id = room_id or str(uuid4())
    table.seats = seats or {}
    return table


def create_mock_user(
    user_id: str | None = None,
    nickname: str = "TestUser",
    balance: int = 10000,
) -> MagicMock:
    """Create a mock User object."""
    user = MagicMock()
    user.id = user_id or str(uuid4())
    user.nickname = nickname
    user.balance = balance
    return user


# =============================================================================
# RedisService Waitlist Tests
# =============================================================================

class TestRedisServiceWaitlist:
    """Tests for RedisService waitlist methods."""

    @pytest.mark.asyncio
    async def test_add_to_waitlist_new_user(self):
        """Test adding a new user to waitlist."""
        from app.utils.redis_client import RedisService

        mock_client = AsyncMock()
        mock_client.zscore.return_value = None  # Not in waitlist
        mock_client.zadd.return_value = 1
        mock_client.zrank.return_value = 0  # First position
        mock_client.expire.return_value = True
        mock_client.setex.return_value = True

        service = RedisService(mock_client)
        room_id = str(uuid4())
        user_id = str(uuid4())
        buy_in = 1000

        result = await service.add_to_waitlist(room_id, user_id, buy_in)

        assert result["position"] == 1
        assert result["already_waiting"] is False
        assert "joined_at" in result

    @pytest.mark.asyncio
    async def test_add_to_waitlist_already_waiting(self):
        """Test adding a user who is already in waitlist."""
        from app.utils.redis_client import RedisService

        mock_client = AsyncMock()
        mock_client.zscore.return_value = 1234567890.0  # Already in waitlist
        mock_client.zrank.return_value = 2  # Third position
        mock_client.get.return_value = '{"user_id": "test", "buy_in": 1000, "joined_at": "2026-01-17T10:00:00Z"}'

        service = RedisService(mock_client)
        room_id = str(uuid4())
        user_id = str(uuid4())
        buy_in = 1000

        result = await service.add_to_waitlist(room_id, user_id, buy_in)

        assert result["position"] == 3
        assert result["already_waiting"] is True

    @pytest.mark.asyncio
    async def test_remove_from_waitlist(self):
        """Test removing a user from waitlist."""
        from app.utils.redis_client import RedisService

        mock_client = AsyncMock()
        mock_client.zrem.return_value = 1  # Removed 1 element
        mock_client.delete.return_value = 1

        service = RedisService(mock_client)
        room_id = str(uuid4())
        user_id = str(uuid4())

        result = await service.remove_from_waitlist(room_id, user_id)

        assert result is True
        mock_client.zrem.assert_called_once()
        mock_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_from_waitlist_not_found(self):
        """Test removing a user not in waitlist."""
        from app.utils.redis_client import RedisService

        mock_client = AsyncMock()
        mock_client.zrem.return_value = 0  # No element removed

        service = RedisService(mock_client)
        room_id = str(uuid4())
        user_id = str(uuid4())

        result = await service.remove_from_waitlist(room_id, user_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_get_waitlist(self):
        """Test getting waitlist."""
        from app.utils.redis_client import RedisService

        user1_id = str(uuid4())
        user2_id = str(uuid4())

        mock_client = AsyncMock()
        mock_client.zrange.return_value = [user1_id, user2_id]
        mock_client.get.side_effect = [
            f'{{"user_id": "{user1_id}", "buy_in": 1000, "joined_at": "2026-01-17T10:00:00Z"}}',
            f'{{"user_id": "{user2_id}", "buy_in": 1500, "joined_at": "2026-01-17T10:01:00Z"}}',
        ]

        service = RedisService(mock_client)
        room_id = str(uuid4())

        result = await service.get_waitlist(room_id)

        assert len(result) == 2
        assert result[0]["position"] == 1
        assert result[1]["position"] == 2

    @pytest.mark.asyncio
    async def test_get_waitlist_position(self):
        """Test getting user's waitlist position."""
        from app.utils.redis_client import RedisService

        mock_client = AsyncMock()
        mock_client.zrank.return_value = 2  # Third position (0-indexed)

        service = RedisService(mock_client)
        room_id = str(uuid4())
        user_id = str(uuid4())

        result = await service.get_waitlist_position(room_id, user_id)

        assert result == 3  # 1-indexed

    @pytest.mark.asyncio
    async def test_get_waitlist_position_not_found(self):
        """Test getting position for user not in waitlist."""
        from app.utils.redis_client import RedisService

        mock_client = AsyncMock()
        mock_client.zrank.return_value = None

        service = RedisService(mock_client)
        room_id = str(uuid4())
        user_id = str(uuid4())

        result = await service.get_waitlist_position(room_id, user_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_first_in_waitlist(self):
        """Test getting first user in waitlist."""
        from app.utils.redis_client import RedisService

        user_id = str(uuid4())

        mock_client = AsyncMock()
        mock_client.zrange.return_value = [user_id]
        mock_client.get.return_value = f'{{"user_id": "{user_id}", "buy_in": 1000, "joined_at": "2026-01-17T10:00:00Z"}}'

        service = RedisService(mock_client)
        room_id = str(uuid4())

        result = await service.get_first_in_waitlist(room_id)

        assert result is not None
        assert result["user_id"] == user_id
        assert result["position"] == 1

    @pytest.mark.asyncio
    async def test_get_first_in_waitlist_empty(self):
        """Test getting first user from empty waitlist."""
        from app.utils.redis_client import RedisService

        mock_client = AsyncMock()
        mock_client.zrange.return_value = []

        service = RedisService(mock_client)
        room_id = str(uuid4())

        result = await service.get_first_in_waitlist(room_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_waitlist_count(self):
        """Test getting waitlist count."""
        from app.utils.redis_client import RedisService

        mock_client = AsyncMock()
        mock_client.zcard.return_value = 5

        service = RedisService(mock_client)
        room_id = str(uuid4())

        result = await service.get_waitlist_count(room_id)

        assert result == 5


# =============================================================================
# RoomService Waitlist Tests
# =============================================================================

class TestRoomServiceWaitlist:
    """Tests for RoomService waitlist methods."""

    @pytest.mark.asyncio
    async def test_add_to_waitlist_room_not_found(self, room_service):
        """Test adding to waitlist when room doesn't exist."""
        room_service.get_room_with_tables = AsyncMock(return_value=None)

        with pytest.raises(RoomError) as exc_info:
            await room_service.add_to_waitlist(
                room_id=str(uuid4()),
                user_id=str(uuid4()),
                buy_in=1000,
            )

        assert exc_info.value.code == "ROOM_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_add_to_waitlist_room_closed(self, room_service):
        """Test adding to waitlist when room is closed."""
        room = create_mock_room(status=RoomStatus.CLOSED.value)
        room_service.get_room_with_tables = AsyncMock(return_value=room)

        with pytest.raises(RoomError) as exc_info:
            await room_service.add_to_waitlist(
                room_id=str(uuid4()),
                user_id=str(uuid4()),
                buy_in=1000,
            )

        assert exc_info.value.code == "ROOM_CLOSED"

    @pytest.mark.asyncio
    async def test_add_to_waitlist_invalid_buyin(self, room_service, mock_db):
        """Test adding to waitlist with invalid buy-in."""
        room = create_mock_room(buy_in_min=500, buy_in_max=2000)
        room_service.get_room_with_tables = AsyncMock(return_value=room)

        with pytest.raises(RoomError) as exc_info:
            await room_service.add_to_waitlist(
                room_id=str(uuid4()),
                user_id=str(uuid4()),
                buy_in=100,  # Below minimum
            )

        assert exc_info.value.code == "ROOM_INVALID_BUYIN"

    @pytest.mark.asyncio
    async def test_add_to_waitlist_user_not_found(self, room_service, mock_db):
        """Test adding to waitlist when user doesn't exist."""
        room = create_mock_room()
        table = create_mock_table()
        room.tables = [table]
        room_service.get_room_with_tables = AsyncMock(return_value=room)
        mock_db.get.return_value = None  # User not found

        with pytest.raises(RoomError) as exc_info:
            await room_service.add_to_waitlist(
                room_id=str(uuid4()),
                user_id=str(uuid4()),
                buy_in=1000,
            )

        assert exc_info.value.code == "USER_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_add_to_waitlist_insufficient_balance(self, room_service, mock_db):
        """Test adding to waitlist with insufficient balance."""
        room = create_mock_room()
        table = create_mock_table()
        room.tables = [table]
        user = create_mock_user(balance=500)  # Not enough balance

        room_service.get_room_with_tables = AsyncMock(return_value=room)
        mock_db.get.return_value = user

        with pytest.raises(RoomError) as exc_info:
            await room_service.add_to_waitlist(
                room_id=str(uuid4()),
                user_id=str(uuid4()),
                buy_in=1000,
            )

        assert exc_info.value.code == "INSUFFICIENT_BALANCE"

    @pytest.mark.asyncio
    async def test_add_to_waitlist_already_seated(self, room_service, mock_db):
        """Test adding to waitlist when user is already seated."""
        user_id = str(uuid4())
        room = create_mock_room()
        table = create_mock_table(seats={"0": {"user_id": user_id}})
        room.tables = [table]
        user = create_mock_user(user_id=user_id, balance=10000)

        room_service.get_room_with_tables = AsyncMock(return_value=room)
        mock_db.get.return_value = user

        with pytest.raises(RoomError) as exc_info:
            await room_service.add_to_waitlist(
                room_id=str(uuid4()),
                user_id=user_id,
                buy_in=1000,
            )

        assert exc_info.value.code == "ALREADY_SEATED"

    @pytest.mark.asyncio
    async def test_add_to_waitlist_success(self, room_service, mock_db):
        """Test successful waitlist addition."""
        user_id = str(uuid4())
        room_id = str(uuid4())
        room = create_mock_room(room_id=room_id)
        table = create_mock_table()
        room.tables = [table]
        user = create_mock_user(user_id=user_id, balance=10000)

        room_service.get_room_with_tables = AsyncMock(return_value=room)
        mock_db.get.return_value = user

        with patch("app.utils.redis_client.get_redis_context") as mock_redis_context:
            mock_redis = AsyncMock()
            mock_redis.__aenter__.return_value = mock_redis
            mock_redis.__aexit__.return_value = None
            mock_redis_context.return_value = mock_redis

            # Mock RedisService methods
            with patch("app.utils.redis_client.RedisService") as mock_redis_service_class:
                mock_redis_service = AsyncMock()
                mock_redis_service.add_to_waitlist.return_value = {
                    "position": 1,
                    "joined_at": "2026-01-17T10:00:00Z",
                    "already_waiting": False,
                }
                mock_redis_service_class.return_value = mock_redis_service

                result = await room_service.add_to_waitlist(
                    room_id=room_id,
                    user_id=user_id,
                    buy_in=1000,
                )

                assert result["room_id"] == room_id
                assert result["user_id"] == user_id
                assert result["position"] == 1
                assert result["already_waiting"] is False

    @pytest.mark.asyncio
    async def test_cancel_waitlist(self, room_service):
        """Test canceling waitlist."""
        room_id = str(uuid4())
        user_id = str(uuid4())

        with patch("app.utils.redis_client.get_redis_context") as mock_redis_context:
            mock_redis = AsyncMock()
            mock_redis.__aenter__.return_value = mock_redis
            mock_redis.__aexit__.return_value = None
            mock_redis_context.return_value = mock_redis

            with patch("app.utils.redis_client.RedisService") as mock_redis_service_class:
                mock_redis_service = AsyncMock()
                mock_redis_service.remove_from_waitlist.return_value = True
                mock_redis_service_class.return_value = mock_redis_service

                result = await room_service.cancel_waitlist(room_id, user_id)

                assert result is True

    @pytest.mark.asyncio
    async def test_get_waitlist(self, room_service):
        """Test getting waitlist."""
        room_id = str(uuid4())
        user1_id = str(uuid4())
        user2_id = str(uuid4())

        expected_waitlist = [
            {"user_id": user1_id, "buy_in": 1000, "position": 1},
            {"user_id": user2_id, "buy_in": 1500, "position": 2},
        ]

        with patch("app.utils.redis_client.get_redis_context") as mock_redis_context:
            mock_redis = AsyncMock()
            mock_redis.__aenter__.return_value = mock_redis
            mock_redis.__aexit__.return_value = None
            mock_redis_context.return_value = mock_redis

            with patch("app.utils.redis_client.RedisService") as mock_redis_service_class:
                mock_redis_service = AsyncMock()
                mock_redis_service.get_waitlist.return_value = expected_waitlist
                mock_redis_service_class.return_value = mock_redis_service

                result = await room_service.get_waitlist(room_id)

                assert len(result) == 2
                assert result[0]["position"] == 1
                assert result[1]["position"] == 2


# =============================================================================
# FIFO Order Tests
# =============================================================================

class TestWaitlistFIFOOrder:
    """Tests for FIFO order in waitlist."""

    @pytest.mark.asyncio
    async def test_fifo_order_maintained(self):
        """Test that FIFO order is maintained in waitlist."""
        from app.utils.redis_client import RedisService
        import time

        # Simulate adding users at different times
        users = []
        timestamps = []
        for i in range(5):
            users.append(str(uuid4()))
            timestamps.append(time.time() + i * 0.1)

        mock_client = AsyncMock()

        # Mock zrange to return users in order
        mock_client.zrange.return_value = users

        # Mock get to return user details
        def get_side_effect(key):
            for i, user_id in enumerate(users):
                if user_id in key:
                    return f'{{"user_id": "{user_id}", "buy_in": 1000, "joined_at": "2026-01-17T10:0{i}:00Z"}}'
            return None

        mock_client.get.side_effect = get_side_effect

        service = RedisService(mock_client)
        room_id = str(uuid4())

        result = await service.get_waitlist(room_id)

        # Verify FIFO order
        assert len(result) == 5
        for i, waiter in enumerate(result):
            assert waiter["position"] == i + 1
            assert waiter["user_id"] == users[i]
