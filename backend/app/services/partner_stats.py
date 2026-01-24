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
        """특정 날짜의 일일 통계 집계 (Bulk Upsert 최적화).

        Args:
            target_date: 집계할 날짜 (UTC 기준)
            partner_id: 특정 파트너 ID (None이면 전체 파트너)

        Returns:
            집계된 레코드 수

        Note:
            - PostgreSQL Bulk UPSERT로 N+1 쿼리 문제 해결
            - 100명 파트너 기준: 200~300 쿼리 → 2~3 쿼리 (100배 개선)
            - User 테이블의 created_at이 target_date인 신규 가입자 집계
            - 수수료는 파트너의 commission_type에 따라 계산
        """
        from sqlalchemy.dialects.postgresql import insert

        # 대상 파트너 조회
        query = select(Partner).where(Partner.status == "active")
        if partner_id:
            query = query.where(Partner.id == partner_id)

        result = await self.db.execute(query)
        partners = result.scalars().all()

        if not partners:
            logger.warning("no_active_partners_found", partner_id=partner_id)
            return 0

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

        # 파트너 ID 리스트 추출
        partner_ids = [p.id for p in partners]
        partner_map = {p.id: p for p in partners}

        # 🚀 최적화: 모든 파트너의 통계를 한 번에 GROUP BY로 집계
        # Before: N개 쿼리 (각 파트너마다)
        # After: 1개 쿼리 (GROUP BY partner_id)
        stats_query = (
            select(
                User.partner_id,
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
                User.partner_id.in_(partner_ids),
                User.created_at >= start_datetime,
                User.created_at < end_datetime,
            )
            .group_by(User.partner_id)
        )

        stats_result = await self.db.execute(stats_query)
        stats_rows = stats_result.all()

        # 통계를 파트너 ID로 매핑
        stats_map = {row.partner_id: row for row in stats_rows}

        # Bulk insert용 데이터 준비
        batch_data = []

        for partner in partners:
            # 해당 파트너의 통계 가져오기 (없으면 0으로 초기화)
            stats = stats_map.get(
                partner.id,
                type(
                    "Stats",
                    (),
                    {
                        "referrals": 0,
                        "bet_amount": 0,
                        "rake": 0,
                        "net_loss": 0,
                    },
                )(),
            )

            # 수수료 계산
            rate = float(partner.commission_rate)
            if partner.commission_type.value == "rakeback":
                commission = int(stats.rake * rate)
            elif partner.commission_type.value == "revshare":
                commission = int(stats.net_loss * rate)
            else:  # turnover
                commission = int(stats.bet_amount * rate)

            # Bulk insert용 데이터 준비
            batch_data.append(
                {
                    "partner_id": partner.id,
                    "date": target_date,
                    "new_referrals": stats.referrals,
                    "total_bet_amount": stats.bet_amount,
                    "total_rake": stats.rake,
                    "total_net_loss": stats.net_loss,
                    "commission_amount": commission,
                }
            )

        # Bulk UPSERT: INSERT ... ON CONFLICT DO UPDATE
        # PostgreSQL 전용 문법 - 단 1개 쿼리로 모든 파트너 처리
        if batch_data:
            stmt = insert(PartnerDailyStats).values(batch_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=["partner_id", "date"],
                set_={
                    "new_referrals": stmt.excluded.new_referrals,
                    "total_bet_amount": stmt.excluded.total_bet_amount,
                    "total_rake": stmt.excluded.total_rake,
                    "total_net_loss": stmt.excluded.total_net_loss,
                    "commission_amount": stmt.excluded.commission_amount,
                    "updated_at": func.now(),
                },
            )
            await self.db.execute(stmt)
            await self.db.commit()

            count = len(batch_data)
            logger.info(
                "partner_daily_stats_aggregated_bulk",
                date=target_date,
                count=count,
                partner_id=partner_id,
            )

            return count

        return 0

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
