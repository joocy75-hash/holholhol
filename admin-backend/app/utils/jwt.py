from datetime import datetime, timedelta
from typing import Any
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import get_settings

settings = get_settings()


class TokenData(BaseModel):
    user_id: str
    email: str
    role: str
    exp: datetime
    type: str = "access"  # access, 2fa_pending
    partner_id: str | None = None  # 파트너 역할인 경우 파트너 ID


class TokenPayload(BaseModel):
    sub: str  # user_id
    email: str
    role: str
    type: str = "access"
    partner_id: str | None = None


def create_access_token(
    user_id: str,
    email: str,
    role: str,
    expires_delta: timedelta | None = None,
    token_type: str = "access",
    partner_id: str | None = None,
) -> str:
    """Create a JWT access token"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )

    to_encode: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": token_type,
        "exp": expire,
    }

    # 파트너 역할인 경우 partner_id 포함
    if partner_id:
        to_encode["partner_id"] = partner_id

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return encoded_jwt


def create_2fa_pending_token(user_id: str, email: str, role: str) -> str:
    """Create a temporary token for 2FA verification"""
    return create_access_token(
        user_id=user_id,
        email=email,
        role=role,
        expires_delta=timedelta(minutes=5),  # 5 minutes to complete 2FA
        token_type="2fa_pending",
    )


def decode_token(token: str) -> TokenData | None:
    """Decode and validate a JWT token"""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return TokenData(
            user_id=payload["sub"],
            email=payload["email"],
            role=payload["role"],
            exp=datetime.fromtimestamp(payload["exp"]),
            type=payload.get("type", "access"),
            partner_id=payload.get("partner_id"),
        )
    except JWTError:
        return None


def verify_token(token: str, required_type: str = "access") -> TokenData | None:
    """Verify token and check type"""
    token_data = decode_token(token)
    if not token_data:
        return None
    if token_data.type != required_type:
        return None
    if token_data.exp < datetime.utcnow():
        return None
    return token_data
