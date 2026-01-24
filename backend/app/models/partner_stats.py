"""Partner Statistics Models.

파트너(총판) 통계 사전 집계 테이블입니다.
실시간 집계 대신 일별로 사전 계산하여 조회 성능을 향상시킵니다.
"""

from datetime import date
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import BigInteger, Date, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.partner import Partner


class PartnerDailyStats(Base):
    """파트너 일별 통계 (사전 집계).

    매일 자정에 배치로 전일 통계를 집계하여 저장합니다.
    이를 통해 통계 조회 시 실시간 집계 대신 사전 집계된 데이터를 반환하여
    성능을 크게 향상시킵니다.

    집계 기준:
    - 신규 가입자: 해당 날짜에 created_at인 User 수
    - 베팅 금액: 해당 날짜의 total_bet_amount_krw 합계
    - 레이크: 해당 날짜의 total_rake_paid_krw 합계
    - 순손실: 해당 날짜의 max(-total_net_profit_krw, 0) 합계
    """

    __tablename__ = "partner_daily_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("partners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="통계 날짜 (UTC 기준)",
    )

    # 신규 가입자 통계
    new_referrals: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
        comment="해당 날짜 신규 추천 회원 수",
    )

    # 베팅 통계 (KRW)
    total_bet_amount: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
        comment="총 베팅 금액 (KRW)",
    )
    total_rake: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
        comment="총 레이크 (하우스 수수료) (KRW)",
    )
    total_net_loss: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
        comment="총 순손실 (유저 관점) (KRW)",
    )

    # 수수료 (파트너 수익)
    commission_amount: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
        comment="수수료 금액 (commission_type에 따라 계산됨) (KRW)",
    )

    # Relationship
    partner: Mapped["Partner"] = relationship(
        "Partner",
        back_populates="daily_stats",
    )

    # Indexes and Constraints
    __table_args__ = (
        # 복합 인덱스: 파트너별 날짜 조회 최적화
        Index("ix_partner_daily_stats_partner_date", "partner_id", "date"),
        # 유니크 제약: 파트너당 날짜별 1개 레코드만 허용
        UniqueConstraint(
            "partner_id",
            "date",
            name="uq_partner_daily_stats_partner_date",
        ),
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<PartnerDailyStats("
            f"id={self.id}, "
            f"partner_id={self.partner_id}, "
            f"date={self.date}, "
            f"commission={self.commission_amount}"
            f")>"
        )
