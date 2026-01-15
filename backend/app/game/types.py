"""TypedDict definitions for game module.

Provides type-safe dictionary structures for:
- Action results from PokerTable.process_action()
- Hand results from PokerTable._complete_hand()
- Player state snapshots
- Available actions from PokerTable.get_available_actions()
"""

from typing import TypedDict, NotRequired, Literal


# =============================================================================
# Player State Types
# =============================================================================


class PlayerState(TypedDict):
    """Player state snapshot during a hand."""
    
    position: int
    stack: int
    bet: int
    totalBet: int
    status: Literal["active", "folded", "all_in", "sitting_out"]


class PlayerInfo(TypedDict):
    """Full player information for table state."""
    
    userId: str
    nickname: str
    stack: int
    bet: int
    status: str
    holeCards: NotRequired[list[str] | None]
    isBot: bool
    isCurrent: bool
    isDealer: bool


# =============================================================================
# Action Types
# =============================================================================


class ActionResult(TypedDict):
    """Result of PokerTable.process_action()."""
    
    success: bool
    error: NotRequired[str]
    action: NotRequired[str]
    amount: NotRequired[int]
    seat: NotRequired[int]
    pot: NotRequired[int]
    phase: NotRequired[str]
    phase_changed: NotRequired[bool]
    new_community_cards: NotRequired[list[str]]
    hand_complete: NotRequired[bool]
    hand_result: NotRequired["HandResult | None"]
    players: NotRequired[list[PlayerState]]
    currentBet: NotRequired[int]
    currentPlayer: NotRequired[int | None]


class AvailableActions(TypedDict):
    """Available actions for a player."""
    
    actions: list[Literal["fold", "check", "call", "raise", "bet", "all_in"]]
    call_amount: NotRequired[int]
    min_raise: NotRequired[int]
    max_raise: NotRequired[int]


# =============================================================================
# Hand Result Types
# =============================================================================


class Winner(TypedDict):
    """Winner information at showdown."""
    
    seat: int
    position: int
    userId: str
    amount: int


class ShowdownHand(TypedDict):
    """Showdown hand information."""
    
    seat: int
    position: int
    holeCards: list[str]


class EliminatedPlayer(TypedDict):
    """Eliminated player information."""
    
    seat: int
    userId: str
    nickname: str


class HandResult(TypedDict):
    """Result of hand completion."""
    
    winners: list[Winner]
    showdown: list[ShowdownHand]
    pot: int
    communityCards: list[str]
    eliminatedPlayers: list[EliminatedPlayer]


# =============================================================================
# Hand Start Types
# =============================================================================


class HandStartResult(TypedDict):
    """Result of starting a new hand."""
    
    success: bool
    error: NotRequired[str]
    hand_number: NotRequired[int]
    dealer: NotRequired[int]


# =============================================================================
# Table State Types
# =============================================================================


class TableState(TypedDict):
    """Full table state snapshot."""
    
    tableId: str
    roomId: str
    tableName: str
    handNumber: int
    phase: str
    pot: int
    communityCards: list[str]
    currentTurn: int | None
    currentBet: int
    dealer: int
    smallBlindSeat: int | None
    bigBlindSeat: int | None
    smallBlind: int
    bigBlind: int
    players: list[PlayerInfo | None]
    seats: dict[str, PlayerInfo | None]


# =============================================================================
# Time Bank Types
# =============================================================================


class TimeBankResult(TypedDict):
    """Result of using time bank."""
    
    success: bool
    remaining: int  # 남은 타임 뱅크 횟수
    added_seconds: int  # 추가된 시간 (초)
    new_deadline: NotRequired[str | None]  # ISO 형식 새 마감 시간
    error: NotRequired[str]
