"""Property-based tests for RoomMatcher service.

Tests room filtering, selection priority, and buy-in calculation using Hypothesis.
"""

from __future__ import annotations

import pytest
from hypothesis import given, strategies as st, assume, settings
from unittest.mock import MagicMock

from app.services.room_matcher import (
    calculate_room_score,
    calculate_default_buy_in,
    BLIND_LEVELS,
)
from app.models.room import RoomStatus
from app.utils.errors import InsufficientBalanceError


# =============================================================================
# Helper Functions (avoid pytest fixtures with Hypothesis)
# =============================================================================

def create_mock_room(
    status: str = RoomStatus.WAITING.value,
    current_players: int = 2,
    max_seats: int = 6,
    small_blind: int = 10,
    big_blind: int = 20,
    buy_in_min: int = 400,
    buy_in_max: int = 2000,
) -> MagicMock:
    """Create a mock Room object for testing."""
    room = MagicMock()
    room.status = status
    room.current_players = current_players
    room.small_blind = small_blind
    room.big_blind = big_blind
    room.config = {
        "max_seats": max_seats,
        "buy_in_min": buy_in_min,
        "buy_in_max": buy_in_max,
    }
    return room


# =============================================================================
# Property Tests: Room Score Calculation
# =============================================================================

class TestRoomScoreProperties:
    """Property-based tests for calculate_room_score function."""

    @given(
        current_players=st.integers(min_value=0, max_value=9),
        max_seats=st.integers(min_value=2, max_value=9),
    )
    def test_score_always_non_negative(self, current_players: int, max_seats: int):
        """Property: Room score is always non-negative."""
        assume(current_players <= max_seats)
        
        room = create_mock_room(
            current_players=current_players,
            max_seats=max_seats,
        )
        
        score = calculate_room_score(room)
        assert score >= 0

    @given(
        current_players=st.integers(min_value=0, max_value=6),
    )
    def test_playing_status_higher_than_waiting(self, current_players: int):
        """Property: PLAYING status rooms score higher than WAITING."""
        playing_room = create_mock_room(
            status=RoomStatus.PLAYING.value,
            current_players=current_players,
        )
        waiting_room = create_mock_room(
            status=RoomStatus.WAITING.value,
            current_players=current_players,
        )
        
        playing_score = calculate_room_score(playing_room)
        waiting_score = calculate_room_score(waiting_room)
        
        assert playing_score > waiting_score

    @given(
        players_a=st.integers(min_value=0, max_value=5),
        players_b=st.integers(min_value=0, max_value=5),
    )
    def test_more_players_higher_score(self, players_a: int, players_b: int):
        """Property: Rooms with more players score higher (same status)."""
        assume(players_a != players_b)
        
        room_a = create_mock_room(
            status=RoomStatus.WAITING.value,
            current_players=players_a,
        )
        room_b = create_mock_room(
            status=RoomStatus.WAITING.value,
            current_players=players_b,
        )
        
        score_a = calculate_room_score(room_a)
        score_b = calculate_room_score(room_b)
        
        if players_a > players_b:
            assert score_a > score_b
        else:
            assert score_a < score_b

    @given(
        current_players=st.integers(min_value=0, max_value=6),
        max_seats=st.integers(min_value=2, max_value=9),
    )
    def test_score_bounded(self, current_players: int, max_seats: int):
        """Property: Score is bounded within reasonable range."""
        assume(current_players <= max_seats)
        
        room = create_mock_room(
            status=RoomStatus.PLAYING.value,
            current_players=current_players,
            max_seats=max_seats,
        )
        
        score = calculate_room_score(room)
        
        # Max possible: 100 (playing) + 90 (9 players * 10) + 20 (full ratio)
        assert score <= 210


# =============================================================================
# Property Tests: Buy-in Calculation
# =============================================================================

class TestBuyInCalculationProperties:
    """Property-based tests for calculate_default_buy_in function."""

    @given(
        buy_in_min=st.integers(min_value=100, max_value=1000),
        buy_in_max=st.integers(min_value=1000, max_value=10000),
        user_balance=st.integers(min_value=100, max_value=20000),
    )
    def test_buy_in_within_bounds(
        self,
        buy_in_min: int,
        buy_in_max: int,
        user_balance: int,
    ):
        """Property: Buy-in is always within [min, max] bounds."""
        assume(buy_in_min <= buy_in_max)
        assume(user_balance >= buy_in_min)
        
        buy_in = calculate_default_buy_in(buy_in_min, buy_in_max, user_balance)
        
        assert buy_in >= buy_in_min
        assert buy_in <= buy_in_max

    @given(
        buy_in_min=st.integers(min_value=100, max_value=1000),
        buy_in_max=st.integers(min_value=1000, max_value=10000),
        user_balance=st.integers(min_value=100, max_value=20000),
    )
    def test_buy_in_never_exceeds_balance(
        self,
        buy_in_min: int,
        buy_in_max: int,
        user_balance: int,
    ):
        """Property: Buy-in never exceeds user balance."""
        assume(buy_in_min <= buy_in_max)
        assume(user_balance >= buy_in_min)
        
        buy_in = calculate_default_buy_in(buy_in_min, buy_in_max, user_balance)
        
        assert buy_in <= user_balance

    @given(
        buy_in_min=st.integers(min_value=100, max_value=1000),
        buy_in_max=st.integers(min_value=1000, max_value=10000),
        user_balance=st.integers(min_value=1, max_value=99),
    )
    def test_insufficient_balance_raises_error(
        self,
        buy_in_min: int,
        buy_in_max: int,
        user_balance: int,
    ):
        """Property: Insufficient balance raises InsufficientBalanceError."""
        assume(buy_in_min <= buy_in_max)
        assume(user_balance < buy_in_min)
        
        with pytest.raises(InsufficientBalanceError):
            calculate_default_buy_in(buy_in_min, buy_in_max, user_balance)

    @given(
        buy_in_max=st.integers(min_value=1000, max_value=10000),
    )
    def test_default_is_half_of_max(self, buy_in_max: int):
        """Property: Default buy-in is 50% of max when balance allows."""
        buy_in_min = 100
        user_balance = buy_in_max * 2  # Plenty of balance
        
        buy_in = calculate_default_buy_in(buy_in_min, buy_in_max, user_balance)
        
        expected = buy_in_max // 2
        assert buy_in == expected

    @given(
        buy_in_min=st.integers(min_value=100, max_value=500),
        buy_in_max=st.integers(min_value=1000, max_value=2000),
    )
    def test_buy_in_capped_by_balance(self, buy_in_min: int, buy_in_max: int):
        """Property: Buy-in is capped by user balance when balance < default."""
        assume(buy_in_min <= buy_in_max)
        
        # Balance between min and default (50% of max)
        default_buy_in = buy_in_max // 2
        user_balance = (buy_in_min + default_buy_in) // 2
        assume(user_balance >= buy_in_min)
        assume(user_balance < default_buy_in)
        
        buy_in = calculate_default_buy_in(buy_in_min, buy_in_max, user_balance)
        
        assert buy_in == user_balance


# =============================================================================
# Property Tests: Room Filtering by Blind Level
# =============================================================================

class TestBlindLevelFilteringProperties:
    """Property-based tests for blind level filtering."""

    @given(
        small_blind=st.integers(min_value=5, max_value=25),
    )
    def test_low_blind_level_range(self, small_blind: int):
        """Property: Low blind level includes SB 5-25."""
        level_config = BLIND_LEVELS["low"]
        
        is_in_range = level_config["min_sb"] <= small_blind <= level_config["max_sb"]
        assert is_in_range

    @given(
        small_blind=st.integers(min_value=25, max_value=100),
    )
    def test_medium_blind_level_range(self, small_blind: int):
        """Property: Medium blind level includes SB 25-100."""
        level_config = BLIND_LEVELS["medium"]
        
        is_in_range = level_config["min_sb"] <= small_blind <= level_config["max_sb"]
        assert is_in_range

    @given(
        small_blind=st.integers(min_value=100, max_value=1000),
    )
    def test_high_blind_level_range(self, small_blind: int):
        """Property: High blind level includes SB 100-1000."""
        level_config = BLIND_LEVELS["high"]
        
        is_in_range = level_config["min_sb"] <= small_blind <= level_config["max_sb"]
        assert is_in_range


# =============================================================================
# Unit Tests: Edge Cases
# =============================================================================

class TestRoomScoreEdgeCases:
    """Unit tests for edge cases in room scoring."""

    def test_empty_room_score(self):
        """Empty room has minimal score."""
        room = create_mock_room(
            status=RoomStatus.WAITING.value,
            current_players=0,
        )
        
        score = calculate_room_score(room)
        
        # WAITING (50) + 0 players + 0 ratio
        assert score == 50

    def test_full_playing_room_score(self):
        """Full playing room has maximum score."""
        room = create_mock_room(
            status=RoomStatus.PLAYING.value,
            current_players=6,
            max_seats=6,
        )
        
        score = calculate_room_score(room)
        
        # PLAYING (100) + 6 players * 10 (60) + full ratio (20)
        assert score == 180


class TestBuyInEdgeCases:
    """Unit tests for edge cases in buy-in calculation."""

    def test_exact_min_balance(self):
        """User with exactly min buy-in gets min buy-in."""
        buy_in = calculate_default_buy_in(
            buy_in_min=400,
            buy_in_max=2000,
            user_balance=400,
        )
        
        assert buy_in == 400

    def test_exact_max_balance(self):
        """User with exactly max buy-in gets default (50% of max)."""
        buy_in = calculate_default_buy_in(
            buy_in_min=400,
            buy_in_max=2000,
            user_balance=2000,
        )
        
        # Default is 50% of max = 1000
        assert buy_in == 1000

    def test_very_high_balance(self):
        """User with very high balance gets default (50% of max)."""
        buy_in = calculate_default_buy_in(
            buy_in_min=400,
            buy_in_max=2000,
            user_balance=100000,
        )
        
        # Default is 50% of max = 1000
        assert buy_in == 1000

    def test_balance_between_min_and_default(self):
        """User with balance between min and default gets their balance."""
        buy_in = calculate_default_buy_in(
            buy_in_min=400,
            buy_in_max=2000,
            user_balance=700,  # Between 400 and 1000
        )
        
        assert buy_in == 700
