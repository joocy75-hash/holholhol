"""
공지사항 서비스 - CRUD 및 브로드캐스트 기능
"""
import json
import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from redis.asyncio import Redis
from sqlalchemy import select, func, desc, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.announcement import (
    Announcement,
    AnnouncementType,
    AnnouncementPriority,
    AnnouncementTarget,
)

logger = logging.getLogger(__name__)


class AnnouncementService:
    """공지사항 CRUD 및 브로드캐스트 서비스"""

    def __init__(self, db: AsyncSession, redis: Redis | None = None):
        self.db = db
        self.redis = redis

    async def create_announcement(
        self,
        title: str,
        content: str,
        created_by: str,
        announcement_type: AnnouncementType = AnnouncementType.NOTICE,
        priority: AnnouncementPriority = AnnouncementPriority.NORMAL,
        target: AnnouncementTarget = AnnouncementTarget.ALL,
        target_room_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        scheduled_at: datetime | None = None,
    ) -> Announcement:
        """새 공지사항 생성"""
        announcement = Announcement(
            id=str(uuid4()),
            title=title,
            content=content,
            announcement_type=announcement_type,
            priority=priority,
            target=target,
            target_room_id=target_room_id,
            start_time=start_time,
            end_time=end_time,
            scheduled_at=scheduled_at,
            created_by=created_by,
        )
        self.db.add(announcement)
        await self.db.commit()
        await self.db.refresh(announcement)

        logger.info(f"공지사항 생성: {announcement.id} - {title}")
        return announcement

    async def get_announcement(self, announcement_id: str) -> Announcement | None:
        """공지사항 상세 조회"""
        result = await self.db.execute(
            select(Announcement).where(Announcement.id == announcement_id)
        )
        return result.scalar_one_or_none()

    async def list_announcements(
        self,
        page: int = 1,
        page_size: int = 20,
        announcement_type: AnnouncementType | None = None,
        priority: AnnouncementPriority | None = None,
        target: AnnouncementTarget | None = None,
        include_expired: bool = False,
    ) -> dict[str, Any]:
        """공지사항 목록 조회 (페이지네이션)"""
        # 기본 쿼리
        query = select(Announcement)
        count_query = select(func.count(Announcement.id))

        # 필터 조건 구성
        filters = []
        if announcement_type:
            filters.append(Announcement.announcement_type == announcement_type)
        if priority:
            filters.append(Announcement.priority == priority)
        if target:
            filters.append(Announcement.target == target)

        # 만료된 공지 제외 (옵션)
        if not include_expired:
            now = datetime.utcnow()
            filters.append(
                or_(
                    Announcement.end_time.is_(None),
                    Announcement.end_time > now
                )
            )

        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))

        # 정렬: 우선순위 높은 순 → 생성일 최신순
        priority_order = {
            AnnouncementPriority.CRITICAL: 0,
            AnnouncementPriority.HIGH: 1,
            AnnouncementPriority.NORMAL: 2,
            AnnouncementPriority.LOW: 3,
        }
        query = query.order_by(desc(Announcement.created_at))

        # 총 개수 조회
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # 페이지네이션
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await self.db.execute(query)
        items = result.scalars().all()

        return {
            "items": [self._to_dict(item) for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
        }

    async def update_announcement(
        self,
        announcement_id: str,
        **updates,
    ) -> Announcement | None:
        """공지사항 수정"""
        announcement = await self.get_announcement(announcement_id)
        if not announcement:
            return None

        # 허용된 필드만 업데이트
        allowed_fields = {
            "title", "content", "announcement_type", "priority",
            "target", "target_room_id", "start_time", "end_time", "scheduled_at"
        }
        for key, value in updates.items():
            if key in allowed_fields and value is not None:
                setattr(announcement, key, value)

        await self.db.commit()
        await self.db.refresh(announcement)

        logger.info(f"공지사항 수정: {announcement_id}")
        return announcement

    async def delete_announcement(self, announcement_id: str) -> bool:
        """공지사항 삭제"""
        announcement = await self.get_announcement(announcement_id)
        if not announcement:
            return False

        await self.db.delete(announcement)
        await self.db.commit()

        logger.info(f"공지사항 삭제: {announcement_id}")
        return True

    async def broadcast_announcement(
        self,
        announcement_id: str,
    ) -> dict[str, Any]:
        """공지사항을 WebSocket으로 브로드캐스트"""
        announcement = await self.get_announcement(announcement_id)
        if not announcement:
            return {"success": False, "error": "공지사항을 찾을 수 없습니다"}

        if not self.redis:
            return {"success": False, "error": "Redis 연결이 필요합니다"}

        # 브로드캐스트 채널 결정
        if announcement.target == AnnouncementTarget.SPECIFIC_ROOM:
            channel = f"table:{announcement.target_room_id}"
        else:
            # ALL 또는 VIP는 lobby 채널로 발송
            channel = "lobby"

        # WebSocket 메시지 구성
        message = {
            "type": "ANNOUNCEMENT",
            "ts": int(datetime.utcnow().timestamp() * 1000),
            "traceId": str(uuid4()),
            "payload": {
                "id": announcement.id,
                "title": announcement.title,
                "content": announcement.content,
                "type": announcement.announcement_type.value,
                "priority": announcement.priority.value,
                "target": announcement.target.value,
                "targetRoomId": announcement.target_room_id,
            },
        }

        # Redis pub/sub 발행
        try:
            await self.redis.publish(
                f"ws:pubsub:{channel}",
                json.dumps({
                    "source_instance": "admin-backend",
                    "exclude_connection": None,
                    "message": message,
                })
            )

            # 브로드캐스트 기록 업데이트
            announcement.broadcasted_at = datetime.utcnow()
            announcement.broadcast_count += 1
            await self.db.commit()

            logger.info(
                f"공지사항 브로드캐스트 완료: {announcement_id} → {channel}"
            )
            return {
                "success": True,
                "channel": channel,
                "broadcast_count": announcement.broadcast_count,
            }

        except Exception as e:
            logger.error(f"공지사항 브로드캐스트 실패: {e}")
            return {"success": False, "error": str(e)}

    async def get_active_announcements(
        self,
        target: AnnouncementTarget | None = None,
        room_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """현재 활성화된 공지사항 목록 조회 (클라이언트 초기 로드용)"""
        now = datetime.utcnow()

        filters = [
            or_(Announcement.start_time.is_(None), Announcement.start_time <= now),
            or_(Announcement.end_time.is_(None), Announcement.end_time > now),
        ]

        if target:
            filters.append(Announcement.target == target)
        if room_id:
            filters.append(
                or_(
                    Announcement.target != AnnouncementTarget.SPECIFIC_ROOM,
                    Announcement.target_room_id == room_id
                )
            )

        query = (
            select(Announcement)
            .where(and_(*filters))
            .order_by(desc(Announcement.priority), desc(Announcement.created_at))
            .limit(10)  # 최대 10개
        )

        result = await self.db.execute(query)
        items = result.scalars().all()

        return [self._to_dict(item) for item in items]

    def _to_dict(self, announcement: Announcement) -> dict[str, Any]:
        """Announcement 모델을 dict로 변환"""
        return {
            "id": announcement.id,
            "title": announcement.title,
            "content": announcement.content,
            "announcement_type": announcement.announcement_type.value,
            "priority": announcement.priority.value,
            "target": announcement.target.value,
            "target_room_id": announcement.target_room_id,
            "start_time": announcement.start_time.isoformat() if announcement.start_time else None,
            "end_time": announcement.end_time.isoformat() if announcement.end_time else None,
            "scheduled_at": announcement.scheduled_at.isoformat() if announcement.scheduled_at else None,
            "broadcasted_at": announcement.broadcasted_at.isoformat() if announcement.broadcasted_at else None,
            "broadcast_count": announcement.broadcast_count,
            "created_by": announcement.created_by,
            "created_at": announcement.created_at.isoformat() if announcement.created_at else None,
            "updated_at": announcement.updated_at.isoformat() if announcement.updated_at else None,
            "is_active": announcement.is_active,
        }
