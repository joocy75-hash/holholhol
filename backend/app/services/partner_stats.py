"""Partner Statistics Service.

파트너(총판) 통계 집계 및 조회 서비스입니다.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.partner import Partner
from app.models.partner_stats import PartnerDailyStats
from app.models.user import User

logger = logging.getLogger(__name__)


class PartnerStatsService:
    """파트너 통계 서비스.

    일일 통계 집계 및 조회 기능을 제공합니다.
    """

    def __init__(self, db: AsyncSession):
        """Initialize service.

        Args:
            db: Database session
        """
        self.db = db

    async def aggregate_daily_stats(
        self,
        target_date: date,
        partner_id: str | None = None,
    ) -> int:
        """특정 날짜의 일일 통계 집계.

        Args:
            target_date: 집계할 날짜 (UTC 기준)
            partner_id: 특정 파트너 ID (None이면 전체 파트너)

        Returns:
            집계된 레코드 수

        Note:
            - 기존 데이터가 있으면 업데이트 (UPSERT)
            - User 테이블의 created_at이 target_date인 신규 가입자 집계
            - 수수료는 파트너의 commission_type에 따라 계산
        """
        count = 0

        # 대상 파트너 조회
        query = select(Partner).where(Partner.status == "active")
        if partner_id:
            query = query.where(Partner.id == partner_id)

        result = await self.db.execute(query)
        partners = result.scalars().all()

        # 날짜 범위 설정 (UTC 기준)
        start_datetime = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            0,
            0,
            0,
            tzinfo=timezone.utc,
        )
        end_datetime = start_datetime + timedelta(days=1)

        for partner in partners:
            # 해당 날짜의 신규 가입자 통계 집계
            stats_query = (
                select(
                    func.count(User.id).label("referrals"),
                    func.coalesce(func.sum(User.total_bet_amount_krw), 0).label(
                        "bet_amount"
                    ),
                    func.coalesce(func.sum(User.total_rake_paid_krw), 0).label("rake"),
                    func.coalesce(
                        func.sum(func.greatest(-User.total_net_profit_krw, 0)), 0
                    ).label("net_loss"),
                )
                .where(
                    User.partner_id == partner.id,
                    User.created_at >= start_datetime,
                    User.created_at < end_datetime,
                )
            )

            stats_result = await self.db.execute(stats_query)
            stats = stats_result.one()

            # 수수료 계산
            rate = float(partner.commission_rate)
            if partner.commission_type.value == "rakeback":
                commission = int(stats.rake * rate)
            elif partner.commission_type.value == "revshare":
                commission = int(stats.net_loss * rate)
            else:  # turnover
                commission = int(stats.bet_amount * rate)

            # UPSERT: 기존 데이터가 있으면 업데이트, 없으면 생성
            existing = await self.db.execute(
                select(PartnerDailyStats).where(
                    PartnerDailyStats.partner_id == partner.id,
                    PartnerDailyStats.date == target_date,
                )
            )
            daily_stats = existing.scalar_one_or_none()

            if daily_stats:
                # 기존 데이터 업데이트
                daily_stats.new_referrals = stats.referrals
                daily_stats.total_bet_amount = stats.bet_amount
                daily_stats.total_rake = stats.rake
                daily_stats.total_net_loss = stats.net_loss
                daily_stats.commission_amount = commission
                daily_stats.updated_at = datetime.now(timezone.utc)
            else:
                # 신규 데이터 생성
                daily_stats = PartnerDailyStats(
                    partner_id=partner.id,
                    date=target_date,
                    new_referrals=stats.referrals,
                    total_bet_amount=stats.bet_amount,
                    total_rake=stats.rake,
                    total_net_loss=stats.net_loss,
                    commission_amount=commission,
                )
                self.db.add(daily_stats)

            count += 1

        await self.db.commit()

        logger.info(
            "partner_daily_stats_aggregated",
            date=target_date,
            count=count,
            partner_id=partner_id,
        )

        return count

    async def get_daily_stats(
        self,
        partner_id: str,
        start_date: date,
        end_date: date,
    ) -> list[PartnerDailyStats]:
        """파트너의 일일 통계 조회.

        Args:
            partner_id: 파트너 ID
            start_date: 시작 날짜 (포함)
            end_date: 종료 날짜 (포함)

        Returns:
            일일 통계 레코드 리스트 (날짜순 정렬)
        """
        query = (
            select(PartnerDailyStats)
            .where(
                PartnerDailyStats.partner_id == partner_id,
                PartnerDailyStats.date >= start_date,
                PartnerDailyStats.date <= end_date,
            )
            .order_by(PartnerDailyStats.date)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_monthly_stats(
        self,
        partner_id: str,
        year: int,
        month: int,
    ) -> dict[str, Any]:
        """파트너의 월간 통계 조회 (일일 통계 합산).

        Args:
            partner_id: 파트너 ID
            year: 연도
            month: 월 (1-12)

        Returns:
            월간 통계 딕셔너리:
                - new_referrals: 신규 추천 회원 수
                - total_bet_amount: 총 베팅 금액
                - total_rake: 총 레이크
                - total_net_loss: 총 순손실
                - commission_amount: 수수료 금액
                - days_count: 집계된 일수
        """
        # 해당 월의 시작/종료 날짜
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        # 일일 통계 합산
        query = (
            select(
                func.sum(PartnerDailyStats.new_referrals).label("new_referrals"),
                func.sum(PartnerDailyStats.total_bet_amount).label("total_bet_amount"),
                func.sum(PartnerDailyStats.total_rake).label("total_rake"),
                func.sum(PartnerDailyStats.total_net_loss).label("total_net_loss"),
                func.sum(PartnerDailyStats.commission_amount).label(
                    "commission_amount"
                ),
                func.count(PartnerDailyStats.id).label("days_count"),
            )
            .where(
                PartnerDailyStats.partner_id == partner_id,
                PartnerDailyStats.date >= start_date,
                PartnerDailyStats.date <= end_date,
            )
        )

        result = await self.db.execute(query)
        row = result.one()

        return {
            "new_referrals": row.new_referrals or 0,
            "total_bet_amount": row.total_bet_amount or 0,
            "total_rake": row.total_rake or 0,
            "total_net_loss": row.total_net_loss or 0,
            "commission_amount": row.commission_amount or 0,
            "days_count": row.days_count or 0,
        }
