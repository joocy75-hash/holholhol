"""친구추천 보상 모델"""

from datetime import datetime
from uuid import UUID
from sqlalchemy import String, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class ReferralReward(Base, UUIDMixin):
    """친구추천 보상 기록"""
    __tablename__ = "referral_rewards"

    # 보상 받은 유저
    user_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="보상 받은 유저 ID",
    )

    # 추천된 유저 (신규 가입자)
    referred_user_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="추천된 유저 (신규 가입자) ID",
    )

    # 보상 타입
    reward_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="보상 타입 (referrer=추천인, referee=피추천인)",
    )

    # 보상 금액 (KRW)
    reward_amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="보상 금액 (KRW)",
    )

    # 보상 지급 시간
    rewarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="보상 지급 시간",
    )

    # 메모
    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="보상 관련 메모",
    )

    # 관계
    user = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="referral_rewards",
    )
    referred_user = relationship(
        "User",
        foreign_keys=[referred_user_id],
    )

    def __repr__(self) -> str:
        return f"<ReferralReward user={self.user_id} type={self.reward_type} amount={self.reward_amount}>"


# 추천 보상 설정
REFERRAL_REWARDS = {
    "referrer": 1000,   # 추천인 보상 (KRW)
    "referee": 500,     # 피추천인 가입 보너스 (KRW)
}
