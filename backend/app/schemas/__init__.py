"""Pydantic schemas for API requests and responses."""

from app.schemas.common import (
    BaseSchema,
    ErrorDetail,
    ErrorResponse,
    PaginatedResponse,
    PaginationMeta,
    PaginationParams,
    SuccessResponse,
    TimestampSchema,
)
from app.schemas.requests import (
    ChangePasswordRequest,
    CreateRoomRequest,
    JoinRoomRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    UpdateProfileRequest,
    UpdateRoomRequest,
)
from app.schemas.responses import (
    AuthResponse,
    HealthCheckResponse,
    JoinRoomResponse,
    LoginResponse,
    RegisterResponse,
    RoomConfigResponse,
    RoomDetailResponse,
    RoomListResponse,
    RoomSummaryResponse,
    TokenResponse,
    UserBasicResponse,
    UserProfileResponse,
    UserStatsResponse,
)

__all__ = [
    # Common
    "BaseSchema",
    "ErrorDetail",
    "ErrorResponse",
    "PaginatedResponse",
    "PaginationMeta",
    "PaginationParams",
    "SuccessResponse",
    "TimestampSchema",
    # Requests
    "ChangePasswordRequest",
    "CreateRoomRequest",
    "JoinRoomRequest",
    "LoginRequest",
    "RefreshTokenRequest",
    "RegisterRequest",
    "UpdateProfileRequest",
    "UpdateRoomRequest",
    # Responses
    "AuthResponse",
    "HealthCheckResponse",
    "JoinRoomResponse",
    "LoginResponse",
    "RegisterResponse",
    "RoomConfigResponse",
    "RoomDetailResponse",
    "RoomListResponse",
    "RoomSummaryResponse",
    "TokenResponse",
    "UserBasicResponse",
    "UserProfileResponse",
    "UserStatsResponse",
]
