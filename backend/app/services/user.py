"""User service."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserStatus
from app.utils.security import hash_password, verify_password


class UserError(Exception):
    """User operation error with code."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class UserService:
    """Service for user management operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user(self, user_id: str) -> User | None:
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

    async def get_user_by_email(self, email: str) -> User | None:
        """Get user by email.

        Args:
            email: User email

        Returns:
            User object or None
        """
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_user_by_nickname(self, nickname: str) -> User | None:
        """Get user by nickname.

        Args:
            nickname: User nickname

        Returns:
            User object or None
        """
        result = await self.db.execute(
            select(User).where(User.nickname == nickname)
        )
        return result.scalar_one_or_none()

    async def update_profile(
        self,
        user_id: str,
        nickname: str | None = None,
        avatar_url: str | None = None,
    ) -> User:
        """Update user profile.

        Args:
            user_id: User ID
            nickname: New nickname
            avatar_url: New avatar URL

        Returns:
            Updated User object

        Raises:
            UserError: If update fails
        """
        user = await self.get_user(user_id)

        if not user:
            raise UserError("USER_NOT_FOUND", "User not found")

        if user.status != UserStatus.ACTIVE.value:
            raise UserError("USER_INACTIVE", "User account is not active")

        # Update nickname if provided
        if nickname is not None and nickname != user.nickname:
            # Check if nickname is taken
            existing = await self.get_user_by_nickname(nickname)
            if existing:
                raise UserError("USER_NICKNAME_EXISTS", "Nickname already taken")
            user.nickname = nickname

        # Update avatar if provided
        if avatar_url is not None:
            user.avatar_url = avatar_url

        return user

    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Change user password.

        Args:
            user_id: User ID
            current_password: Current password
            new_password: New password

        Returns:
            True if changed successfully

        Raises:
            UserError: If change fails
        """
        user = await self.get_user(user_id)

        if not user:
            raise UserError("USER_NOT_FOUND", "User not found")

        if not verify_password(current_password, user.password_hash):
            raise UserError("USER_INVALID_PASSWORD", "Current password is incorrect")

        user.password_hash = hash_password(new_password)
        return True

    async def get_user_stats(self, user_id: str) -> dict[str, Any]:
        """Get user statistics.

        Args:
            user_id: User ID

        Returns:
            Dict with user stats

        Raises:
            UserError: If user not found
        """
        user = await self.get_user(user_id)

        if not user:
            raise UserError("USER_NOT_FOUND", "User not found")

        # TODO: Calculate detailed stats from hand history
        return {
            "total_hands": user.total_hands,
            "total_winnings": user.total_winnings,
            "hands_won": 0,  # To be calculated
            "biggest_pot": 0,  # To be calculated
            "vpip": 0.0,  # To be calculated
            "pfr": 0.0,  # To be calculated
        }

    async def update_stats(
        self,
        user_id: str,
        hands_played: int = 0,
        winnings: int = 0,
    ) -> User:
        """Update user statistics.

        Args:
            user_id: User ID
            hands_played: Hands played to add
            winnings: Winnings to add

        Returns:
            Updated User object

        Raises:
            UserError: If update fails
        """
        user = await self.get_user(user_id)

        if not user:
            raise UserError("USER_NOT_FOUND", "User not found")

        user.total_hands += hands_played
        user.total_winnings += winnings

        return user

    async def deactivate_user(self, user_id: str) -> bool:
        """Deactivate user account.

        Args:
            user_id: User ID

        Returns:
            True if deactivated successfully

        Raises:
            UserError: If deactivation fails
        """
        user = await self.get_user(user_id)

        if not user:
            raise UserError("USER_NOT_FOUND", "User not found")

        user.status = UserStatus.DELETED.value
        return True
