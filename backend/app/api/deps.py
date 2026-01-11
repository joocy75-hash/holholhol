"""API dependencies for authentication and common utilities."""

from typing import Annotated
import uuid

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User
from app.services.auth import AuthService
from app.utils.db import get_db
from app.utils.security import verify_access_token

settings = get_settings()

# HTTP Bearer security scheme
security = HTTPBearer(auto_error=False)


def get_trace_id(x_trace_id: Annotated[str | None, Header()] = None) -> str:
    """Get or generate trace ID for request tracking.

    Args:
        x_trace_id: Optional trace ID from header

    Returns:
        Trace ID string
    """
    return x_trace_id or str(uuid.uuid4())


async def get_current_user_optional(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    """Get current user from token if provided (optional auth).

    Args:
        credentials: Bearer token credentials
        db: Database session

    Returns:
        User object or None if not authenticated
    """
    if not credentials:
        return None

    token = credentials.credentials
    payload = verify_access_token(token)

    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    auth_service = AuthService(db)
    return await auth_service.get_user_by_id(user_id)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Get current user from token (required auth).

    Args:
        credentials: Bearer token credentials
        db: Database session

    Returns:
        User object

    Raises:
        HTTPException: If not authenticated or token invalid
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_REQUIRED",
                    "message": "Authentication required",
                    "details": {},
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = verify_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_INVALID_TOKEN",
                    "message": "Invalid or expired token",
                    "details": {},
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_INVALID_TOKEN",
                    "message": "Invalid token payload",
                    "details": {},
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTH_USER_NOT_FOUND",
                    "message": "User not found",
                    "details": {},
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "AUTH_ACCOUNT_INACTIVE",
                    "message": f"Account is {user.status}",
                    "details": {},
                }
            },
        )

    return user


def get_client_info(request: Request) -> dict[str, str | None]:
    """Extract client information from request.

    Args:
        request: FastAPI request

    Returns:
        Dict with user_agent and ip_address
    """
    return {
        "user_agent": request.headers.get("user-agent"),
        "ip_address": request.client.host if request.client else None,
    }


# Type aliases for cleaner annotations
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
TraceId = Annotated[str, Depends(get_trace_id)]
