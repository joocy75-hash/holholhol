from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_admin_db
from app.models.admin_user import AdminUser, AdminRole
from app.services.admin_user_service import AdminUserService
from app.utils.jwt import verify_token, TokenData

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_admin_db),
) -> AdminUser:
    """Get current authenticated admin user"""
    token = credentials.credentials
    token_data = verify_token(token, required_type="access")

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    service = AdminUserService(db)
    user = await service.get_by_id(token_data.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is deactivated",
        )

    return user


async def get_2fa_pending_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_admin_db),
) -> AdminUser:
    """Get user from 2FA pending token"""
    token = credentials.credentials
    token_data = verify_token(token, required_type="2fa_pending")

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired 2FA token",
        )

    service = AdminUserService(db)
    user = await service.get_by_id(token_data.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


def require_role(*roles: AdminRole):
    """Dependency to require specific roles"""

    async def role_checker(
        current_user: AdminUser = Depends(get_current_user),
    ) -> AdminUser:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {[r.value for r in roles]}",
            )
        return current_user

    return role_checker


# Convenience dependencies for common role requirements
require_viewer = require_role(
    AdminRole.viewer, AdminRole.operator, AdminRole.supervisor, AdminRole.admin
)
require_operator = require_role(AdminRole.operator, AdminRole.supervisor, AdminRole.admin)
require_supervisor = require_role(AdminRole.supervisor, AdminRole.admin)
require_admin = require_role(AdminRole.admin)
