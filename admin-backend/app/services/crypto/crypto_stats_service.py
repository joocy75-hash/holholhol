"""Crypto Statistics Service for deposit/withdrawal analytics.

Provides comprehensive statistics including:
- Daily/weekly/monthly aggregations
- Hourly patterns analysis
- Top users by volume
- Trend detection

Used by the admin dashboard for crypto monitoring.
"""

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List
from dataclasses import dataclass

from sqlalchemy import select, func, and_, text, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crypto import (
    CryptoDeposit,
    CryptoWithdrawal,
    TransactionStatus,
    ExchangeRateHistory,
)

logger = logging.getLogger(__name__)


# ============================================================
# Data Classes
# ============================================================

@dataclass
class DailyStats:
    """일별 통계"""
    date: str
    deposit_count: int
    deposit_amount_usdt: float
    deposit_amount_krw: int
    withdrawal_count: int
    withdrawal_amount_usdt: float
    withdrawal_amount_krw: int
    net_flow_usdt: float
    net_flow_krw: int


@dataclass
class HourlyPattern:
    """시간대별 패턴"""
    hour: int
    deposit_count: int
    withdrawal_count: int
    total_volume_usdt: float


@dataclass
class TopUser:
    """볼륨 상위 사용자"""
    user_id: str
    deposit_count: int
    deposit_amount_usdt: float
    withdrawal_count: int
    withdrawal_amount_usdt: float
    net_flow_usdt: float


# ============================================================
# Crypto Stats Service
# ============================================================

class CryptoStatsService:
    """암호화폐 통계 서비스.

    입출금 데이터를 분석하여 다양한 통계를 제공합니다:
    - 일별/주별/월별 집계
    - 시간대별 패턴
    - 사용자별 볼륨
    - 트렌드 분석
    """

    def __init__(self, db: AsyncSession):
        """Initialize stats service.

        Args:
            db: Database session
        """
        self.db = db

    async def close(self) -> None:
        """Close any resources."""
        pass

    # ============================================================
    # Summary Statistics
    # ============================================================

    async def get_summary_stats(self, days: int = 30) -> dict:
        """전체 요약 통계 조회.

        Args:
            days: 조회 기간 (일)

        Returns:
            dict: 요약 통계
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # 입금 통계
        deposit_stats = await self._get_deposit_stats(start_date)
        today_deposit_stats = await self._get_deposit_stats(today_start)

        # 출금 통계
        withdrawal_stats = await self._get_withdrawal_stats(start_date)
        today_withdrawal_stats = await self._get_withdrawal_stats(today_start)

        # 대기 중인 건수
        pending_deposits = await self._count_pending_deposits()
        pending_withdrawals = await self._count_pending_withdrawals()

        return {
            "period_days": days,
            "period": {
                "deposits": {
                    "count": deposit_stats["count"],
                    "amount_usdt": deposit_stats["amount_usdt"],
                    "amount_krw": deposit_stats["amount_krw"],
                },
                "withdrawals": {
                    "count": withdrawal_stats["count"],
                    "amount_usdt": withdrawal_stats["amount_usdt"],
                    "amount_krw": withdrawal_stats["amount_krw"],
                },
                "net_flow_usdt": deposit_stats["amount_usdt"] - withdrawal_stats["amount_usdt"],
                "net_flow_krw": deposit_stats["amount_krw"] - withdrawal_stats["amount_krw"],
            },
            "today": {
                "deposits": {
                    "count": today_deposit_stats["count"],
                    "amount_usdt": today_deposit_stats["amount_usdt"],
                    "amount_krw": today_deposit_stats["amount_krw"],
                },
                "withdrawals": {
                    "count": today_withdrawal_stats["count"],
                    "amount_usdt": today_withdrawal_stats["amount_usdt"],
                    "amount_krw": today_withdrawal_stats["amount_krw"],
                },
            },
            "pending": {
                "deposits": pending_deposits,
                "withdrawals": pending_withdrawals,
            },
        }

    async def _get_deposit_stats(self, start_date: datetime) -> dict:
        """입금 통계 조회."""
        query = select(
            func.count(),
            func.coalesce(func.sum(CryptoDeposit.amount_usdt), 0),
            func.coalesce(func.sum(CryptoDeposit.amount_krw), 0),
        ).where(
            and_(
                CryptoDeposit.status == TransactionStatus.COMPLETED,
                CryptoDeposit.credited_at >= start_date,
            )
        )

        result = await self.db.execute(query)
        row = result.one()

        return {
            "count": row[0] or 0,
            "amount_usdt": float(row[1]) if row[1] else 0.0,
            "amount_krw": int(row[2]) if row[2] else 0,
        }

    async def _get_withdrawal_stats(self, start_date: datetime) -> dict:
        """출금 통계 조회."""
        query = select(
            func.count(),
            func.coalesce(func.sum(CryptoWithdrawal.amount_usdt), 0),
            func.coalesce(func.sum(CryptoWithdrawal.amount_krw), 0),
        ).where(
            and_(
                CryptoWithdrawal.status == TransactionStatus.COMPLETED,
                CryptoWithdrawal.processed_at >= start_date,
            )
        )

        result = await self.db.execute(query)
        row = result.one()

        return {
            "count": row[0] or 0,
            "amount_usdt": float(row[1]) if row[1] else 0.0,
            "amount_krw": int(row[2]) if row[2] else 0,
        }

    async def _count_pending_deposits(self) -> int:
        """대기 중인 입금 건수."""
        query = select(func.count()).select_from(CryptoDeposit).where(
            CryptoDeposit.status.in_([
                TransactionStatus.PENDING,
                TransactionStatus.CONFIRMING,
            ])
        )
        result = await self.db.execute(query)
        return result.scalar() or 0

    async def _count_pending_withdrawals(self) -> int:
        """대기 중인 출금 건수."""
        query = select(func.count()).select_from(CryptoWithdrawal).where(
            CryptoWithdrawal.status.in_([
                TransactionStatus.PENDING,
                TransactionStatus.PROCESSING,
            ])
        )
        result = await self.db.execute(query)
        return result.scalar() or 0

    # ============================================================
    # Daily Statistics
    # ============================================================

    async def get_daily_stats(self, days: int = 30) -> List[dict]:
        """일별 통계 조회.

        Args:
            days: 조회 기간 (일)

        Returns:
            List of daily statistics
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        # 일별 입금 집계 (PostgreSQL DATE_TRUNC 사용)
        deposit_query = text("""
            SELECT
                DATE_TRUNC('day', credited_at)::date as date,
                COUNT(*) as count,
                COALESCE(SUM(amount_usdt), 0) as amount_usdt,
                COALESCE(SUM(amount_krw), 0) as amount_krw
            FROM crypto_deposits
            WHERE status = 'completed' AND credited_at >= :start_date
            GROUP BY DATE_TRUNC('day', credited_at)::date
            ORDER BY date
        """)

        deposit_result = await self.db.execute(
            deposit_query, {"start_date": start_date}
        )
        deposit_rows = {
            str(row[0]): {
                "count": row[1],
                "amount_usdt": float(row[2]),
                "amount_krw": int(row[3]),
            }
            for row in deposit_result
        }

        # 일별 출금 집계
        withdrawal_query = text("""
            SELECT
                DATE_TRUNC('day', processed_at)::date as date,
                COUNT(*) as count,
                COALESCE(SUM(amount_usdt), 0) as amount_usdt,
                COALESCE(SUM(amount_krw), 0) as amount_krw
            FROM crypto_withdrawals
            WHERE status = 'completed' AND processed_at >= :start_date
            GROUP BY DATE_TRUNC('day', processed_at)::date
            ORDER BY date
        """)

        withdrawal_result = await self.db.execute(
            withdrawal_query, {"start_date": start_date}
        )
        withdrawal_rows = {
            str(row[0]): {
                "count": row[1],
                "amount_usdt": float(row[2]),
                "amount_krw": int(row[3]),
            }
            for row in withdrawal_result
        }

        # 날짜별 통합
        all_dates = set(deposit_rows.keys()) | set(withdrawal_rows.keys())
        result = []

        for date_str in sorted(all_dates):
            dep = deposit_rows.get(date_str, {"count": 0, "amount_usdt": 0.0, "amount_krw": 0})
            wit = withdrawal_rows.get(date_str, {"count": 0, "amount_usdt": 0.0, "amount_krw": 0})

            result.append({
                "date": date_str,
                "deposit_count": dep["count"],
                "deposit_amount_usdt": dep["amount_usdt"],
                "deposit_amount_krw": dep["amount_krw"],
                "withdrawal_count": wit["count"],
                "withdrawal_amount_usdt": wit["amount_usdt"],
                "withdrawal_amount_krw": wit["amount_krw"],
                "net_flow_usdt": dep["amount_usdt"] - wit["amount_usdt"],
                "net_flow_krw": dep["amount_krw"] - wit["amount_krw"],
            })

        return result

    # ============================================================
    # Hourly Pattern Analysis
    # ============================================================

    async def get_hourly_patterns(self, days: int = 7) -> List[dict]:
        """시간대별 패턴 분석.

        지난 N일간의 데이터를 시간대별로 집계합니다.

        Args:
            days: 분석 기간 (일)

        Returns:
            List of hourly patterns (0-23)
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        # 입금 시간대별 집계
        deposit_query = text("""
            SELECT
                EXTRACT(HOUR FROM detected_at) as hour,
                COUNT(*) as count,
                COALESCE(SUM(amount_usdt), 0) as amount_usdt
            FROM crypto_deposits
            WHERE status = 'completed' AND detected_at >= :start_date
            GROUP BY EXTRACT(HOUR FROM detected_at)
        """)

        deposit_result = await self.db.execute(
            deposit_query, {"start_date": start_date}
        )
        deposit_by_hour = {
            int(row[0]): {"count": row[1], "amount_usdt": float(row[2])}
            for row in deposit_result
        }

        # 출금 시간대별 집계
        withdrawal_query = text("""
            SELECT
                EXTRACT(HOUR FROM requested_at) as hour,
                COUNT(*) as count,
                COALESCE(SUM(amount_usdt), 0) as amount_usdt
            FROM crypto_withdrawals
            WHERE status = 'completed' AND requested_at >= :start_date
            GROUP BY EXTRACT(HOUR FROM requested_at)
        """)

        withdrawal_result = await self.db.execute(
            withdrawal_query, {"start_date": start_date}
        )
        withdrawal_by_hour = {
            int(row[0]): {"count": row[1], "amount_usdt": float(row[2])}
            for row in withdrawal_result
        }

        # 0-23시 통합
        result = []
        for hour in range(24):
            dep = deposit_by_hour.get(hour, {"count": 0, "amount_usdt": 0.0})
            wit = withdrawal_by_hour.get(hour, {"count": 0, "amount_usdt": 0.0})

            result.append({
                "hour": hour,
                "deposit_count": dep["count"],
                "deposit_amount_usdt": dep["amount_usdt"],
                "withdrawal_count": wit["count"],
                "withdrawal_amount_usdt": wit["amount_usdt"],
                "total_volume_usdt": dep["amount_usdt"] + wit["amount_usdt"],
            })

        return result

    # ============================================================
    # Top Users
    # ============================================================

    async def get_top_users(self, days: int = 30, limit: int = 10) -> List[dict]:
        """볼륨 상위 사용자 조회.

        Args:
            days: 조회 기간 (일)
            limit: 상위 N명

        Returns:
            List of top users by volume
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        # 사용자별 입금 집계
        deposit_query = text("""
            SELECT
                user_id,
                COUNT(*) as count,
                COALESCE(SUM(amount_usdt), 0) as amount_usdt
            FROM crypto_deposits
            WHERE status = 'completed' AND credited_at >= :start_date
            GROUP BY user_id
        """)

        deposit_result = await self.db.execute(
            deposit_query, {"start_date": start_date}
        )
        deposit_by_user = {
            row[0]: {"count": row[1], "amount_usdt": float(row[2])}
            for row in deposit_result
        }

        # 사용자별 출금 집계
        withdrawal_query = text("""
            SELECT
                user_id,
                COUNT(*) as count,
                COALESCE(SUM(amount_usdt), 0) as amount_usdt
            FROM crypto_withdrawals
            WHERE status = 'completed' AND processed_at >= :start_date
            GROUP BY user_id
        """)

        withdrawal_result = await self.db.execute(
            withdrawal_query, {"start_date": start_date}
        )
        withdrawal_by_user = {
            row[0]: {"count": row[1], "amount_usdt": float(row[2])}
            for row in withdrawal_result
        }

        # 사용자별 통합 및 정렬
        all_users = set(deposit_by_user.keys()) | set(withdrawal_by_user.keys())
        user_stats = []

        for user_id in all_users:
            dep = deposit_by_user.get(user_id, {"count": 0, "amount_usdt": 0.0})
            wit = withdrawal_by_user.get(user_id, {"count": 0, "amount_usdt": 0.0})

            total_volume = dep["amount_usdt"] + wit["amount_usdt"]
            user_stats.append({
                "user_id": user_id,
                "deposit_count": dep["count"],
                "deposit_amount_usdt": dep["amount_usdt"],
                "withdrawal_count": wit["count"],
                "withdrawal_amount_usdt": wit["amount_usdt"],
                "total_volume_usdt": total_volume,
                "net_flow_usdt": dep["amount_usdt"] - wit["amount_usdt"],
            })

        # 볼륨 기준 정렬
        user_stats.sort(key=lambda x: x["total_volume_usdt"], reverse=True)

        return user_stats[:limit]

    # ============================================================
    # Exchange Rate History
    # ============================================================

    async def get_exchange_rate_history(self, hours: int = 24) -> List[dict]:
        """환율 변동 히스토리 조회.

        Args:
            hours: 조회 기간 (시간)

        Returns:
            List of exchange rate records
        """
        start_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        query = (
            select(
                ExchangeRateHistory.rate,
                ExchangeRateHistory.source,
                ExchangeRateHistory.recorded_at,
            )
            .where(ExchangeRateHistory.recorded_at >= start_time)
            .order_by(ExchangeRateHistory.recorded_at.asc())
        )

        result = await self.db.execute(query)
        rows = result.all()

        return [
            {
                "rate": float(row[0]),
                "source": row[1],
                "recorded_at": row[2].isoformat() if row[2] else None,
            }
            for row in rows
        ]

    # ============================================================
    # Trend Analysis
    # ============================================================

    async def get_trend_analysis(self, days: int = 7) -> dict:
        """트렌드 분석.

        최근 N일과 그 이전 N일을 비교하여 트렌드를 분석합니다.

        Args:
            days: 비교 기간 (일)

        Returns:
            dict with trend indicators
        """
        now = datetime.now(timezone.utc)
        current_start = now - timedelta(days=days)
        previous_start = now - timedelta(days=days * 2)
        previous_end = current_start

        # 현재 기간 통계
        current_deposits = await self._get_deposit_stats(current_start)
        current_withdrawals = await self._get_withdrawal_stats(current_start)

        # 이전 기간 통계 (임시로 start_date 변경)
        deposit_query = select(
            func.count(),
            func.coalesce(func.sum(CryptoDeposit.amount_usdt), 0),
        ).where(
            and_(
                CryptoDeposit.status == TransactionStatus.COMPLETED,
                CryptoDeposit.credited_at >= previous_start,
                CryptoDeposit.credited_at < previous_end,
            )
        )
        result = await self.db.execute(deposit_query)
        row = result.one()
        previous_deposits = {
            "count": row[0] or 0,
            "amount_usdt": float(row[1]) if row[1] else 0.0,
        }

        withdrawal_query = select(
            func.count(),
            func.coalesce(func.sum(CryptoWithdrawal.amount_usdt), 0),
        ).where(
            and_(
                CryptoWithdrawal.status == TransactionStatus.COMPLETED,
                CryptoWithdrawal.processed_at >= previous_start,
                CryptoWithdrawal.processed_at < previous_end,
            )
        )
        result = await self.db.execute(withdrawal_query)
        row = result.one()
        previous_withdrawals = {
            "count": row[0] or 0,
            "amount_usdt": float(row[1]) if row[1] else 0.0,
        }

        # 변화율 계산
        def calc_change(current: float, previous: float) -> float:
            if previous == 0:
                return 100.0 if current > 0 else 0.0
            return round((current - previous) / previous * 100, 2)

        return {
            "period_days": days,
            "deposits": {
                "current_count": current_deposits["count"],
                "previous_count": previous_deposits["count"],
                "count_change_percent": calc_change(
                    current_deposits["count"], previous_deposits["count"]
                ),
                "current_amount_usdt": current_deposits["amount_usdt"],
                "previous_amount_usdt": previous_deposits["amount_usdt"],
                "amount_change_percent": calc_change(
                    current_deposits["amount_usdt"], previous_deposits["amount_usdt"]
                ),
            },
            "withdrawals": {
                "current_count": current_withdrawals["count"],
                "previous_count": previous_withdrawals["count"],
                "count_change_percent": calc_change(
                    current_withdrawals["count"], previous_withdrawals["count"]
                ),
                "current_amount_usdt": current_withdrawals["amount_usdt"],
                "previous_amount_usdt": previous_withdrawals["amount_usdt"],
                "amount_change_percent": calc_change(
                    current_withdrawals["amount_usdt"], previous_withdrawals["amount_usdt"]
                ),
            },
        }
