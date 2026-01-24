"""출석체크 모델"""

from datetime import date, datetime
from uuid import UUID
from sqlalchemy import String, Date, DateTime, ForeignKey, Integer, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class DailyCheckin(Base):
    """일일 출석체크 기록"""
    __tablename__ = "daily_checkins"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 유저 정보
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 출석 날짜 (KST 기준)
    checkin_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="출석 날짜 (KST)",
    )

    # 연속 출석 일수 (해당 시점)
    streak_days: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="연속 출석 일수",
    )

    # 지급된 보상
    reward_amount: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="지급 보상 금액",
    )

    # 보상 타입 (daily, weekly_bonus, monthly_bonus)
    reward_type: Mapped[str] = mapped_column(
        String(20),
        default="daily",
        nullable=False,
        comment="보상 타입",
    )

    # 출석 시간
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="출석 시간",
    )

    # 관계
    user = relationship("User", back_populates="checkins", lazy="selectin")

    __table_args__ = (
        # 유저당 하루 1회만 출석 가능
        UniqueConstraint("user_id", "checkin_date", name="uq_user_checkin_date"),
        # 조회 성능을 위한 인덱스
        Index("ix_checkin_user_date", "user_id", "checkin_date"),
    )

    def __repr__(self) -> str:
        return f"<DailyCheckin user={self.user_id} date={self.checkin_date}>"


# 출석 보상 설정
CHECKIN_REWARDS = {
    "daily": 100,           # 일일 기본 보상
    "streak_7": 500,        # 7일 연속 보너스
    "streak_14": 1000,      # 14일 연속 보너스
    "streak_30": 3000,      # 30일 연속 보너스
}
