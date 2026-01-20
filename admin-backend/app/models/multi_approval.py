"""다중 승인 시스템 모델.

고액 출금에 대한 다중 관리자 승인을 위한 모델입니다.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import String, DateTime, Numeric, ForeignKey, Integer, Text, Enum as SQLEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ApprovalStatus(str, Enum):
    """승인 상태."""
    PENDING = "pending"          # 승인 대기
    PARTIALLY_APPROVED = "partially_approved"  # 부분 승인
    APPROVED = "approved"        # 완전 승인
    REJECTED = "rejected"        # 거부
    EXPIRED = "expired"          # 만료


class ApprovalAction(str, Enum):
    """승인 행동."""
    APPROVE = "approve"
    REJECT = "reject"


class ApprovalPolicy(Base, UUIDMixin, TimestampMixin):
    """승인 정책.

    금액 범위에 따른 필요 승인 수를 정의합니다.
    """
    __tablename__ = "approval_policies"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 금액 범위 (USDT)
    min_amount_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    max_amount_usdt: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6), nullable=True)

    # 필요 승인 수
    required_approvals: Mapped[int] = mapped_column(Integer, nullable=False, default=2)

    # 승인 만료 시간 (분)
    expiry_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)

    # 활성화 여부
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # 우선순위 (높을수록 우선 적용)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<ApprovalPolicy {self.name}: {self.min_amount_usdt}-{self.max_amount_usdt} USDT, {self.required_approvals} approvals>"


class WithdrawalApprovalRequest(Base, UUIDMixin, TimestampMixin):
    """출금 다중 승인 요청.

    고액 출금에 대한 다중 승인 추적을 위한 모델입니다.
    """
    __tablename__ = "withdrawal_approval_requests"

    # 출금 연결
    withdrawal_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # 적용된 정책
    policy_id: Mapped[str] = mapped_column(String(36), ForeignKey("approval_policies.id"), nullable=False)
    policy: Mapped["ApprovalPolicy"] = relationship("ApprovalPolicy")

    # 출금 정보 스냅샷
    amount_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    amount_krw: Mapped[Decimal] = mapped_column(Numeric(20, 0), nullable=False)
    to_address: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # 승인 요구사항
    required_approvals: Mapped[int] = mapped_column(Integer, nullable=False)
    current_approvals: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 상태
    status: Mapped[ApprovalStatus] = mapped_column(
        SQLEnum(ApprovalStatus),
        default=ApprovalStatus.PENDING,
        nullable=False,
        index=True,
    )

    # 만료 시간
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # 최종 처리 정보
    final_decision: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    final_decision_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    final_decision_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # 승인 기록
    approval_records: Mapped[list["ApprovalRecord"]] = relationship(
        "ApprovalRecord",
        back_populates="approval_request",
        order_by="ApprovalRecord.created_at",
    )

    def __repr__(self) -> str:
        return (
            f"<WithdrawalApprovalRequest {self.id[:8]}... "
            f"{self.amount_usdt} USDT, {self.current_approvals}/{self.required_approvals} approvals>"
        )

    @property
    def is_fully_approved(self) -> bool:
        """완전 승인 여부."""
        return self.current_approvals >= self.required_approvals

    @property
    def is_expired(self) -> bool:
        """만료 여부."""
        return datetime.now(self.expires_at.tzinfo) > self.expires_at


class ApprovalRecord(Base, UUIDMixin, TimestampMixin):
    """승인 기록.

    개별 관리자의 승인/거부 기록입니다.
    """
    __tablename__ = "approval_records"

    # 승인 요청 연결
    approval_request_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("withdrawal_approval_requests.id"),
        nullable=False,
        index=True,
    )
    approval_request: Mapped["WithdrawalApprovalRequest"] = relationship(
        "WithdrawalApprovalRequest",
        back_populates="approval_records",
    )

    # 관리자 정보
    admin_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    admin_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # 행동
    action: Mapped[ApprovalAction] = mapped_column(SQLEnum(ApprovalAction), nullable=False)

    # 메모/사유
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # IP 주소
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)

    def __repr__(self) -> str:
        return f"<ApprovalRecord {self.admin_name} {self.action.value} at {self.created_at}>"
