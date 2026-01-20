"""Hot wallet balance monitoring task.

Background task that periodically snapshots hot wallet balance
and checks for low balance conditions.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, Optional, Awaitable

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.crypto import HotWalletBalance
from app.services.crypto.wallet_balance_service import (
    WalletBalanceService,
    WalletBalanceServiceError,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class HotWalletBalanceTask:
    """Background task for monitoring hot wallet balance.

    Periodically snapshots wallet balance and checks for:
    - Low balance alerts
    - Large pending withdrawals
    - Balance history tracking
    """

    def __init__(
        self,
        db_session_factory: Callable[[], AsyncSession],
        redis_client=None,
        interval: int = 3600,  # Snapshot every hour
        on_low_balance: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        """Initialize hot wallet balance task.

        Args:
            db_session_factory: Factory function to create DB sessions
            redis_client: Redis client for services
            interval: Seconds between snapshots (default: 3600 = 1 hour)
            on_low_balance: Callback when balance is below threshold
        """
        self.db_session_factory = db_session_factory
        self.redis_client = redis_client
        self.interval = interval
        self._on_low_balance = on_low_balance
        self._running = False
        self._consecutive_errors = 0
        self._max_consecutive_errors = 5
        self._last_low_balance_alert: Optional[datetime] = None
        self._alert_cooldown = 3600  # Only alert once per hour

    def set_low_balance_callback(
        self,
        callback: Callable[[dict], Awaitable[None]],
    ):
        """Set callback for low balance alerts.

        Args:
            callback: Async function called with balance data
        """
        self._on_low_balance = callback

    async def start(self):
        """Start the balance monitoring loop.

        Runs continuously until stop() is called.
        """
        self._running = True
        logger.info(
            f"Starting hot wallet balance task (interval: {self.interval}s)"
        )

        # Take initial snapshot immediately
        await self._safe_snapshot()

        while self._running:
            await asyncio.sleep(self.interval)

            if not self._running:
                break

            await self._safe_snapshot()

        logger.info("Hot wallet balance task stopped")

    def stop(self):
        """Stop the monitoring loop."""
        self._running = False

    async def _safe_snapshot(self):
        """Take snapshot with error handling."""
        try:
            await self._snapshot_balance()
            self._consecutive_errors = 0
        except Exception as e:
            self._consecutive_errors += 1

            if self._consecutive_errors <= 3 or self._consecutive_errors % 5 == 0:
                logger.error(
                    f"Error taking wallet snapshot "
                    f"(attempt {self._consecutive_errors}): {e}"
                )

            # Don't back off too much - wallet monitoring is critical
            if self._consecutive_errors >= self._max_consecutive_errors:
                logger.warning(
                    f"Wallet monitoring degraded - "
                    f"{self._consecutive_errors} consecutive errors"
                )

    async def _snapshot_balance(self):
        """Take a balance snapshot and check thresholds."""
        async with self.db_session_factory() as db:
            # Create wallet balance service
            service = WalletBalanceService(
                db=db,
                redis_client=self.redis_client,
            )

            try:
                # Get current balance
                balance_data = await service.get_current_balance()

                # Save snapshot
                await self._save_snapshot(db, balance_data)

                # Check threshold
                await self._check_threshold(balance_data)

            finally:
                await service.close()

    async def _save_snapshot(self, db: AsyncSession, balance_data: dict):
        """Save balance snapshot to database.

        Args:
            db: Database session
            balance_data: Balance data from WalletBalanceService
        """
        snapshot = HotWalletBalance(
            address=balance_data["address"],
            balance_usdt=Decimal(str(balance_data["balance_usdt"])),
            balance_krw=Decimal(str(balance_data["balance_krw"])),
            exchange_rate=Decimal(str(balance_data["exchange_rate"])),
            recorded_at=datetime.now(timezone.utc),
        )
        db.add(snapshot)
        await db.commit()

        logger.info(
            f"Hot wallet snapshot: {balance_data['balance_usdt']:.2f} USDT "
            f"(available: {balance_data['available_usdt']:.2f} USDT)"
        )

    async def _check_threshold(self, balance_data: dict):
        """Check if balance is below threshold and trigger alerts.

        Args:
            balance_data: Balance data from WalletBalanceService
        """
        available_usdt = Decimal(str(balance_data["available_usdt"]))
        threshold = Decimal(str(settings.hot_wallet_min_balance))

        if available_usdt < threshold:
            # Check alert cooldown
            now = datetime.now(timezone.utc)
            if (
                self._last_low_balance_alert is None
                or (now - self._last_low_balance_alert).total_seconds()
                >= self._alert_cooldown
            ):
                deficit = threshold - available_usdt

                logger.warning(
                    f"⚠️ Hot wallet balance below threshold! "
                    f"Available: {available_usdt:.2f} USDT, "
                    f"Threshold: {threshold:.2f} USDT, "
                    f"Deficit: {deficit:.2f} USDT"
                )

                # Trigger callback if set
                if self._on_low_balance:
                    try:
                        await self._on_low_balance({
                            "available_usdt": float(available_usdt),
                            "threshold_usdt": float(threshold),
                            "deficit_usdt": float(deficit),
                            "pending_usdt": balance_data["pending_withdrawals_usdt"],
                            "balance_usdt": balance_data["balance_usdt"],
                            "timestamp": now.isoformat(),
                        })
                    except Exception as e:
                        logger.error(f"Error in low balance callback: {e}")

                self._last_low_balance_alert = now


async def snapshot_wallet_balance_once(
    db: AsyncSession,
    redis_client=None,
) -> HotWalletBalance:
    """One-shot function to snapshot wallet balance.

    Can be called from API endpoints or manual triggers.

    Args:
        db: Database session
        redis_client: Optional Redis client

    Returns:
        HotWalletBalance: The created snapshot record
    """
    service = WalletBalanceService(
        db=db,
        redis_client=redis_client,
    )

    try:
        balance_data = await service.get_current_balance()

        snapshot = HotWalletBalance(
            address=balance_data["address"],
            balance_usdt=Decimal(str(balance_data["balance_usdt"])),
            balance_krw=Decimal(str(balance_data["balance_krw"])),
            exchange_rate=Decimal(str(balance_data["exchange_rate"])),
            recorded_at=datetime.now(timezone.utc),
        )
        db.add(snapshot)
        await db.commit()

        logger.info(
            f"Manual wallet snapshot: {balance_data['balance_usdt']:.2f} USDT"
        )
        return snapshot

    finally:
        await service.close()
