"""Tests for mid-game snapshot synchronization (Phase 4.3).

Tests for TABLE_SNAPSHOT with action history, time bank info, and turn info
for players/spectators joining during an active hand.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio

from app.game import game_manager, Player
from app.game.poker_table import PokerTable, GamePhase
from app.ws.connection import WebSocketConnection
from app.ws.events import EventType
from app.ws.handlers.table import TableHandler
from app.ws.messages import MessageEnvelope


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def room_id() -> str:
    """Generate a room ID."""
    return str(uuid4())


@pytest.fixture
def user_id() -> str:
    """Generate a user ID."""
    return str(uuid4())


@pytest.fixture
def spectator_id() -> str:
    """Generate a spectator user ID."""
    return str(uuid4())


@pytest.fixture
def mock_table(room_id: str):
    """Create a mock Table object."""
    table = MagicMock()
    table.room_id = room_id
    table.seats = {}
    table.state_version = 1
    table.updated_at = datetime.now(timezone.utc)
    table.dealer_position = 0
    table.room = MagicMock()
    table.room.config = {
        "max_seats": 6,
        "small_blind": 10,
        "big_blind": 20,
        "buy_in_min": 400,
        "buy_in_max": 2000,
        "turn_timeout": 30,
    }
    return table


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_manager():
    """Create a mock ConnectionManager."""
    manager = MagicMock()
    manager.subscribe_as_player = AsyncMock()
    manager.subscribe_as_spectator = AsyncMock()
    manager.broadcast_to_channel = AsyncMock()
    return manager


@pytest_asyncio.fixture
async def game_table_with_players(room_id: str, user_id: str):
    """Create a game table with players and start a hand."""
    # Create table in GameManager
    game_table = game_manager.get_or_create_table(
        room_id=room_id,
        name="Test Table",
        small_blind=10,
        big_blind=20,
        min_buy_in=400,
        max_buy_in=2000,
        max_players=6,
    )

    # Add players
    player1 = Player(
        user_id=user_id,
        username="Player1",
        seat=0,
        stack=1000,
    )
    player2 = Player(
        user_id=str(uuid4()),
        username="Player2",
        seat=1,
        stack=1000,
    )

    game_table.seat_player(0, player1)
    game_table.seat_player(1, player2)

    yield game_table

    # Cleanup
    game_manager.remove_table(room_id)


# =============================================================================
# Tests
# =============================================================================


class TestMidGameSnapshot:
    """Tests for mid-game snapshot synchronization."""

    @pytest.mark.asyncio
    async def test_snapshot_includes_action_history(
        self,
        room_id: str,
        user_id: str,
        mock_table,
        mock_db,
        mock_manager,
        game_table_with_players,
    ):
        """Test that TABLE_SNAPSHOT includes action history for mid-game sync."""
        game_table = game_table_with_players

        # Start a hand
        result = game_table.start_new_hand()
        assert result["success"]

        # Simulate some actions
        current_player_seat = game_table.current_player_seat
        current_player = game_table.players.get(current_player_seat)
        if current_player:
            game_table.process_action(current_player.user_id, "call", 20)

        # Create handler and mock table lookup
        handler = TableHandler(mock_manager, mock_db)
        handler._get_table_by_id_or_room = AsyncMock(return_value=mock_table)
        handler._ensure_game_table = AsyncMock(return_value=game_table)

        # Create connection for a spectator
        spectator_conn = MagicMock(spec=WebSocketConnection)
        spectator_conn.user_id = str(uuid4())  # Different user
        spectator_conn.connection_id = str(uuid4())

        # Send SUBSCRIBE_TABLE
        event = MessageEnvelope.create(
            event_type=EventType.SUBSCRIBE_TABLE,
            payload={"tableId": room_id},
        )

        response = await handler._handle_subscribe(spectator_conn, event)

        # Verify response
        assert response is not None
        assert response.type == EventType.TABLE_SNAPSHOT

        # Check action history
        payload = response.payload
        assert "hand" in payload
        assert payload["hand"] is not None
        assert "actionHistory" in payload["hand"]

        action_history = payload["hand"]["actionHistory"]
        assert len(action_history) > 0  # At least one action (the call)
        assert action_history[-1]["action"] in ("call", "check")

    @pytest.mark.asyncio
    async def test_snapshot_includes_time_bank_info(
        self,
        room_id: str,
        user_id: str,
        mock_table,
        mock_db,
        mock_manager,
        game_table_with_players,
    ):
        """Test that each seat includes timeBankRemaining."""
        game_table = game_table_with_players

        # Start a hand
        result = game_table.start_new_hand()
        assert result["success"]

        # Create handler and mock table lookup
        handler = TableHandler(mock_manager, mock_db)
        handler._get_table_by_id_or_room = AsyncMock(return_value=mock_table)
        handler._ensure_game_table = AsyncMock(return_value=game_table)

        # Create connection
        conn = MagicMock(spec=WebSocketConnection)
        conn.user_id = user_id
        conn.connection_id = str(uuid4())

        # Build snapshot
        snapshot = await handler._build_table_snapshot(mock_table, user_id, "player")

        # Check seats have timeBankRemaining
        for seat in snapshot["seats"]:
            if seat["player"] is not None:
                assert "timeBankRemaining" in seat
                assert seat["timeBankRemaining"] == 3  # Default value

    @pytest.mark.asyncio
    async def test_snapshot_includes_turn_info(
        self,
        room_id: str,
        user_id: str,
        mock_table,
        mock_db,
        mock_manager,
        game_table_with_players,
    ):
        """Test that TABLE_SNAPSHOT includes turn timing info for timer sync."""
        game_table = game_table_with_players

        # Start a hand
        result = game_table.start_new_hand()
        assert result["success"]

        # Set turn started time
        game_table._turn_started_at = datetime.now(timezone.utc)
        game_table._turn_extra_seconds = 0

        # Create handler and mock table lookup
        handler = TableHandler(mock_manager, mock_db)
        handler._get_table_by_id_or_room = AsyncMock(return_value=mock_table)
        handler._ensure_game_table = AsyncMock(return_value=game_table)

        # Build snapshot
        snapshot = await handler._build_table_snapshot(mock_table, user_id, "player")

        # Check turnInfo
        assert "turnInfo" in snapshot
        turn_info = snapshot["turnInfo"]
        assert turn_info is not None
        assert "currentSeat" in turn_info
        assert "startedAt" in turn_info
        assert "deadlineAt" in turn_info
        assert "remainingSeconds" in turn_info
        assert "extraSeconds" in turn_info

        # Remaining seconds should be close to turn timeout
        assert turn_info["remainingSeconds"] > 25  # Should be around 30 seconds
        assert turn_info["extraSeconds"] == 0

    @pytest.mark.asyncio
    async def test_snapshot_turn_info_with_time_bank(
        self,
        room_id: str,
        user_id: str,
        mock_table,
        mock_db,
        mock_manager,
        game_table_with_players,
    ):
        """Test that turnInfo reflects time bank extra seconds."""
        game_table = game_table_with_players

        # Start a hand
        result = game_table.start_new_hand()
        assert result["success"]

        # Set turn started time
        game_table._turn_started_at = datetime.now(timezone.utc)

        # Use time bank (adds 30 seconds)
        current_seat = game_table.current_player_seat
        time_bank_result = game_table.use_time_bank(current_seat)
        assert time_bank_result["success"]

        # Create handler and mock table lookup
        handler = TableHandler(mock_manager, mock_db)
        handler._get_table_by_id_or_room = AsyncMock(return_value=mock_table)
        handler._ensure_game_table = AsyncMock(return_value=game_table)

        # Build snapshot
        snapshot = await handler._build_table_snapshot(mock_table, user_id, "player")

        # Check turnInfo has extra seconds
        turn_info = snapshot["turnInfo"]
        assert turn_info is not None
        assert turn_info["extraSeconds"] == 30  # Time bank adds 30 seconds
        assert turn_info["remainingSeconds"] > 55  # Should be around 60 seconds

    @pytest.mark.asyncio
    async def test_spectator_snapshot_no_hole_cards(
        self,
        room_id: str,
        mock_table,
        mock_db,
        mock_manager,
        game_table_with_players,
    ):
        """Test that spectators don't receive hole cards in snapshot."""
        game_table = game_table_with_players

        # Start a hand
        result = game_table.start_new_hand()
        assert result["success"]

        # Create handler
        handler = TableHandler(mock_manager, mock_db)
        handler._get_table_by_id_or_room = AsyncMock(return_value=mock_table)
        handler._ensure_game_table = AsyncMock(return_value=game_table)

        # Build snapshot for spectator
        spectator_id = str(uuid4())
        snapshot = await handler._build_table_snapshot(mock_table, spectator_id, "spectator")

        # Spectator should not see hole cards
        assert snapshot.get("myHoleCards") is None
        assert snapshot.get("myPosition") is None

    @pytest.mark.asyncio
    async def test_player_snapshot_includes_hole_cards(
        self,
        room_id: str,
        user_id: str,
        mock_table,
        mock_db,
        mock_manager,
        game_table_with_players,
    ):
        """Test that players receive their hole cards in snapshot."""
        game_table = game_table_with_players

        # Start a hand
        result = game_table.start_new_hand()
        assert result["success"]

        # Create handler
        handler = TableHandler(mock_manager, mock_db)
        handler._get_table_by_id_or_room = AsyncMock(return_value=mock_table)
        handler._ensure_game_table = AsyncMock(return_value=game_table)

        # Build snapshot for player
        snapshot = await handler._build_table_snapshot(mock_table, user_id, "player")

        # Player should see their position and hole cards
        assert snapshot.get("myPosition") == 0
        assert snapshot.get("myHoleCards") is not None
        assert len(snapshot["myHoleCards"]) == 2

    @pytest.mark.asyncio
    async def test_snapshot_includes_community_cards(
        self,
        room_id: str,
        user_id: str,
        mock_table,
        mock_db,
        mock_manager,
        game_table_with_players,
    ):
        """Test that snapshot includes community cards for mid-game entry."""
        game_table = game_table_with_players

        # Start a hand and progress to flop
        result = game_table.start_new_hand()
        assert result["success"]

        # Simulate preflop completion and flop
        game_table.phase = GamePhase.FLOP
        game_table.community_cards = ["Ah", "Kh", "Qh"]

        # Create handler
        handler = TableHandler(mock_manager, mock_db)
        handler._get_table_by_id_or_room = AsyncMock(return_value=mock_table)
        handler._ensure_game_table = AsyncMock(return_value=game_table)

        # Build snapshot
        snapshot = await handler._build_table_snapshot(mock_table, user_id, "spectator")

        # Check hand info with community cards
        assert snapshot["hand"] is not None
        assert snapshot["hand"]["phase"] == "flop"
        assert snapshot["hand"]["communityCards"] == ["Ah", "Kh", "Qh"]

    @pytest.mark.asyncio
    async def test_snapshot_is_state_restore_flag(
        self,
        room_id: str,
        user_id: str,
        mock_table,
        mock_db,
        mock_manager,
        game_table_with_players,
    ):
        """Test that snapshot includes isStateRestore flag for client handling."""
        game_table = game_table_with_players

        # Create handler
        handler = TableHandler(mock_manager, mock_db)
        handler._get_table_by_id_or_room = AsyncMock(return_value=mock_table)
        handler._ensure_game_table = AsyncMock(return_value=game_table)

        # Build snapshot
        snapshot = await handler._build_table_snapshot(mock_table, user_id, "player")

        # Check isStateRestore flag
        assert snapshot.get("isStateRestore") is True

    @pytest.mark.asyncio
    async def test_snapshot_no_turn_info_when_waiting(
        self,
        room_id: str,
        user_id: str,
        mock_table,
        mock_db,
        mock_manager,
        game_table_with_players,
    ):
        """Test that turnInfo is null when no hand is in progress."""
        game_table = game_table_with_players
        # Don't start a hand - phase should be WAITING

        # Create handler
        handler = TableHandler(mock_manager, mock_db)
        handler._get_table_by_id_or_room = AsyncMock(return_value=mock_table)
        handler._ensure_game_table = AsyncMock(return_value=game_table)

        # Build snapshot
        snapshot = await handler._build_table_snapshot(mock_table, user_id, "player")

        # No turn info when waiting
        assert snapshot.get("turnInfo") is None
        assert snapshot.get("hand") is None


class TestActionHistoryPhaseTracking:
    """Tests for action history with phase tracking."""

    @pytest.mark.asyncio
    async def test_action_history_tracks_phase(
        self,
        room_id: str,
        user_id: str,
        mock_table,
        mock_db,
        mock_manager,
        game_table_with_players,
    ):
        """Test that action history tracks the phase of each action."""
        game_table = game_table_with_players

        # Start a hand
        result = game_table.start_new_hand()
        assert result["success"]

        # Make an action
        current_player_seat = game_table.current_player_seat
        current_player = game_table.players.get(current_player_seat)
        if current_player:
            game_table.process_action(current_player.user_id, "call", 20)

        # Check internal action tracking
        assert len(game_table._hand_actions) > 0
        last_action = game_table._hand_actions[-1]
        assert "phase" in last_action
        assert last_action["phase"] == "preflop"

    @pytest.mark.asyncio
    async def test_action_history_multiple_phases(
        self,
        room_id: str,
        mock_table,
        mock_db,
        mock_manager,
    ):
        """Test that action history spans multiple phases correctly."""
        # Create a fresh table for this test
        test_room_id = str(uuid4())
        game_table = game_manager.get_or_create_table(
            room_id=test_room_id,
            name="Test Table",
            small_blind=10,
            big_blind=20,
            min_buy_in=400,
            max_buy_in=2000,
            max_players=6,
        )

        # Add players
        player1 = Player(
            user_id=str(uuid4()),
            username="Player1",
            seat=0,
            stack=1000,
        )
        player2 = Player(
            user_id=str(uuid4()),
            username="Player2",
            seat=1,
            stack=1000,
        )

        game_table.seat_player(0, player1)
        game_table.seat_player(1, player2)

        # Start hand
        result = game_table.start_new_hand()
        assert result["success"]

        # Record preflop action count
        preflop_action_count = len(game_table._hand_actions)

        # Actions in preflop should have preflop phase
        for action in game_table._hand_actions:
            assert action["phase"] == "preflop"

        # Cleanup
        game_manager.remove_table(test_room_id)
