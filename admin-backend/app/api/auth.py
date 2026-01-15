from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_admin_db
from app.models.admin_user import AdminUser, AdminRole
from app.services.admin_user_service import AdminUserService
from app.services.session_service import get_session_service, SessionService
from app.utils.jwt import create_access_token, create_2fa_pending_token
from app.utils.two_factor import setup_two_factor, verify_totp
from app.utils.dependencies import get_current_user, get_2fa_pending_user

router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    requires_two_factor: bool = False
    two_factor_token: str | None = None


class TwoFactorVerifyRequest(BaseModel):
    code: str


class TwoFactorSetupResponse(BaseModel):
    secret: str
    qr_code: str  # base64 encoded PNG


class AdminUserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    two_factor_enabled: bool
    last_login: str | None
    created_at: str

    class Config:
        from_attributes = True


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    req: Request,
    db: AsyncSession = Depends(get_admin_db),
):
    """Admin login endpoint"""
    service = AdminUserService(db)
    user = await service.authenticate(request.email, request.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Check if 2FA is enabled
    if user.two_factor_enabled and user.two_factor_secret:
        # Return temporary token for 2FA verification
        two_factor_token = create_2fa_pending_token(
            user_id=user.id,
            email=user.email,
            role=user.role.value,
        )
        return LoginResponse(
            access_token="",
            requires_two_factor=True,
            two_factor_token=two_factor_token,
        )

    # No 2FA, create access token directly
    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role.value,
    )

    # Update last login
    await service.update_last_login(user)

    # Create session
    session_service = await get_session_service()
    await session_service.create_session(
        user_id=user.id,
        token=access_token,
        ip_address=req.client.host if req.client else "unknown",
        user_agent=req.headers.get("user-agent", "unknown"),
    )

    return LoginResponse(
        access_token=access_token,
        requires_two_factor=False,
    )


@router.post("/2fa/verify", response_model=LoginResponse)
async def verify_two_factor(
    request: TwoFactorVerifyRequest,
    req: Request,
    user: AdminUser = Depends(get_2fa_pending_user),
    db: AsyncSession = Depends(get_admin_db),
):
    """Verify 2FA code and complete login"""
    if not user.two_factor_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA not configured for this user",
        )

    if not verify_totp(user.two_factor_secret, request.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid 2FA code",
        )

    # Create access token
    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role.value,
    )

    # Update last login
    service = AdminUserService(db)
    await service.update_last_login(user)

    # Create session
    session_service = await get_session_service()
    await session_service.create_session(
        user_id=user.id,
        token=access_token,
        ip_address=req.client.host if req.client else "unknown",
        user_agent=req.headers.get("user-agent", "unknown"),
    )

    return LoginResponse(
        access_token=access_token,
        requires_two_factor=False,
    )


@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_2fa(
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_admin_db),
):
    """Set up 2FA for current user"""
    if current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is already enabled",
        )

    secret, uri, qr_code = setup_two_factor(current_user.email)

    # Store secret (not enabled yet until verified)
    service = AdminUserService(db)
    current_user.two_factor_secret = secret
    await db.commit()

    return TwoFactorSetupResponse(
        secret=secret,
        qr_code=qr_code,
    )


@router.post("/2fa/enable")
async def enable_2fa(
    request: TwoFactorVerifyRequest,
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_admin_db),
):
    """Enable 2FA after verifying setup code"""
    if not current_user.two_factor_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA setup not initiated. Call /2fa/setup first.",
        )

    if not verify_totp(current_user.two_factor_secret, request.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid 2FA code",
        )

    service = AdminUserService(db)
    current_user.two_factor_enabled = True
    await db.commit()

    return {"message": "2FA enabled successfully"}


@router.post("/2fa/disable")
async def disable_2fa(
    request: TwoFactorVerifyRequest,
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_admin_db),
):
    """Disable 2FA (requires current 2FA code)"""
    if not current_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled",
        )

    if not verify_totp(current_user.two_factor_secret, request.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid 2FA code",
        )

    service = AdminUserService(db)
    await service.disable_two_factor(current_user)

    return {"message": "2FA disabled successfully"}


@router.post("/logout")
async def logout(
    req: Request,
    current_user: AdminUser = Depends(get_current_user),
):
    """Logout and invalidate session"""
    auth_header = req.headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "")

    session_service = await get_session_service()
    await session_service.invalidate_session(token)

    return {"message": "Logged out successfully"}


@router.get("/me", response_model=AdminUserResponse)
async def get_current_user_info(
    current_user: AdminUser = Depends(get_current_user),
):
    """Get current admin user info"""
    return AdminUserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role.value,
        is_active=current_user.is_active,
        two_factor_enabled=current_user.two_factor_enabled,
        last_login=current_user.last_login.isoformat() if current_user.last_login else None,
        created_at=current_user.created_at.isoformat(),
    )


@router.post("/refresh")
async def refresh_session(
    req: Request,
    current_user: AdminUser = Depends(get_current_user),
):
    """Refresh session timeout"""
    auth_header = req.headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "")

    session_service = await get_session_service()
    success = await session_service.refresh_session(token)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found or expired",
        )

    return {"message": "Session refreshed"}
