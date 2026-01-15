from datetime import datetime
from enum import Enum
from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class AnnouncementTarget(str, Enum):
    ALL = "all"
    VIP = "vip"
    SPECIFIC_ROOM = "specific_room"


class Announcement(Base, UUIDMixin, TimestampMixin):
    """System announcement model"""
    __tablename__ = "announcements"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[AnnouncementTarget] = mapped_column(
        SQLEnum(AnnouncementTarget),
        default=AnnouncementTarget.ALL,
        nullable=False,
    )
    target_room_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    broadcasted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("admin_users.id"),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Announcement {self.title}>"
