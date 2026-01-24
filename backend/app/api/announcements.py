"""Announcements API - 유저용 활성 공지 조회."""

from datetime import datetime, timezone
from enum import Enum

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select, and_, or_

from app.api.deps import DbSession

router = APIRouter(prefix="/announcements", tags=["Announcements"])


# =============================================================================
# Enums (admin-backend와 동일)
# =============================================================================


class AnnouncementType(str, Enum):
    """공지사항 유형"""
    NOTICE = "notice"
    EVENT = "event"
    MAINTENANCE = "maintenance"
    URGENT = "urgent"


class AnnouncementPriority(str, Enum):
    """공지사항 우선순위"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class AnnouncementTarget(str, Enum):
    """공지사항 대상"""
    ALL = "all"
    VIP = "vip"
    SPECIFIC_ROOM = "specific_room"


# =============================================================================
# Response Models
# =============================================================================


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
    created_at: str | None


class AnnouncementListResponse(BaseModel):
    """공지사항 목록 응답"""
    items: list[AnnouncementResponse]
    total: int


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/active", response_model=AnnouncementListResponse)
async def get_active_announcements(
    db: DbSession,
    announcement_type: AnnouncementType | None = Query(None, description="유형 필터"),
    limit: int = Query(10, ge=1, le=50, description="조회 개수"),
):
    """
    현재 활성화된 공지사항 목록 조회.

    - start_time이 없거나 현재 시간 이전
    - end_time이 없거나 현재 시간 이후
    - 우선순위 높은 순 → 생성일 최신순 정렬
    """
    now = datetime.now(timezone.utc)

    # Raw SQL로 announcements 테이블 조회
    # admin-backend와 같은 DB를 공유하므로 직접 쿼리
    query = """
        SELECT
            id,
            title,
            content,
            announcement_type,
            priority,
            target,
            target_room_id,
            start_time,
            end_time,
            created_at
        FROM announcements
        WHERE
            (start_time IS NULL OR start_time <= :now)
            AND (end_time IS NULL OR end_time >= :now)
            AND target = 'all'
    """

    params = {"now": now}

    if announcement_type:
        query += " AND announcement_type = :announcement_type"
        params["announcement_type"] = announcement_type.value

    # 우선순위 정렬 (critical > high > normal > low)
    query += """
        ORDER BY
            CASE priority
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'normal' THEN 3
                WHEN 'low' THEN 4
                ELSE 5
            END,
            created_at DESC
        LIMIT :limit
    """
    params["limit"] = limit

    from sqlalchemy import text
    result = await db.execute(text(query), params)
    rows = result.fetchall()

    items = []
    for row in rows:
        items.append(AnnouncementResponse(
            id=str(row.id),
            title=row.title,
            content=row.content,
            announcement_type=row.announcement_type,
            priority=row.priority,
            target=row.target,
            target_room_id=row.target_room_id,
            start_time=row.start_time.isoformat() if row.start_time else None,
            end_time=row.end_time.isoformat() if row.end_time else None,
            created_at=row.created_at.isoformat() if row.created_at else None,
        ))

    return AnnouncementListResponse(
        items=items,
        total=len(items),
    )
