"""Audit log model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class AuditLog(Base, UUIDMixin):
    """Audit log for security and debugging."""

    __tablename__ = "audit_logs"

    # Actor (who performed the action)
    actor_user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Action type
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    """
    Action examples:
    - user.login
    - user.logout
    - user.register
    - room.create
    - room.join
    - room.leave
    - table.sit
    - table.stand
    - hand.action
    - admin.ban_user
    """

    # Context (additional data)
    context: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    """
    Context examples:
    {
        "ip_address": "192.168.1.1",
        "user_agent": "Mozilla/5.0...",
        "room_id": "...",
        "table_id": "...",
        "result": "success" | "failure",
        "reason": "invalid_password"
    }
    """

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        actor = self.actor_user_id[:8] if self.actor_user_id else "system"
        return f"<AuditLog {self.action} by={actor}...>"
