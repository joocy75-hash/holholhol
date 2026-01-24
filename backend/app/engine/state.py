"""Immutable state models for the game engine.

All state classes use frozen=True dataclasses to ensure immutability.
Collections use tuple instead of list for immutability.
State updates are performed via dataclasses.replace().
"""

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# =============================================================================
# Card Models
# =============================================================================


class Rank(Enum):
    """Card rank with numeric value and symbol."""

    TWO = (2, "2")
    THREE = (3, "3")
    FOUR = (4, "4")
    FIVE = (5, "5")
    SIX = (6, "6")
    SEVEN = (7, "7")
    EIGHT = (8, "8")
    NINE = (9, "9")
    TEN = (10, "T")
    JACK = (11, "J")
    QUEEN = (12, "Q")
    KING = (13, "K")
    ACE = (14, "A")

    @property
    def value(self) -> int:
        """Get numeric rank value (2-14)."""
        return self._value_[0]

    @property
    def symbol(self) -> str:
        """Get single-character rank symbol."""
        return self._value_[1]

    @classmethod
    def from_symbol(cls, symbol: str) -> "Rank":
        """Parse rank from symbol (2-9, T, J, Q, K, A)."""
        symbol = symbol.upper()
        for rank in cls:
            if rank.symbol == symbol:
                return rank
        raise ValueError(f"Invalid rank symbol: {symbol}")


class Suit(Enum):
    """Card suit with symbol."""

    CLUBS = ("c", "♣")
    DIAMONDS = ("d", "♦")
    HEARTS = ("h", "♥")
    SPADES = ("s", "♠")

    @property
    def symbol(self) -> str:
        """Get single-character suit symbol (c, d, h, s)."""
        return self._value_[0]

    @property
    def unicode(self) -> str:
        """Get unicode suit symbol."""
        return self._value_[1]

    @classmethod
    def from_symbol(cls, symbol: str) -> "Suit":
        """Parse suit from symbol (c, d, h, s)."""
        symbol = symbol.lower()
        for suit in cls:
            if suit.symbol == symbol:
                return suit
        raise ValueError(f"Invalid suit symbol: {symbol}")


@dataclass(frozen=True)
class Card:
    """Immutable playing card.

    Cards are represented as rank + suit, e.g., "Ah" for Ace of Hearts.
    """

    rank: Rank
    suit: Suit

    def __str__(self) -> str:
        """Return string representation like 'Ah', '2c', 'Td'."""
        return f"{self.rank.symbol}{self.suit.symbol}"

    def __repr__(self) -> str:
        return f"Card({self})"

    @classmethod
    def from_string(cls, s: str) -> "Card":
        """Parse card from string like 'Ah', '2c', 'Td'.

        Args:
            s: Card string (e.g., "Ah" for Ace of Hearts)

        Returns:
            Card instance

        Raises:
            ValueError: If string is invalid
        """
        if len(s) != 2:
            raise ValueError(f"Card string must be 2 characters: {s}")
        return cls(
            rank=Rank.from_symbol(s[0]),
            suit=Suit.from_symbol(s[1]),
        )


# =============================================================================
# Player & Seat Models
# =============================================================================


@dataclass(frozen=True)
class Player:
    """Player identity information (not game state)."""

    user_id: str
    nickname: str
    avatar_url: str | None = None


class SeatStatus(Enum):
    """Seat occupancy status."""

    EMPTY = "empty"
    WAITING = "waiting"  # Waiting for next hand
    ACTIVE = "active"  # Participating in current hand
    SITTING_OUT = "sitting_out"
    DISCONNECTED = "disconnected"


@dataclass(frozen=True)
class SeatState:
    """State of a single seat at the table."""

    position: int  # 0-based seat index
    player: Player | None  # None if seat is empty
    stack: int  # Current chip count
    status: SeatStatus


# =============================================================================
# Table Configuration
# =============================================================================


@dataclass(frozen=True)
class TableConfig:
    """Immutable table configuration."""

    max_seats: int  # 2-9
    small_blind: int
    big_blind: int
    min_buy_in: int
    max_buy_in: int
    turn_timeout_seconds: int = 30
    ante: int = 0

    def __post_init__(self) -> None:
        """Validate configuration."""
        if not 2 <= self.max_seats <= 9:
            raise ValueError(f"max_seats must be 2-9, got {self.max_seats}")
        if self.small_blind <= 0:
            raise ValueError("small_blind must be positive")
        if self.big_blind <= 0:
            raise ValueError("big_blind must be positive")
        if self.small_blind >= self.big_blind:
            raise ValueError("small_blind must be less than big_blind")


# =============================================================================
# Action Models
# =============================================================================


class ActionType(Enum):
    """Player action types."""

    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"


@dataclass(frozen=True)
class ActionRequest:
    """Client action request (input)."""

    request_id: str
    action_type: ActionType
    amount: int | None = None  # Required for bet/raise


@dataclass(frozen=True)
class PlayerAction:
    """Processed player action (output)."""

    position: int
    action_type: ActionType
    amount: int
    timestamp: datetime


@dataclass(frozen=True)
class ValidAction:
    """Available action with constraints."""

    action_type: ActionType
    min_amount: int | None = None  # For bet/raise
    max_amount: int | None = None  # For bet/raise (max is stack)


# =============================================================================
# Pot Models
# =============================================================================


@dataclass(frozen=True)
class SidePot:
    """Side pot created by all-in situations."""

    amount: int
    eligible_positions: tuple[int, ...]


@dataclass(frozen=True)
class PotState:
    """Pot state including main pot and side pots."""

    main_pot: int
    side_pots: tuple[SidePot, ...] = ()

    @property
    def total(self) -> int:
        """Total amount in all pots."""
        return self.main_pot + sum(sp.amount for sp in self.side_pots)


# =============================================================================
# Hand State Models
# =============================================================================


class GamePhase(Enum):
    """Game phase within a hand."""

    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    FINISHED = "finished"


class PlayerHandStatus(Enum):
    """Player's status within a hand."""

    ACTIVE = "active"
    FOLDED = "folded"
    ALL_IN = "all_in"


@dataclass(frozen=True)
class PlayerHandState:
    """Player's state within a hand."""

    position: int
    hole_cards: tuple[Card, Card] | None  # None if folded
    bet_amount: int  # Current betting round
    total_bet: int  # Entire hand
    status: PlayerHandStatus
    last_action: PlayerAction | None


@dataclass(frozen=True)
class HandState:
    """State of a single hand."""

    hand_id: str
    hand_number: int
    phase: GamePhase
    community_cards: tuple[Card, ...]
    pot: PotState
    player_states: tuple[PlayerHandState, ...]
    current_turn: int | None  # Seat position or None if hand finished
    last_aggressor: int | None
    min_raise: int
    started_at: datetime

    def get_player_state(self, position: int) -> PlayerHandState | None:
        """Get player state by seat position."""
        for ps in self.player_states:
            if ps.position == position:
                return ps
        return None


# =============================================================================
# Hand Result Models
# =============================================================================


class HandRank(Enum):
    """Poker hand rankings."""

    HIGH_CARD = (1, "High Card")
    ONE_PAIR = (2, "One Pair")
    TWO_PAIR = (3, "Two Pair")
    THREE_OF_A_KIND = (4, "Three of a Kind")
    STRAIGHT = (5, "Straight")
    FLUSH = (6, "Flush")
    FULL_HOUSE = (7, "Full House")
    FOUR_OF_A_KIND = (8, "Four of a Kind")
    STRAIGHT_FLUSH = (9, "Straight Flush")
    ROYAL_FLUSH = (10, "Royal Flush")

    @property
    def value(self) -> int:
        """Numeric rank value (1-10)."""
        return self._value_[0]

    @property
    def display_name(self) -> str:
        """Human-readable rank name."""
        return self._value_[1]


@dataclass(frozen=True)
class ShowdownHand:
    """Hand shown at showdown."""

    position: int
    hole_cards: tuple[Card, Card]
    hand_rank: HandRank
    best_five: tuple[Card, ...]  # Best 5-card combination


@dataclass(frozen=True)
class WinnerInfo:
    """Information about a pot winner."""

    position: int
    amount: int
    pot_type: str  # "main", "side_0", "side_1", etc.


@dataclass(frozen=True)
class HandResult:
    """Result of a completed hand."""

    hand_id: str
    winners: tuple[WinnerInfo, ...]
    showdown_hands: tuple[ShowdownHand, ...] | None  # None if no showdown


# =============================================================================
# Table State Model
# =============================================================================


@dataclass(frozen=True)
class TableState:
    """Complete immutable table state.

    This is the top-level state object containing all game state.
    """

    table_id: str
    config: TableConfig
    seats: tuple[SeatState, ...]
    hand: HandState | None  # None between hands
    dealer_position: int
    state_version: int
    updated_at: datetime

    # Internal: PokerKit state snapshot for engine use
    _pk_snapshot: Any = field(default=None, repr=False, compare=False)

    def with_hand(self, hand: HandState) -> "TableState":
        """Create new state with updated hand."""
        return replace(
            self,
            hand=hand,
            state_version=self.state_version + 1,
            updated_at=datetime.now(timezone.utc),
        )

    def with_seats(self, seats: tuple[SeatState, ...]) -> "TableState":
        """Create new state with updated seats."""
        return replace(
            self,
            seats=seats,
            state_version=self.state_version + 1,
            updated_at=datetime.now(timezone.utc),
        )

    def increment_version(self) -> "TableState":
        """Bump version without other changes."""
        return replace(
            self,
            state_version=self.state_version + 1,
            updated_at=datetime.now(timezone.utc),
        )

    def get_seat(self, position: int) -> SeatState | None:
        """Get seat by position."""
        for seat in self.seats:
            if seat.position == position:
                return seat
        return None

    def get_active_seats(self) -> tuple[SeatState, ...]:
        """Get all seats with active players."""
        return tuple(
            seat
            for seat in self.seats
            if seat.status == SeatStatus.ACTIVE and seat.player is not None
        )


# =============================================================================
# View State Models (for client transmission)
# =============================================================================


@dataclass(frozen=True)
class PlayerViewState:
    """State view for a specific player (shows their hole cards only)."""

    table_id: str
    config: TableConfig
    seats: tuple[SeatState, ...]
    hand: HandState | None
    my_position: int
    my_hole_cards: tuple[Card, Card] | None
    allowed_actions: tuple[ValidAction, ...]
    turn_deadline_at: datetime | None
    state_version: int


@dataclass(frozen=True)
class SpectatorViewState:
    """State view for spectators (all hole cards hidden)."""

    table_id: str
    config: TableConfig
    seats: tuple[SeatState, ...]
    hand: HandState | None  # With hole_cards masked
    state_version: int


# =============================================================================
# State Transition Models
# =============================================================================


@dataclass(frozen=True)
class StateTransition:
    """Information about a state transition."""

    old_version: int
    new_version: int
    action: PlayerAction | None  # None for system events
    phase_changed: bool
    hand_completed: bool
