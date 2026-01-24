"""PokerKit wrapper for game engine.

This module wraps the PokerKit library to provide:
- Immutable state semantics (mutable PokerKit state -> immutable snapshots)
- Clean interface for the application layer
- State serialization/deserialization with HMAC integrity verification

Security Notes:
- pickle is required for PokerKit state serialization (complex object graph not JSON-serializable)
- HMAC-SHA256 signature verifies data integrity before deserialization
- Only server-generated snapshots are deserialized (never external input)
- Tampering detection prevents RCE attacks via malicious pickle payloads
"""

import hashlib
import hmac
import logging
import pickle  # noqa: S301 - Required for PokerKit State; secured with HMAC verification
import uuid

from app.config import get_settings

logger = logging.getLogger(__name__)
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from pokerkit import Automation, NoLimitTexasHoldem
from pokerkit.state import State as PKState
from pokerkit.utilities import Card as PKCard

from app.engine.state import (
    ActionRequest,
    ActionType,
    Card,
    GamePhase,
    HandRank,
    HandResult,
    HandState,
    PlayerAction,
    PlayerHandState,
    PlayerHandStatus,
    PotState,
    Rank,
    SeatState,
    ShowdownHand,
    SidePot,
    Suit,
    TableState,
    ValidAction,
    WinnerInfo,
)


# =============================================================================
# Exceptions
# =============================================================================


class EngineError(Exception):
    """Base engine error."""


class InvalidActionError(EngineError):
    """Action not valid in current state."""


class NotYourTurnError(EngineError):
    """Action attempted out of turn."""


class InsufficientStackError(EngineError):
    """Not enough chips for the action."""


class GameStateError(EngineError):
    """Internal game state error."""


# =============================================================================
# Card Mapping
# =============================================================================

# PokerKit rank mapping (PokerKit uses '?' for unknown)
PK_RANK_MAP: dict[str, Rank] = {
    "2": Rank.TWO,
    "3": Rank.THREE,
    "4": Rank.FOUR,
    "5": Rank.FIVE,
    "6": Rank.SIX,
    "7": Rank.SEVEN,
    "8": Rank.EIGHT,
    "9": Rank.NINE,
    "T": Rank.TEN,
    "J": Rank.JACK,
    "Q": Rank.QUEEN,
    "K": Rank.KING,
    "A": Rank.ACE,
}

# PokerKit suit mapping
PK_SUIT_MAP: dict[str, Suit] = {
    "c": Suit.CLUBS,
    "d": Suit.DIAMONDS,
    "h": Suit.HEARTS,
    "s": Suit.SPADES,
}

# Reverse mapping for our Card to PokerKit
RANK_TO_PK: dict[Rank, str] = {v: k for k, v in PK_RANK_MAP.items()}
SUIT_TO_PK: dict[Suit, str] = {v: k for k, v in PK_SUIT_MAP.items()}


def pk_card_to_card(pk_card: PKCard) -> Card:
    """Convert PokerKit card to our Card model."""
    # PokerKit Card has rank and suit as strings
    rank_str = pk_card.rank
    suit_str = pk_card.suit

    return Card(
        rank=PK_RANK_MAP[rank_str],
        suit=PK_SUIT_MAP[suit_str],
    )


def card_to_pk_string(card: Card) -> str:
    """Convert our Card to PokerKit string format."""
    return f"{RANK_TO_PK[card.rank]}{SUIT_TO_PK[card.suit]}"


# =============================================================================
# PokerKit Wrapper
# =============================================================================


class PokerKitWrapper:
    """Wraps PokerKit library to provide immutable state semantics.

    Key Responsibilities:
    1. Create PokerKit game states from our TableConfig
    2. Apply actions and return new immutable TableState
    3. Query valid actions for current player
    4. Evaluate hand results at showdown
    """

    def __init__(self) -> None:
        """Initialize wrapper (stateless)."""
        pass

    # =========================================================================
    # State Creation
    # =========================================================================

    def create_initial_hand(
        self,
        table_state: TableState,
        hand_id: str | None = None,
        hand_number: int | None = None,
    ) -> TableState:
        """Create a new hand state within table.

        Args:
            table_state: Current table state
            hand_id: Unique hand identifier (generated if not provided)
            hand_number: Sequential hand number (incremented if not provided)

        Returns:
            New TableState with HandState initialized

        Raises:
            ValueError: If not enough active players
        """
        if hand_id is None:
            hand_id = str(uuid.uuid4())
        if hand_number is None:
            hand_number = table_state.hand.hand_number + 1 if table_state.hand else 1

        # Get active players
        active_seats = list(table_state.get_active_seats())

        if len(active_seats) < 2:
            raise ValueError("Need at least 2 active players to start a hand")

        # Sort by position for consistent ordering
        active_seats.sort(key=lambda s: s.position)

        # Build starting stacks
        starting_stacks = tuple(seat.stack for seat in active_seats)
        player_count = len(active_seats)

        # Create PokerKit state with automations
        # PokerKit 0.7.2 API changes:
        # - Uses raw_blinds_or_straddles instead of blinds_or_straddles
        # - dealer_index parameter removed (PokerKit handles dealer internally)
        # - CARD_BURNING required for proper board dealing sequence
        # - HAND_KILLING required for mucking/showing at showdown
        pk_state = NoLimitTexasHoldem.create_state(
            automations=(
                Automation.ANTE_POSTING,
                Automation.BET_COLLECTION,
                Automation.BLIND_OR_STRADDLE_POSTING,
                Automation.CARD_BURNING,
                Automation.HOLE_DEALING,
                Automation.BOARD_DEALING,
                Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
                Automation.HAND_KILLING,
                Automation.CHIPS_PUSHING,
                Automation.CHIPS_PULLING,
            ),
            ante_trimming_status=True,
            raw_antes={-1: table_state.config.ante},  # -1 means everyone
            raw_blinds_or_straddles=(
                table_state.config.small_blind,
                table_state.config.big_blind,
            ),
            min_bet=table_state.config.big_blind,
            raw_starting_stacks=starting_stacks,
            player_count=player_count,
        )

        # Extract initial hand state
        hand_state = self._extract_hand_state(
            pk_state=pk_state,
            hand_id=hand_id,
            hand_number=hand_number,
            active_seats=active_seats,
            started_at=datetime.now(timezone.utc),
        )

        # Serialize PokerKit state (internal server use only)
        pk_snapshot = self._serialize_pk_state(pk_state)

        # Create new table state
        return replace(
            table_state,
            hand=hand_state,
            state_version=table_state.state_version + 1,
            updated_at=datetime.now(timezone.utc),
            _pk_snapshot=pk_snapshot,
        )

    # =========================================================================
    # Action Processing
    # =========================================================================

    def apply_action(
        self,
        table_state: TableState,
        position: int,
        action: ActionRequest,
    ) -> tuple[TableState, PlayerAction]:
        """Apply player action and return new state.

        Args:
            table_state: Current table state
            position: Player seat position
            action: Requested action

        Returns:
            (new_table_state, executed_action)

        Raises:
            InvalidActionError: Action not valid
            NotYourTurnError: Not player's turn
        """
        if table_state.hand is None:
            raise InvalidActionError("No active hand")

        if table_state._pk_snapshot is None:
            raise GameStateError("No PokerKit state snapshot")

        # Restore PokerKit state (from our own serialized data)
        pk_state = self._deserialize_pk_state(table_state._pk_snapshot)

        # Get active seats for position mapping
        active_seats = list(table_state.get_active_seats())
        active_seats.sort(key=lambda s: s.position)

        # Map position to PokerKit player index
        pk_index = self._position_to_pk_index(position, active_seats)

        # Validate turn
        if pk_state.actor_index is None:
            raise InvalidActionError("No player to act")
        if pk_state.actor_index != pk_index:
            raise NotYourTurnError(
                f"Not your turn (current actor: seat {active_seats[pk_state.actor_index].position})"
            )

        # Execute action (mutates pk_state)
        # Returns (amount, actual_action_type) - action type may differ from request
        # e.g., FOLD -> CHECK when no bet to face, CALL -> CHECK when amount is 0
        executed_amount, actual_action_type = self._execute_pk_action(pk_state, action)

        # Create action record with actual executed action type
        player_action = PlayerAction(
            position=position,
            action_type=actual_action_type,
            amount=executed_amount,
            timestamp=datetime.now(timezone.utc),
        )

        # Extract new hand state
        new_hand = self._extract_hand_state(
            pk_state=pk_state,
            hand_id=table_state.hand.hand_id,
            hand_number=table_state.hand.hand_number,
            active_seats=active_seats,
            started_at=table_state.hand.started_at,
        )

        # Create new table state
        new_table = replace(
            table_state,
            hand=new_hand,
            state_version=table_state.state_version + 1,
            updated_at=datetime.now(timezone.utc),
            _pk_snapshot=self._serialize_pk_state(pk_state),
        )

        return new_table, player_action

    # =========================================================================
    # Valid Actions Query
    # =========================================================================

    def get_valid_actions(
        self,
        table_state: TableState,
        position: int,
    ) -> tuple[ValidAction, ...]:
        """Get valid actions for player at position.

        Args:
            table_state: Current table state
            position: Player seat position

        Returns:
            Tuple of ValidAction objects (empty if not player's turn)
        """
        if table_state.hand is None or table_state._pk_snapshot is None:
            return ()

        pk_state = self._deserialize_pk_state(table_state._pk_snapshot)

        if pk_state.actor_index is None:
            return ()

        # Map position to PK index
        active_seats = list(table_state.get_active_seats())
        active_seats.sort(key=lambda s: s.position)

        try:
            pk_index = self._position_to_pk_index(position, active_seats)
        except ValueError:
            return ()

        if pk_state.actor_index != pk_index:
            return ()

        valid = []

        # Check fold
        if pk_state.can_fold():
            valid.append(ValidAction(action_type=ActionType.FOLD))

        # Check/Call
        if pk_state.can_check_or_call():
            call_amount = pk_state.checking_or_calling_amount or 0
            if call_amount == 0:
                valid.append(
                    ValidAction(
                        action_type=ActionType.CHECK,
                        min_amount=0,
                        max_amount=0,
                    )
                )
            else:
                valid.append(
                    ValidAction(
                        action_type=ActionType.CALL,
                        min_amount=call_amount,
                        max_amount=call_amount,
                    )
                )

        # Bet/Raise
        min_raise = pk_state.min_completion_betting_or_raising_to_amount
        max_raise = pk_state.max_completion_betting_or_raising_to_amount

        if min_raise is not None and max_raise is not None:
            if pk_state.can_complete_bet_or_raise_to(min_raise):
                # Determine if this is a bet or raise
                # It's a bet if there's no outstanding bet to call
                current_bet = (
                    pk_state.bets[pk_index] if pk_index < len(pk_state.bets) else 0
                )
                max_bet_at_table = max(pk_state.bets) if pk_state.bets else 0

                if max_bet_at_table == current_bet:
                    # No one has bet more, this would be a bet
                    valid.append(
                        ValidAction(
                            action_type=ActionType.BET,
                            min_amount=min_raise,
                            max_amount=max_raise,
                        )
                    )
                else:
                    # Someone has bet more, this is a raise
                    valid.append(
                        ValidAction(
                            action_type=ActionType.RAISE,
                            min_amount=min_raise,
                            max_amount=max_raise,
                        )
                    )

                # All-in is always an option if we can bet/raise
                valid.append(
                    ValidAction(
                        action_type=ActionType.ALL_IN,
                        min_amount=max_raise,
                        max_amount=max_raise,
                    )
                )

        return tuple(valid)

    # =========================================================================
    # Hand Evaluation
    # =========================================================================

    def evaluate_hand(self, table_state: TableState) -> HandResult:
        """Evaluate completed hand and return results.

        패 판정 로직 - 수학적 증명 (WSOP 표준):
        ═══════════════════════════════════════════════════════════════════════

        핸드 랭킹 (내림차순, 확률 기반):
        1. 로얄 플러시 - P = 4/C(52,5) = 0.000154%
        2. 스트레이트 플러시 - P = 36/C(52,5) = 0.00139%
        3. 포카드 - P = 624/C(52,5) = 0.024%
        4. 풀하우스 - P = 3,744/C(52,5) = 0.144%
        5. 플러시 - P = 5,108/C(52,5) = 0.197%
        6. 스트레이트 - P = 10,200/C(52,5) = 0.392%
        7. 쓰리오브어카인드 - P = 54,912/C(52,5) = 2.11%
        8. 투페어 - P = 123,552/C(52,5) = 4.75%
        9. 원페어 - P = 1,098,240/C(52,5) = 42.26%
        10. 하이카드 - P = 1,302,540/C(52,5) = 50.12%

        총 경우의 수: C(52,5) = 2,598,960

        동점 처리 (Kickers):
        - 같은 랭크 시 키커(보조 카드) 비교
        - 키커도 동점 시 팟 분할 (Split Pot)
        - 홀수 칩은 버튼 왼쪽 가장 가까운 플레이어에게
        ═══════════════════════════════════════════════════════════════════════

        Args:
            table_state: Table state with completed hand

        Returns:
            HandResult with winners and showdown info

        Raises:
            ValueError: If hand not finished
        """
        if table_state.hand is None:
            raise ValueError("No hand to evaluate")

        if table_state._pk_snapshot is None:
            raise GameStateError("No PokerKit state snapshot")

        pk_state = self._deserialize_pk_state(table_state._pk_snapshot)

        if pk_state.status:  # True means hand still active
            raise ValueError("Hand not finished")

        active_seats = list(table_state.get_active_seats())
        active_seats.sort(key=lambda s: s.position)

        # Extract winners from payoffs
        winners = []
        payoffs = pk_state.payoffs

        for pk_idx, payoff in enumerate(payoffs):
            if payoff > 0:
                position = active_seats[pk_idx].position
                winners.append(
                    WinnerInfo(
                        position=position,
                        amount=payoff,
                        pot_type="main",  # Simplified - could track side pots
                    )
                )

        # Extract showdown hands if available
        showdown_hands = None
        if pk_state.hand_killing_statuses:
            shown = []
            for pk_idx, not_killed in enumerate(pk_state.hand_killing_statuses):
                if not_killed and pk_idx < len(pk_state.hole_cards):
                    hole_cards = pk_state.hole_cards[pk_idx]
                    if hole_cards and len(hole_cards) >= 2:
                        try:
                            hand_eval = pk_state.get_up_hand(pk_idx)
                            hand_rank = self._map_hand_rank(hand_eval)
                            best_five = self._extract_best_five(pk_state, pk_idx)

                            shown.append(
                                ShowdownHand(
                                    position=active_seats[pk_idx].position,
                                    hole_cards=(
                                        pk_card_to_card(hole_cards[0]),
                                        pk_card_to_card(hole_cards[1]),
                                    ),
                                    hand_rank=hand_rank,
                                    best_five=best_five,
                                )
                            )
                        except (IndexError, AttributeError) as e:
                            # Log but continue - partial showdown data is acceptable
                            logger.warning(
                                f"Failed to extract showdown hand for player {pk_idx}: {e}"
                            )

            if shown:
                showdown_hands = tuple(shown)

        return HandResult(
            hand_id=table_state.hand.hand_id,
            winners=tuple(winners),
            showdown_hands=showdown_hands,
        )

    def is_hand_finished(self, table_state: TableState) -> bool:
        """Check if current hand is finished."""
        if table_state.hand is None or table_state._pk_snapshot is None:
            return True

        pk_state = self._deserialize_pk_state(table_state._pk_snapshot)
        return not pk_state.status

    # =========================================================================
    # Private Helpers
    # =========================================================================

    def _serialize_pk_state(self, pk_state: PKState) -> bytes:
        """Serialize PokerKit state to bytes with HMAC signature.

        Security:
        - Prepends HMAC-SHA256 signature (32 bytes) to serialized data
        - Only server-generated data is serialized
        - Signature prevents tampering and validates integrity on load
        """
        settings = get_settings()
        data = pickle.dumps(pk_state)
        signature = hmac.new(
            settings.serialization_hmac_key.encode(),
            data,
            hashlib.sha256,
        ).digest()
        return signature + data

    def _deserialize_pk_state(self, snapshot: bytes) -> PKState:
        """Deserialize PokerKit state from bytes with HMAC verification.

        Security:
        - Verifies HMAC-SHA256 signature before deserializing
        - Raises GameStateError if signature is invalid (tampering detected)
        - Only our own generated snapshots pass verification
        """
        if len(snapshot) < 32:
            raise GameStateError("Invalid snapshot: too short")

        settings = get_settings()
        signature = snapshot[:32]
        data = snapshot[32:]

        expected_signature = hmac.new(
            settings.serialization_hmac_key.encode(),
            data,
            hashlib.sha256,
        ).digest()

        if not hmac.compare_digest(signature, expected_signature):
            logger.error("HMAC verification failed - possible data tampering")
            raise GameStateError("Invalid snapshot: signature verification failed")

        return pickle.loads(data)  # noqa: S301 - Safe after HMAC verification

    def _position_to_pk_index(
        self,
        position: int,
        active_seats: list[SeatState],
    ) -> int:
        """Map seat position to PokerKit player index."""
        for pk_idx, seat in enumerate(active_seats):
            if seat.position == position:
                return pk_idx
        raise ValueError(f"Position {position} not in active seats")

    def _pk_index_to_position(
        self,
        pk_index: int,
        active_seats: list[SeatState],
    ) -> int:
        """Map PokerKit player index to seat position."""
        if pk_index < len(active_seats):
            return active_seats[pk_index].position
        raise ValueError(f"PK index {pk_index} out of range")

    def _execute_pk_action(
        self,
        pk_state: PKState,
        action: ActionRequest,
    ) -> tuple[int, ActionType]:
        """Execute action on PokerKit state.

        Returns tuple of (actual amount committed, actual action type).
        The action type may differ from request if conversion occurred
        (e.g., FOLD -> CHECK when no bet to face, CALL -> CHECK when amount is 0).
        """
        match action.action_type:
            case ActionType.FOLD:
                # Check if fold is valid (can't fold if you can check for free)
                if pk_state.can_fold():
                    pk_state.fold()
                    return (0, ActionType.FOLD)
                else:
                    # If can't fold (no bet to face), check instead
                    if pk_state.can_check_or_call():
                        pk_state.check_or_call()
                        return (0, ActionType.CHECK)  # Converted to check
                    raise InvalidActionError("Cannot fold or check")

            case ActionType.CHECK:
                if not pk_state.can_check_or_call():
                    raise InvalidActionError("Cannot check")
                pk_state.check_or_call()
                return (0, ActionType.CHECK)

            case ActionType.CALL:
                if not pk_state.can_check_or_call():
                    raise InvalidActionError("Cannot call")
                amount = pk_state.checking_or_calling_amount or 0
                pk_state.check_or_call()
                # If call amount is 0, it's effectively a check
                actual_type = ActionType.CHECK if amount == 0 else ActionType.CALL
                return (amount, actual_type)

            case ActionType.BET | ActionType.RAISE:
                if action.amount is None:
                    raise InvalidActionError("Amount required for bet/raise")
                if not pk_state.can_complete_bet_or_raise_to(action.amount):
                    raise InvalidActionError(f"Cannot bet/raise to {action.amount}")
                pk_state.complete_bet_or_raise_to(action.amount)
                return (action.amount, action.action_type)

            case ActionType.ALL_IN:
                max_amount = pk_state.max_completion_betting_or_raising_to_amount
                if max_amount is None:
                    # If can't raise, just call all-in
                    if pk_state.can_check_or_call():
                        amount = pk_state.checking_or_calling_amount or 0
                        pk_state.check_or_call()
                        actual_type = (
                            ActionType.CHECK if amount == 0 else ActionType.CALL
                        )
                        return (amount, actual_type)
                    raise InvalidActionError("Cannot go all-in")
                pk_state.complete_bet_or_raise_to(max_amount)
                return (max_amount, ActionType.ALL_IN)

            case _:
                raise InvalidActionError(f"Unknown action type: {action.action_type}")

    def _extract_hand_state(
        self,
        pk_state: PKState,
        hand_id: str,
        hand_number: int,
        active_seats: list[SeatState],
        started_at: datetime,
    ) -> HandState:
        """Convert PokerKit state to immutable HandState."""
        # Determine phase
        phase = self._map_pk_street_to_phase(pk_state)

        # Extract community cards
        # PokerKit 0.7.2 returns board_cards as nested list: [[card1], [card2], ...]
        # Flatten the structure to get individual cards, filtering out None values
        flat_board_cards = []
        for card_list in pk_state.board_cards or []:
            if isinstance(card_list, list):
                flat_board_cards.extend(c for c in card_list if c is not None)
            elif card_list is not None:
                flat_board_cards.append(card_list)
        community_cards = tuple(pk_card_to_card(c) for c in flat_board_cards)

        # Build pot state (active_seats 전달하여 eligible_positions 계산)
        pot_state = self._extract_pot_state(pk_state, active_seats)

        # Build player hand states
        player_states = []
        for pk_idx, seat in enumerate(active_seats):
            hole_cards = None
            status = PlayerHandStatus.ACTIVE

            # Check if folded using statuses field
            # statuses[i] = True means player is still active
            # statuses[i] = False means player has folded
            if pk_state.statuses and pk_idx < len(pk_state.statuses):
                if not pk_state.statuses[pk_idx]:
                    status = PlayerHandStatus.FOLDED

            # Check if all-in
            if pk_idx < len(pk_state.stacks) and pk_state.stacks[pk_idx] == 0:
                if status != PlayerHandStatus.FOLDED:
                    status = PlayerHandStatus.ALL_IN

            # Get hole cards if not folded
            if status != PlayerHandStatus.FOLDED:
                if pk_state.hole_cards and pk_idx < len(pk_state.hole_cards):
                    cards = pk_state.hole_cards[pk_idx]
                    if cards and len(cards) >= 2:
                        hole_cards = (
                            pk_card_to_card(cards[0]),
                            pk_card_to_card(cards[1]),
                        )

            # Get bet amount
            bet_amount = pk_state.bets[pk_idx] if pk_idx < len(pk_state.bets) else 0

            player_states.append(
                PlayerHandState(
                    position=seat.position,
                    hole_cards=hole_cards,
                    bet_amount=bet_amount,
                    total_bet=0,  # Could track via operations
                    status=status,
                    last_action=None,  # Could track via operations
                )
            )

        # Determine current turn
        current_turn = None
        if pk_state.status and pk_state.actor_index is not None:
            current_turn = active_seats[pk_state.actor_index].position

        # Calculate min raise
        min_raise = pk_state.min_completion_betting_or_raising_to_amount or 0

        return HandState(
            hand_id=hand_id,
            hand_number=hand_number,
            phase=phase,
            community_cards=community_cards,
            pot=pot_state,
            player_states=tuple(player_states),
            current_turn=current_turn,
            last_aggressor=None,  # Could track
            min_raise=min_raise,
            started_at=started_at,
        )

    def _extract_pot_state(
        self,
        pk_state: PKState,
        active_seats: list[SeatState],
    ) -> PotState:
        """Extract pot information from PokerKit state.

        사이드팟 계산 - 수학적 증명 (WSOP 표준):
        ═══════════════════════════════════════════════════════════════════════

        정의:
        - n명의 플레이어가 각각 스택 s[i]를 갖고 베팅
        - 올인 플레이어들의 스택을 오름차순 정렬: s[1] ≤ s[2] ≤ ... ≤ s[k]

        메인팟 (Main Pot):
        - 금액 = min(s[i]) × n (모든 플레이어 참여 가능)
        - 증명: 가장 작은 스택 s[1]까지만 모든 n명이 참여 가능

        사이드팟 i (Side Pot):
        - 금액 = (s[i+1] - s[i]) × (n - i) (i+1번째 플레이어부터 참여 가능)
        - 증명: s[i] 초과 ~ s[i+1] 이하 금액은 (n-i)명만 참여 가능

        칩 보존 법칙:
        - 총 베팅 = 메인팟 + Σ사이드팟[i] for i in 1..k
        - 증명: Σs[i] = s[1]×n + Σ(s[i+1]-s[i])×(n-i) (텔레스코핑 합)

        홀수 칩 규칙:
        - 분할 시 남는 칩은 버튼 왼쪽(시계방향) 가장 가까운 플레이어에게
        - PokerKit CHIPS_PUSHING 자동화가 이 규칙을 적용
        ═══════════════════════════════════════════════════════════════════════

        Args:
            pk_state: PokerKit 게임 상태
            active_seats: 활성 좌석 목록 (pk_index -> position 변환용)
        """
        # PokerKit 0.7.2 returns a generator, convert to list for indexing
        # (Pots list is typically small: 1 main + 0-2 side pots)
        pots = list(pk_state.pots)

        if not pots:
            return PotState(main_pot=0)

        main_pot = pots[0].amount
        side_pots = []

        for pot in pots[1:]:
            # pot.player_indices에서 eligible players 추출하여 position으로 변환
            eligible_positions: tuple[int, ...] = ()
            if hasattr(pot, 'player_indices') and pot.player_indices:
                try:
                    eligible_positions = tuple(
                        self._pk_index_to_position(pk_idx, active_seats)
                        for pk_idx in pot.player_indices
                    )
                except (ValueError, IndexError):
                    # 변환 실패 시 빈 튜플 유지 (안전 처리)
                    pass

            side_pots.append(
                SidePot(
                    amount=pot.amount,
                    eligible_positions=eligible_positions,
                )
            )

        return PotState(
            main_pot=main_pot,
            side_pots=tuple(side_pots),
        )

    def _map_pk_street_to_phase(self, pk_state: PKState) -> GamePhase:
        """Map PokerKit street to GamePhase."""
        if not pk_state.status:
            return GamePhase.FINISHED

        street_index = pk_state.street_index

        if street_index is None:
            return GamePhase.PREFLOP

        match street_index:
            case 0:
                return GamePhase.PREFLOP
            case 1:
                return GamePhase.FLOP
            case 2:
                return GamePhase.TURN
            case 3:
                return GamePhase.RIVER
            case _:
                return GamePhase.SHOWDOWN

    def _map_hand_rank(self, hand_eval: Any) -> HandRank:
        """Map PokerKit hand evaluation to HandRank."""
        # PokerKit returns a Hand object with a type
        if hand_eval is None:
            return HandRank.HIGH_CARD

        # Get the hand type name from PokerKit
        try:
            hand_type = str(hand_eval.__class__.__name__).lower()

            if "royalflush" in hand_type or "royal" in hand_type:
                return HandRank.ROYAL_FLUSH
            elif "straightflush" in hand_type:
                return HandRank.STRAIGHT_FLUSH
            elif "fourofakind" in hand_type or "quads" in hand_type:
                return HandRank.FOUR_OF_A_KIND
            elif "fullhouse" in hand_type:
                return HandRank.FULL_HOUSE
            elif "flush" in hand_type:
                return HandRank.FLUSH
            elif "straight" in hand_type:
                return HandRank.STRAIGHT
            elif "threeofakind" in hand_type or "trips" in hand_type:
                return HandRank.THREE_OF_A_KIND
            elif "twopair" in hand_type:
                return HandRank.TWO_PAIR
            elif "onepair" in hand_type or "pair" in hand_type:
                return HandRank.ONE_PAIR
            else:
                return HandRank.HIGH_CARD
        except Exception as e:
            logger.warning(f"Failed to map hand rank: {e}")
            return HandRank.HIGH_CARD

    def _extract_best_five(
        self,
        pk_state: PKState,
        pk_idx: int,
    ) -> tuple[Card, ...]:
        """Extract best 5-card hand for player."""
        try:
            hand = pk_state.get_up_hand(pk_idx)
            if hand and hasattr(hand, "cards"):
                return tuple(pk_card_to_card(c) for c in hand.cards[:5])
        except Exception as e:
            logger.warning(f"Failed to get best five cards for player {pk_idx}: {e}")

        # Fallback: combine hole cards and board
        cards = []
        if pk_state.hole_cards and pk_idx < len(pk_state.hole_cards):
            for c in pk_state.hole_cards[pk_idx][:2]:
                cards.append(pk_card_to_card(c))
        if pk_state.board_cards:
            for c in pk_state.board_cards[: 5 - len(cards)]:
                cards.append(pk_card_to_card(c))

        return tuple(cards[:5])
