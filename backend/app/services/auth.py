"""Authentication service."""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import Session, User, UserStatus
from app.utils.security import (
    create_token_pair,
    generate_session_id,
    hash_password,
    hash_token,
    verify_password,
    verify_refresh_token,
)

settings = get_settings()


class AuthError(Exception):
    """Authentication error with code."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class AuthService:
    """Service for authentication operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(
        self,
        email: str,
        password: str,
        nickname: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """Register a new user.

        Args:
            email: User email
            password: Plain text password
            nickname: Display name
            user_agent: Client user agent
            ip_address: Client IP address

        Returns:
            Dict with user info and tokens

        Raises:
            AuthError: If email or nickname already exists
        """
        # Check if email exists
        existing = await self.db.execute(
            select(User).where(User.email == email)
        )
        if existing.scalar_one_or_none():
            raise AuthError("AUTH_EMAIL_EXISTS", "Email already registered")

        # Check if nickname exists
        existing = await self.db.execute(
            select(User).where(User.nickname == nickname)
        )
        if existing.scalar_one_or_none():
            raise AuthError("AUTH_NICKNAME_EXISTS", "Nickname already taken")

        # Create user
        user = User(
            email=email,
            password_hash=hash_password(password),
            nickname=nickname,
            status=UserStatus.ACTIVE.value,
        )
        self.db.add(user)
        await self.db.flush()

        # Create session and tokens
        session_id = generate_session_id()
        tokens = create_token_pair(user.id, session_id)

        # Store session
        session = Session(
            user_id=user.id,
            refresh_token_hash=hash_token(tokens["refresh_token"]),
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days),
        )
        self.db.add(session)

        return {
            "user": {
                "id": user.id,
                "nickname": user.nickname,
                "avatar_url": user.avatar_url,
            },
            "tokens": tokens,
        }

    async def login(
        self,
        email: str,
        password: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """Authenticate a user and create session.

        Args:
            email: User email
            password: Plain text password
            user_agent: Client user agent
            ip_address: Client IP address

        Returns:
            Dict with user info and tokens

        Raises:
            AuthError: If credentials are invalid
        """
        # Find user
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
            raise AuthError("AUTH_INVALID_CREDENTIALS", "Invalid email or password")

        if user.status != UserStatus.ACTIVE.value:
            raise AuthError("AUTH_ACCOUNT_INACTIVE", f"Account is {user.status}")

        # Create session and tokens
        session_id = generate_session_id()
        tokens = create_token_pair(user.id, session_id)

        # Store session
        session = Session(
            user_id=user.id,
            refresh_token_hash=hash_token(tokens["refresh_token"]),
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days),
        )
        self.db.add(session)

        return {
            "user": {
                "id": user.id,
                "nickname": user.nickname,
                "avatar_url": user.avatar_url,
            },
            "tokens": tokens,
        }

    async def refresh_tokens(
        self,
        refresh_token: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        """Refresh access token using refresh token.

        Args:
            refresh_token: Current refresh token
            user_agent: Client user agent
            ip_address: Client IP address

        Returns:
            Dict with new tokens

        Raises:
            AuthError: If refresh token is invalid or expired
        """
        # Verify refresh token
        payload = verify_refresh_token(refresh_token)
        if not payload:
            raise AuthError("AUTH_INVALID_TOKEN", "Invalid refresh token")

        user_id = payload.get("sub")
        if not user_id:
            raise AuthError("AUTH_INVALID_TOKEN", "Invalid refresh token payload")

        # Find session by token hash
        token_hash = hash_token(refresh_token)
        result = await self.db.execute(
            select(Session).where(
                Session.user_id == user_id,
                Session.refresh_token_hash == token_hash,
            )
        )
        session = result.scalar_one_or_none()

        if not session:
            raise AuthError("AUTH_SESSION_NOT_FOUND", "Session not found")

        if session.expires_at < datetime.now(timezone.utc):
            raise AuthError("AUTH_SESSION_EXPIRED", "Session has expired")

        # Get user
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user or user.status != UserStatus.ACTIVE.value:
            raise AuthError("AUTH_ACCOUNT_INACTIVE", "Account is not active")

        # Generate new tokens
        session_id = generate_session_id()
        tokens = create_token_pair(user.id, session_id)

        # Update session with new refresh token
        session.refresh_token_hash = hash_token(tokens["refresh_token"])
        session.last_seen_at = datetime.now(timezone.utc)
        session.user_agent = user_agent or session.user_agent
        session.ip_address = ip_address or session.ip_address
        session.expires_at = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)

        return {
            "tokens": tokens,
        }

    async def logout(self, user_id: str, refresh_token: str | None = None) -> bool:
        """Logout user and invalidate session.

        Args:
            user_id: User ID
            refresh_token: Optional refresh token to invalidate specific session

        Returns:
            True if logout successful
        """
        if refresh_token:
            # Invalidate specific session
            token_hash = hash_token(refresh_token)
            result = await self.db.execute(
                select(Session).where(
                    Session.user_id == user_id,
                    Session.refresh_token_hash == token_hash,
                )
            )
            session = result.scalar_one_or_none()
            if session:
                await self.db.delete(session)
        else:
            # Invalidate all sessions for user
            result = await self.db.execute(
                select(Session).where(Session.user_id == user_id)
            )
            sessions = result.scalars().all()
            for session in sessions:
                await self.db.delete(session)

        return True

    async def get_user_by_id(self, user_id: str) -> User | None:
        """Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User object or None
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def validate_session(self, user_id: str) -> bool:
        """Validate if user has active session.

        Args:
            user_id: User ID

        Returns:
            True if user has active session
        """
        result = await self.db.execute(
            select(Session).where(
                Session.user_id == user_id,
                Session.expires_at > datetime.now(timezone.utc),
            )
        )
        return result.scalar_one_or_none() is not None
