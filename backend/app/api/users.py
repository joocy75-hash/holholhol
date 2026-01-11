"""User management API endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession, TraceId
from app.schemas import (
    ChangePasswordRequest,
    ErrorResponse,
    SuccessResponse,
    UpdateProfileRequest,
    UserProfileResponse,
    UserStatsResponse,
)
from app.services.user import UserError, UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserProfileResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def get_current_user_profile(
    current_user: CurrentUser,
):
    """Get current user's profile.

    Returns detailed profile information for the authenticated user.
    """
    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        nickname=current_user.nickname,
        avatar_url=current_user.avatar_url,
        status=current_user.status,
        total_hands=current_user.total_hands,
        total_winnings=current_user.total_winnings,
        created_at=current_user.created_at,
    )


@router.patch(
    "/me",
    response_model=UserProfileResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        409: {"model": ErrorResponse, "description": "Nickname already taken"},
    },
)
async def update_profile(
    request_body: UpdateProfileRequest,
    current_user: CurrentUser,
    db: DbSession,
    trace_id: TraceId,
):
    """Update current user's profile.

    Updates the nickname and/or avatar URL for the authenticated user.
    """
    user_service = UserService(db)

    try:
        updated_user = await user_service.update_profile(
            user_id=current_user.id,
            nickname=request_body.nickname,
            avatar_url=request_body.avatar_url,
        )

        return UserProfileResponse(
            id=updated_user.id,
            email=updated_user.email,
            nickname=updated_user.nickname,
            avatar_url=updated_user.avatar_url,
            status=updated_user.status,
            total_hands=updated_user.total_hands,
            total_winnings=updated_user.total_winnings,
            created_at=updated_user.created_at,
        )

    except UserError as e:
        status_code = status.HTTP_400_BAD_REQUEST
        if "NICKNAME_EXISTS" in e.code:
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
    "/me/password",
    response_model=SuccessResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid current password"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def change_password(
    request_body: ChangePasswordRequest,
    current_user: CurrentUser,
    db: DbSession,
    trace_id: TraceId,
):
    """Change current user's password.

    Requires the current password for verification.
    """
    user_service = UserService(db)

    try:
        await user_service.change_password(
            user_id=current_user.id,
            current_password=request_body.current_password,
            new_password=request_body.new_password,
        )

        return SuccessResponse(
            success=True,
            message="Password changed successfully",
        )

    except UserError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": e.details,
                },
                "traceId": trace_id,
            },
        )


@router.get(
    "/me/stats",
    response_model=UserStatsResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def get_current_user_stats(
    current_user: CurrentUser,
    db: DbSession,
):
    """Get current user's game statistics.

    Returns detailed statistics including hands played, winnings, and performance metrics.
    """
    user_service = UserService(db)
    stats = await user_service.get_user_stats(current_user.id)

    return UserStatsResponse(
        total_hands=stats["total_hands"],
        total_winnings=stats["total_winnings"],
        hands_won=stats["hands_won"],
        biggest_pot=stats["biggest_pot"],
        vpip=stats["vpip"],
        pfr=stats["pfr"],
    )


@router.delete(
    "/me",
    response_model=SuccessResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def deactivate_account(
    current_user: CurrentUser,
    db: DbSession,
):
    """Deactivate current user's account.

    This soft-deletes the account. The user will no longer be able to log in.
    """
    user_service = UserService(db)
    await user_service.deactivate_user(current_user.id)

    return SuccessResponse(
        success=True,
        message="Account deactivated successfully",
    )


@router.get(
    "/{user_id}",
    response_model=UserProfileResponse,
    responses={
        404: {"model": ErrorResponse, "description": "User not found"},
    },
)
async def get_user_profile(
    user_id: str,
    db: DbSession,
    trace_id: TraceId,
):
    """Get a user's public profile.

    Returns public profile information for any user.
    Note: Email is not included in public profiles for privacy.
    """
    user_service = UserService(db)
    user = await user_service.get_user(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "USER_NOT_FOUND",
                    "message": "User not found",
                    "details": {},
                },
                "traceId": trace_id,
            },
        )

    # Return limited info for public profile
    return UserProfileResponse(
        id=user.id,
        email="***@***.***",  # Hide email for privacy
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        status=user.status,
        total_hands=user.total_hands,
        total_winnings=user.total_winnings,
        created_at=user.created_at,
    )
