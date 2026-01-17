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
# Hand History Responses (Phase 2.5)
# =============================================================================


class HandParticipantResponse(BaseSchema):
    """핸드 참가자 정보."""

    user_id: str = Field(..., alias="userId")
    seat: int
    hole_cards: list[str] | None = Field(None, alias="holeCards")
    bet_amount: int = Field(..., alias="betAmount")
    won_amount: int = Field(..., alias="wonAmount")
    final_action: str = Field(..., alias="finalAction")
    net_result: int | None = Field(None, alias="netResult", description="승패 금액 (won - bet)")


class HandEventResponse(BaseSchema):
    """핸드 이벤트 정보."""

    seq_no: int = Field(..., alias="seqNo")
    event_type: str = Field(..., alias="eventType")
    payload: dict[str, Any]
    created_at: datetime | None = Field(None, alias="createdAt")


class HandSummaryResponse(BaseSchema):
    """핸드 요약 정보 (히스토리 목록용)."""

    hand_id: str = Field(..., alias="handId")
    table_id: str = Field(..., alias="tableId")
    hand_number: int = Field(..., alias="handNumber")
    started_at: datetime | None = Field(None, alias="startedAt")
    ended_at: datetime | None = Field(None, alias="endedAt")
    pot_size: int = Field(..., alias="potSize")
    community_cards: list[str] = Field(default_factory=list, alias="communityCards")
    user_seat: int = Field(..., alias="userSeat")
    user_hole_cards: list[str] | None = Field(None, alias="userHoleCards")
    user_bet_amount: int = Field(..., alias="userBetAmount")
    user_won_amount: int = Field(..., alias="userWonAmount")
    user_final_action: str = Field(..., alias="userFinalAction")
    net_result: int = Field(..., alias="netResult", description="유저의 승패 금액")


class HandDetailResponse(BaseSchema):
    """핸드 상세 정보 (리플레이용)."""

    hand_id: str = Field(..., alias="handId")
    table_id: str = Field(..., alias="tableId")
    hand_number: int = Field(..., alias="handNumber")
    started_at: datetime | None = Field(None, alias="startedAt")
    ended_at: datetime | None = Field(None, alias="endedAt")
    initial_state: dict[str, Any] | None = Field(None, alias="initialState")
    result: dict[str, Any] | None = None
    participants: list[HandParticipantResponse]
    events: list[HandEventResponse] = Field(default_factory=list)


class HandHistoryListResponse(BaseModel):
    """핸드 히스토리 목록 응답."""

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    hands: list[HandSummaryResponse]
    pagination: PaginationMeta


# =============================================================================
# Health Check Response
# =============================================================================


class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str = "1.0.0"
    timestamp: datetime
    services: dict[str, str] = Field(default_factory=dict)
