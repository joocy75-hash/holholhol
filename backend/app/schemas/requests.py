"""API request schemas."""

import re

from pydantic import BaseModel, EmailStr, Field, field_validator

# Reserved nicknames that cannot be used (case-insensitive)
RESERVED_NICKNAMES = {
    "admin", "administrator", "system", "moderator", "mod",
    "support", "help", "official", "staff", "bot", "server",
    "root", "operator", "dealer", "host", "owner", "manager",
}


# =============================================================================
# Auth Requests
# =============================================================================


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="Password (min 8 chars, must include number and letter)",
    )
    nickname: str = Field(
        ...,
        min_length=2,
        max_length=50,
        description="Display name",
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password complexity."""
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        return v

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, v: str) -> str:
        """Validate nickname format and check reserved names."""
        # Check reserved names (case-insensitive)
        if v.lower() in RESERVED_NICKNAMES:
            raise ValueError("This nickname is reserved and cannot be used")
        # Validate format
        if not re.match(r"^[a-zA-Z0-9가-힣_]+$", v):
            raise ValueError("Nickname can only contain letters, numbers, Korean, and underscores")
        return v


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class RefreshTokenRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str = Field(..., alias="refreshToken", description="Refresh token")


# =============================================================================
# Room Requests
# =============================================================================


class CreateRoomRequest(BaseModel):
    """Room creation request."""

    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Room name",
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Room description",
    )
    max_seats: int = Field(
        default=6,
        ge=2,
        le=9,
        alias="maxSeats",
        description="Maximum number of seats (2-9)",
    )
    small_blind: int = Field(
        default=10,
        ge=1,
        alias="smallBlind",
        description="Small blind amount",
    )
    big_blind: int = Field(
        default=20,
        ge=2,
        alias="bigBlind",
        description="Big blind amount",
    )
    buy_in_min: int = Field(
        default=400,
        ge=1,
        alias="buyInMin",
        description="Minimum buy-in amount",
    )
    buy_in_max: int = Field(
        default=2000,
        ge=1,
        alias="buyInMax",
        description="Maximum buy-in amount",
    )
    is_private: bool = Field(
        default=False,
        alias="isPrivate",
        description="Whether room requires password",
    )
    password: str | None = Field(
        default=None,
        min_length=4,
        max_length=20,
        description="Room password (required if isPrivate is true)",
    )

    @field_validator("big_blind")
    @classmethod
    def validate_big_blind(cls, v: int, info) -> int:
        """Validate big blind is at least 2x small blind."""
        small_blind = info.data.get("small_blind", 10)
        if v < small_blind * 2:
            raise ValueError("Big blind must be at least 2x small blind")
        return v

    @field_validator("buy_in_max")
    @classmethod
    def validate_buy_in_max(cls, v: int, info) -> int:
        """Validate max buy-in is greater than min."""
        buy_in_min = info.data.get("buy_in_min", 400)
        if v < buy_in_min:
            raise ValueError("Max buy-in must be >= min buy-in")
        return v


class JoinRoomRequest(BaseModel):
    """Room join request."""

    password: str | None = Field(
        default=None,
        description="Room password (if private room)",
    )
    buy_in: int = Field(
        ...,
        ge=1,
        alias="buyIn",
        description="Buy-in amount",
    )


class UpdateRoomRequest(BaseModel):
    """Room update request."""

    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_private: bool | None = Field(default=None, alias="isPrivate")
    password: str | None = Field(default=None, min_length=4, max_length=20)


# =============================================================================
# User Requests
# =============================================================================


class UpdateProfileRequest(BaseModel):
    """User profile update request."""

    nickname: str | None = Field(default=None, min_length=2, max_length=50)
    avatar_url: str | None = Field(default=None, alias="avatarUrl", max_length=500)

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, v: str | None) -> str | None:
        """Validate nickname format and check reserved names if provided."""
        if v is not None:
            # Check reserved names (case-insensitive)
            if v.lower() in RESERVED_NICKNAMES:
                raise ValueError("This nickname is reserved and cannot be used")
            # Validate format
            if not re.match(r"^[a-zA-Z0-9가-힣_]+$", v):
                raise ValueError("Nickname can only contain letters, numbers, Korean, and underscores")
        return v


class ChangePasswordRequest(BaseModel):
    """Password change request."""

    current_password: str = Field(..., alias="currentPassword")
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        alias="newPassword",
    )

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password complexity."""
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        return v


# =============================================================================
# Quick Join Requests
# =============================================================================


class QuickJoinRequest(BaseModel):
    """Quick join request for automatic room matching."""

    blind_level: str | None = Field(
        default=None,
        alias="blindLevel",
        description="Preferred blind level: 'low' (10/20), 'medium' (25/50), 'high' (50/100), or specific like '10/20'",
    )

    @field_validator("blind_level")
    @classmethod
    def validate_blind_level(cls, v: str | None) -> str | None:
        """Validate blind level format."""
        if v is None:
            return v
        valid_levels = {"low", "medium", "high"}
        if v.lower() in valid_levels:
            return v.lower()
        # Check for specific format like "10/20"
        if "/" in v:
            parts = v.split("/")
            if len(parts) == 2:
                try:
                    int(parts[0])
                    int(parts[1])
                    return v
                except ValueError:
                    pass
        raise ValueError("Invalid blind level. Use 'low', 'medium', 'high', or specific format like '10/20'")
