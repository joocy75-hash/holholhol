"""Authentication API endpoints."""

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

router = APIRouter(prefix="/auth", tags=["Authentication"])


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
            email=request_body.email,
            password=request_body.password,
            nickname=request_body.nickname,
            user_agent=client_info["user_agent"],
            ip_address=client_info["ip_address"],
        )

        return RegisterResponse(
            user=UserBasicResponse(
                id=result["user"]["id"],
                nickname=result["user"]["nickname"],
                avatar_url=result["user"]["avatar_url"],
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
        if "EMAIL_EXISTS" in e.code or "NICKNAME_EXISTS" in e.code:
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
    },
)
async def login(
    request_body: LoginRequest,
    request: Request,
    db: DbSession,
    trace_id: TraceId,
):
    """Authenticate user and return tokens.

    Validates email and password, creates a new session,
    and returns access and refresh tokens.
    """
    client_info = get_client_info(request)
    auth_service = AuthService(db)

    try:
        result = await auth_service.login(
            email=request_body.email,
            password=request_body.password,
            user_agent=client_info["user_agent"],
            ip_address=client_info["ip_address"],
        )

        return LoginResponse(
            user=UserBasicResponse(
                id=result["user"]["id"],
                nickname=result["user"]["nickname"],
                avatar_url=result["user"]["avatar_url"],
            ),
            tokens=TokenResponse(
                access_token=result["tokens"]["access_token"],
                refresh_token=result["tokens"]["refresh_token"],
                token_type=result["tokens"]["token_type"],
                expires_in=result["tokens"]["expires_in"],
            ),
        )

    except AuthError as e:
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
