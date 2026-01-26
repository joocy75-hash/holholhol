"""Security utilities for authentication and authorization.

Provides password hashing, JWT token management, and security utilities.
All failures are properly logged for debugging and security auditing.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)


# =============================================================================
# Password Utilities
# =============================================================================


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    bcrypt has a 72-byte limit, so we first hash the password with SHA-256
    to handle longer passwords safely.

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    # SHA-256 해시로 72바이트 제한 우회 (표준 방식)
    password_sha256 = hashlib.sha256(password.encode()).hexdigest()
    return pwd_context.hash(password_sha256)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against

    Returns:
        True if password matches, False otherwise
    """
    # SHA-256 해시로 72바이트 제한 우회 (hash_password와 동일 방식)
    password_sha256 = hashlib.sha256(plain_password.encode()).hexdigest()
    return pwd_context.verify(password_sha256, hashed_password)


# =============================================================================
# JWT Token Utilities
# =============================================================================


def create_access_token(
    user_id: str,
    additional_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token.

    Args:
        user_id: User ID to encode in token
        additional_claims: Additional claims to include
        expires_delta: Custom expiration time

    Returns:
        Encoded JWT token string
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    payload = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": expire,
    }

    if additional_claims:
        payload.update(additional_claims)

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(
    user_id: str,
    session_id: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT refresh token.

    Args:
        user_id: User ID to encode in token
        session_id: Session ID for token tracking
        expires_delta: Custom expiration time

    Returns:
        Encoded JWT refresh token string
    """
    if expires_delta is None:
        expires_delta = timedelta(days=settings.jwt_refresh_token_expire_days)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    payload = {
        "sub": user_id,
        "type": "refresh",
        "sid": session_id,
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


class TokenError(Exception):
    """Token validation error with specific code."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and verify a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded payload dict or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("Token decode failed: token expired")
        return None
    except jwt.JWTClaimsError as e:
        logger.debug(f"Token decode failed: invalid claims - {e}")
        return None
    except JWTError as e:
        logger.warning(f"Token decode failed: {type(e).__name__}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during token decode: {type(e).__name__}: {e}")
        return None


def verify_access_token(token: str) -> dict[str, Any] | None:
    """Verify an access token and return its payload.

    Args:
        token: JWT access token

    Returns:
        Token payload if valid, None otherwise

    Raises:
        TokenError: If token is expired or invalid with specific error code
    """
    # Early validation
    if not token:
        logger.debug("Access token verification failed: empty token")
        return None
    
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "type", "iat"]},
        )
    except jwt.ExpiredSignatureError:
        logger.debug("Access token verification failed: token expired")
        raise TokenError("TOKEN_EXPIRED", "Token has expired")
    except jwt.JWTClaimsError as e:
        logger.debug(f"Access token verification failed: invalid claims - {e}")
        return None
    except JWTError as e:
        logger.warning(f"Access token verification failed: {type(e).__name__}")
        return None

    # Verify token type (early return pattern)
    if payload.get("type") != "access":
        logger.debug("Access token verification failed: wrong token type")
        return None

    # Explicit expiration check (belt and suspenders)
    exp = payload.get("exp")
    if exp is None:
        logger.debug("Access token verification failed: missing exp claim")
        return None

    now = datetime.now(timezone.utc).timestamp()
    if exp < now:
        logger.debug("Access token verification failed: token expired (double-check)")
        raise TokenError("TOKEN_EXPIRED", "Token has expired")

    return payload


def verify_refresh_token(token: str) -> dict[str, Any] | None:
    """Verify a refresh token and return its payload.

    Args:
        token: JWT refresh token

    Returns:
        Token payload if valid, None otherwise
    """
    # Early validation
    if not token:
        logger.debug("Refresh token verification failed: empty token")
        return None
    
    payload = decode_token(token)
    if payload is None:
        logger.debug("Refresh token verification failed: decode failed")
        return None

    if payload.get("type") != "refresh":
        logger.debug("Refresh token verification failed: wrong token type")
        return None

    # Verify required fields
    if not payload.get("sub") or not payload.get("sid"):
        logger.debug("Refresh token verification failed: missing required fields")
        return None

    return payload


# =============================================================================
# Token Hash Utilities (for storing refresh tokens securely)
# =============================================================================


def hash_token(token: str) -> str:
    """Create a hash of a token for secure storage.

    Args:
        token: Token string to hash

    Returns:
        SHA-256 hash of the token
    """
    return hashlib.sha256(token.encode()).hexdigest()


def generate_session_id() -> str:
    """Generate a secure random session ID.

    Returns:
        Random 32-character hex string
    """
    return secrets.token_hex(16)


# =============================================================================
# Token Response Helper
# =============================================================================


def create_token_pair(user_id: str, session_id: str) -> dict[str, Any]:
    """Create both access and refresh tokens.

    Args:
        user_id: User ID
        session_id: Session ID

    Returns:
        Dict with access_token, refresh_token, and expires_in
    """
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id, session_id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
    }
