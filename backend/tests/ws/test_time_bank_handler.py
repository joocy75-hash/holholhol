"""Unit Tests for Time Bank WebSocket Handler.

Tests the TIME_BANK_REQUEST handler in ActionHandler.

**Feature: p1-time-bank**
**Validates: Requirements 2.1-2.5**
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.ws.handlers.action import ActionHandler
from app.ws.events import EventType
from app.ws.messages import MessageEnvelope
from app.game.poker_table import PokerTable, Player, GamePhase


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_connection():
    """Create a mock WebSocket connection."""
    conn = MagicMock()
    conn.user_id = "test_user_0"
    conn.room_id = "test-room"
    return conn


@pytest.fixture
def mock_manager():
    """Create a mock connection manager."""
    manager = MagicMock()
    manager.broadcast_to_room = AsyncMock()
    return manager


@pytest.fixture
def action_handler(mock_manager):
    """Create an ActionHandler instance."""
    handler = ActionHandler(mock_manager)
    return handler


@pytest.fixture
def table_with_active_hand():
    """Create a table with an active hand."""
    table = PokerTable(
        room_id="test-room",
        name="Test Table",
        small_blind=50,
        big_blind=100,
        min_buy_in=1000,
        max_buy_in=10000,
        max_players=9,
    )
    
    # Seat 3 players
    for i, seat in enumerate([0, 1, 2]):
        player = Player(
            user_id=f"test_user_{i}",
            username=f"Player{i}",
            seat=seat,
            stack=5000,
        )
        table.seat_player(seat, player)
    
    # Start a hand
    table.start_new_hand()
    
    return table


def create_time_bank_request(table_id: str, trace_id: str = "test-trace"):
    """Create a TIME_BANK_REQUEST message envelope."""
    return MessageEnvelope.create(
        event_type=EventType.TIME_BANK_REQUEST,
        payload={"tableId": table_id},
        request_id="test-request-id",
        trace_id=trace_id,
    )


# =============================================================================
# Success Cases
# =============================================================================

class TestTimeBankHandlerSuccess:
    """Test successful time bank usage."""
    
    @pytest.mark.asyncio
    async def test_time_bank_success(
        self, action_handler, mock_connection, table_with_active_hand
    ):
        """Time bank request should succeed when it's player's turn."""
        table = table_with_active_hand
        current_seat = table.current_player_seat
        current_player = table.players[current_seat]
        
        # Set connection user_id to current player
        mock_connection.user_id = current_player.user_id
        
        event = create_time_bank_request(table.room_id)
        
        with patch("app.ws.handlers.action.game_manager") as mock_game_manager:
            mock_game_manager.get_table.return_value = table
            
            result = await action_handler._handle_time_bank(mock_connection, event)
        
        assert result.payload["success"] is True
        assert result.payload["remaining"] == table.TIME_BANK_COUNT - 1
        assert result.payload["addedSeconds"] == table.TIME_BANK_SECONDS
        assert result.payload["seat"] == current_seat
    
    @pytest.mark.asyncio
    async def test_time_bank_broadcasts_to_room(
        self, action_handler, mock_connection, mock_manager, table_with_active_hand
    ):
        """Time bank usage should broadcast to all players in room."""
        table = table_with_active_hand
        current_seat = table.current_player_seat
        current_player = table.players[current_seat]
        
        mock_connection.user_id = current_player.user_id
        
        event = create_time_bank_request(table.room_id)
        
        with patch("app.ws.handlers.action.game_manager") as mock_game_manager:
            mock_game_manager.get_table.return_value = table
            
            await action_handler._handle_time_bank(mock_connection, event)
        
        # Should have called broadcast
        mock_manager.broadcast_to_room.assert_called_once()
        call_args = mock_manager.broadcast_to_room.call_args
        assert call_args[0][0] == table.room_id  # room_id


# =============================================================================
# Error Cases
# =============================================================================

class TestTimeBankHandlerErrors:
    """Test error handling for time bank requests."""
    
    @pytest.mark.asyncio
    async def test_time_bank_table_not_found(self, action_handler, mock_connection):
        """Should return error when table doesn't exist."""
        event = create_time_bank_request("non-existent-room")
        
        with patch("app.ws.handlers.action.game_manager") as mock_game_manager:
            mock_game_manager.get_table.return_value = None
            
            result = await action_handler._handle_time_bank(mock_connection, event)
        
        assert result.payload["success"] is False
        assert result.payload["errorCode"] == "TABLE_NOT_FOUND"
    
    @pytest.mark.asyncio
    async def test_time_bank_not_a_player(
        self, action_handler, mock_connection, table_with_active_hand
    ):
        """Should return error when user is not seated at table."""
        table = table_with_active_hand
        mock_connection.user_id = "not_a_player"
        
        event = create_time_bank_request(table.room_id)
        
        with patch("app.ws.handlers.action.game_manager") as mock_game_manager:
            mock_game_manager.get_table.return_value = table
            
            result = await action_handler._handle_time_bank(mock_connection, event)
        
        assert result.payload["success"] is False
        assert result.payload["errorCode"] == "NOT_A_PLAYER"
    
    @pytest.mark.asyncio
    async def test_time_bank_not_your_turn(
        self, action_handler, mock_connection, table_with_active_hand
    ):
        """Should return error when it's not player's turn."""
        table = table_with_active_hand
        current_seat = table.current_player_seat
        
        # Find a player who is NOT current
        other_player = None
        for seat, player in table.players.items():
            if player is not None and seat != current_seat:
                other_player = player
                break
        
        assert other_player is not None
        mock_connection.user_id = other_player.user_id
        
        event = create_time_bank_request(table.room_id)
        
        with patch("app.ws.handlers.action.game_manager") as mock_game_manager:
            mock_game_manager.get_table.return_value = table
            
            result = await action_handler._handle_time_bank(mock_connection, event)
        
        assert result.payload["success"] is False
        assert result.payload["errorCode"] == "NOT_YOUR_TURN"
    
    @pytest.mark.asyncio
    async def test_time_bank_no_remaining(
        self, action_handler, mock_connection, table_with_active_hand
    ):
        """Should return error when no time banks remaining."""
        table = table_with_active_hand
        current_seat = table.current_player_seat
        current_player = table.players[current_seat]
        
        # Use all time banks
        current_player.time_bank_remaining = 0
        
        mock_connection.user_id = current_player.user_id
        
        event = create_time_bank_request(table.room_id)
        
        with patch("app.ws.handlers.action.game_manager") as mock_game_manager:
            mock_game_manager.get_table.return_value = table
            
            result = await action_handler._handle_time_bank(mock_connection, event)
        
        assert result.payload["success"] is False
        assert result.payload["errorCode"] == "NO_TIME_BANK"


# =============================================================================
# Integration Tests
# =============================================================================

class TestTimeBankHandlerIntegration:
    """Integration tests for time bank handler."""
    
    @pytest.mark.asyncio
    async def test_multiple_time_bank_uses(
        self, action_handler, mock_connection, table_with_active_hand
    ):
        """Should allow multiple time bank uses until exhausted."""
        table = table_with_active_hand
        current_seat = table.current_player_seat
        current_player = table.players[current_seat]
        
        mock_connection.user_id = current_player.user_id
        
        with patch("app.ws.handlers.action.game_manager") as mock_game_manager:
            mock_game_manager.get_table.return_value = table
            
            # Use all time banks
            for i in range(table.TIME_BANK_COUNT):
                event = create_time_bank_request(table.room_id)
                result = await action_handler._handle_time_bank(mock_connection, event)
                
                assert result.payload["success"] is True
                assert result.payload["remaining"] == table.TIME_BANK_COUNT - i - 1
            
            # Next use should fail
            event = create_time_bank_request(table.room_id)
            result = await action_handler._handle_time_bank(mock_connection, event)
            
            assert result.payload["success"] is False
            assert result.payload["errorCode"] == "NO_TIME_BANK"
    
    @pytest.mark.asyncio
    async def test_time_bank_response_format(
        self, action_handler, mock_connection, table_with_active_hand
    ):
        """Response should have correct format."""
        table = table_with_active_hand
        current_seat = table.current_player_seat
        current_player = table.players[current_seat]
        
        mock_connection.user_id = current_player.user_id
        
        event = create_time_bank_request(table.room_id)
        
        with patch("app.ws.handlers.action.game_manager") as mock_game_manager:
            mock_game_manager.get_table.return_value = table
            
            result = await action_handler._handle_time_bank(mock_connection, event)
        
        # Check response format
        assert result.type == EventType.TIME_BANK_USED
        assert "success" in result.payload
        assert "tableId" in result.payload
        assert "seat" in result.payload
        assert "remaining" in result.payload
        assert "addedSeconds" in result.payload
