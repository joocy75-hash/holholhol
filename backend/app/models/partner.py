"""Partner (총판) and Settlement models.

파트너 시스템:
- Partner: 파트너(총판) 계정 정보
- PartnerSettlement: 파트너 정산 내역
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class PartnerStatus(str, Enum):
    """Partner account status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class CommissionType(str, Enum):
    """Commission calculation type.

    - RAKEBACK: 하위 유저 레이크의 X%
    - REVSHARE: 하위 유저 순손실의 X%
    - TURNOVER: 하위 유저 베팅량의 X%
    """

    RAKEBACK = "rakeback"
    REVSHARE = "revshare"
    TURNOVER = "turnover"


class SettlementStatus(str, Enum):
    """Settlement status."""

    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"
    REJECTED = "rejected"


class SettlementPeriod(str, Enum):
    """Settlement period type."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class Partner(Base, UUIDMixin, TimestampMixin):
    """Partner (총판) account model.

    파트너는 고유한 파트너 코드를 가지며, 이 코드로 가입한 유저들의
    활동에 따라 수수료를 정산받습니다.
    """

    __tablename__ = "partners"

    # 파트너 계정 (1:1 관계)
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
        index=True,
    )

    # 파트너 코드 (8자리 영문숫자)
    partner_code: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )

    # 파트너 정보
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    contact_info: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # 수수료 설정
    commission_type: Mapped[CommissionType] = mapped_column(
        SQLEnum(
            CommissionType,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=CommissionType.RAKEBACK,
    )
    commission_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),  # 예: 0.3000 = 30%
        nullable=False,
        default=Decimal("0.3000"),
    )

    # 상태
    status: Mapped[PartnerStatus] = mapped_column(
        SQLEnum(
            PartnerStatus,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=PartnerStatus.ACTIVE,
        nullable=False,
    )

    # 통계 (비정규화 - 빠른 조회용)
    total_referrals: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
        comment="총 추천 회원 수",
    )
    total_commission_earned: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
        comment="누적 수수료 (KRW)",
    )
    current_month_commission: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
        comment="이번 달 수수료 (KRW)",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[user_id],
        backref="partner_account",
    )
    settlements: Mapped[list["PartnerSettlement"]] = relationship(
        "PartnerSettlement",
        back_populates="partner",
        cascade="all, delete-orphan",
        order_by="desc(PartnerSettlement.created_at)",
    )

    def __repr__(self) -> str:
        return f"<Partner {self.partner_code} ({self.name})>"


class PartnerSettlement(Base, UUIDMixin, TimestampMixin):
    """Partner settlement record.

    파트너 정산 내역을 기록합니다.
    정산 시점의 수수료 타입과 비율을 스냅샷으로 저장합니다.
    """

    __tablename__ = "partner_settlements"

    # 파트너 참조
    partner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("partners.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # 정산 기간
    period_type: Mapped[SettlementPeriod] = mapped_column(
        SQLEnum(
            SettlementPeriod,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # 정산 시점 스냅샷
    commission_type: Mapped[CommissionType] = mapped_column(
        SQLEnum(
            CommissionType,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    commission_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
    )

    # 정산 금액
    base_amount: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="기준 금액 (레이크/순손실/베팅량)",
    )
    commission_amount: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="수수료 금액 (KRW)",
    )

    # 정산 상태
    status: Mapped[SettlementStatus] = mapped_column(
        SQLEnum(
            SettlementStatus,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=SettlementStatus.PENDING,
        nullable=False,
        index=True,
    )

    # 승인/지급 정보
    approved_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # 거부 사유
    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # 상세 내역 (하위 유저별 breakdown)
    detail: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="하위 유저별 정산 상세",
    )

    # Relationships
    partner: Mapped["Partner"] = relationship("Partner", back_populates="settlements")
    approver: Mapped["User"] = relationship("User", foreign_keys=[approved_by])

    def __repr__(self) -> str:
        return (
            f"<PartnerSettlement {self.id[:8]}... "
            f"partner={self.partner_id[:8]}... "
            f"amount={self.commission_amount}>"
        )
