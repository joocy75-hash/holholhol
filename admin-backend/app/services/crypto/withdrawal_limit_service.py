"""출금 한도 관리 서비스.

일별/사용자별 출금 한도를 관리하고 VIP 등급별 차등 적용합니다.
"""

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crypto import CryptoWithdrawal, TransactionStatus
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class WithdrawalLimitError(Exception):
    """출금 한도 오류."""
    pass


class DailyLimitExceededError(WithdrawalLimitError):
    """일일 한도 초과."""
    pass


class UserLimitExceededError(WithdrawalLimitError):
    """사용자 한도 초과."""
    pass


class TransactionLimitExceededError(WithdrawalLimitError):
    """건당 한도 초과."""
    pass


# VIP 등급별 출금 한도 설정 (USDT)
VIP_LIMITS = {
    0: {  # 일반
        "daily_limit_usdt": Decimal("1000"),
        "per_transaction_limit_usdt": Decimal("500"),
        "monthly_limit_usdt": Decimal("10000"),
        "min_withdrawal_usdt": Decimal("10"),
    },
    1: {  # VIP 1
        "daily_limit_usdt": Decimal("5000"),
        "per_transaction_limit_usdt": Decimal("2000"),
        "monthly_limit_usdt": Decimal("50000"),
        "min_withdrawal_usdt": Decimal("10"),
    },
    2: {  # VIP 2
        "daily_limit_usdt": Decimal("10000"),
        "per_transaction_limit_usdt": Decimal("5000"),
        "monthly_limit_usdt": Decimal("100000"),
        "min_withdrawal_usdt": Decimal("10"),
    },
    3: {  # VIP 3
        "daily_limit_usdt": Decimal("50000"),
        "per_transaction_limit_usdt": Decimal("20000"),
        "monthly_limit_usdt": Decimal("500000"),
        "min_withdrawal_usdt": Decimal("10"),
    },
    4: {  # VIP 4 (무제한)
        "daily_limit_usdt": Decimal("999999999"),
        "per_transaction_limit_usdt": Decimal("999999999"),
        "monthly_limit_usdt": Decimal("999999999"),
        "min_withdrawal_usdt": Decimal("10"),
    },
}


class WithdrawalLimitService:
    """출금 한도 관리 서비스.

    사용 흐름:
    1. 출금 요청 전 check_withdrawal_limit() 호출
    2. 한도 초과 시 예외 발생
    3. 사용자 한도 현황 조회: get_user_limit_status()

    Example:
        ```python
        service = WithdrawalLimitService(db)

        # 한도 확인
        try:
            await service.check_withdrawal_limit(
                user_id="...",
                amount_usdt=Decimal("100"),
                vip_level=1,
            )
        except DailyLimitExceededError as e:
            print(f"일일 한도 초과: {e}")

        # 한도 현황 조회
        status = await service.get_user_limit_status(user_id, vip_level=1)
        ```
    """

    def __init__(self, db: AsyncSession):
        """초기화.

        Args:
            db: 데이터베이스 세션
        """
        self.db = db

    def get_limits_for_vip(self, vip_level: int) -> dict:
        """VIP 등급별 한도 조회.

        Args:
            vip_level: VIP 등급 (0-4)

        Returns:
            한도 정보 딕셔너리
        """
        return VIP_LIMITS.get(vip_level, VIP_LIMITS[0])

    async def get_user_daily_total(
        self,
        user_id: str,
        date: Optional[datetime] = None,
    ) -> Decimal:
        """사용자의 일별 출금 총액 조회.

        Args:
            user_id: 사용자 ID
            date: 기준 날짜 (None이면 오늘)

        Returns:
            일별 출금 총액 (USDT)
        """
        if date is None:
            date = datetime.now(timezone.utc)

        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        stmt = select(func.coalesce(func.sum(CryptoWithdrawal.amount_usdt), 0)).where(
            and_(
                CryptoWithdrawal.user_id == user_id,
                CryptoWithdrawal.requested_at >= day_start,
                CryptoWithdrawal.requested_at < day_end,
                CryptoWithdrawal.status.in_([
                    TransactionStatus.PENDING,
                    TransactionStatus.PROCESSING,
                    TransactionStatus.COMPLETED,
                ]),
            )
        )
        result = await self.db.execute(stmt)
        return Decimal(str(result.scalar() or 0))

    async def get_user_monthly_total(
        self,
        user_id: str,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> Decimal:
        """사용자의 월별 출금 총액 조회.

        Args:
            user_id: 사용자 ID
            year: 연도 (None이면 현재)
            month: 월 (None이면 현재)

        Returns:
            월별 출금 총액 (USDT)
        """
        now = datetime.now(timezone.utc)
        if year is None:
            year = now.year
        if month is None:
            month = now.month

        month_start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            month_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            month_end = datetime(year, month + 1, 1, tzinfo=timezone.utc)

        stmt = select(func.coalesce(func.sum(CryptoWithdrawal.amount_usdt), 0)).where(
            and_(
                CryptoWithdrawal.user_id == user_id,
                CryptoWithdrawal.requested_at >= month_start,
                CryptoWithdrawal.requested_at < month_end,
                CryptoWithdrawal.status.in_([
                    TransactionStatus.PENDING,
                    TransactionStatus.PROCESSING,
                    TransactionStatus.COMPLETED,
                ]),
            )
        )
        result = await self.db.execute(stmt)
        return Decimal(str(result.scalar() or 0))

    async def get_user_pending_total(self, user_id: str) -> Decimal:
        """사용자의 대기 중인 출금 총액 조회.

        Args:
            user_id: 사용자 ID

        Returns:
            대기 중 출금 총액 (USDT)
        """
        stmt = select(func.coalesce(func.sum(CryptoWithdrawal.amount_usdt), 0)).where(
            and_(
                CryptoWithdrawal.user_id == user_id,
                CryptoWithdrawal.status.in_([
                    TransactionStatus.PENDING,
                    TransactionStatus.PROCESSING,
                ]),
            )
        )
        result = await self.db.execute(stmt)
        return Decimal(str(result.scalar() or 0))

    async def check_withdrawal_limit(
        self,
        user_id: str,
        amount_usdt: Decimal,
        vip_level: int = 0,
    ) -> dict:
        """출금 한도 확인.

        Args:
            user_id: 사용자 ID
            amount_usdt: 출금 금액 (USDT)
            vip_level: VIP 등급

        Returns:
            한도 확인 결과

        Raises:
            TransactionLimitExceededError: 건당 한도 초과
            DailyLimitExceededError: 일일 한도 초과
            WithdrawalLimitError: 월 한도 초과
        """
        limits = self.get_limits_for_vip(vip_level)

        # 최소 출금 금액 확인
        if amount_usdt < limits["min_withdrawal_usdt"]:
            raise WithdrawalLimitError(
                f"최소 출금 금액은 {limits['min_withdrawal_usdt']} USDT입니다"
            )

        # 건당 한도 확인
        if amount_usdt > limits["per_transaction_limit_usdt"]:
            raise TransactionLimitExceededError(
                f"건당 출금 한도를 초과했습니다. "
                f"한도: {limits['per_transaction_limit_usdt']} USDT, "
                f"요청: {amount_usdt} USDT"
            )

        # 일일 한도 확인
        daily_total = await self.get_user_daily_total(user_id)
        if daily_total + amount_usdt > limits["daily_limit_usdt"]:
            remaining = limits["daily_limit_usdt"] - daily_total
            raise DailyLimitExceededError(
                f"일일 출금 한도를 초과했습니다. "
                f"한도: {limits['daily_limit_usdt']} USDT, "
                f"오늘 사용: {daily_total} USDT, "
                f"남은 한도: {max(Decimal('0'), remaining)} USDT"
            )

        # 월간 한도 확인
        monthly_total = await self.get_user_monthly_total(user_id)
        if monthly_total + amount_usdt > limits["monthly_limit_usdt"]:
            remaining = limits["monthly_limit_usdt"] - monthly_total
            raise WithdrawalLimitError(
                f"월간 출금 한도를 초과했습니다. "
                f"한도: {limits['monthly_limit_usdt']} USDT, "
                f"이번 달 사용: {monthly_total} USDT, "
                f"남은 한도: {max(Decimal('0'), remaining)} USDT"
            )

        return {
            "allowed": True,
            "vip_level": vip_level,
            "amount_usdt": float(amount_usdt),
            "daily_used": float(daily_total),
            "daily_limit": float(limits["daily_limit_usdt"]),
            "daily_remaining": float(limits["daily_limit_usdt"] - daily_total - amount_usdt),
            "monthly_used": float(monthly_total),
            "monthly_limit": float(limits["monthly_limit_usdt"]),
        }

    async def get_user_limit_status(
        self,
        user_id: str,
        vip_level: int = 0,
    ) -> dict:
        """사용자 출금 한도 현황 조회.

        Args:
            user_id: 사용자 ID
            vip_level: VIP 등급

        Returns:
            한도 현황 딕셔너리
        """
        limits = self.get_limits_for_vip(vip_level)
        daily_used = await self.get_user_daily_total(user_id)
        monthly_used = await self.get_user_monthly_total(user_id)
        pending = await self.get_user_pending_total(user_id)

        return {
            "user_id": user_id,
            "vip_level": vip_level,
            "limits": {
                "per_transaction_usdt": float(limits["per_transaction_limit_usdt"]),
                "daily_usdt": float(limits["daily_limit_usdt"]),
                "monthly_usdt": float(limits["monthly_limit_usdt"]),
                "min_withdrawal_usdt": float(limits["min_withdrawal_usdt"]),
            },
            "usage": {
                "daily_used_usdt": float(daily_used),
                "daily_remaining_usdt": float(max(Decimal("0"), limits["daily_limit_usdt"] - daily_used)),
                "daily_usage_percent": float((daily_used / limits["daily_limit_usdt"]) * 100) if limits["daily_limit_usdt"] > 0 else 0,
                "monthly_used_usdt": float(monthly_used),
                "monthly_remaining_usdt": float(max(Decimal("0"), limits["monthly_limit_usdt"] - monthly_used)),
                "monthly_usage_percent": float((monthly_used / limits["monthly_limit_usdt"]) * 100) if limits["monthly_limit_usdt"] > 0 else 0,
                "pending_usdt": float(pending),
            },
        }

    async def get_all_vip_limits(self) -> list[dict]:
        """모든 VIP 등급별 한도 조회.

        Returns:
            VIP 등급별 한도 목록
        """
        return [
            {
                "vip_level": level,
                "name": self._get_vip_name(level),
                "per_transaction_usdt": float(limits["per_transaction_limit_usdt"]),
                "daily_usdt": float(limits["daily_limit_usdt"]),
                "monthly_usdt": float(limits["monthly_limit_usdt"]),
                "min_withdrawal_usdt": float(limits["min_withdrawal_usdt"]),
            }
            for level, limits in VIP_LIMITS.items()
        ]

    def _get_vip_name(self, level: int) -> str:
        """VIP 등급 이름."""
        names = {
            0: "일반",
            1: "VIP 1",
            2: "VIP 2",
            3: "VIP 3",
            4: "VIP 4 (무제한)",
        }
        return names.get(level, f"VIP {level}")

    async def get_global_daily_stats(self) -> dict:
        """전체 일별 출금 통계.

        Returns:
            오늘 전체 출금 통계
        """
        today = datetime.now(timezone.utc)
        day_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        # 오늘 출금 총액
        total_stmt = select(
            func.coalesce(func.sum(CryptoWithdrawal.amount_usdt), 0),
            func.count(CryptoWithdrawal.id),
        ).where(
            and_(
                CryptoWithdrawal.requested_at >= day_start,
                CryptoWithdrawal.requested_at < day_end,
                CryptoWithdrawal.status.in_([
                    TransactionStatus.PENDING,
                    TransactionStatus.PROCESSING,
                    TransactionStatus.COMPLETED,
                ]),
            )
        )
        result = await self.db.execute(total_stmt)
        row = result.one()

        # 대기 중 출금
        pending_stmt = select(
            func.coalesce(func.sum(CryptoWithdrawal.amount_usdt), 0),
            func.count(CryptoWithdrawal.id),
        ).where(
            and_(
                CryptoWithdrawal.requested_at >= day_start,
                CryptoWithdrawal.requested_at < day_end,
                CryptoWithdrawal.status == TransactionStatus.PENDING,
            )
        )
        pending_result = await self.db.execute(pending_stmt)
        pending_row = pending_result.one()

        return {
            "date": day_start.date().isoformat(),
            "total_amount_usdt": float(row[0]),
            "total_count": row[1],
            "pending_amount_usdt": float(pending_row[0]),
            "pending_count": pending_row[1],
        }
