"""Unit tests for RoomService quick join methods.

Tests find_available_rooms and quick_join_room methods.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

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
    current_players: int = 2,
    max_seats: int = 6,
    small_blind: int = 10,
    big_blind: int = 20,
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
    room.small_blind = small_blind
    room.big_blind = big_blind
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
# Tests: find_available_rooms
# =============================================================================

class TestFindAvailableRooms:
    """Tests for find_available_rooms method."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_rooms(self, room_service, mock_db):
        """Returns empty list when no rooms available."""
        # Setup: No rooms in database
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        # Execute
        rooms = await room_service.find_available_rooms(user_balance=10000)

        # Verify
        assert rooms == []

    @pytest.mark.asyncio
    async def test_filters_by_balance(self, room_service, mock_db):
        """Filters out rooms where user can't afford min buy-in."""
        # Setup: Two rooms, one affordable, one not
        affordable_room = create_mock_room(buy_in_min=400)
        expensive_room = create_mock_room(buy_in_min=5000)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [affordable_room, expensive_room]
        mock_db.execute.return_value = mock_result

        # Execute with balance that can only afford one room
        rooms = await room_service.find_available_rooms(user_balance=1000)

        # Verify
        assert len(rooms) == 1
        assert rooms[0] == affordable_room

    @pytest.mark.asyncio
    async def test_sorts_by_priority_score(self, room_service, mock_db):
        """Rooms are sorted by priority score (playing > waiting)."""
        # Setup: Two rooms with different statuses
        waiting_room = create_mock_room(
            status=RoomStatus.WAITING.value,
            current_players=2,
        )
        playing_room = create_mock_room(
            status=RoomStatus.PLAYING.value,
            current_players=2,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [waiting_room, playing_room]
        mock_db.execute.return_value = mock_result

        # Execute
        rooms = await room_service.find_available_rooms(user_balance=10000)

        # Verify: Playing room should be first
        assert len(rooms) == 2
        assert rooms[0] == playing_room
        assert rooms[1] == waiting_room


# =============================================================================
# Tests: quick_join_room
# =============================================================================

class TestQuickJoinRoom:
    """Tests for quick_join_room method."""

    @pytest.mark.asyncio
    async def test_successful_join(self, room_service, mock_db):
        """Successfully joins room with valid parameters."""
        # Setup
        user_id = str(uuid4())
        room_id = str(uuid4())
        table = create_mock_table(room_id=room_id, seats={})
        room = create_mock_room(
            room_id=room_id,
            status=RoomStatus.WAITING.value,
            current_players=1,
            tables=[table],
        )
        user = create_mock_user(user_id=user_id, balance=10000)

        # Mock get_room_with_tables
        room_service.get_room_with_tables = AsyncMock(return_value=room)
        mock_db.get.return_value = user

        # Execute
        result = await room_service.quick_join_room(
            user_id=user_id,
            room_id=room_id,
            seat=0,
            buy_in=1000,
        )

        # Verify
        assert result["table_id"] == table.id
        assert result["position"] == 0
        assert result["stack"] == 1000
        assert user.balance == 9000  # Deducted

    @pytest.mark.asyncio
    async def test_room_not_found(self, room_service, mock_db):
        """Raises error when room not found."""
        room_service.get_room_with_tables = AsyncMock(return_value=None)

        with pytest.raises(RoomError) as exc_info:
            await room_service.quick_join_room(
                user_id=str(uuid4()),
                room_id=str(uuid4()),
                seat=0,
                buy_in=1000,
            )

        assert exc_info.value.code == "ROOM_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_room_closed(self, room_service, mock_db):
        """Raises error when room is closed."""
        room = create_mock_room(status=RoomStatus.CLOSED.value)
        room_service.get_room_with_tables = AsyncMock(return_value=room)

        with pytest.raises(RoomError) as exc_info:
            await room_service.quick_join_room(
                user_id=str(uuid4()),
                room_id=room.id,
                seat=0,
                buy_in=1000,
            )

        assert exc_info.value.code == "ROOM_CLOSED"

    @pytest.mark.asyncio
    async def test_room_full(self, room_service, mock_db):
        """Raises error when room is full."""
        room = create_mock_room(current_players=6, max_seats=6)
        room.is_full = True
        room_service.get_room_with_tables = AsyncMock(return_value=room)

        with pytest.raises(RoomError) as exc_info:
            await room_service.quick_join_room(
                user_id=str(uuid4()),
                room_id=room.id,
                seat=0,
                buy_in=1000,
            )

        assert exc_info.value.code == "ROOM_FULL"

    @pytest.mark.asyncio
    async def test_insufficient_balance(self, room_service, mock_db):
        """Raises error when user has insufficient balance."""
        user_id = str(uuid4())
        table = create_mock_table(seats={})
        room = create_mock_room(tables=[table])
        user = create_mock_user(user_id=user_id, balance=500)

        room_service.get_room_with_tables = AsyncMock(return_value=room)
        mock_db.get.return_value = user

        with pytest.raises(RoomError) as exc_info:
            await room_service.quick_join_room(
                user_id=user_id,
                room_id=room.id,
                seat=0,
                buy_in=1000,
            )

        assert exc_info.value.code == "INSUFFICIENT_BALANCE"

    @pytest.mark.asyncio
    async def test_seat_taken_finds_alternative(self, room_service, mock_db):
        """Finds alternative seat when requested seat is taken."""
        user_id = str(uuid4())
        other_user_id = str(uuid4())
        
        # Seat 0 is taken
        table = create_mock_table(seats={
            "0": {"user_id": other_user_id, "stack": 1000},
        })
        room = create_mock_room(
            current_players=1,
            max_seats=6,
            tables=[table],
        )
        user = create_mock_user(user_id=user_id, balance=10000)

        room_service.get_room_with_tables = AsyncMock(return_value=room)
        mock_db.get.return_value = user

        # Request seat 0 (taken)
        result = await room_service.quick_join_room(
            user_id=user_id,
            room_id=room.id,
            seat=0,
            buy_in=1000,
        )

        # Should get seat 1 instead
        assert result["position"] == 1

    @pytest.mark.asyncio
    async def test_already_seated_returns_existing(self, room_service, mock_db):
        """Returns existing seat info if user already seated."""
        user_id = str(uuid4())
        
        # User already in seat 2
        table = create_mock_table(seats={
            "2": {"user_id": user_id, "stack": 1500},
        })
        room = create_mock_room(
            current_players=1,
            tables=[table],
        )

        room_service.get_room_with_tables = AsyncMock(return_value=room)

        result = await room_service.quick_join_room(
            user_id=user_id,
            room_id=room.id,
            seat=0,
            buy_in=1000,
        )

        assert result["position"] == 2
        assert result["stack"] == 1500
        assert result.get("already_seated") is True

    @pytest.mark.asyncio
    async def test_updates_room_status_when_enough_players(self, room_service, mock_db):
        """Updates room status to PLAYING when 2+ players."""
        user_id = str(uuid4())
        other_user_id = str(uuid4())
        
        # One player already seated
        table = create_mock_table(seats={
            "0": {"user_id": other_user_id, "stack": 1000},
        })
        room = create_mock_room(
            status=RoomStatus.WAITING.value,
            current_players=1,
            tables=[table],
        )
        user = create_mock_user(user_id=user_id, balance=10000)

        room_service.get_room_with_tables = AsyncMock(return_value=room)
        mock_db.get.return_value = user

        await room_service.quick_join_room(
            user_id=user_id,
            room_id=room.id,
            seat=1,
            buy_in=1000,
        )

        # Room should now be PLAYING
        assert room.status == RoomStatus.PLAYING.value
        assert room.current_players == 2
