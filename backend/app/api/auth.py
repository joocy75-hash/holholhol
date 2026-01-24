"""Authentication API endpoints.

Phase 4 Enhancement:
- Security event logging for login failures
- Structured logging for authentication events
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import CurrentUser, DbSession, TraceId, get_client_info
from app.schemas import (
    ErrorResponse,
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    SuccessResponse,
    TokenResponse,
    UserBasicResponse,
)
from app.services.auth import AuthError, AuthService
from app.logging_config import get_logger

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = get_logger(__name__)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        409: {"model": ErrorResponse, "description": "Email or nickname exists"},
    },
)
async def register(
    request_body: RegisterRequest,
    request: Request,
    db: DbSession,
    trace_id: TraceId,
):
    """Register a new user account.

    Creates a new user with the provided email, password, and nickname.
    Returns authentication tokens for immediate login.
    """
    client_info = get_client_info(request)
    auth_service = AuthService(db)

    try:
        result = await auth_service.register(
            username=request_body.username,
            email=request_body.email,
            password=request_body.password,
            nickname=request_body.nickname,
            partner_code=request_body.partner_code,
            usdt_wallet_address=request_body.usdt_wallet_address,
            usdt_wallet_type=request_body.usdt_wallet_type,
            user_agent=client_info["user_agent"],
            ip_address=client_info["ip_address"],
        )

        return RegisterResponse(
            user=UserBasicResponse(
                id=result["user"]["id"],
                nickname=result["user"]["nickname"],
                avatar_url=result["user"]["avatar_url"],
                balance=result["user"]["balance"],
            ),
            tokens=TokenResponse(
                access_token=result["tokens"]["access_token"],
                refresh_token=result["tokens"]["refresh_token"],
                token_type=result["tokens"]["token_type"],
                expires_in=result["tokens"]["expires_in"],
            ),
        )

    except AuthError as e:
        status_code = status.HTTP_409_CONFLICT
        if "EMAIL_EXISTS" in e.code or "NICKNAME_EXISTS" in e.code or "USERNAME_EXISTS" in e.code:
            status_code = status.HTTP_409_CONFLICT
        raise HTTPException(
            status_code=status_code,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": e.details,
                },
                "traceId": trace_id,
            },
        )


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        403: {"model": ErrorResponse, "description": "Account inactive"},
        429: {"model": ErrorResponse, "description": "Too many failed attempts"},
    },
)
async def login(
    request_body: LoginRequest,
    request: Request,
    db: DbSession,
    trace_id: TraceId,
):
    """Authenticate user and return tokens.

    Validates username and password, creates a new session,
    and returns access and refresh tokens.

    Rate limiting: 5 failed attempts result in 15 minute lockout.
    """
    from fastapi.responses import JSONResponse
    from app.services.login_limiter import get_login_limiter

    client_info = get_client_info(request)
    auth_service = AuthService(db)
    login_limiter = get_login_limiter()

    # Check if account is locked due to too many failed attempts
    if login_limiter:
        attempt_result = await login_limiter.check_login_allowed(request_body.username)

        if attempt_result.is_locked:
            logger.warning(
                "login_blocked_account_locked",
                username=request_body.username,
                ip_address=client_info["ip_address"],
                retry_after=attempt_result.retry_after_seconds,
                trace_id=trace_id,
            )

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "LOGIN_ATTEMPT_LIMIT_EXCEEDED",
                        "message": f"Too many failed login attempts. Please try again in {attempt_result.retry_after_seconds // 60} minutes.",
                        "details": {
                            "retry_after_seconds": attempt_result.retry_after_seconds,
                        },
                    },
                    "traceId": trace_id,
                },
                headers={
                    "Retry-After": str(attempt_result.retry_after_seconds),
                },
            )

    try:
        result = await auth_service.login(
            username=request_body.username,
            password=request_body.password,
            user_agent=client_info["user_agent"],
            ip_address=client_info["ip_address"],
        )

        # Reset failed attempt counter on successful login
        if login_limiter:
            await login_limiter.reset_attempts(request_body.username)

        # Log successful login
        logger.info(
            "login_success",
            user_id=result["user"]["id"],
            username=request_body.username,
            ip_address=client_info["ip_address"],
            trace_id=trace_id,
        )

        return LoginResponse(
            user=UserBasicResponse(
                id=result["user"]["id"],
                nickname=result["user"]["nickname"],
                avatar_url=result["user"]["avatar_url"],
                balance=result["user"]["balance"],
            ),
            tokens=TokenResponse(
                access_token=result["tokens"]["access_token"],
                refresh_token=result["tokens"]["refresh_token"],
                token_type=result["tokens"]["token_type"],
                expires_in=result["tokens"]["expires_in"],
            ),
        )

    except AuthError as e:
        # Record failed attempt
        if login_limiter:
            attempt_result = await login_limiter.record_failed_attempt(
                request_body.username,
                client_info["ip_address"],
            )

            # If account just got locked, return 429
            if attempt_result.is_locked:
                logger.warning(
                    "login_failed_account_now_locked",
                    username=request_body.username,
                    error_code=e.code,
                    ip_address=client_info["ip_address"],
                    failed_attempts=attempt_result.total_attempts,
                    trace_id=trace_id,
                )

                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": {
                            "code": "LOGIN_ATTEMPT_LIMIT_EXCEEDED",
                            "message": f"Too many failed login attempts. Account locked for {attempt_result.retry_after_seconds // 60} minutes.",
                            "details": {
                                "retry_after_seconds": attempt_result.retry_after_seconds,
                            },
                        },
                        "traceId": trace_id,
                    },
                    headers={
                        "Retry-After": str(attempt_result.retry_after_seconds),
                    },
                )

        # Log login failure (security event)
        logger.warning(
            "login_failed",
            username=request_body.username,
            error_code=e.code,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
            trace_id=trace_id,
        )

        status_code = status.HTTP_401_UNAUTHORIZED
        if "INACTIVE" in e.code:
            status_code = status.HTTP_403_FORBIDDEN
        raise HTTPException(
            status_code=status_code,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": e.details,
                },
                "traceId": trace_id,
            },
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
    },
)
async def refresh_token(
    request_body: RefreshTokenRequest,
    request: Request,
    db: DbSession,
    trace_id: TraceId,
):
    """Refresh access token using refresh token.

    Validates the refresh token, generates new access and refresh tokens,
    and updates the session.
    """
    client_info = get_client_info(request)
    auth_service = AuthService(db)

    try:
        result = await auth_service.refresh_tokens(
            refresh_token=request_body.refresh_token,
            user_agent=client_info["user_agent"],
            ip_address=client_info["ip_address"],
        )

        return TokenResponse(
            access_token=result["tokens"]["access_token"],
            refresh_token=result["tokens"]["refresh_token"],
            token_type=result["tokens"]["token_type"],
            expires_in=result["tokens"]["expires_in"],
        )

    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": e.details,
                },
                "traceId": trace_id,
            },
        )


@router.post(
    "/logout",
    response_model=SuccessResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def logout(
    current_user: CurrentUser,
    db: DbSession,
    refresh_token: str | None = None,
):
    """Logout user and invalidate session.

    If refresh_token is provided, only that session is invalidated.
    Otherwise, all sessions for the user are invalidated.
    """
    auth_service = AuthService(db)
    await auth_service.logout(current_user.id, refresh_token)

    return SuccessResponse(
        success=True,
        message="Logged out successfully",
    )


# =============================================================================
# Two-Factor Authentication Endpoints
# =============================================================================

from datetime import datetime, timezone
import json
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.models.user import UserTwoFactor
from app.services.two_factor import get_two_factor_service


class TwoFactorSetupResponse(BaseModel):
    """Response for 2FA setup."""
    secret: str = Field(..., description="TOTP secret (keep this safe!)")
    qr_code_uri: str = Field(..., description="URI for QR code generation")
    backup_codes: list[str] = Field(..., description="One-time backup codes")
    message: str = Field(default="Scan the QR code with your authenticator app")


class TwoFactorVerifyRequest(BaseModel):
    """Request to verify and enable 2FA."""
    code: str = Field(..., min_length=6, max_length=6, description="6-digit TOTP code")


class TwoFactorStatusResponse(BaseModel):
    """Response for 2FA status check."""
    is_enabled: bool
    backup_codes_remaining: int
    last_used_at: datetime | None = None


class TwoFactorDisableRequest(BaseModel):
    """Request to disable 2FA."""
    code: str = Field(..., description="6-digit TOTP code or backup code")


@router.post(
    "/2fa/setup",
    response_model=TwoFactorSetupResponse,
    responses={
        400: {"model": ErrorResponse, "description": "2FA already enabled"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def setup_two_factor(
    current_user: CurrentUser,
    db: DbSession,
    trace_id: TraceId,
):
    """Set up two-factor authentication.
    
    Generates a new TOTP secret and backup codes.
    The user must verify with a code before 2FA is enabled.
    """
    # Check if 2FA is already set up
    query = select(UserTwoFactor).where(UserTwoFactor.user_id == current_user.id)
    result = await db.execute(query)
    existing = result.scalar_one_or_none()
    
    if existing and existing.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "2FA_ALREADY_ENABLED",
                    "message": "Two-factor authentication is already enabled",
                    "details": {},
                },
                "traceId": trace_id,
            },
        )
    
    # Generate new secret and backup codes
    two_factor_service = get_two_factor_service()
    setup = two_factor_service.generate_secret(current_user.id, current_user.email)
    
    # Hash backup codes for storage
    hashed_codes = two_factor_service.hash_backup_codes(setup.backup_codes)
    
    # Store or update the 2FA configuration (not enabled yet)
    if existing:
        existing.secret_encrypted = setup.secret
        existing.backup_codes_hash = json.dumps(hashed_codes)
        existing.backup_codes_remaining = len(setup.backup_codes)
        existing.is_enabled = False
    else:
        from uuid import uuid4
        new_2fa = UserTwoFactor(
            id=str(uuid4()),
            user_id=current_user.id,
            secret_encrypted=setup.secret,
            backup_codes_hash=json.dumps(hashed_codes),
            backup_codes_remaining=len(setup.backup_codes),
            is_enabled=False,
        )
        db.add(new_2fa)
    
    await db.commit()
    
    return TwoFactorSetupResponse(
        secret=setup.secret,
        qr_code_uri=setup.qr_code_uri,
        backup_codes=setup.backup_codes,
    )


@router.post(
    "/2fa/verify",
    response_model=SuccessResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid code or 2FA not set up"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def verify_and_enable_two_factor(
    request_body: TwoFactorVerifyRequest,
    current_user: CurrentUser,
    db: DbSession,
    trace_id: TraceId,
):
    """Verify TOTP code and enable two-factor authentication.
    
    Must be called after /2fa/setup to enable 2FA.
    """
    # Get the 2FA configuration
    query = select(UserTwoFactor).where(UserTwoFactor.user_id == current_user.id)
    result = await db.execute(query)
    two_factor = result.scalar_one_or_none()
    
    if not two_factor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "2FA_NOT_SETUP",
                    "message": "Two-factor authentication is not set up. Call /2fa/setup first.",
                    "details": {},
                },
                "traceId": trace_id,
            },
        )
    
    # Verify the code
    two_factor_service = get_two_factor_service()
    is_valid = two_factor_service.verify_code(two_factor.secret_encrypted, request_body.code)
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_2FA_CODE",
                    "message": "Invalid verification code",
                    "details": {},
                },
                "traceId": trace_id,
            },
        )
    
    # Enable 2FA
    two_factor.is_enabled = True
    two_factor.last_used_at = datetime.now(timezone.utc)
    await db.commit()
    
    return SuccessResponse(
        success=True,
        message="Two-factor authentication enabled successfully",
    )


@router.get(
    "/2fa/status",
    response_model=TwoFactorStatusResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def get_two_factor_status(
    current_user: CurrentUser,
    db: DbSession,
):
    """Get the current 2FA status for the user."""
    query = select(UserTwoFactor).where(UserTwoFactor.user_id == current_user.id)
    result = await db.execute(query)
    two_factor = result.scalar_one_or_none()
    
    if not two_factor:
        return TwoFactorStatusResponse(
            is_enabled=False,
            backup_codes_remaining=0,
        )
    
    return TwoFactorStatusResponse(
        is_enabled=two_factor.is_enabled,
        backup_codes_remaining=two_factor.backup_codes_remaining,
        last_used_at=two_factor.last_used_at,
    )


@router.delete(
    "/2fa",
    response_model=SuccessResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid code or 2FA not enabled"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def disable_two_factor(
    request_body: TwoFactorDisableRequest,
    current_user: CurrentUser,
    db: DbSession,
    trace_id: TraceId,
):
    """Disable two-factor authentication.
    
    Requires a valid TOTP code or backup code.
    """
    # Get the 2FA configuration
    query = select(UserTwoFactor).where(UserTwoFactor.user_id == current_user.id)
    result = await db.execute(query)
    two_factor = result.scalar_one_or_none()
    
    if not two_factor or not two_factor.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "2FA_NOT_ENABLED",
                    "message": "Two-factor authentication is not enabled",
                    "details": {},
                },
                "traceId": trace_id,
            },
        )
    
    two_factor_service = get_two_factor_service()
    
    # Try TOTP code first
    is_valid = two_factor_service.verify_code(two_factor.secret_encrypted, request_body.code)
    
    # If not valid, try backup code
    if not is_valid and two_factor.backup_codes_hash:
        hashed_codes = json.loads(two_factor.backup_codes_hash)
        is_valid, used_index = two_factor_service.verify_backup_code(request_body.code, hashed_codes)
        
        if is_valid and used_index is not None:
            # Remove used backup code
            hashed_codes.pop(used_index)
            two_factor.backup_codes_hash = json.dumps(hashed_codes)
            two_factor.backup_codes_remaining = len(hashed_codes)
            two_factor.last_backup_used_at = datetime.now(timezone.utc)
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_2FA_CODE",
                    "message": "Invalid verification code",
                    "details": {},
                },
                "traceId": trace_id,
            },
        )
    
    # Disable 2FA
    two_factor.is_enabled = False
    await db.commit()
    
    return SuccessResponse(
        success=True,
        message="Two-factor authentication disabled successfully",
    )
