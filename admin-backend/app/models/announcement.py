from datetime import datetime
from enum import Enum
from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SQLEnum, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class AnnouncementTarget(str, Enum):
    """공지사항 대상"""
    ALL = "all"
    VIP = "vip"
    SPECIFIC_ROOM = "specific_room"


class AnnouncementType(str, Enum):
    """공지사항 유형"""
    NOTICE = "notice"        # 일반 공지
    EVENT = "event"          # 이벤트 공지
    MAINTENANCE = "maintenance"  # 점검 공지
    URGENT = "urgent"        # 긴급 공지


class AnnouncementPriority(str, Enum):
    """공지사항 우선순위"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class Announcement(Base, UUIDMixin, TimestampMixin):
    """System announcement model"""
    __tablename__ = "announcements"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 공지 유형 및 우선순위
    announcement_type: Mapped[AnnouncementType] = mapped_column(
        SQLEnum(AnnouncementType),
        default=AnnouncementType.NOTICE,
        nullable=False,
    )
    priority: Mapped[AnnouncementPriority] = mapped_column(
        SQLEnum(AnnouncementPriority),
        default=AnnouncementPriority.NORMAL,
        nullable=False,
    )

    # 대상 설정
    target: Mapped[AnnouncementTarget] = mapped_column(
        SQLEnum(AnnouncementTarget),
        default=AnnouncementTarget.ALL,
        nullable=False,
    )
    target_room_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # 스케줄링
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    broadcasted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 브로드캐스트 횟수 (반복 발송 추적용)
    broadcast_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 생성자
    created_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("admin_users.id"),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Announcement {self.title}>"

    @property
    def is_active(self) -> bool:
        """현재 활성화된 공지인지 확인"""
        now = datetime.utcnow()
        if self.start_time and now < self.start_time:
            return False
        if self.end_time and now > self.end_time:
            return False
        return True
