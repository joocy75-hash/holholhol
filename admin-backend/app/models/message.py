"""쪽지 시스템 모델 - 관리자 → 유저 방향 쪽지"""

from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Message(Base, UUIDMixin, TimestampMixin):
    """관리자가 유저에게 보내는 쪽지"""
    __tablename__ = "messages"

    # 발신자 (관리자)
    sender_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("admin_users.id"),
        nullable=False,
        comment="발신자 (관리자) ID",
    )

    # 수신자 (유저) - backend DB의 users 테이블 참조
    recipient_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
        comment="수신자 (유저) ID",
    )

    # 쪽지 내용
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="쪽지 제목",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="쪽지 내용",
    )

    # 읽음 상태
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="읽음 여부",
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="읽은 시간",
    )

    def __repr__(self) -> str:
        return f"<Message {self.id}: {self.title[:20]}...>"
