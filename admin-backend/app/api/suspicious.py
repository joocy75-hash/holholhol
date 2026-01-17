"""
Suspicious Users API - 의심 사용자 조회 및 검토 엔드포인트

Phase 3.7: 부정 사용자 의심 리스트
"""
from typing import Optional, Literal
from fastapi import APIRouter, Query, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_main_db, get_admin_db
from app.utils.dependencies import require_viewer, require_operator, require_supervisor
from app.models.admin_user import AdminUser
from app.services.suspicious_user_service import SuspiciousUserService
from app.services.audit_service import AuditService


router = APIRouter()


# Response Models
class DetectionBreakdown(BaseModel):
    chip_dumping: int = 0
    bot_detection: int = 0
    anomaly_detection: int = 0


class SuspiciousUserItem(BaseModel):
    user_id: str
    username: str
    email: Optional[str] = None
    is_banned: bool = False
    suspicion_score: float
    detection_count: int
    pending_count: int
    confirmed_count: int
    max_severity: str
    detection_breakdown: DetectionBreakdown
    last_detected: Optional[str] = None


class PaginatedSuspiciousUsers(BaseModel):
    items: list[SuspiciousUserItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class SuspicionSummary(BaseModel):
    total_suspicious_users: int
    users_with_pending: int
    users_with_confirmed: int
    by_severity: dict


class StatisticsDetail(BaseModel):
    total_detections: int
    pending: int
    reviewing: int
    confirmed: int
    dismissed: int
    by_type: dict
    by_severity: dict


class ActivityItem(BaseModel):
    id: int
    detection_type: str
    severity: str
    status: str
    details: dict
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    reviewed_by: Optional[str] = None


class SuspiciousUserDetail(BaseModel):
    user_id: str
    username: Optional[str] = None
    email: Optional[str] = None
    balance: float = 0
    is_banned: bool = False
    ban_reason: Optional[str] = None
    created_at: Optional[str] = None
    last_login: Optional[str] = None
    suspicion_score: float
    statistics: StatisticsDetail
    activities: list[ActivityItem]


class UserInfo(BaseModel):
    user_id: str
    username: str
    is_banned: bool = False


class ActivityDetail(BaseModel):
    id: int
    detection_type: str
    user_ids: list[str]
    users: list[UserInfo]
    details: dict
    severity: str
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_notes: Optional[str] = None


class ReviewStatusUpdate(BaseModel):
    status: Literal["pending", "reviewing", "confirmed", "dismissed"]
    notes: Optional[str] = Field(None, max_length=1000)


class ReviewStatusResponse(BaseModel):
    id: int
    detection_type: str
    severity: str
    status: str
    reviewed_by: str
    reviewed_at: str
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# API Endpoints

@router.get("", response_model=PaginatedSuspiciousUsers)
async def get_suspicious_users(
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    detection_type: Optional[str] = Query(
        None,
        description="탐지 유형 필터 (chip_dumping, bot_detection, anomaly_detection)"
    ),
    severity: Optional[str] = Query(
        None,
        description="심각도 필터 (low, medium, high)"
    ),
    status: Optional[str] = Query(
        None,
        description="검토 상태 필터 (pending, reviewing, confirmed, dismissed)"
    ),
    min_score: Optional[float] = Query(
        None,
        ge=0,
        description="최소 의심 점수"
    ),
    sort_by: str = Query(
        "suspicion_score",
        description="정렬 기준 (suspicion_score, detection_count, last_detected)"
    ),
    sort_order: str = Query("desc", description="정렬 순서 (asc, desc)"),
    main_db: AsyncSession = Depends(get_main_db),
    admin_db: AsyncSession = Depends(get_admin_db),
    _: AdminUser = Depends(require_viewer),
):
    """
    의심 사용자 목록 조회

    사용자별로 집계된 의심 활동 정보를 조회합니다.
    의심 점수, 탐지 횟수, 심각도 등으로 정렬/필터링할 수 있습니다.
    """
    service = SuspiciousUserService(main_db, admin_db)
    result = await service.get_suspicious_users(
        page=page,
        page_size=page_size,
        detection_type=detection_type,
        severity=severity,
        status=status,
        min_score=min_score,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return result


@router.get("/summary", response_model=SuspicionSummary)
async def get_suspicion_summary(
    admin_db: AsyncSession = Depends(get_admin_db),
    main_db: AsyncSession = Depends(get_main_db),
    _: AdminUser = Depends(require_viewer),
):
    """
    의심 사용자 요약 통계 조회

    전체 의심 사용자 수, 검토 대기 수, 확인된 수, 심각도별 분포 등을 반환합니다.
    """
    service = SuspiciousUserService(main_db, admin_db)
    return await service.get_suspicion_summary()


@router.get("/users/{user_id}", response_model=SuspiciousUserDetail)
async def get_suspicious_user_detail(
    user_id: str,
    main_db: AsyncSession = Depends(get_main_db),
    admin_db: AsyncSession = Depends(get_admin_db),
    _: AdminUser = Depends(require_viewer),
):
    """
    의심 사용자 상세 정보 조회

    특정 사용자의 모든 의심 활동 기록과 통계를 반환합니다.
    """
    service = SuspiciousUserService(main_db, admin_db)
    result = await service.get_suspicious_user_detail(user_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"사용자를 찾을 수 없습니다: {user_id}"
        )

    return result


@router.get("/activities/{activity_id}", response_model=ActivityDetail)
async def get_activity_detail(
    activity_id: int,
    main_db: AsyncSession = Depends(get_main_db),
    admin_db: AsyncSession = Depends(get_admin_db),
    _: AdminUser = Depends(require_viewer),
):
    """
    의심 활동 상세 조회

    특정 의심 활동의 상세 정보를 조회합니다.
    """
    service = SuspiciousUserService(main_db, admin_db)
    result = await service.get_activity_detail(activity_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"활동을 찾을 수 없습니다: {activity_id}"
        )

    return result


@router.patch("/activities/{activity_id}/review", response_model=ReviewStatusResponse)
async def update_review_status(
    activity_id: int,
    body: ReviewStatusUpdate,
    main_db: AsyncSession = Depends(get_main_db),
    admin_db: AsyncSession = Depends(get_admin_db),
    current_user: AdminUser = Depends(require_operator),
):
    """
    의심 활동 검토 상태 업데이트

    관리자가 의심 활동을 검토하고 상태를 변경합니다.
    - pending: 검토 대기
    - reviewing: 검토 중
    - confirmed: 부정 행위 확인됨
    - dismissed: 오탐으로 처리됨
    """
    service = SuspiciousUserService(main_db, admin_db)

    try:
        result = await service.update_review_status(
            activity_id=activity_id,
            status=body.status,
            admin_user_id=str(current_user.id),
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"활동을 찾을 수 없습니다: {activity_id}"
        )

    # 감사 로그 기록
    audit_service = AuditService(admin_db)
    await audit_service.log_action(
        user_id=str(current_user.id),
        action="update_review_status",
        resource_type="suspicious_activity",
        resource_id=str(activity_id),
        details={
            "new_status": body.status,
            "notes": body.notes,
        },
    )

    return result


@router.get("/detection-types")
async def get_detection_types(
    _: AdminUser = Depends(require_viewer),
):
    """
    탐지 유형 목록 조회

    필터링에 사용할 수 있는 탐지 유형 목록을 반환합니다.
    """
    return {
        "detection_types": [
            {"value": "chip_dumping", "label": "칩 밀어주기", "weight": 40},
            {"value": "bot_detection", "label": "봇 탐지", "weight": 35},
            {"value": "anomaly_detection", "label": "이상 행동", "weight": 25},
            {"value": "auto_detection", "label": "종합 탐지", "weight": 30},
        ],
        "severities": [
            {"value": "low", "label": "낮음", "multiplier": 1.0},
            {"value": "medium", "label": "중간", "multiplier": 1.5},
            {"value": "high", "label": "높음", "multiplier": 2.5},
        ],
        "statuses": [
            {"value": "pending", "label": "검토 대기"},
            {"value": "reviewing", "label": "검토 중"},
            {"value": "confirmed", "label": "부정 확인"},
            {"value": "dismissed", "label": "오탐 처리"},
        ],
    }
