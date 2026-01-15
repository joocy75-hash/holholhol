"""
Users API - 사용자 조회 및 관리 엔드포인트
"""
from fastapi import APIRouter, Query, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_main_db
from app.utils.dependencies import require_viewer, require_operator
from app.models.admin_user import AdminUser
from app.services.user_service import UserService


router = APIRouter()


# Response Models
class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    balance: float
    created_at: str | None
    last_login: str | None
    is_banned: bool


class UserDetailResponse(UserResponse):
    ban_reason: str | None = None
    ban_expires_at: str | None = None


class PaginatedUsers(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class TransactionItem(BaseModel):
    id: str
    type: str
    amount: float
    balance_before: float
    balance_after: float
    description: str | None
    created_at: str | None


class PaginatedTransactions(BaseModel):
    items: list[TransactionItem]
    total: int
    page: int
    page_size: int


class LoginHistoryItem(BaseModel):
    id: str
    ip_address: str | None
    user_agent: str | None
    success: bool
    created_at: str | None


class PaginatedLoginHistory(BaseModel):
    items: list[LoginHistoryItem]
    total: int
    page: int
    page_size: int


class HandHistoryItem(BaseModel):
    id: str
    hand_id: str
    room_id: str | None
    position: int | None
    cards: str | None
    bet_amount: float
    won_amount: float
    pot_size: float
    created_at: str | None


class PaginatedHandHistory(BaseModel):
    items: list[HandHistoryItem]
    total: int
    page: int
    page_size: int


# Endpoints
@router.get("", response_model=PaginatedUsers)
async def list_users(
    search: Optional[str] = Query(None, description="Search by username, email, or ID"),
    is_banned: Optional[bool] = Query(None, description="Filter by ban status"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AdminUser = Depends(require_viewer),
    db: AsyncSession = Depends(get_main_db),
):
    """List users with search and pagination"""
    service = UserService(db)
    result = await service.search_users(
        search=search,
        page=page,
        page_size=page_size,
        is_banned=is_banned,
        sort_by=sort_by,
        sort_order=sort_order
    )
    return PaginatedUsers(**result)


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user(
    user_id: str,
    current_user: AdminUser = Depends(require_viewer),
    db: AsyncSession = Depends(get_main_db),
):
    """Get user details"""
    service = UserService(db)
    user = await service.get_user_detail(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserDetailResponse(**user)


@router.get("/{user_id}/transactions", response_model=PaginatedTransactions)
async def get_user_transactions(
    user_id: str,
    tx_type: Optional[str] = Query(None, description="Filter by transaction type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AdminUser = Depends(require_viewer),
    db: AsyncSession = Depends(get_main_db),
):
    """Get user transaction history"""
    service = UserService(db)
    result = await service.get_user_transactions(
        user_id=user_id,
        page=page,
        page_size=page_size,
        tx_type=tx_type
    )
    return PaginatedTransactions(**result)


@router.get("/{user_id}/login-history", response_model=PaginatedLoginHistory)
async def get_user_login_history(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AdminUser = Depends(require_viewer),
    db: AsyncSession = Depends(get_main_db),
):
    """Get user login history"""
    service = UserService(db)
    result = await service.get_user_login_history(
        user_id=user_id,
        page=page,
        page_size=page_size
    )
    return PaginatedLoginHistory(**result)


@router.get("/{user_id}/hands", response_model=PaginatedHandHistory)
async def get_user_hands(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AdminUser = Depends(require_viewer),
    db: AsyncSession = Depends(get_main_db),
):
    """Get user hand history"""
    service = UserService(db)
    result = await service.get_user_hands(
        user_id=user_id,
        page=page,
        page_size=page_size
    )
    return PaginatedHandHistory(**result)
