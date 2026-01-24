from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

from app.models.admin_user import AdminUser, AdminRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AdminUserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def hash_password(self, password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)

    async def create_admin_user(
        self,
        username: str,
        email: str,
        password: str,
        role: AdminRole = AdminRole.viewer,
    ) -> AdminUser:
        """Create a new admin user"""
        admin_user = AdminUser(
            id=str(uuid4()),
            username=username,
            email=email,
            password_hash=self.hash_password(password),
            role=role,
            is_active=True,
        )
        self.db.add(admin_user)
        await self.db.commit()
        await self.db.refresh(admin_user)
        return admin_user

    async def get_by_id(self, user_id: str) -> AdminUser | None:
        """Get admin user by ID"""
        result = await self.db.execute(select(AdminUser).where(AdminUser.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> AdminUser | None:
        """Get admin user by email"""
        result = await self.db.execute(select(AdminUser).where(AdminUser.email == email))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> AdminUser | None:
        """Get admin user by username"""
        result = await self.db.execute(select(AdminUser).where(AdminUser.username == username))
        return result.scalar_one_or_none()

    async def authenticate(self, username: str, password: str) -> AdminUser | None:
        """Authenticate admin user by username and password"""
        user = await self.get_by_username(username)
        if not user:
            return None
        if not user.is_active:
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        return user

    async def update_last_login(self, user: AdminUser) -> None:
        """Update user's last login timestamp"""
        user.last_login = datetime.now(timezone.utc)
        await self.db.commit()

    async def update_two_factor_secret(self, user: AdminUser, secret: str) -> None:
        """Update user's 2FA secret"""
        user.two_factor_secret = secret
        user.two_factor_enabled = True
        await self.db.commit()

    async def disable_two_factor(self, user: AdminUser) -> None:
        """Disable 2FA for user"""
        user.two_factor_secret = None
        user.two_factor_enabled = False
        await self.db.commit()

    async def list_admin_users(
        self,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[AdminUser], int]:
        """List admin users with pagination"""
        # Get total count
        count_result = await self.db.execute(select(AdminUser))
        total = len(count_result.scalars().all())

        # Get paginated results
        result = await self.db.execute(
            select(AdminUser).order_by(AdminUser.created_at.desc()).offset(skip).limit(limit)
        )
        users = result.scalars().all()
        return list(users), total

    async def deactivate_user(self, user: AdminUser) -> None:
        """Deactivate an admin user"""
        user.is_active = False
        await self.db.commit()

    async def activate_user(self, user: AdminUser) -> None:
        """Activate an admin user"""
        user.is_active = True
        await self.db.commit()

    async def update_role(self, user: AdminUser, role: AdminRole) -> None:
        """Update user's role"""
        user.role = role
        await self.db.commit()
