"""Tests for sit out/sit in functionality."""

import pytest
from app.game.poker_table import PokerTable, Player, GamePhase


@pytest.fixture
def table():
    """Create a basic poker table for testing."""
    return PokerTable(
        room_id="test-room",
        name="Test Table",
        small_blind=10,
        big_blind=20,
        min_buy_in=100,
        max_buy_in=1000,
        max_players=9,
    )


@pytest.fixture
def seated_table(table):
    """Create a table with 3 players seated and active."""
    players = [
        Player(user_id="user1", username="Player1", seat=0, stack=500),
        Player(user_id="user2", username="Player2", seat=1, stack=500),
        Player(user_id="user3", username="Player3", seat=2, stack=500),
    ]
    for p in players:
        table.seat_player(p.seat, p)
        table.sit_in(p.seat)
    return table


class TestSitOut:
    """Tests for sit_out functionality."""

    def test_sit_out_success(self, seated_table):
        """Test that a player can sit out successfully."""
        result = seated_table.sit_out(0)
        assert result is True
        assert seated_table.players[0].status == "sitting_out"

    def test_sit_out_empty_seat(self, table):
        """Test that sitting out from empty seat returns False."""
        result = table.sit_out(0)
        assert result is False

    def test_sit_out_already_sitting_out(self, seated_table):
        """Test that sitting out when already sitting out returns False."""
        seated_table.sit_out(0)
        result = seated_table.sit_out(0)
        assert result is False

    def test_sit_out_player_excluded_from_active(self, seated_table):
        """Test that sitting out player is excluded from active players."""
        initial_active = len(seated_table.get_active_players())
        seated_table.sit_out(0)
        assert len(seated_table.get_active_players()) == initial_active - 1

    def test_sit_out_player_excluded_from_seated(self, seated_table):
        """Test that sitting out player is excluded from seated players."""
        initial_seated = len(seated_table.get_seated_players())
        seated_table.sit_out(0)
        assert len(seated_table.get_seated_players()) == initial_seated - 1


class TestSitIn:
    """Tests for sit_in functionality."""

    def test_sit_in_success(self, seated_table):
        """Test that a sitting out player can sit back in."""
        seated_table.sit_out(0)
        result = seated_table.sit_in(0)
        assert result is True
        assert seated_table.players[0].status == "active"

    def test_sit_in_empty_seat(self, table):
        """Test that sitting in from empty seat returns False."""
        result = table.sit_in(0)
        assert result is False

    def test_sit_in_not_sitting_out(self, seated_table):
        """Test that sitting in when not sitting out returns False."""
        result = seated_table.sit_in(0)
        assert result is False

    def test_sit_in_player_included_in_active(self, seated_table):
        """Test that sitting in player is included in active players."""
        seated_table.sit_out(0)
        initial_active = len(seated_table.get_active_players())
        seated_table.sit_in(0)
        assert len(seated_table.get_active_players()) == initial_active + 1


class TestIsSittingOut:
    """Tests for is_sitting_out functionality."""

    def test_is_sitting_out_true(self, seated_table):
        """Test is_sitting_out returns True for sitting out player."""
        seated_table.sit_out(0)
        assert seated_table.is_sitting_out(0) is True

    def test_is_sitting_out_false_active(self, seated_table):
        """Test is_sitting_out returns False for active player."""
        assert seated_table.is_sitting_out(0) is False

    def test_is_sitting_out_false_empty(self, table):
        """Test is_sitting_out returns False for empty seat."""
        assert table.is_sitting_out(0) is False


class TestSitOutGameInteraction:
    """Tests for sit out interaction with game mechanics."""

    def test_cannot_start_hand_with_only_sitting_out_players(self, seated_table):
        """Test that hand cannot start if all but one player is sitting out."""
        seated_table.sit_out(0)
        seated_table.sit_out(1)
        # Only player 2 is active, need at least 2 to start
        assert seated_table.can_start_hand() is False

    def test_can_start_hand_with_enough_active_players(self, seated_table):
        """Test that hand can start with enough active players."""
        seated_table.sit_out(0)
        # Players 1 and 2 are still active
        assert seated_table.can_start_hand() is True

    def test_sitting_out_player_not_dealt_cards(self, seated_table):
        """Test that sitting out player is not dealt cards in new hand.

        Note: BB 위치의 sitting_out 플레이어는 자동 활성화되므로,
        BB가 아닌 위치의 플레이어를 테스트합니다.
        """
        # 좌석 0, 1, 2 중 딜러가 1이면 SB=2, BB=0
        # 그러므로 1을 sit_out하면 BB가 아니므로 카드를 받지 않음
        seated_table.sit_out(1)
        result = seated_table.start_new_hand()
        assert result["success"] is True

        # Player 1 is sitting out and NOT at BB, should not have hole cards
        assert seated_table.players[1].hole_cards is None
        assert seated_table.players[1].status == "sitting_out"

        # Players 0 and 2 should have hole cards (they are active)
        assert seated_table.players[0].hole_cards is not None
        assert seated_table.players[2].hole_cards is not None
