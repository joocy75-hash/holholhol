"""API response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import BaseSchema, PaginationMeta


# =============================================================================
# Auth Responses
# =============================================================================


class TokenResponse(BaseModel):
    """Authentication token response."""

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    access_token: str = Field(..., alias="accessToken")
    refresh_token: str = Field(..., alias="refreshToken")
    token_type: str = Field(default="Bearer", alias="tokenType")
    expires_in: int = Field(..., alias="expiresIn", description="Access token expiry in seconds")


class UserBasicResponse(BaseSchema):
    """Basic user information."""

    id: str
    nickname: str
    avatar_url: str | None = Field(None, alias="avatarUrl")
    balance: int = Field(default=0, description="User's current chip balance")


class AuthResponse(BaseModel):
    """Full authentication response with user info."""

    user: UserBasicResponse
    tokens: TokenResponse


class RegisterResponse(AuthResponse):
    """Registration response (same as auth response)."""

    pass


class LoginResponse(AuthResponse):
    """Login response (same as auth response)."""

    pass


# =============================================================================
# User Responses
# =============================================================================


class UserProfileResponse(BaseSchema):
    """Detailed user profile response."""

    id: str
    email: str
    nickname: str
    avatar_url: str | None = Field(None, alias="avatarUrl")
    status: str
    balance: int = Field(default=0, description="User's current chip balance")
    total_hands: int = Field(..., alias="totalHands")
    total_winnings: int = Field(..., alias="totalWinnings")
    created_at: datetime = Field(..., alias="createdAt")


class UserStatsResponse(BaseModel):
    """User statistics response."""

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    total_hands: int = Field(..., alias="totalHands")
    total_winnings: int = Field(..., alias="totalWinnings")
    hands_won: int = Field(..., alias="handsWon")
    biggest_pot: int = Field(..., alias="biggestPot")
    vpip: float = Field(..., description="Voluntarily Put In Pot percentage")
    pfr: float = Field(..., description="Pre-flop Raise percentage")


# =============================================================================
# Room Responses
# =============================================================================


class RoomConfigResponse(BaseModel):
    """Room configuration response."""

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    max_seats: int = Field(..., alias="maxSeats")
    small_blind: int = Field(..., alias="smallBlind")
    big_blind: int = Field(..., alias="bigBlind")
    buy_in_min: int = Field(..., alias="buyInMin")
    buy_in_max: int = Field(..., alias="buyInMax")
    turn_timeout: int = Field(..., alias="turnTimeout")
    is_private: bool = Field(..., alias="isPrivate")


class RoomSummaryResponse(BaseSchema):
    """Room summary for list view."""

    id: str
    name: str
    blinds: str = Field(..., description="Formatted blinds (e.g., '10/20')")
    max_seats: int = Field(..., alias="maxSeats")
    player_count: int = Field(..., alias="playerCount")  # FE expects "playerCount"
    status: str
    is_private: bool = Field(..., alias="isPrivate")
    buy_in_min: int = Field(..., alias="buyInMin")
    buy_in_max: int = Field(..., alias="buyInMax")

    @classmethod
    def from_room(cls, room: Any) -> "RoomSummaryResponse":
        """Create from Room model."""
        return cls(
            id=room.id,
            name=room.name,
            blinds=f"{room.small_blind}/{room.big_blind}",
            max_seats=room.max_seats,
            player_count=room.current_players,
            status=room.status,
            is_private=room.config.get("is_private", False),
            buy_in_min=room.config.get("buy_in_min", 400),
            buy_in_max=room.config.get("buy_in_max", 2000),
        )


class RoomDetailResponse(BaseSchema):
    """Detailed room response."""

    id: str
    name: str
    description: str | None
    config: RoomConfigResponse
    status: str
    current_players: int = Field(..., alias="currentPlayers")
    owner: UserBasicResponse | None
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")


class RoomListResponse(BaseModel):
    """Paginated room list response."""

    rooms: list[RoomSummaryResponse]
    pagination: PaginationMeta


class JoinRoomResponse(BaseModel):
    """Room join result response."""

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    success: bool
    room_id: str = Field(..., alias="roomId")
    table_id: str = Field(..., alias="tableId")
    position: int | None = Field(None, description="Assigned seat position (null if spectator)")
    message: str


class QuickJoinResponse(BaseModel):
    """Quick join result response."""

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    success: bool = True
    room_id: str = Field(..., alias="roomId")
    table_id: str = Field(..., alias="tableId")
    seat: int = Field(..., description="Assigned seat position")
    buy_in: int = Field(..., alias="buyIn", description="Auto-calculated buy-in amount")
    room_name: str = Field(..., alias="roomName")
    blinds: str = Field(..., description="Room blinds (e.g., '10/20')")


# =============================================================================
# Health Check Response
# =============================================================================


class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str = "1.0.0"
    timestamp: datetime
    services: dict[str, str] = Field(default_factory=dict)
