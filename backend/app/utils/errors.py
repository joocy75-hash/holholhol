"""Custom exception classes for game errors.

Provides structured error handling with error codes and user-friendly messages.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    """Standard error codes for game errors."""

    # General errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"

    # Table errors
    TABLE_NOT_FOUND = "TABLE_NOT_FOUND"
    TABLE_FULL = "TABLE_FULL"
    TABLE_CLOSED = "TABLE_CLOSED"

    # Room errors
    ROOM_NOT_FOUND = "ROOM_NOT_FOUND"
    NO_AVAILABLE_ROOM = "NO_AVAILABLE_ROOM"
    ROOM_FULL = "ROOM_FULL"

    # Player errors
    PLAYER_NOT_FOUND = "PLAYER_NOT_FOUND"
    NOT_YOUR_TURN = "NOT_YOUR_TURN"
    NOT_A_PLAYER = "NOT_A_PLAYER"
    ALREADY_SEATED = "ALREADY_SEATED"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"

    # Action errors
    INVALID_ACTION = "INVALID_ACTION"
    INVALID_ACTION_TYPE = "INVALID_ACTION_TYPE"
    INVALID_AMOUNT = "INVALID_AMOUNT"
    NO_ACTIVE_HAND = "NO_ACTIVE_HAND"
    CANNOT_FOLD = "CANNOT_FOLD"
    CANNOT_CHECK = "CANNOT_CHECK"
    CANNOT_CALL = "CANNOT_CALL"
    CANNOT_RAISE = "CANNOT_RAISE"

    # Game state errors
    GAME_ALREADY_STARTED = "GAME_ALREADY_STARTED"
    NOT_ENOUGH_PLAYERS = "NOT_ENOUGH_PLAYERS"
    HAND_IN_PROGRESS = "HAND_IN_PROGRESS"

    # Connection errors
    CONNECTION_LOST = "CONNECTION_LOST"
    RECONNECT_FAILED = "RECONNECT_FAILED"

    # Validation errors
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    MISSING_FIELD = "MISSING_FIELD"


class GameError(Exception):
    """Base exception for game-related errors.

    Attributes:
        code: Error code for programmatic handling
        message: User-friendly error message
        details: Additional error details
        recoverable: Whether the error is recoverable
    """

    def __init__(
        self,
        code: ErrorCode | str,
        message: str,
        details: dict[str, Any] | None = None,
        recoverable: bool = True,
    ):
        self.code = code if isinstance(code, str) else code.value
        self.message = message
        self.details = details or {}
        self.recoverable = recoverable
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "errorCode": self.code,
            "errorMessage": self.message,
            "details": self.details,
            "recoverable": self.recoverable,
        }


class InvalidActionError(GameError):
    """Raised when a player attempts an invalid action."""

    def __init__(
        self,
        message: str = "Invalid action",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(
            code=ErrorCode.INVALID_ACTION,
            message=message,
            details=details,
            recoverable=True,
        )


class NotYourTurnError(GameError):
    """Raised when a player acts out of turn."""

    def __init__(self, message: str = "It's not your turn"):
        super().__init__(
            code=ErrorCode.NOT_YOUR_TURN,
            message=message,
            recoverable=True,
        )


class TableNotFoundError(GameError):
    """Raised when a table is not found."""

    def __init__(self, table_id: str):
        super().__init__(
            code=ErrorCode.TABLE_NOT_FOUND,
            message=f"Table not found: {table_id}",
            details={"tableId": table_id},
            recoverable=False,
        )


class InsufficientFundsError(GameError):
    """Raised when a player has insufficient funds."""

    def __init__(
        self,
        required: int,
        available: int,
    ):
        super().__init__(
            code=ErrorCode.INSUFFICIENT_FUNDS,
            message=f"Insufficient funds: required {required}, available {available}",
            details={"required": required, "available": available},
            recoverable=True,
        )


class InvalidAmountError(GameError):
    """Raised when a bet/raise amount is invalid."""

    def __init__(
        self,
        amount: int,
        min_amount: int | None = None,
        max_amount: int | None = None,
    ):
        message = f"Invalid amount: {amount}"
        if min_amount is not None:
            message += f", minimum: {min_amount}"
        if max_amount is not None:
            message += f", maximum: {max_amount}"

        super().__init__(
            code=ErrorCode.INVALID_AMOUNT,
            message=message,
            details={
                "amount": amount,
                "minAmount": min_amount,
                "maxAmount": max_amount,
            },
            recoverable=True,
        )


class NoActiveHandError(GameError):
    """Raised when there is no active hand."""

    def __init__(self):
        super().__init__(
            code=ErrorCode.NO_ACTIVE_HAND,
            message="No active hand in progress",
            recoverable=True,
        )


class GameAlreadyStartedError(GameError):
    """Raised when trying to start a game that's already started."""

    def __init__(self):
        super().__init__(
            code=ErrorCode.GAME_ALREADY_STARTED,
            message="Game has already started",
            recoverable=True,
        )


class NotEnoughPlayersError(GameError):
    """Raised when there aren't enough players to start."""

    def __init__(self, current: int, required: int = 2):
        super().__init__(
            code=ErrorCode.NOT_ENOUGH_PLAYERS,
            message=f"Not enough players: {current}/{required}",
            details={"current": current, "required": required},
            recoverable=True,
        )


# =============================================================================
# Quick Join Errors
# =============================================================================


class NoAvailableRoomError(GameError):
    """Raised when no available room is found for quick join."""

    def __init__(
        self,
        blind_level: str | None = None,
    ):
        message = "No available room found"
        if blind_level:
            message += f" for blind level: {blind_level}"
        super().__init__(
            code=ErrorCode.NO_AVAILABLE_ROOM,
            message=message,
            details={"blindLevel": blind_level} if blind_level else {},
            recoverable=True,
        )


class InsufficientBalanceError(GameError):
    """Raised when user balance is insufficient for minimum buy-in."""

    def __init__(
        self,
        balance: int,
        min_buy_in: int,
    ):
        super().__init__(
            code=ErrorCode.INSUFFICIENT_BALANCE,
            message=f"Insufficient balance: {balance}, minimum buy-in required: {min_buy_in}",
            details={"balance": balance, "minBuyIn": min_buy_in},
            recoverable=True,
        )


class RoomFullError(GameError):
    """Raised when trying to join a full room (race condition)."""

    def __init__(self, room_id: str):
        super().__init__(
            code=ErrorCode.ROOM_FULL,
            message="Room is full",
            details={"roomId": room_id},
            recoverable=True,
        )


class AlreadySeatedError(GameError):
    """Raised when user is already seated in another room."""

    def __init__(self, room_id: str):
        super().__init__(
            code=ErrorCode.ALREADY_SEATED,
            message="Already seated in another room",
            details={"roomId": room_id},
            recoverable=True,
        )
