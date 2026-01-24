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
    UserServiceError,
    DuplicateEmailError,
    DuplicateNicknameError,
)
from app.services.audit_service import AuditService


router = APIRouter()


# Response Models
class UserResponse(BaseModel):
    id: str
    username: str  # 로그인 아이디
    nickname: str | None = None  # 표시 이름
    email: str
    balance: float
    created_at: str | None
    last_login: str | None
    is_banned: bool


class UserDetailResponse(UserResponse):
    nickname: str | None = None  # 표시 이름 (username과 별개)
    partner_code: str | None = None  # 추천인 파트너 코드
    partner_name: str | None = None  # 추천인 파트너 이름
    usdt_wallet_address: str | None = None  # USDT 지갑 주소
    usdt_wallet_type: str | None = None  # 지갑 타입 (TRC20/ERC20)
    krw_balance: int = 0  # KRW 잔액
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


# 사용자 관리 Request/Response Models
class CreateUserRequest(BaseModel):
    """사용자 생성 요청"""
    nickname: str = Field(..., min_length=2, max_length=50, description="닉네임")
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$', description="이메일")
    password: str = Field(..., min_length=8, description="비밀번호")
    balance: int = Field(default=10000, ge=0, description="초기 잔액")


class CreateUserResponse(BaseModel):
    """사용자 생성 응답"""
    id: str
    username: str
    email: str
    balance: float
    status: str
    created_at: str


class UpdateStatusRequest(BaseModel):
    """상태 변경 요청"""
    status: Literal['active', 'suspended']


class UpdateStatusResponse(BaseModel):
    """상태 변경 응답"""
    id: str
    username: str
    email: str
    status: str


class ResetPasswordRequest(BaseModel):
    """비밀번호 초기화 요청"""
    new_password: str = Field(..., min_length=8, description="새 비밀번호")


class ResetPasswordResponse(BaseModel):
    """비밀번호 초기화 응답"""
    id: str
    username: str
    email: str
    message: str = "비밀번호가 초기화되었습니다"


class UpdateUserRequest(BaseModel):
    """사용자 프로필 수정 요청"""
    nickname: Optional[str] = Field(None, min_length=2, max_length=50, description="새 닉네임")
    email: Optional[str] = Field(None, description="새 이메일")


class UpdateUserResponse(BaseModel):
    """사용자 프로필 수정 응답"""
    id: str
    username: str
    email: str
    balance: float
    status: str
    created_at: str | None


class DeleteUserResponse(BaseModel):
    """사용자 삭제 응답"""
    id: str
    username: str
    email: str
    status: str
    message: str = "사용자가 삭제되었습니다"


# Response Model for /me endpoint
class AdminUserMeResponse(BaseModel):
    """현재 로그인한 관리자 정보"""
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    last_login: str | None
    created_at: str | None


# Endpoints
@router.get("/me", response_model=AdminUserMeResponse)
async def get_current_user(
    current_user: AdminUser = Depends(require_viewer),
):
    """
    현재 로그인한 관리자 정보 조회

    JWT 토큰에서 추출한 현재 사용자 정보를 반환합니다.
    """
    return AdminUserMeResponse(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        role=current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role),
        is_active=current_user.is_active,
        last_login=current_user.last_login.isoformat() if current_user.last_login else None,
        created_at=current_user.created_at.isoformat() if current_user.created_at else None,
    )


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
    try:
        result = await service.search_users(
            search=search,
            page=page,
            page_size=page_size,
            is_banned=is_banned,
            sort_by=sort_by,
            sort_order=sort_order
        )
        return PaginatedUsers(**result)
    except UserServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user(
    user_id: str,
    current_user: AdminUser = Depends(require_viewer),
    db: AsyncSession = Depends(get_main_db),
):
    """Get user details"""
    service = UserService(db)
    try:
        user = await service.get_user_detail(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserDetailResponse(**user)
    except UserServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


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
    try:
        result = await service.get_user_transactions(
            user_id=user_id,
            page=page,
            page_size=page_size,
            tx_type=tx_type
        )
        return PaginatedTransactions(**result)
    except UserServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


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
    try:
        result = await service.get_user_login_history(
            user_id=user_id,
            page=page,
            page_size=page_size
        )
        return PaginatedLoginHistory(**result)
    except UserServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


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
    try:
        result = await service.get_user_hands(
            user_id=user_id,
            page=page,
            page_size=page_size
        )
        return PaginatedHandHistory(**result)
    except UserServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


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
    try:
        result = await service.get_user_activity(
            user_id=user_id,
            page=page,
            page_size=page_size,
            activity_type=activity_type,
            start_date=start_date,
            end_date=end_date
        )
        return PaginatedActivity(**result)
    except UserServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


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


# 사용자 관리 엔드포인트
@router.post("", response_model=CreateUserResponse)
async def create_user(
    request: CreateUserRequest,
    current_user: AdminUser = Depends(require_supervisor),
    main_db: AsyncSession = Depends(get_main_db),
    admin_db: AsyncSession = Depends(get_admin_db),
):
    """
    사용자 생성 (supervisor 이상 권한 필요)

    새로운 사용자를 생성합니다.
    """
    user_service = UserService(main_db)
    audit_service = AuditService(admin_db)

    try:
        result = await user_service.create_user(
            nickname=request.nickname,
            email=request.email,
            password=request.password,
            balance=request.balance
        )

        # 감사 로그 기록
        await audit_service.log_action(
            admin_user_id=str(current_user.id),
            admin_username=current_user.username,
            action="create_user",
            target_type="user",
            target_id=result["id"],
            details={
                "nickname": request.nickname,
                "email": request.email,
                "balance": request.balance
            }
        )

        return CreateUserResponse(**result)

    except DuplicateEmailError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except DuplicateNicknameError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except UserServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{user_id}", response_model=DeleteUserResponse)
async def delete_user(
    user_id: str,
    current_user: AdminUser = Depends(require_supervisor),
    main_db: AsyncSession = Depends(get_main_db),
    admin_db: AsyncSession = Depends(get_admin_db),
):
    """
    사용자 삭제 (supervisor 이상 권한 필요)

    사용자를 soft-delete 처리합니다 (status='deleted').
    """
    user_service = UserService(main_db)
    audit_service = AuditService(admin_db)

    try:
        result = await user_service.delete_user(user_id)

        # 감사 로그 기록
        await audit_service.log_action(
            admin_user_id=str(current_user.id),
            admin_username=current_user.username,
            action="delete_user",
            target_type="user",
            target_id=user_id,
            details={
                "username": result["username"],
                "email": result["email"]
            }
        )

        return DeleteUserResponse(**result)

    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except UserServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch("/{user_id}/status", response_model=UpdateStatusResponse)
async def update_user_status(
    user_id: str,
    request: UpdateStatusRequest,
    current_user: AdminUser = Depends(require_operator),
    main_db: AsyncSession = Depends(get_main_db),
    admin_db: AsyncSession = Depends(get_admin_db),
):
    """
    사용자 상태 변경 (operator 이상 권한 필요)

    사용자의 상태를 active 또는 suspended로 변경합니다.
    """
    user_service = UserService(main_db)
    audit_service = AuditService(admin_db)

    try:
        result = await user_service.update_status(user_id, request.status)

        # 감사 로그 기록
        await audit_service.log_action(
            admin_user_id=str(current_user.id),
            admin_username=current_user.username,
            action="update_user_status",
            target_type="user",
            target_id=user_id,
            details={
                "new_status": request.status
            }
        )

        return UpdateStatusResponse(**result)

    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except UserServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{user_id}/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    user_id: str,
    request: ResetPasswordRequest,
    current_user: AdminUser = Depends(require_supervisor),
    main_db: AsyncSession = Depends(get_main_db),
    admin_db: AsyncSession = Depends(get_admin_db),
):
    """
    비밀번호 초기화 (supervisor 이상 권한 필요)

    사용자의 비밀번호를 새로운 비밀번호로 초기화합니다.
    """
    user_service = UserService(main_db)
    audit_service = AuditService(admin_db)

    try:
        result = await user_service.reset_password(user_id, request.new_password)

        # 감사 로그 기록
        await audit_service.log_action(
            admin_user_id=str(current_user.id),
            admin_username=current_user.username,
            action="reset_password",
            target_type="user",
            target_id=user_id,
            details={}  # 비밀번호는 기록하지 않음
        )

        return ResetPasswordResponse(**result)

    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except UserServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/{user_id}", response_model=UpdateUserResponse)
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    current_user: AdminUser = Depends(require_operator),
    main_db: AsyncSession = Depends(get_main_db),
    admin_db: AsyncSession = Depends(get_admin_db),
):
    """
    사용자 프로필 수정 (operator 이상 권한 필요)

    사용자의 닉네임 또는 이메일을 수정합니다.
    """
    user_service = UserService(main_db)
    audit_service = AuditService(admin_db)

    try:
        result = await user_service.update_user(
            user_id,
            nickname=request.nickname,
            email=request.email
        )

        # 감사 로그 기록
        await audit_service.log_action(
            admin_user_id=str(current_user.id),
            admin_username=current_user.username,
            action="update_user",
            target_type="user",
            target_id=user_id,
            details={
                "nickname": request.nickname,
                "email": request.email
            }
        )

        return UpdateUserResponse(**result)

    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except DuplicateEmailError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except DuplicateNicknameError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
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
