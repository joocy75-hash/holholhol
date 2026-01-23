from uuid import uuid4
from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext

from app.database import get_admin_db, get_main_db
from app.models.admin_user import AdminUser, AdminRole
from app.services.admin_user_service import AdminUserService
from app.services.session_service import get_session_service, SessionService
from app.utils.jwt import create_access_token, create_2fa_pending_token
from app.utils.two_factor import setup_two_factor, verify_totp
from app.utils.dependencies import get_current_user, get_2fa_pending_user
from app.middleware.rate_limit import limiter, RateLimits

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
    partner_id: str | None = None

    class Config:
        from_attributes = True


class PartnerLoginRequest(BaseModel):
    partner_code: str = Field(alias="partnerCode")
    password: str

    class Config:
        populate_by_name = True


class PartnerLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    partner_id: str
    partner_name: str
    partner_code: str


@router.post("/login", response_model=LoginResponse)
@limiter.limit(RateLimits.AUTH_LOGIN)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_admin_db),
):
    """Admin login endpoint"""
    service = AdminUserService(db)
    user = await service.authenticate(login_data.email, login_data.password)

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
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", "unknown"),
    )

    return LoginResponse(
        access_token=access_token,
        requires_two_factor=False,
    )


@router.post("/2fa/verify", response_model=LoginResponse)
@limiter.limit(RateLimits.AUTH_2FA)
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
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", "unknown"),
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
    auth_header = request.headers.get("authorization", "")
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
        partner_id=str(current_user.partner_id) if current_user.partner_id else None,
    )


@router.post("/refresh")
async def refresh_session(
    req: Request,
    current_user: AdminUser = Depends(get_current_user),
):
    """Refresh session timeout"""
    auth_header = request.headers.get("authorization", "")
    token = auth_header.replace("Bearer ", "")

    session_service = await get_session_service()
    success = await session_service.refresh_session(token)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found or expired",
        )

    return {"message": "Session refreshed"}


@router.post("/partner/login", response_model=PartnerLoginResponse)
@limiter.limit(RateLimits.AUTH_LOGIN)
async def partner_login(
    request: Request,
    login_data: PartnerLoginRequest,
    admin_db: AsyncSession = Depends(get_admin_db),
    main_db: AsyncSession = Depends(get_main_db),
):
    """파트너 로그인 엔드포인트

    1. partner_code로 Partner 조회 (main_db)
    2. 연결된 User의 password 검증 (main_db)
    3. AdminUser 조회 또는 생성 (admin_db)
    4. partner 역할로 JWT 토큰 발급
    """
    # 1. 파트너 조회 (main_db)
    partner_query = text("""
        SELECT p.id, p.partner_code, p.name, p.user_id, p.status
        FROM partners p
        WHERE p.partner_code = :partner_code
    """)
    result = await main_db.execute(partner_query, {"partner_code": login_data.partner_code})
    partner_row = result.fetchone()

    if not partner_row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 파트너 코드입니다.",
        )

    partner_id = str(partner_row.id)
    partner_code = partner_row.partner_code
    partner_name = partner_row.name
    user_id = str(partner_row.user_id)
    partner_status = partner_row.status

    # 파트너 상태 확인
    if partner_status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="파트너 계정이 활성화되지 않았습니다.",
        )

    # 2. 유저 조회 및 비밀번호 검증 (main_db)
    user_query = text("""
        SELECT id, email, password_hash, status
        FROM users
        WHERE id = :user_id
    """)
    user_result = await main_db.execute(user_query, {"user_id": user_id})
    user_row = user_result.fetchone()

    if not user_row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="연결된 사용자 계정을 찾을 수 없습니다.",
        )

    if user_row.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="사용자 계정이 비활성화되었습니다.",
        )

    # 비밀번호 검증
    if not pwd_context.verify(login_data.password, user_row.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="비밀번호가 일치하지 않습니다.",
        )

    user_email = user_row.email

    # 3. AdminUser 조회 또는 생성 (admin_db)
    admin_user_result = await admin_db.execute(
        select(AdminUser).where(AdminUser.partner_id == partner_id)
    )
    admin_user = admin_user_result.scalar_one_or_none()

    if not admin_user:
        # 파트너용 admin_user 생성
        admin_user = AdminUser(
            id=str(uuid4()),
            username=f"partner_{partner_code}",
            email=user_email,
            password_hash="",  # 파트너는 main_db의 비밀번호 사용
            role=AdminRole.partner,
            is_active=True,
            partner_id=partner_id,
        )
        admin_db.add(admin_user)
        await admin_db.commit()
        await admin_db.refresh(admin_user)
    else:
        # 기존 계정 활성화 상태 확인
        if not admin_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="파트너 관리자 계정이 비활성화되었습니다.",
            )

    # 4. JWT 토큰 발급
    access_token = create_access_token(
        user_id=admin_user.id,
        email=admin_user.email,
        role=AdminRole.partner.value,
        partner_id=partner_id,
    )

    # Update last login
    service = AdminUserService(admin_db)
    await service.update_last_login(admin_user)

    # Create session
    session_service = await get_session_service()
    await session_service.create_session(
        user_id=admin_user.id,
        token=access_token,
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", "unknown"),
    )

    return PartnerLoginResponse(
        access_token=access_token,
        partner_id=partner_id,
        partner_name=partner_name,
        partner_code=partner_code,
    )
