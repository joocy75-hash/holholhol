from datetime import datetime
from enum import Enum
from sqlalchemy import String, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class FlagType(str, Enum):
    SAME_IP = "same_ip"
    CHIP_DUMPING = "chip_dumping"
    BOT_PATTERN = "bot_pattern"
    UNUSUAL_ACTIVITY = "unusual_activity"


class CaseStatus(str, Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    CLEARED = "cleared"
    ESCALATED = "escalated"


class SuspiciousCase(Base, UUIDMixin, TimestampMixin):
    """Suspicious user case for review"""
    __tablename__ = "suspicious_cases"

    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    flag_type: Mapped[FlagType] = mapped_column(
        SQLEnum(FlagType),
        nullable=False,
        index=True,
    )
    flag_details: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    related_user_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    related_hand_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[CaseStatus] = mapped_column(
        SQLEnum(CaseStatus),
        default=CaseStatus.PENDING,
        nullable=False,
        index=True,
    )
    reviewed_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("admin_users.id"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<SuspiciousCase {self.flag_type} for user {self.user_id[:8]}...>"
