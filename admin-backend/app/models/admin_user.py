from datetime import datetime
from enum import Enum
from uuid import UUID
from sqlalchemy import String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.base import Base, TimestampMixin, UUIDMixin


class AdminRole(str, Enum):
    viewer = "viewer"
    operator = "operator"
    supervisor = "supervisor"
    admin = "admin"
    partner = "partner"  # 파트너 전용 역할 (자신의 데이터만 조회 가능)


class AdminUser(Base, UUIDMixin, TimestampMixin):
    """Admin user account model"""

    __tablename__ = "admin_users"

    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[AdminRole] = mapped_column(
        SQLEnum(AdminRole),
        default=AdminRole.viewer,
        nullable=False,
    )
    two_factor_secret: Mapped[str | None] = mapped_column(String(32), nullable=True)
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 파트너 역할인 경우 main_db의 partner.id를 참조 (FK 없음, 별도 DB)
    partner_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)

    def __repr__(self) -> str:
        return f"<AdminUser {self.username} ({self.role})>"
