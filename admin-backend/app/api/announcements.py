"""
공지사항 API - CRUD 및 브로드캐스트 엔드포인트
"""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Query, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.config import get_settings
from app.database import get_admin_db
from app.utils.dependencies import require_admin, require_supervisor
from app.models.admin_user import AdminUser
from app.models.announcement import (
    AnnouncementType,
    AnnouncementPriority,
    AnnouncementTarget,
)
from app.services.announcement_service import AnnouncementService
from app.services.audit_service import AuditService

router = APIRouter()
settings = get_settings()

# Redis 클라이언트 (의존성 주입용)
_redis_client: Redis | None = None


async def get_redis() -> Redis | None:
    """Redis 클라이언트 의존성"""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
        except Exception:
            return None
    return _redis_client


# ============================================================================
# Request/Response Models
# ============================================================================


class AnnouncementCreateRequest(BaseModel):
    """공지사항 생성 요청"""
    title: str = Field(..., min_length=1, max_length=200, description="공지 제목")
    content: str = Field(..., min_length=1, description="공지 내용")
    announcement_type: AnnouncementType = Field(
        default=AnnouncementType.NOTICE,
        description="공지 유형"
    )
    priority: AnnouncementPriority = Field(
        default=AnnouncementPriority.NORMAL,
        description="우선순위"
    )
    target: AnnouncementTarget = Field(
        default=AnnouncementTarget.ALL,
        description="대상"
    )
    target_room_id: str | None = Field(
        default=None,
        description="특정 방 ID (target이 specific_room인 경우)"
    )
    start_time: datetime | None = Field(
        default=None,
        description="시작 시간 (없으면 즉시 활성화)"
    )
    end_time: datetime | None = Field(
        default=None,
        description="종료 시간 (없으면 무기한)"
    )
    scheduled_at: datetime | None = Field(
        default=None,
        description="예약 발송 시간"
    )
    broadcast_immediately: bool = Field(
        default=False,
        description="생성 시 즉시 브로드캐스트 여부"
    )


class AnnouncementUpdateRequest(BaseModel):
    """공지사항 수정 요청"""
    title: str | None = Field(None, min_length=1, max_length=200)
    content: str | None = Field(None, min_length=1)
    announcement_type: AnnouncementType | None = None
    priority: AnnouncementPriority | None = None
    target: AnnouncementTarget | None = None
    target_room_id: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    scheduled_at: datetime | None = None


class AnnouncementResponse(BaseModel):
    """공지사항 응답"""
    id: str
    title: str
    content: str
    announcement_type: str
    priority: str
    target: str
    target_room_id: str | None
    start_time: str | None
    end_time: str | None
    scheduled_at: str | None
    broadcasted_at: str | None
    broadcast_count: int
    created_by: str
    created_at: str | None
    updated_at: str | None
    is_active: bool


class PaginatedAnnouncements(BaseModel):
    """페이지네이션된 공지사항 목록"""
    items: list[AnnouncementResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class BroadcastResponse(BaseModel):
    """브로드캐스트 응답"""
    success: bool
    channel: str | None = None
    broadcast_count: int | None = None
    error: str | None = None


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
async def create_announcement(
    request: AnnouncementCreateRequest,
    current_user: AdminUser = Depends(require_supervisor),
    db: AsyncSession = Depends(get_admin_db),
    redis: Redis | None = Depends(get_redis),
):
    """
    공지사항 생성 (supervisor 이상 권한)

    - target이 specific_room인 경우 target_room_id 필수
    - broadcast_immediately=true인 경우 생성 즉시 WebSocket 브로드캐스트
    """
    # SPECIFIC_ROOM인 경우 room_id 검증
    if request.target == AnnouncementTarget.SPECIFIC_ROOM and not request.target_room_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target이 specific_room인 경우 target_room_id가 필요합니다"
        )

    service = AnnouncementService(db, redis)
    announcement = await service.create_announcement(
        title=request.title,
        content=request.content,
        created_by=str(current_user.id),
        announcement_type=request.announcement_type,
        priority=request.priority,
        target=request.target,
        target_room_id=request.target_room_id,
        start_time=request.start_time,
        end_time=request.end_time,
        scheduled_at=request.scheduled_at,
    )

    # 감사 로그
    audit_service = AuditService(db)
    await audit_service.log_action(
        admin_user_id=str(current_user.id),
        action="create_announcement",
        target_type="announcement",
        target_id=announcement.id,
        details={
            "title": announcement.title,
            "type": announcement.announcement_type.value,
            "priority": announcement.priority.value,
            "target": announcement.target.value,
        },
    )

    # 즉시 브로드캐스트 옵션
    if request.broadcast_immediately:
        await service.broadcast_announcement(announcement.id)

    return AnnouncementResponse(**service._to_dict(announcement))


@router.get("", response_model=PaginatedAnnouncements)
async def list_announcements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    announcement_type: AnnouncementType | None = Query(None, description="유형 필터"),
    priority: AnnouncementPriority | None = Query(None, description="우선순위 필터"),
    target: AnnouncementTarget | None = Query(None, description="대상 필터"),
    include_expired: bool = Query(False, description="만료된 공지 포함 여부"),
    current_user: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_admin_db),
):
    """
    공지사항 목록 조회 (관리자 권한)

    - 우선순위 높은 순 → 생성일 최신순 정렬
    - include_expired=false인 경우 만료된 공지 제외
    """
    service = AnnouncementService(db)
    result = await service.list_announcements(
        page=page,
        page_size=page_size,
        announcement_type=announcement_type,
        priority=priority,
        target=target,
        include_expired=include_expired,
    )
    return PaginatedAnnouncements(**result)


@router.get("/active", response_model=list[AnnouncementResponse])
async def get_active_announcements(
    target: AnnouncementTarget | None = Query(None),
    room_id: str | None = Query(None, description="방 ID (해당 방 공지 포함)"),
    current_user: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_admin_db),
):
    """현재 활성화된 공지사항 목록 조회"""
    service = AnnouncementService(db)
    items = await service.get_active_announcements(target=target, room_id=room_id)
    return [AnnouncementResponse(**item) for item in items]


@router.get("/{announcement_id}", response_model=AnnouncementResponse)
async def get_announcement(
    announcement_id: str,
    current_user: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_admin_db),
):
    """공지사항 상세 조회"""
    service = AnnouncementService(db)
    announcement = await service.get_announcement(announcement_id)

    if not announcement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="공지사항을 찾을 수 없습니다"
        )

    return AnnouncementResponse(**service._to_dict(announcement))


@router.put("/{announcement_id}", response_model=AnnouncementResponse)
async def update_announcement(
    announcement_id: str,
    request: AnnouncementUpdateRequest,
    current_user: AdminUser = Depends(require_supervisor),
    db: AsyncSession = Depends(get_admin_db),
):
    """공지사항 수정 (supervisor 이상 권한)"""
    service = AnnouncementService(db)

    # 기존 공지 확인
    existing = await service.get_announcement(announcement_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="공지사항을 찾을 수 없습니다"
        )

    # SPECIFIC_ROOM으로 변경 시 room_id 검증
    new_target = request.target or existing.target
    new_room_id = request.target_room_id if request.target_room_id is not None else existing.target_room_id
    if new_target == AnnouncementTarget.SPECIFIC_ROOM and not new_room_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target이 specific_room인 경우 target_room_id가 필요합니다"
        )

    # 업데이트
    updates = request.model_dump(exclude_unset=True)
    announcement = await service.update_announcement(announcement_id, **updates)

    # 감사 로그
    audit_service = AuditService(db)
    await audit_service.log_action(
        admin_user_id=str(current_user.id),
        action="update_announcement",
        target_type="announcement",
        target_id=announcement_id,
        details={"updates": list(updates.keys())},
    )

    return AnnouncementResponse(**service._to_dict(announcement))


@router.delete("/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_announcement(
    announcement_id: str,
    current_user: AdminUser = Depends(require_supervisor),
    db: AsyncSession = Depends(get_admin_db),
):
    """공지사항 삭제 (supervisor 이상 권한)"""
    service = AnnouncementService(db)

    # 기존 공지 확인
    existing = await service.get_announcement(announcement_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="공지사항을 찾을 수 없습니다"
        )

    title = existing.title
    await service.delete_announcement(announcement_id)

    # 감사 로그
    audit_service = AuditService(db)
    await audit_service.log_action(
        admin_user_id=str(current_user.id),
        action="delete_announcement",
        target_type="announcement",
        target_id=announcement_id,
        details={"title": title},
    )

    return None


@router.post("/{announcement_id}/broadcast", response_model=BroadcastResponse)
async def broadcast_announcement(
    announcement_id: str,
    current_user: AdminUser = Depends(require_supervisor),
    db: AsyncSession = Depends(get_admin_db),
    redis: Redis | None = Depends(get_redis),
):
    """
    공지사항 브로드캐스트 (supervisor 이상 권한)

    - WebSocket을 통해 모든 연결된 클라이언트에게 공지 전송
    - target에 따라 lobby 또는 특정 테이블 채널로 발송
    """
    if not redis:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis 서버에 연결할 수 없습니다"
        )

    service = AnnouncementService(db, redis)
    result = await service.broadcast_announcement(announcement_id)

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "브로드캐스트 실패")
        )

    # 감사 로그
    audit_service = AuditService(db)
    await audit_service.log_action(
        admin_user_id=str(current_user.id),
        action="broadcast_announcement",
        target_type="announcement",
        target_id=announcement_id,
        details={
            "channel": result.get("channel"),
            "broadcast_count": result.get("broadcast_count"),
        },
    )

    return BroadcastResponse(**result)


@router.get("/types/list")
async def list_announcement_types(
    current_user: AdminUser = Depends(require_admin),
):
    """공지사항 유형 목록"""
    return {
        "types": [
            {"value": AnnouncementType.NOTICE.value, "label": "일반 공지"},
            {"value": AnnouncementType.EVENT.value, "label": "이벤트 공지"},
            {"value": AnnouncementType.MAINTENANCE.value, "label": "점검 공지"},
            {"value": AnnouncementType.URGENT.value, "label": "긴급 공지"},
        ],
        "priorities": [
            {"value": AnnouncementPriority.LOW.value, "label": "낮음"},
            {"value": AnnouncementPriority.NORMAL.value, "label": "보통"},
            {"value": AnnouncementPriority.HIGH.value, "label": "높음"},
            {"value": AnnouncementPriority.CRITICAL.value, "label": "긴급"},
        ],
        "targets": [
            {"value": AnnouncementTarget.ALL.value, "label": "전체 사용자"},
            {"value": AnnouncementTarget.VIP.value, "label": "VIP 사용자"},
            {"value": AnnouncementTarget.SPECIFIC_ROOM.value, "label": "특정 방"},
        ],
    }
