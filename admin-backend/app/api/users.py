"""
Users API - 사용자 조회 및 관리 엔드포인트
"""
from datetime import datetime
from typing import Optional, Literal
from fastapi import APIRouter, Query, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_main_db, get_admin_db
from app.utils.dependencies import require_viewer, require_operator, require_supervisor
from app.models.admin_user import AdminUser
from app.services.user_service import (
    UserService,
    UserNotFoundError,
    InsufficientBalanceError,
    UserServiceError
)
from app.services.audit_service import AuditService


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


# 통합 활동 로그 Models
class ActivityItem(BaseModel):
    """통합 활동 로그 항목"""
    id: str
    activity_type: Literal["login", "transaction", "hand"]
    description: str | None
    amount: float | None = None
    ip_address: str | None = None
    device_info: str | None = None
    room_id: str | None = None
    hand_id: str | None = None
    created_at: str | None


class PaginatedActivity(BaseModel):
    """통합 활동 로그 페이지네이션 응답"""
    items: list[ActivityItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# 자산 관리 Request/Response Models
class ChipTransactionRequest(BaseModel):
    """칩 지급/회수 요청"""
    amount: float = Field(..., gt=0, description="금액 (양수)")
    reason: str = Field(..., min_length=1, max_length=500, description="사유")


class ChipTransactionResponse(BaseModel):
    """칩 지급/회수 응답"""
    transaction_id: str
    user_id: str
    username: str
    type: str  # credit / debit
    amount: float
    balance_before: float
    balance_after: float
    reason: str
    admin_user_id: str
    admin_username: str
    created_at: str


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


@router.get("/{user_id}/activity", response_model=PaginatedActivity)
async def get_user_activity(
    user_id: str,
    activity_type: Optional[Literal["login", "transaction", "hand"]] = Query(
        None, description="활동 타입 필터 (login, transaction, hand)"
    ),
    start_date: Optional[datetime] = Query(None, description="시작 날짜 (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="종료 날짜 (ISO 8601)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AdminUser = Depends(require_viewer),
    db: AsyncSession = Depends(get_main_db),
):
    """
    사용자 통합 활동 로그 조회

    로그인 기록, 거래 내역, 핸드 기록을 통합하여 시간순으로 조회합니다.

    필터 옵션:
    - activity_type: login, transaction, hand 중 선택
    - start_date/end_date: 날짜 범위 필터 (ISO 8601 형식)
    """
    service = UserService(db)
    result = await service.get_user_activity(
        user_id=user_id,
        page=page,
        page_size=page_size,
        activity_type=activity_type,
        start_date=start_date,
        end_date=end_date
    )
    return PaginatedActivity(**result)


@router.post("/{user_id}/credit", response_model=ChipTransactionResponse)
async def credit_chips(
    user_id: str,
    request: ChipTransactionRequest,
    current_user: AdminUser = Depends(require_supervisor),
    main_db: AsyncSession = Depends(get_main_db),
    admin_db: AsyncSession = Depends(get_admin_db),
):
    """
    칩 지급 (supervisor 이상 권한 필요)

    사용자에게 칩을 지급합니다. 고객 보상, 이벤트 지급, 오류 수정 등에 사용됩니다.
    모든 지급 내역은 트랜잭션 및 감사 로그에 기록됩니다.
    """
    user_service = UserService(main_db)
    audit_service = AuditService(admin_db)

    try:
        # 칩 지급 처리
        result = await user_service.credit_chips(
            user_id=user_id,
            amount=request.amount,
            reason=request.reason,
            admin_user_id=str(current_user.id),
            admin_username=current_user.username
        )

        # 감사 로그 기록
        await audit_service.log_action(
            admin_user_id=str(current_user.id),
            admin_username=current_user.username,
            action="credit_chips",
            target_type="user",
            target_id=user_id,
            details={
                "amount": request.amount,
                "reason": request.reason,
                "balance_before": result["balance_before"],
                "balance_after": result["balance_after"],
                "transaction_id": result["transaction_id"]
            }
        )

        return ChipTransactionResponse(**result)

    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except UserServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{user_id}/debit", response_model=ChipTransactionResponse)
async def debit_chips(
    user_id: str,
    request: ChipTransactionRequest,
    current_user: AdminUser = Depends(require_supervisor),
    main_db: AsyncSession = Depends(get_main_db),
    admin_db: AsyncSession = Depends(get_admin_db),
):
    """
    칩 회수 (supervisor 이상 권한 필요)

    사용자로부터 칩을 회수합니다. 부정 행위 대응, 오류 수정 등에 사용됩니다.
    잔액이 부족한 경우 에러가 발생합니다.
    모든 회수 내역은 트랜잭션 및 감사 로그에 기록됩니다.
    """
    user_service = UserService(main_db)
    audit_service = AuditService(admin_db)

    try:
        # 칩 회수 처리
        result = await user_service.debit_chips(
            user_id=user_id,
            amount=request.amount,
            reason=request.reason,
            admin_user_id=str(current_user.id),
            admin_username=current_user.username
        )

        # 감사 로그 기록
        await audit_service.log_action(
            admin_user_id=str(current_user.id),
            admin_username=current_user.username,
            action="debit_chips",
            target_type="user",
            target_id=user_id,
            details={
                "amount": request.amount,
                "reason": request.reason,
                "balance_before": result["balance_before"],
                "balance_after": result["balance_after"],
                "transaction_id": result["transaction_id"]
            }
        )

        return ChipTransactionResponse(**result)

    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except InsufficientBalanceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except UserServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
