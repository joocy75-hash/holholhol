"""Wallet Balance Service for hot wallet monitoring.

Provides real-time balance information combining:
- TON blockchain wallet balance
- Pending withdrawal amounts
- Exchange rate conversion to KRW
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.crypto import CryptoWithdrawal, TransactionStatus
from app.services.crypto.ton_client import TonClient, TonClientError
from app.services.crypto.ton_exchange_rate import TonExchangeRateService

logger = logging.getLogger(__name__)
settings = get_settings()


class WalletBalanceServiceError(Exception):
    """지갑 잔액 서비스 기본 예외"""
    pass


class WalletBalanceService:
    """Service for querying hot wallet balance and pending withdrawals.

    Combines data from:
    - TON blockchain (via TonClient)
    - Admin database (pending withdrawals)
    - Exchange rate service (KRW conversion)
    """

    def __init__(
        self,
        db: AsyncSession,
        redis_client=None,
        ton_client: Optional[TonClient] = None,
        rate_service: Optional[TonExchangeRateService] = None,
    ):
        """Initialize wallet balance service.

        Args:
            db: Database session for querying pending withdrawals
            redis_client: Redis client for exchange rate caching
            ton_client: Optional pre-configured TonClient
            rate_service: Optional pre-configured TonExchangeRateService
        """
        self.db = db
        self.redis = redis_client
        self._ton_client = ton_client
        self._rate_service = rate_service

    async def _get_ton_client(self) -> TonClient:
        """Get or create TonClient."""
        if self._ton_client is None:
            self._ton_client = TonClient()
        return self._ton_client

    async def _get_rate_service(self) -> TonExchangeRateService:
        """Get or create TonExchangeRateService."""
        if self._rate_service is None:
            self._rate_service = TonExchangeRateService(self.redis)
        return self._rate_service

    async def close(self):
        """Close connections."""
        if self._ton_client:
            await self._ton_client.close()
        if self._rate_service:
            await self._rate_service.close()

    async def get_current_balance(self) -> dict:
        """Get current hot wallet balance with pending withdrawals.

        Returns:
            dict: {
                address: Hot wallet address
                balance_usdt: Current USDT balance on blockchain
                balance_krw: KRW equivalent of balance
                pending_withdrawals_usdt: Sum of pending withdrawals
                pending_withdrawals_krw: KRW equivalent of pending
                available_usdt: balance - pending
                available_krw: KRW equivalent of available
                exchange_rate: Current USDT/KRW rate
                last_updated: Timestamp
            }

        Raises:
            WalletBalanceServiceError: If balance cannot be retrieved
        """
        try:
            ton_client = await self._get_ton_client()
            rate_service = await self._get_rate_service()

            # Get blockchain balance
            try:
                balance_usdt = await ton_client.get_wallet_balance()
            except TonClientError as e:
                logger.error(f"블록체인 잔액 조회 실패: {e}")
                # 블록체인 조회 실패 시 0으로 처리하고 계속 진행
                balance_usdt = Decimal("0")

            # Get pending withdrawals sum
            pending_usdt = await self._get_pending_withdrawals_sum()

            # Get current exchange rate
            try:
                exchange_rate = await rate_service.get_usdt_krw_rate()
            except Exception as e:
                logger.error(f"환율 조회 실패: {e}")
                # 환율 조회 실패 시 기본값 사용
                exchange_rate = Decimal("1380")

            # Calculate KRW amounts
            balance_krw = int(balance_usdt * exchange_rate)
            pending_krw = int(pending_usdt * exchange_rate)
            available_usdt = balance_usdt - pending_usdt
            available_krw = int(available_usdt * exchange_rate)

            wallet_address = settings.ton_hot_wallet_address or "not_configured"

            return {
                "address": wallet_address,
                "balance_usdt": float(balance_usdt),
                "balance_krw": balance_krw,
                "pending_withdrawals_usdt": float(pending_usdt),
                "pending_withdrawals_krw": pending_krw,
                "available_usdt": float(available_usdt),
                "available_krw": available_krw,
                "exchange_rate": float(exchange_rate),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"지갑 잔액 조회 실패: {e}", exc_info=True)
            raise WalletBalanceServiceError(f"지갑 잔액을 조회할 수 없습니다: {e}")

    async def _get_pending_withdrawals_sum(self) -> Decimal:
        """Get sum of pending withdrawal amounts in USDT.

        Returns:
            Decimal: Total pending USDT amount
        """
        result = await self.db.execute(
            select(func.coalesce(func.sum(CryptoWithdrawal.amount_usdt), 0))
            .where(
                CryptoWithdrawal.status.in_([
                    TransactionStatus.PENDING,
                    TransactionStatus.PROCESSING
                ])
            )
        )
        return Decimal(str(result.scalar() or 0))

    async def check_balance_threshold(self) -> dict:
        """Check if wallet balance is below threshold.

        Returns:
            dict: {
                is_below_threshold: bool
                threshold_usdt: Configured threshold
                current_usdt: Current balance
                deficit_usdt: Amount below threshold (0 if above)
            }
        """
        try:
            balance_data = await self.get_current_balance()
            available_usdt = Decimal(str(balance_data["available_usdt"]))
            threshold = Decimal(str(settings.hot_wallet_min_balance))

            is_below = available_usdt < threshold
            deficit = max(threshold - available_usdt, Decimal("0"))

            return {
                "is_below_threshold": is_below,
                "threshold_usdt": float(threshold),
                "current_usdt": float(available_usdt),
                "deficit_usdt": float(deficit),
            }

        except WalletBalanceServiceError:
            raise
        except Exception as e:
            logger.error(f"잔액 임계값 체크 실패: {e}")
            raise WalletBalanceServiceError(f"잔액 임계값을 체크할 수 없습니다: {e}")

    async def get_balance_history(
        self,
        hours: int = 24,
        limit: int = 100,
    ) -> list:
        """Get balance history from snapshots.

        Args:
            hours: Number of hours to look back
            limit: Maximum number of records

        Returns:
            list: List of balance snapshots
        """
        from datetime import timedelta
        from app.models.crypto import HotWalletBalance

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        result = await self.db.execute(
            select(HotWalletBalance)
            .where(HotWalletBalance.recorded_at >= cutoff)
            .order_by(HotWalletBalance.recorded_at.desc())
            .limit(limit)
        )
        snapshots = result.scalars().all()

        return [
            {
                "address": s.address,
                "balance_usdt": float(s.balance_usdt),
                "balance_krw": int(s.balance_krw),
                "exchange_rate": float(s.exchange_rate),
                "recorded_at": s.recorded_at.isoformat(),
            }
            for s in snapshots
        ]
