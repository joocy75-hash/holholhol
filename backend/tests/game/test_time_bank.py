"""Property-Based Tests for Time Bank feature.

Tests universal correctness properties:
- Property 1: Time Bank Initialization
- Property 2: Time Bank Usage Effect
- Property 3: Time Bank Bounds

**Feature: p1-time-bank**
**Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from typing import List
from unittest.mock import MagicMock

from app.game.poker_table import PokerTable, Player, GamePhase


# Helper function to create a fresh table
def create_basic_table():
    """Create a basic poker table for testing."""
    return PokerTable(
        room_id="test-room",
        name="Test Table",
        small_blind=50,
        big_blind=100,
        min_buy_in=1000,
        max_buy_in=10000,
        max_players=9,
    )


def create_table_with_players():
    """Create a table with 3 players seated."""
    table = create_basic_table()
    
    # Seat 3 players
    for i, seat in enumerate([0, 1, 2]):
        player = Player(
            user_id=f"user_{i}",
            username=f"Player{i}",
            seat=seat,
            stack=5000,
        )
        table.seat_player(seat, player)
    
    return table


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def basic_table():
    """Create a basic poker table for testing."""
    return create_basic_table()


@pytest.fixture
def table_with_players():
    """Create a table with 3 players seated."""
    return create_table_with_players()


# =============================================================================
# Property 1: Time Bank Initialization
# **Validates: Requirements 1.1, 1.2, 1.3**
# =============================================================================

class TestTimeBankInitialization:
    """Property 1: Time Bank Initialization
    
    *For any* player seated at a table, their time_bank_remaining should be 
    initialized to TIME_BANK_COUNT (default 3) when they sit down or when 
    a new hand starts.
    """
    
    def test_player_default_time_bank(self):
        """New player should have default time bank count."""
        player = Player(
            user_id="test_user",
            username="TestPlayer",
            seat=0,
            stack=5000,
        )
        assert player.time_bank_remaining == 3
    
    @given(initial_count=st.integers(min_value=0, max_value=10))
    @settings(max_examples=50)
    def test_reset_time_banks_sets_to_default(self, initial_count):
        """Property: reset_time_banks() always sets to TIME_BANK_COUNT.
        
        **Feature: p1-time-bank, Property 1: Time Bank Initialization**
        **Validates: Requirements 1.1, 1.3**
        """
        table = create_basic_table()
        
        # Seat a player with arbitrary initial time bank
        player = Player(
            user_id="test_user",
            username="TestPlayer",
            seat=0,
            stack=5000,
            time_bank_remaining=initial_count,
        )
        table.seat_player(0, player)
        
        # Reset time banks
        table.reset_time_banks()
        
        # Should always be TIME_BANK_COUNT after reset
        assert player.time_bank_remaining == table.TIME_BANK_COUNT
    
    @given(num_players=st.integers(min_value=2, max_value=9))
    @settings(max_examples=30)
    def test_all_players_reset_on_hand_start(self, num_players):
        """Property: All players get time banks reset when hand starts.
        
        **Feature: p1-time-bank, Property 1: Time Bank Initialization**
        **Validates: Requirements 1.1**
        """
        table = create_basic_table()
        
        # Seat players with varying time bank counts
        for i in range(num_players):
            player = Player(
                user_id=f"user_{i}",
                username=f"Player{i}",
                seat=i,
                stack=5000,
                time_bank_remaining=i % 4,  # Varying initial counts
            )
            table.seat_player(i, player)
        
        # Start a hand (which should reset time banks)
        result = table.start_new_hand()
        
        if result.get("success"):
            # All players should have TIME_BANK_COUNT
            for seat, player in table.players.items():
                if player is not None:
                    assert player.time_bank_remaining == table.TIME_BANK_COUNT, \
                        f"Player at seat {seat} should have {table.TIME_BANK_COUNT} time banks"


# =============================================================================
# Property 2: Time Bank Usage Effect
# **Validates: Requirements 2.1, 2.2**
# =============================================================================

class TestTimeBankUsageEffect:
    """Property 2: Time Bank Usage Effect
    
    *For any* valid time bank request (player's turn, remaining > 0), 
    the turn deadline should increase by exactly TIME_BANK_SECONDS and 
    the player's remaining count should decrease by exactly 1.
    """
    
    def test_time_bank_decreases_by_one(self, table_with_players):
        """Using time bank should decrease remaining by exactly 1.
        
        **Feature: p1-time-bank, Property 2: Time Bank Usage Effect**
        **Validates: Requirements 2.1**
        """
        table = table_with_players
        
        # Start a hand
        result = table.start_new_hand()
        assert result.get("success"), "Hand should start successfully"
        
        # Get current player
        current_seat = table.current_player_seat
        assert current_seat is not None, "Should have a current player"
        
        player = table.players[current_seat]
        initial_count = player.time_bank_remaining
        
        # Use time bank
        result = table.use_time_bank(current_seat)
        
        assert result["success"], f"Time bank should succeed: {result.get('error')}"
        assert player.time_bank_remaining == initial_count - 1
        assert result["remaining"] == initial_count - 1
    
    def test_time_bank_adds_correct_seconds(self, table_with_players):
        """Using time bank should add exactly TIME_BANK_SECONDS.
        
        **Feature: p1-time-bank, Property 2: Time Bank Usage Effect**
        **Validates: Requirements 2.2**
        """
        table = table_with_players
        
        # Start a hand
        result = table.start_new_hand()
        assert result.get("success")
        
        current_seat = table.current_player_seat
        
        # Use time bank
        result = table.use_time_bank(current_seat)
        
        assert result["success"]
        assert result["added_seconds"] == table.TIME_BANK_SECONDS
    
    @given(uses=st.integers(min_value=1, max_value=3))
    @settings(max_examples=20)
    def test_multiple_time_bank_uses(self, uses):
        """Property: Multiple uses decrease count correctly.
        
        **Feature: p1-time-bank, Property 2: Time Bank Usage Effect**
        **Validates: Requirements 2.1, 2.2**
        """
        table = create_table_with_players()
        
        # Start a hand
        result = table.start_new_hand()
        assume(result.get("success"))
        
        current_seat = table.current_player_seat
        assume(current_seat is not None)
        
        player = table.players[current_seat]
        initial_count = player.time_bank_remaining
        
        # Use time bank multiple times
        successful_uses = 0
        for _ in range(uses):
            result = table.use_time_bank(current_seat)
            if result["success"]:
                successful_uses += 1
        
        # Count should decrease by number of successful uses
        expected_remaining = max(0, initial_count - successful_uses)
        assert player.time_bank_remaining == expected_remaining


# =============================================================================
# Property 3: Time Bank Bounds
# **Validates: Requirements 1.2**
# =============================================================================

class TestTimeBankBounds:
    """Property 3: Time Bank Bounds
    
    *For any* player, their time_bank_remaining should always be 
    in range [0, TIME_BANK_COUNT].
    """
    
    def test_time_bank_never_negative(self, table_with_players):
        """Time bank count should never go below 0.
        
        **Feature: p1-time-bank, Property 3: Time Bank Bounds**
        **Validates: Requirements 1.2**
        """
        table = table_with_players
        
        # Start a hand
        result = table.start_new_hand()
        assert result.get("success")
        
        current_seat = table.current_player_seat
        player = table.players[current_seat]
        
        # Try to use time bank more times than available
        for _ in range(table.TIME_BANK_COUNT + 5):
            table.use_time_bank(current_seat)
        
        # Should never be negative
        assert player.time_bank_remaining >= 0
    
    def test_time_bank_never_exceeds_max(self, basic_table):
        """Time bank count should never exceed TIME_BANK_COUNT.
        
        **Feature: p1-time-bank, Property 3: Time Bank Bounds**
        **Validates: Requirements 1.2**
        """
        table = basic_table
        
        # Create player with artificially high count
        player = Player(
            user_id="test_user",
            username="TestPlayer",
            seat=0,
            stack=5000,
            time_bank_remaining=100,  # Way above max
        )
        table.seat_player(0, player)
        
        # Reset should cap it
        table.reset_time_banks()
        
        assert player.time_bank_remaining == table.TIME_BANK_COUNT
        assert player.time_bank_remaining <= table.TIME_BANK_COUNT
    
    @given(attempts=st.integers(min_value=0, max_value=20))
    @settings(max_examples=30)
    def test_bounds_after_any_operations(self, attempts):
        """Property: Bounds maintained after any sequence of operations.
        
        **Feature: p1-time-bank, Property 3: Time Bank Bounds**
        **Validates: Requirements 1.2**
        """
        table = create_table_with_players()
        
        # Start a hand
        result = table.start_new_hand()
        assume(result.get("success"))
        
        current_seat = table.current_player_seat
        assume(current_seat is not None)
        
        player = table.players[current_seat]
        
        # Perform random number of time bank uses
        for _ in range(attempts):
            table.use_time_bank(current_seat)
        
        # Bounds should always be maintained
        assert 0 <= player.time_bank_remaining <= table.TIME_BANK_COUNT


# =============================================================================
# Error Cases
# =============================================================================

class TestTimeBankErrors:
    """Test error handling for time bank operations."""
    
    def test_time_bank_not_your_turn(self, table_with_players):
        """Using time bank when not your turn should fail."""
        table = table_with_players
        
        # Start a hand
        result = table.start_new_hand()
        assert result.get("success")
        
        current_seat = table.current_player_seat
        
        # Find a seat that's not current
        other_seat = None
        for seat, player in table.players.items():
            if player is not None and seat != current_seat:
                other_seat = seat
                break
        
        assert other_seat is not None, "Should have another player"
        
        # Try to use time bank from wrong seat
        result = table.use_time_bank(other_seat)
        
        assert not result["success"]
        assert result["error"] == "NOT_YOUR_TURN"
    
    def test_time_bank_no_remaining(self, table_with_players):
        """Using time bank with 0 remaining should fail."""
        table = table_with_players
        
        # Start a hand
        result = table.start_new_hand()
        assert result.get("success")
        
        current_seat = table.current_player_seat
        player = table.players[current_seat]
        
        # Use all time banks
        for _ in range(table.TIME_BANK_COUNT):
            table.use_time_bank(current_seat)
        
        assert player.time_bank_remaining == 0
        
        # Try to use one more
        result = table.use_time_bank(current_seat)
        
        assert not result["success"]
        assert result["error"] == "NO_TIME_BANK"
    
    def test_time_bank_no_active_hand(self, table_with_players):
        """Using time bank without active hand should fail."""
        table = table_with_players
        
        # Don't start a hand - phase is WAITING
        assert table.phase == GamePhase.WAITING
        
        # Try to use time bank - current_player_seat is None, so NOT_YOUR_TURN
        result = table.use_time_bank(0)
        
        assert not result["success"]
        # When no hand is active, current_player_seat is None, so it's NOT_YOUR_TURN
        assert result["error"] in ("NO_ACTIVE_HAND", "NOT_YOUR_TURN")
    
    def test_time_bank_player_not_found(self, basic_table):
        """Using time bank for non-existent player should fail."""
        table = basic_table
        
        # No players seated
        result = table.use_time_bank(0)
        
        assert not result["success"]
        assert result["error"] in ("PLAYER_NOT_FOUND", "NOT_YOUR_TURN")


# =============================================================================
# Integration Tests
# =============================================================================

class TestTimeBankIntegration:
    """Integration tests for time bank with game flow."""
    
    def test_time_bank_persists_through_hand(self, table_with_players):
        """Time bank count should persist through a hand."""
        table = table_with_players
        
        # Start a hand
        result = table.start_new_hand()
        assert result.get("success")
        
        current_seat = table.current_player_seat
        player = table.players[current_seat]
        
        # Use one time bank
        result = table.use_time_bank(current_seat)
        assert result["success"]
        
        remaining_after_use = player.time_bank_remaining
        
        # Perform an action (fold)
        table.process_action(player.user_id, "fold")
        
        # Time bank count should still be the same
        assert player.time_bank_remaining == remaining_after_use
    
    def test_time_bank_resets_on_new_hand(self, table_with_players):
        """Time bank should reset when new hand starts."""
        table = table_with_players
        
        # Start first hand
        result = table.start_new_hand()
        assert result.get("success")
        
        current_seat = table.current_player_seat
        player = table.players[current_seat]
        
        # Use all time banks
        for _ in range(table.TIME_BANK_COUNT):
            table.use_time_bank(current_seat)
        
        assert player.time_bank_remaining == 0
        
        # End the hand by folding everyone except one
        for seat, p in table.players.items():
            if p is not None and p.status == "active":
                table.process_action(p.user_id, "fold")
                if table.phase == GamePhase.WAITING:
                    break
        
        # Start new hand
        result = table.start_new_hand()
        if result.get("success"):
            # All players should have full time banks again
            for seat, p in table.players.items():
                if p is not None:
                    assert p.time_bank_remaining == table.TIME_BANK_COUNT
