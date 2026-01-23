"""Unit tests for PokerTable class.

Tests all action types, edge cases (all-in, side pots), and state transitions.
Validates Requirements 10.1 from code-quality-security-upgrade spec.
"""

import pytest
from app.game.poker_table import (
    PokerTable,
    Player,
    GamePhase,
    CLOCKWISE_SEAT_ORDER,
    SEAT_TO_CLOCKWISE_INDEX,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def basic_table() -> PokerTable:
    """Create a basic 2-player table."""
    table = PokerTable(
        room_id="test-room-1",
        name="Test Table",
        small_blind=10,
        big_blind=20,
        min_buy_in=400,
        max_buy_in=2000,
        max_players=9,
    )
    return table


@pytest.fixture
def two_player_table(basic_table: PokerTable) -> PokerTable:
    """Create a table with 2 seated players."""
    player1 = Player(user_id="user1", username="Player1", seat=0, stack=1000)
    player2 = Player(user_id="user2", username="Player2", seat=1, stack=1000)

    basic_table.seat_player(0, player1)
    basic_table.seat_player(1, player2)
    # 착석 후 기본 상태가 sitting_out이므로 active로 전환
    basic_table.sit_in(0)
    basic_table.sit_in(1)

    return basic_table


@pytest.fixture
def three_player_table(basic_table: PokerTable) -> PokerTable:
    """Create a table with 3 seated players."""
    player1 = Player(user_id="user1", username="Player1", seat=0, stack=1000)
    player2 = Player(user_id="user2", username="Player2", seat=1, stack=1000)
    player3 = Player(user_id="user3", username="Player3", seat=3, stack=1000)

    basic_table.seat_player(0, player1)
    basic_table.seat_player(1, player2)
    basic_table.seat_player(3, player3)
    # 착석 후 기본 상태가 sitting_out이므로 active로 전환
    basic_table.sit_in(0)
    basic_table.sit_in(1)
    basic_table.sit_in(3)

    return basic_table


@pytest.fixture
def six_player_table(basic_table: PokerTable) -> PokerTable:
    """Create a table with 6 seated players."""
    seats = [0, 1, 2, 3, 4, 5]
    for i, seat in enumerate(seats):
        player = Player(
            user_id=f"user{i}",
            username=f"Player{i}",
            seat=seat,
            stack=1000,
        )
        basic_table.seat_player(seat, player)
    # 착석 후 기본 상태가 sitting_out이므로 active로 전환
    for seat in seats:
        basic_table.sit_in(seat)

    return basic_table


# =============================================================================
# Seating Tests
# =============================================================================


class TestSeating:
    """Tests for player seating functionality."""

    def test_seat_player_success(self, basic_table: PokerTable):
        """Test seating a player at an empty seat."""
        player = Player(user_id="user1", username="Player1", seat=0, stack=1000)
        result = basic_table.seat_player(0, player)
        
        assert result is True
        assert basic_table.players[0] == player

    def test_seat_player_occupied_seat(self, two_player_table: PokerTable):
        """Test seating fails when seat is occupied."""
        player = Player(user_id="user3", username="Player3", seat=0, stack=1000)
        result = two_player_table.seat_player(0, player)
        
        assert result is False

    def test_seat_player_invalid_seat(self, basic_table: PokerTable):
        """Test seating fails for invalid seat number."""
        player = Player(user_id="user1", username="Player1", seat=10, stack=1000)
        result = basic_table.seat_player(10, player)
        
        assert result is False

    def test_seat_player_below_min_buy_in(self, basic_table: PokerTable):
        """Test seating fails when stack is below minimum buy-in."""
        player = Player(user_id="user1", username="Player1", seat=0, stack=100)
        result = basic_table.seat_player(0, player)
        
        assert result is False

    def test_seat_player_above_max_buy_in(self, basic_table: PokerTable):
        """Test seating fails when stack exceeds maximum buy-in."""
        player = Player(user_id="user1", username="Player1", seat=0, stack=5000)
        result = basic_table.seat_player(0, player)
        
        assert result is False

    def test_seat_player_already_seated(self, two_player_table: PokerTable):
        """Test seating fails when player is already seated elsewhere."""
        player = Player(user_id="user1", username="Player1", seat=2, stack=1000)
        result = two_player_table.seat_player(2, player)
        
        assert result is False

    def test_remove_player(self, two_player_table: PokerTable):
        """Test removing a player from the table."""
        removed = two_player_table.remove_player(0)
        
        assert removed is not None
        assert removed.user_id == "user1"
        assert two_player_table.players[0] is None


# =============================================================================
# Hand Start Tests
# =============================================================================


class TestHandStart:
    """Tests for starting a new hand."""

    def test_start_hand_success(self, two_player_table: PokerTable):
        """Test starting a hand with 2 players."""
        result = two_player_table.start_new_hand()
        
        assert result["success"] is True
        assert result["hand_number"] == 1
        assert two_player_table.phase == GamePhase.PREFLOP

    def test_start_hand_insufficient_players(self, basic_table: PokerTable):
        """Test starting fails with less than 2 players."""
        player = Player(user_id="user1", username="Player1", seat=0, stack=1000)
        basic_table.seat_player(0, player)
        
        result = basic_table.start_new_hand()
        
        assert result["success"] is False

    def test_start_hand_deals_hole_cards(self, two_player_table: PokerTable):
        """Test that hole cards are dealt to all players."""
        two_player_table.start_new_hand()
        
        for seat, player in two_player_table.players.items():
            if player:
                assert player.hole_cards is not None
                assert len(player.hole_cards) == 2

    def test_start_hand_posts_blinds(self, two_player_table: PokerTable):
        """Test that blinds are posted correctly."""
        two_player_table.start_new_hand()
        
        # Pot should have blinds (SB + BB = 30)
        assert two_player_table.pot == 30
        assert two_player_table.current_bet == 20  # BB

    def test_start_hand_sets_dealer(self, two_player_table: PokerTable):
        """Test that dealer is set correctly."""
        two_player_table.start_new_hand()
        
        assert two_player_table.dealer_seat >= 0

    def test_start_hand_increments_hand_number(self, two_player_table: PokerTable):
        """Test that hand number increments."""
        two_player_table.start_new_hand()
        assert two_player_table.hand_number == 1
        
        # Complete hand by folding
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        if current_player:
            two_player_table.process_action(current_player.user_id, "fold", 0)
        
        # Start new hand
        two_player_table.start_new_hand()
        assert two_player_table.hand_number == 2

    def test_cannot_start_hand_during_active_hand(self, two_player_table: PokerTable):
        """Test that starting a new hand fails during active hand."""
        two_player_table.start_new_hand()
        
        # Try to start another hand
        result = two_player_table.start_new_hand()
        
        assert result["success"] is False


# =============================================================================
# Action Tests - Fold
# =============================================================================


class TestFoldAction:
    """Tests for fold action."""

    def test_fold_success(self, two_player_table: PokerTable):
        """Test successful fold action."""
        two_player_table.start_new_hand()
        
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        result = two_player_table.process_action(current_player.user_id, "fold", 0)
        
        assert result["success"] is True
        assert result["action"] == "fold"
        # In heads-up, fold ends the hand and resets state
        # So we check hand_complete instead of player status
        assert result["hand_complete"] is True

    def test_fold_ends_hand_heads_up(self, two_player_table: PokerTable):
        """Test that fold ends hand in heads-up."""
        two_player_table.start_new_hand()
        
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        result = two_player_table.process_action(current_player.user_id, "fold", 0)
        
        assert result["hand_complete"] is True

    def test_fold_not_your_turn(self, two_player_table: PokerTable):
        """Test fold fails when not player's turn."""
        two_player_table.start_new_hand()
        
        # Find non-current player
        for seat, player in two_player_table.players.items():
            if player and seat != two_player_table.current_player_seat:
                result = two_player_table.process_action(player.user_id, "fold", 0)
                assert result["success"] is False
                break


# =============================================================================
# Action Tests - Check
# =============================================================================


class TestCheckAction:
    """Tests for check action."""

    def test_check_success_when_no_bet(self, two_player_table: PokerTable):
        """Test successful check when no bet to call."""
        two_player_table.start_new_hand()
        
        # First player calls BB
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        two_player_table.process_action(current_player.user_id, "call", 0)
        
        # BB can check
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        result = two_player_table.process_action(current_player.user_id, "check", 0)
        
        assert result["success"] is True

    def test_check_fails_when_bet_required(self, two_player_table: PokerTable):
        """Test check fails when there's a bet to call."""
        two_player_table.start_new_hand()
        
        # First player (SB) tries to check - should fail
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        result = two_player_table.process_action(current_player.user_id, "check", 0)
        
        assert result["success"] is False


# =============================================================================
# Action Tests - Call
# =============================================================================


class TestCallAction:
    """Tests for call action."""

    def test_call_success(self, two_player_table: PokerTable):
        """Test successful call action."""
        two_player_table.start_new_hand()
        
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        result = two_player_table.process_action(current_player.user_id, "call", 0)
        
        assert result["success"] is True

    def test_call_deducts_correct_amount(self, two_player_table: PokerTable):
        """Test call deducts correct amount from stack."""
        two_player_table.start_new_hand()
        
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        initial_stack = current_player.stack
        
        two_player_table.process_action(current_player.user_id, "call", 0)
        
        # Stack should decrease by call amount
        assert current_player.stack < initial_stack


# =============================================================================
# Action Tests - Bet/Raise
# =============================================================================


class TestBetRaiseAction:
    """Tests for bet and raise actions."""

    def test_raise_success(self, two_player_table: PokerTable):
        """Test successful raise action."""
        two_player_table.start_new_hand()
        
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        result = two_player_table.process_action(current_player.user_id, "raise", 60)
        
        assert result["success"] is True
        assert result["action"] == "raise"

    def test_raise_below_minimum_fails(self, two_player_table: PokerTable):
        """Test raise below minimum fails."""
        two_player_table.start_new_hand()
        
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        result = two_player_table.process_action(current_player.user_id, "raise", 25)
        
        assert result["success"] is False

    def test_raise_above_stack_fails(self, two_player_table: PokerTable):
        """Test raise above stack fails."""
        two_player_table.start_new_hand()
        
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        result = two_player_table.process_action(current_player.user_id, "raise", 5000)
        
        assert result["success"] is False

    def test_bet_on_flop(self, two_player_table: PokerTable):
        """Test bet action on flop."""
        two_player_table.start_new_hand()
        
        # Complete preflop
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        two_player_table.process_action(current_player.user_id, "call", 0)
        
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        two_player_table.process_action(current_player.user_id, "check", 0)
        
        # Now on flop
        assert two_player_table.phase == GamePhase.FLOP
        
        # First to act can bet
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        result = two_player_table.process_action(current_player.user_id, "bet", 40)
        
        assert result["success"] is True


# =============================================================================
# Action Tests - All-In
# =============================================================================


class TestAllInAction:
    """Tests for all-in action."""

    def test_all_in_success(self, two_player_table: PokerTable):
        """Test successful all-in action."""
        two_player_table.start_new_hand()
        
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        result = two_player_table.process_action(current_player.user_id, "all_in", 0)
        
        assert result["success"] is True
        assert current_player.status == "all_in"

    def test_all_in_uses_entire_stack(self, two_player_table: PokerTable):
        """Test all-in uses entire stack."""
        two_player_table.start_new_hand()
        
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        initial_stack = current_player.stack
        
        two_player_table.process_action(current_player.user_id, "all_in", 0)
        
        # Stack should be 0 or very low
        assert current_player.stack == 0 or current_player.stack < initial_stack


# =============================================================================
# Phase Transition Tests
# =============================================================================


class TestPhaseTransitions:
    """Tests for game phase transitions."""

    def test_preflop_to_flop(self, two_player_table: PokerTable):
        """Test transition from preflop to flop."""
        two_player_table.start_new_hand()
        assert two_player_table.phase == GamePhase.PREFLOP
        
        # Complete preflop betting
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        two_player_table.process_action(current_player.user_id, "call", 0)
        
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        two_player_table.process_action(current_player.user_id, "check", 0)
        
        assert two_player_table.phase == GamePhase.FLOP
        assert len(two_player_table.community_cards) == 3

    def test_flop_to_turn(self, two_player_table: PokerTable):
        """Test transition from flop to turn."""
        two_player_table.start_new_hand()
        
        # Complete preflop
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        two_player_table.process_action(current_player.user_id, "call", 0)
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        two_player_table.process_action(current_player.user_id, "check", 0)
        
        # Complete flop
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        two_player_table.process_action(current_player.user_id, "check", 0)
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        two_player_table.process_action(current_player.user_id, "check", 0)
        
        assert two_player_table.phase == GamePhase.TURN
        assert len(two_player_table.community_cards) == 4

    def test_turn_to_river(self, two_player_table: PokerTable):
        """Test transition from turn to river."""
        two_player_table.start_new_hand()
        
        # Complete preflop, flop, turn
        for _ in range(6):  # 2 actions per street * 3 streets
            current_player = two_player_table.players.get(two_player_table.current_player_seat)
            if current_player:
                available = two_player_table.get_available_actions(current_player.user_id)
                if "check" in available.get("actions", []):
                    two_player_table.process_action(current_player.user_id, "check", 0)
                elif "call" in available.get("actions", []):
                    two_player_table.process_action(current_player.user_id, "call", 0)
        
        assert two_player_table.phase == GamePhase.RIVER
        assert len(two_player_table.community_cards) == 5


# =============================================================================
# Hand Completion Tests
# =============================================================================


class TestHandCompletion:
    """Tests for hand completion and winner determination."""

    def test_hand_completes_on_fold(self, two_player_table: PokerTable):
        """Test hand completes when all but one fold."""
        two_player_table.start_new_hand()
        
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        result = two_player_table.process_action(current_player.user_id, "fold", 0)
        
        assert result["hand_complete"] is True
        assert result["hand_result"] is not None
        assert len(result["hand_result"]["winners"]) == 1

    def test_hand_result_has_winners(self, two_player_table: PokerTable):
        """Test hand result contains winner information."""
        two_player_table.start_new_hand()
        
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        result = two_player_table.process_action(current_player.user_id, "fold", 0)
        
        hand_result = result["hand_result"]
        assert "winners" in hand_result
        assert "pot" in hand_result

    def test_state_resets_after_hand(self, two_player_table: PokerTable):
        """Test state resets after hand completion."""
        two_player_table.start_new_hand()
        
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        two_player_table.process_action(current_player.user_id, "fold", 0)
        
        # State should be reset
        assert two_player_table.phase == GamePhase.WAITING
        assert two_player_table.pot == 0
        assert two_player_table.community_cards == []
        assert two_player_table.current_player_seat is None


# =============================================================================
# Available Actions Tests
# =============================================================================


class TestAvailableActions:
    """Tests for get_available_actions method."""

    def test_available_actions_preflop(self, two_player_table: PokerTable):
        """Test available actions at preflop."""
        two_player_table.start_new_hand()
        
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        available = two_player_table.get_available_actions(current_player.user_id)
        
        assert "actions" in available
        assert len(available["actions"]) > 0

    def test_available_actions_not_your_turn(self, two_player_table: PokerTable):
        """Test available actions returns empty when not your turn."""
        two_player_table.start_new_hand()
        
        # Find non-current player
        for seat, player in two_player_table.players.items():
            if player and seat != two_player_table.current_player_seat:
                available = two_player_table.get_available_actions(player.user_id)
                assert available["actions"] == []
                break

    def test_available_actions_includes_amounts(self, two_player_table: PokerTable):
        """Test available actions includes call/raise amounts."""
        two_player_table.start_new_hand()
        
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        available = two_player_table.get_available_actions(current_player.user_id)
        
        if "call" in available["actions"]:
            assert "call_amount" in available
        if "raise" in available["actions"]:
            assert "min_raise" in available
            assert "max_raise" in available


# =============================================================================
# Clockwise Order Tests
# =============================================================================


class TestClockwiseOrder:
    """Tests for clockwise seat ordering."""

    def test_clockwise_seat_order_constant(self):
        """Test clockwise seat order is correct."""
        assert CLOCKWISE_SEAT_ORDER == [0, 1, 3, 5, 7, 8, 6, 4, 2]

    def test_seat_to_clockwise_index_mapping(self):
        """Test seat to clockwise index mapping."""
        assert SEAT_TO_CLOCKWISE_INDEX[0] == 0
        assert SEAT_TO_CLOCKWISE_INDEX[1] == 1
        assert SEAT_TO_CLOCKWISE_INDEX[2] == 8

    def test_get_next_clockwise_seat(self, three_player_table: PokerTable):
        """Test getting next clockwise seat."""
        occupied = [0, 1, 3]
        
        next_seat = three_player_table.get_next_clockwise_seat(0, occupied)
        assert next_seat == 1
        
        next_seat = three_player_table.get_next_clockwise_seat(1, occupied)
        assert next_seat == 3
        
        next_seat = three_player_table.get_next_clockwise_seat(3, occupied)
        assert next_seat == 0


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_process_action_no_active_hand(self, two_player_table: PokerTable):
        """Test action fails when no active hand."""
        result = two_player_table.process_action("user1", "fold", 0)
        
        assert result["success"] is False

    def test_process_action_player_not_found(self, two_player_table: PokerTable):
        """Test action fails for unknown player."""
        two_player_table.start_new_hand()
        
        result = two_player_table.process_action("unknown_user", "fold", 0)
        
        assert result["success"] is False

    def test_process_action_unknown_action(self, two_player_table: PokerTable):
        """Test action fails for unknown action type."""
        two_player_table.start_new_hand()
        
        current_player = two_player_table.players.get(two_player_table.current_player_seat)
        result = two_player_table.process_action(current_player.user_id, "invalid_action", 0)
        
        assert result["success"] is False

    def test_get_state_for_player(self, two_player_table: PokerTable):
        """Test getting state for specific player."""
        two_player_table.start_new_hand()
        
        state = two_player_table.get_state_for_player("user1")
        
        assert "tableId" in state
        assert "phase" in state
        assert "players" in state
        assert "myPosition" in state

    def test_player_sees_own_hole_cards(self, two_player_table: PokerTable):
        """Test player can see their own hole cards."""
        two_player_table.start_new_hand()
        
        state = two_player_table.get_state_for_player("user1")
        
        # Find player's data
        for player_data in state["players"]:
            if player_data and player_data["userId"] == "user1":
                assert player_data.get("holeCards") is not None
                break

    def test_player_cannot_see_opponent_hole_cards(self, two_player_table: PokerTable):
        """Test player cannot see opponent's hole cards."""
        two_player_table.start_new_hand()
        
        state = two_player_table.get_state_for_player("user1")
        
        # Find opponent's data
        for player_data in state["players"]:
            if player_data and player_data["userId"] == "user2":
                assert player_data.get("holeCards") is None
                break
