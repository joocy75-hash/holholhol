"""Tests for action processing (actions.py).

This module tests ActionProcessor and StateManager classes,
covering validation, action execution, and error handling paths.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.engine.actions import (
    ActionProcessor,
    ActionResult,
    StateManager,
    ValidationResult,
)
from app.engine.core import (
    EngineError,
    InvalidActionError,
    NotYourTurnError,
    PokerKitWrapper,
)
from app.engine.state import (
    ActionRequest,
    ActionType,
    Card,
    GamePhase,
    HandState,
    Player,
    PlayerAction,
    PlayerHandState,
    PlayerHandStatus,
    PotState,
    Rank,
    SeatState,
    SeatStatus,
    Suit,
    TableConfig,
    TableState,
    ValidAction,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def table_config() -> TableConfig:
    """Create a test table configuration."""
    return TableConfig(
        max_seats=6,
        small_blind=10,
        big_blind=20,
        min_buy_in=400,
        max_buy_in=2000,
    )


@pytest.fixture
def two_player_seats() -> tuple[SeatState, ...]:
    """Create seats with 2 active players."""
    player1 = Player(user_id="user1", nickname="Player1")
    player2 = Player(user_id="user2", nickname="Player2")

    return (
        SeatState(position=0, player=player1, stack=1000, status=SeatStatus.ACTIVE),
        SeatState(position=1, player=player2, stack=1000, status=SeatStatus.ACTIVE),
        SeatState(position=2, player=None, stack=0, status=SeatStatus.EMPTY),
        SeatState(position=3, player=None, stack=0, status=SeatStatus.EMPTY),
        SeatState(position=4, player=None, stack=0, status=SeatStatus.EMPTY),
        SeatState(position=5, player=None, stack=0, status=SeatStatus.EMPTY),
    )


@pytest.fixture
def table_without_hand(table_config: TableConfig, two_player_seats) -> TableState:
    """Create a table without an active hand."""
    return TableState(
        table_id="table-1",
        config=table_config,
        seats=two_player_seats,
        hand=None,
        dealer_position=0,
        state_version=0,
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def hand_state() -> HandState:
    """Create a basic hand state at preflop."""
    return HandState(
        hand_id="hand-1",
        hand_number=1,
        phase=GamePhase.PREFLOP,
        community_cards=(),
        pot=PotState(main_pot=30, side_pots=()),
        player_states=(
            PlayerHandState(
                position=0,
                hole_cards=(Card(Rank.ACE, Suit.HEARTS), Card(Rank.KING, Suit.HEARTS)),
                bet_amount=10,
                total_bet=10,
                status=PlayerHandStatus.ACTIVE,
                last_action=None,
            ),
            PlayerHandState(
                position=1,
                hole_cards=(Card(Rank.QUEEN, Suit.SPADES), Card(Rank.JACK, Suit.SPADES)),
                bet_amount=20,
                total_bet=20,
                status=PlayerHandStatus.ACTIVE,
                last_action=None,
            ),
        ),
        current_turn=0,
        last_aggressor=None,
        min_raise=20,
        started_at=datetime.utcnow(),
    )


@pytest.fixture
def table_with_hand(
    table_config: TableConfig,
    two_player_seats,
    hand_state: HandState,
) -> TableState:
    """Create a table with an active hand."""
    return TableState(
        table_id="table-1",
        config=table_config,
        seats=two_player_seats,
        hand=hand_state,
        dealer_position=0,
        state_version=1,
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def finished_hand_state() -> HandState:
    """Create a finished hand state."""
    return HandState(
        hand_id="hand-1",
        hand_number=1,
        phase=GamePhase.FINISHED,
        community_cards=(),
        pot=PotState(main_pot=0, side_pots=()),
        player_states=(),
        current_turn=None,
        last_aggressor=None,
        min_raise=0,
        started_at=datetime.utcnow(),
    )


@pytest.fixture
def table_with_finished_hand(
    table_config: TableConfig,
    two_player_seats,
    finished_hand_state: HandState,
) -> TableState:
    """Create a table with a finished hand."""
    return TableState(
        table_id="table-1",
        config=table_config,
        seats=two_player_seats,
        hand=finished_hand_state,
        dealer_position=0,
        state_version=2,
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def mock_wrapper() -> MagicMock:
    """Create a mock PokerKitWrapper."""
    wrapper = MagicMock(spec=PokerKitWrapper)
    return wrapper


@pytest.fixture
def processor(mock_wrapper: MagicMock) -> ActionProcessor:
    """Create an ActionProcessor with mock wrapper."""
    return ActionProcessor(mock_wrapper)


# =============================================================================
# ValidationResult Tests
# =============================================================================


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_result(self):
        """Test creating a valid result."""
        result = ValidationResult(valid=True)
        assert result.valid is True
        assert result.error_code is None
        assert result.error_message is None

    def test_invalid_result_with_error(self):
        """Test creating an invalid result with error info."""
        result = ValidationResult(
            valid=False,
            error_code="TEST_ERROR",
            error_message="Test error message",
        )
        assert result.valid is False
        assert result.error_code == "TEST_ERROR"
        assert result.error_message == "Test error message"

    def test_result_immutable(self):
        """Test ValidationResult is immutable (frozen dataclass)."""
        result = ValidationResult(valid=True)
        with pytest.raises(AttributeError):
            result.valid = False


# =============================================================================
# ActionResult Tests
# =============================================================================


class TestActionResult:
    """Tests for ActionResult dataclass."""

    def test_success_result(self):
        """Test creating a success result."""
        result = ActionResult(
            success=True,
            request_id="req-1",
            state_version=5,
        )
        assert result.success is True
        assert result.request_id == "req-1"
        assert result.state_version == 5
        assert result.error_code is None

    def test_failure_result(self):
        """Test creating a failure result."""
        result = ActionResult(
            success=False,
            request_id="req-2",
            error_code="INVALID_ACTION",
            error_message="Cannot perform action",
        )
        assert result.success is False
        assert result.request_id == "req-2"
        assert result.error_code == "INVALID_ACTION"
        assert result.new_state is None


# =============================================================================
# ActionProcessor.validate_action Tests
# =============================================================================


class TestActionProcessorValidation:
    """Tests for ActionProcessor.validate_action method."""

    def test_player_not_seated(
        self,
        processor: ActionProcessor,
        table_with_hand: TableState,
    ):
        """Test validation fails when player is not seated."""
        action = ActionRequest(
            action_type=ActionType.FOLD,
            request_id="req-1",
        )

        result = processor.validate_action(
            table_with_hand,
            "unknown_user",  # Not seated
            action,
        )

        assert result.valid is False
        assert result.error_code == "PLAYER_NOT_SEATED"

    def test_invalid_seat_status_sitting_out(
        self,
        processor: ActionProcessor,
        table_config: TableConfig,
        hand_state: HandState,
    ):
        """Test validation fails when player is sitting out."""
        player1 = Player(user_id="user1", nickname="Player1")
        seats = (
            SeatState(position=0, player=player1, stack=1000, status=SeatStatus.SITTING_OUT),
            SeatState(position=1, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=2, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=3, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=4, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=5, player=None, stack=0, status=SeatStatus.EMPTY),
        )
        table = TableState(
            table_id="table-1",
            config=table_config,
            seats=seats,
            hand=hand_state,
            dealer_position=0,
            state_version=1,
            updated_at=datetime.utcnow(),
        )

        action = ActionRequest(action_type=ActionType.FOLD, request_id="req-1")
        result = processor.validate_action(table, "user1", action)

        assert result.valid is False
        assert result.error_code == "INVALID_SEAT_STATUS"

    def test_invalid_seat_status_disconnected(
        self,
        processor: ActionProcessor,
        table_config: TableConfig,
        hand_state: HandState,
    ):
        """Test validation fails when player is disconnected."""
        player1 = Player(user_id="user1", nickname="Player1")
        seats = (
            SeatState(position=0, player=player1, stack=1000, status=SeatStatus.DISCONNECTED),
            SeatState(position=1, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=2, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=3, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=4, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=5, player=None, stack=0, status=SeatStatus.EMPTY),
        )
        table = TableState(
            table_id="table-1",
            config=table_config,
            seats=seats,
            hand=hand_state,
            dealer_position=0,
            state_version=1,
            updated_at=datetime.utcnow(),
        )

        action = ActionRequest(action_type=ActionType.FOLD, request_id="req-1")
        result = processor.validate_action(table, "user1", action)

        assert result.valid is False
        assert result.error_code == "INVALID_SEAT_STATUS"

    def test_no_active_hand(
        self,
        processor: ActionProcessor,
        table_without_hand: TableState,
    ):
        """Test validation fails when no hand is active."""
        action = ActionRequest(action_type=ActionType.FOLD, request_id="req-1")
        result = processor.validate_action(table_without_hand, "user1", action)

        assert result.valid is False
        assert result.error_code == "NO_ACTIVE_HAND"

    def test_hand_finished(
        self,
        processor: ActionProcessor,
        table_with_finished_hand: TableState,
    ):
        """Test validation fails when hand has finished."""
        action = ActionRequest(action_type=ActionType.FOLD, request_id="req-1")
        result = processor.validate_action(table_with_finished_hand, "user1", action)

        assert result.valid is False
        assert result.error_code == "HAND_FINISHED"

    def test_not_your_turn(
        self,
        processor: ActionProcessor,
        table_with_hand: TableState,
        mock_wrapper: MagicMock,
    ):
        """Test validation fails when it's not the player's turn."""
        # Current turn is position 0 (user1), so user2 should fail
        action = ActionRequest(action_type=ActionType.FOLD, request_id="req-1")
        result = processor.validate_action(table_with_hand, "user2", action)

        assert result.valid is False
        assert result.error_code == "NOT_YOUR_TURN"

    def test_invalid_action_type(
        self,
        processor: ActionProcessor,
        table_with_hand: TableState,
        mock_wrapper: MagicMock,
    ):
        """Test validation fails when action type is not allowed."""
        # Mock wrapper to return only FOLD and CALL as valid
        mock_wrapper.get_valid_actions.return_value = (
            ValidAction(action_type=ActionType.FOLD),
            ValidAction(action_type=ActionType.CALL, min_amount=20, max_amount=20),
        )

        # Try to CHECK when it's not allowed
        action = ActionRequest(action_type=ActionType.CHECK, request_id="req-1")
        result = processor.validate_action(table_with_hand, "user1", action)

        assert result.valid is False
        assert result.error_code == "INVALID_ACTION_TYPE"

    def test_amount_required_for_bet(
        self,
        processor: ActionProcessor,
        table_with_hand: TableState,
        mock_wrapper: MagicMock,
    ):
        """Test validation fails when bet amount is missing."""
        mock_wrapper.get_valid_actions.return_value = (
            ValidAction(action_type=ActionType.FOLD),
            ValidAction(action_type=ActionType.BET, min_amount=20, max_amount=1000),
        )

        # BET without amount
        action = ActionRequest(action_type=ActionType.BET, request_id="req-1", amount=None)
        result = processor.validate_action(table_with_hand, "user1", action)

        assert result.valid is False
        assert result.error_code == "AMOUNT_REQUIRED"

    def test_amount_required_for_raise(
        self,
        processor: ActionProcessor,
        table_with_hand: TableState,
        mock_wrapper: MagicMock,
    ):
        """Test validation fails when raise amount is missing."""
        mock_wrapper.get_valid_actions.return_value = (
            ValidAction(action_type=ActionType.FOLD),
            ValidAction(action_type=ActionType.RAISE, min_amount=40, max_amount=1000),
        )

        # RAISE without amount
        action = ActionRequest(action_type=ActionType.RAISE, request_id="req-1", amount=None)
        result = processor.validate_action(table_with_hand, "user1", action)

        assert result.valid is False
        assert result.error_code == "AMOUNT_REQUIRED"

    def test_amount_too_low(
        self,
        processor: ActionProcessor,
        table_with_hand: TableState,
        mock_wrapper: MagicMock,
    ):
        """Test validation fails when bet amount is too low."""
        mock_wrapper.get_valid_actions.return_value = (
            ValidAction(action_type=ActionType.FOLD),
            ValidAction(action_type=ActionType.RAISE, min_amount=40, max_amount=1000),
        )

        # RAISE with amount below minimum
        action = ActionRequest(action_type=ActionType.RAISE, request_id="req-1", amount=30)
        result = processor.validate_action(table_with_hand, "user1", action)

        assert result.valid is False
        assert result.error_code == "AMOUNT_TOO_LOW"

    def test_amount_too_high(
        self,
        processor: ActionProcessor,
        table_with_hand: TableState,
        mock_wrapper: MagicMock,
    ):
        """Test validation fails when bet amount is too high."""
        mock_wrapper.get_valid_actions.return_value = (
            ValidAction(action_type=ActionType.FOLD),
            ValidAction(action_type=ActionType.BET, min_amount=20, max_amount=500),
        )

        # BET with amount above maximum
        action = ActionRequest(action_type=ActionType.BET, request_id="req-1", amount=1000)
        result = processor.validate_action(table_with_hand, "user1", action)

        assert result.valid is False
        assert result.error_code == "AMOUNT_TOO_HIGH"

    def test_valid_fold_action(
        self,
        processor: ActionProcessor,
        table_with_hand: TableState,
        mock_wrapper: MagicMock,
    ):
        """Test validation passes for valid FOLD action."""
        mock_wrapper.get_valid_actions.return_value = (
            ValidAction(action_type=ActionType.FOLD),
            ValidAction(action_type=ActionType.CALL, min_amount=20, max_amount=20),
        )

        action = ActionRequest(action_type=ActionType.FOLD, request_id="req-1")
        result = processor.validate_action(table_with_hand, "user1", action)

        assert result.valid is True
        assert result.error_code is None

    def test_valid_call_action(
        self,
        processor: ActionProcessor,
        table_with_hand: TableState,
        mock_wrapper: MagicMock,
    ):
        """Test validation passes for valid CALL action."""
        mock_wrapper.get_valid_actions.return_value = (
            ValidAction(action_type=ActionType.FOLD),
            ValidAction(action_type=ActionType.CALL, min_amount=10, max_amount=10),
        )

        action = ActionRequest(action_type=ActionType.CALL, request_id="req-1")
        result = processor.validate_action(table_with_hand, "user1", action)

        assert result.valid is True

    def test_valid_raise_action_with_correct_amount(
        self,
        processor: ActionProcessor,
        table_with_hand: TableState,
        mock_wrapper: MagicMock,
    ):
        """Test validation passes for valid RAISE with correct amount."""
        mock_wrapper.get_valid_actions.return_value = (
            ValidAction(action_type=ActionType.FOLD),
            ValidAction(action_type=ActionType.RAISE, min_amount=40, max_amount=1000),
        )

        action = ActionRequest(action_type=ActionType.RAISE, request_id="req-1", amount=100)
        result = processor.validate_action(table_with_hand, "user1", action)

        assert result.valid is True

    def test_valid_action_with_waiting_status(
        self,
        processor: ActionProcessor,
        table_config: TableConfig,
        hand_state: HandState,
        mock_wrapper: MagicMock,
    ):
        """Test validation passes when player has WAITING status."""
        player1 = Player(user_id="user1", nickname="Player1")
        player2 = Player(user_id="user2", nickname="Player2")
        seats = (
            SeatState(position=0, player=player1, stack=1000, status=SeatStatus.WAITING),
            SeatState(position=1, player=player2, stack=1000, status=SeatStatus.ACTIVE),
            SeatState(position=2, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=3, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=4, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=5, player=None, stack=0, status=SeatStatus.EMPTY),
        )
        table = TableState(
            table_id="table-1",
            config=table_config,
            seats=seats,
            hand=hand_state,
            dealer_position=0,
            state_version=1,
            updated_at=datetime.utcnow(),
        )

        mock_wrapper.get_valid_actions.return_value = (
            ValidAction(action_type=ActionType.FOLD),
        )

        action = ActionRequest(action_type=ActionType.FOLD, request_id="req-1")
        result = processor.validate_action(table, "user1", action)

        assert result.valid is True


# =============================================================================
# ActionProcessor.process_action Tests
# =============================================================================


class TestActionProcessorExecution:
    """Tests for ActionProcessor.process_action method."""

    def test_process_action_validation_failure(
        self,
        processor: ActionProcessor,
        table_without_hand: TableState,
    ):
        """Test process_action returns error when validation fails."""
        action = ActionRequest(action_type=ActionType.FOLD, request_id="req-1")
        result = processor.process_action(table_without_hand, "user1", action)

        assert result.success is False
        assert result.request_id == "req-1"
        assert result.error_code == "NO_ACTIVE_HAND"
        assert result.new_state is None

    def test_process_action_success(
        self,
        processor: ActionProcessor,
        table_with_hand: TableState,
        mock_wrapper: MagicMock,
    ):
        """Test process_action returns success with new state."""
        # Setup mock
        mock_wrapper.get_valid_actions.return_value = (
            ValidAction(action_type=ActionType.FOLD),
        )

        new_state = table_with_hand  # Simplified - in reality would be modified
        executed_action = PlayerAction(
            position=0,
            action_type=ActionType.FOLD,
            amount=0,
            timestamp=datetime.utcnow(),
        )
        mock_wrapper.apply_action.return_value = (new_state, executed_action)

        action = ActionRequest(action_type=ActionType.FOLD, request_id="req-1")
        result = processor.process_action(table_with_hand, "user1", action)

        assert result.success is True
        assert result.request_id == "req-1"
        assert result.new_state is not None
        assert result.executed_action is not None
        assert result.state_version is not None

    def test_process_action_not_your_turn_error(
        self,
        processor: ActionProcessor,
        table_with_hand: TableState,
        mock_wrapper: MagicMock,
    ):
        """Test process_action handles NotYourTurnError."""
        mock_wrapper.get_valid_actions.return_value = (
            ValidAction(action_type=ActionType.FOLD),
        )
        mock_wrapper.apply_action.side_effect = NotYourTurnError("Not your turn")

        action = ActionRequest(action_type=ActionType.FOLD, request_id="req-1")
        result = processor.process_action(table_with_hand, "user1", action)

        assert result.success is False
        assert result.error_code == "NOT_YOUR_TURN"

    def test_process_action_invalid_action_error(
        self,
        processor: ActionProcessor,
        table_with_hand: TableState,
        mock_wrapper: MagicMock,
    ):
        """Test process_action handles InvalidActionError."""
        mock_wrapper.get_valid_actions.return_value = (
            ValidAction(action_type=ActionType.FOLD),
        )
        mock_wrapper.apply_action.side_effect = InvalidActionError("Invalid action")

        action = ActionRequest(action_type=ActionType.FOLD, request_id="req-1")
        result = processor.process_action(table_with_hand, "user1", action)

        assert result.success is False
        assert result.error_code == "INVALID_ACTION"

    def test_process_action_engine_error(
        self,
        processor: ActionProcessor,
        table_with_hand: TableState,
        mock_wrapper: MagicMock,
    ):
        """Test process_action handles general EngineError."""
        mock_wrapper.get_valid_actions.return_value = (
            ValidAction(action_type=ActionType.FOLD),
        )
        mock_wrapper.apply_action.side_effect = EngineError("Engine failure")

        action = ActionRequest(action_type=ActionType.FOLD, request_id="req-1")
        result = processor.process_action(table_with_hand, "user1", action)

        assert result.success is False
        assert result.error_code == "ENGINE_ERROR"


# =============================================================================
# ActionProcessor.get_available_actions Tests
# =============================================================================


class TestGetAvailableActions:
    """Tests for ActionProcessor.get_available_actions method."""

    def test_player_not_seated_returns_empty(
        self,
        processor: ActionProcessor,
        table_with_hand: TableState,
    ):
        """Test returns empty tuple when player is not seated."""
        result = processor.get_available_actions(table_with_hand, "unknown_user")
        assert result == ()

    def test_no_active_hand_returns_empty(
        self,
        processor: ActionProcessor,
        table_without_hand: TableState,
    ):
        """Test returns empty tuple when no hand is active."""
        result = processor.get_available_actions(table_without_hand, "user1")
        assert result == ()

    def test_not_players_turn_returns_empty(
        self,
        processor: ActionProcessor,
        table_with_hand: TableState,
    ):
        """Test returns empty tuple when it's not player's turn."""
        # Current turn is position 0 (user1), so user2 should get empty
        result = processor.get_available_actions(table_with_hand, "user2")
        assert result == ()

    def test_players_turn_returns_actions(
        self,
        processor: ActionProcessor,
        table_with_hand: TableState,
        mock_wrapper: MagicMock,
    ):
        """Test returns valid actions when it's player's turn."""
        expected_actions = (
            ValidAction(action_type=ActionType.FOLD),
            ValidAction(action_type=ActionType.CALL, min_amount=10, max_amount=10),
            ValidAction(action_type=ActionType.RAISE, min_amount=40, max_amount=1000),
        )
        mock_wrapper.get_valid_actions.return_value = expected_actions

        result = processor.get_available_actions(table_with_hand, "user1")

        assert result == expected_actions
        mock_wrapper.get_valid_actions.assert_called_once_with(table_with_hand, 0)


# =============================================================================
# StateManager Tests
# =============================================================================


class TestStateManager:
    """Tests for StateManager convenience class."""

    def test_initialization(self):
        """Test StateManager initializes with wrapper and processor."""
        manager = StateManager()
        assert manager.wrapper is not None
        assert manager.processor is not None
        assert isinstance(manager.wrapper, PokerKitWrapper)
        assert isinstance(manager.processor, ActionProcessor)

    def test_start_hand(self, table_config: TableConfig, two_player_seats):
        """Test starting a new hand."""
        table = TableState(
            table_id="table-1",
            config=table_config,
            seats=two_player_seats,
            hand=None,
            dealer_position=0,
            state_version=0,
            updated_at=datetime.utcnow(),
        )

        manager = StateManager()
        new_state = manager.start_hand(table, "hand-123")

        assert new_state.hand is not None
        assert new_state.hand.hand_id == "hand-123"
        assert new_state.hand.phase == GamePhase.PREFLOP

    def test_start_hand_generates_id(self, table_config: TableConfig, two_player_seats):
        """Test start_hand generates hand_id if not provided."""
        table = TableState(
            table_id="table-1",
            config=table_config,
            seats=two_player_seats,
            hand=None,
            dealer_position=0,
            state_version=0,
            updated_at=datetime.utcnow(),
        )

        manager = StateManager()
        new_state = manager.start_hand(table)

        assert new_state.hand is not None
        assert new_state.hand.hand_id is not None
        assert len(new_state.hand.hand_id) > 0

    def test_process_action(self, table_config: TableConfig, two_player_seats):
        """Test processing an action through StateManager."""
        table = TableState(
            table_id="table-1",
            config=table_config,
            seats=two_player_seats,
            hand=None,
            dealer_position=0,
            state_version=0,
            updated_at=datetime.utcnow(),
        )

        manager = StateManager()
        table_with_hand = manager.start_hand(table)

        # Get current turn player
        current_pos = table_with_hand.hand.current_turn
        player_id = None
        for seat in table_with_hand.seats:
            if seat.position == current_pos and seat.player:
                player_id = seat.player.user_id
                break

        if player_id:
            action = ActionRequest(action_type=ActionType.FOLD, request_id="req-1")
            result = manager.process_action(table_with_hand, player_id, action)

            # The action should be processed (success depends on game state)
            assert result.request_id == "req-1"

    def test_is_hand_finished_no_hand(self, table_config: TableConfig, two_player_seats):
        """Test is_hand_finished returns True when no hand exists."""
        table = TableState(
            table_id="table-1",
            config=table_config,
            seats=two_player_seats,
            hand=None,
            dealer_position=0,
            state_version=0,
            updated_at=datetime.utcnow(),
        )

        manager = StateManager()
        # No hand = considered finished
        assert manager.is_hand_finished(table) is True

    def test_is_hand_finished_active_hand(self, table_config: TableConfig, two_player_seats):
        """Test is_hand_finished returns False for active hand."""
        table = TableState(
            table_id="table-1",
            config=table_config,
            seats=two_player_seats,
            hand=None,
            dealer_position=0,
            state_version=0,
            updated_at=datetime.utcnow(),
        )

        manager = StateManager()
        table_with_hand = manager.start_hand(table)

        # Active hand should not be finished
        assert manager.is_hand_finished(table_with_hand) is False

    def test_get_hand_result_active_hand_returns_none(
        self,
        table_config: TableConfig,
        two_player_seats,
    ):
        """Test get_hand_result returns None for active hand."""
        table = TableState(
            table_id="table-1",
            config=table_config,
            seats=two_player_seats,
            hand=None,
            dealer_position=0,
            state_version=0,
            updated_at=datetime.utcnow(),
        )

        manager = StateManager()
        table_with_hand = manager.start_hand(table)

        result = manager.get_hand_result(table_with_hand)
        assert result is None


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_validate_bet_with_no_min_max(
        self,
        processor: ActionProcessor,
        table_with_hand: TableState,
        mock_wrapper: MagicMock,
    ):
        """Test validation when ValidAction has no min/max amounts."""
        mock_wrapper.get_valid_actions.return_value = (
            ValidAction(action_type=ActionType.BET, min_amount=None, max_amount=None),
        )

        # BET with any amount should pass validation (no constraints)
        action = ActionRequest(action_type=ActionType.BET, request_id="req-1", amount=100)
        result = processor.validate_action(table_with_hand, "user1", action)

        assert result.valid is True

    def test_validate_amount_at_minimum_boundary(
        self,
        processor: ActionProcessor,
        table_with_hand: TableState,
        mock_wrapper: MagicMock,
    ):
        """Test validation passes when amount equals minimum."""
        mock_wrapper.get_valid_actions.return_value = (
            ValidAction(action_type=ActionType.RAISE, min_amount=40, max_amount=1000),
        )

        action = ActionRequest(action_type=ActionType.RAISE, request_id="req-1", amount=40)
        result = processor.validate_action(table_with_hand, "user1", action)

        assert result.valid is True

    def test_validate_amount_at_maximum_boundary(
        self,
        processor: ActionProcessor,
        table_with_hand: TableState,
        mock_wrapper: MagicMock,
    ):
        """Test validation passes when amount equals maximum."""
        mock_wrapper.get_valid_actions.return_value = (
            ValidAction(action_type=ActionType.BET, min_amount=20, max_amount=500),
        )

        action = ActionRequest(action_type=ActionType.BET, request_id="req-1", amount=500)
        result = processor.validate_action(table_with_hand, "user1", action)

        assert result.valid is True

    def test_multiple_players_same_action_type(
        self,
        processor: ActionProcessor,
        table_config: TableConfig,
        mock_wrapper: MagicMock,
    ):
        """Test validation for different players with same action."""
        player1 = Player(user_id="user1", nickname="Player1")
        player2 = Player(user_id="user2", nickname="Player2")
        player3 = Player(user_id="user3", nickname="Player3")

        seats = (
            SeatState(position=0, player=player1, stack=1000, status=SeatStatus.ACTIVE),
            SeatState(position=1, player=player2, stack=1000, status=SeatStatus.ACTIVE),
            SeatState(position=2, player=player3, stack=1000, status=SeatStatus.ACTIVE),
            SeatState(position=3, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=4, player=None, stack=0, status=SeatStatus.EMPTY),
            SeatState(position=5, player=None, stack=0, status=SeatStatus.EMPTY),
        )

        hand_state = HandState(
            hand_id="hand-1",
            hand_number=1,
            phase=GamePhase.PREFLOP,
            community_cards=(),
            pot=PotState(main_pot=30, side_pots=()),
            player_states=(),
            current_turn=1,  # It's user2's turn
            last_aggressor=None,
            min_raise=20,
            started_at=datetime.utcnow(),
        )

        table = TableState(
            table_id="table-1",
            config=table_config,
            seats=seats,
            hand=hand_state,
            dealer_position=0,
            state_version=1,
            updated_at=datetime.utcnow(),
        )

        mock_wrapper.get_valid_actions.return_value = (
            ValidAction(action_type=ActionType.FOLD),
        )

        action = ActionRequest(action_type=ActionType.FOLD, request_id="req-1")

        # user1 (position 0) - not their turn
        result1 = processor.validate_action(table, "user1", action)
        assert result1.valid is False
        assert result1.error_code == "NOT_YOUR_TURN"

        # user2 (position 1) - their turn
        result2 = processor.validate_action(table, "user2", action)
        assert result2.valid is True

        # user3 (position 2) - not their turn
        result3 = processor.validate_action(table, "user3", action)
        assert result3.valid is False
        assert result3.error_code == "NOT_YOUR_TURN"
