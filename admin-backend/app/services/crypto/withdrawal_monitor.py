"""Withdrawal Monitor Service for tracking transaction confirmations.

Monitors sent withdrawal transactions and:
1. Verifies transaction confirmation on TON blockchain
2. Updates withdrawal status to COMPLETED on confirmation
3. Handles timeout and failed transactions
4. Sends notifications for important events

Runs as a background task alongside WithdrawalExecutor.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Callable, Awaitable

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.models.crypto import CryptoWithdrawal, TransactionStatus
from app.models.audit_log import AuditLog
from app.services.crypto.ton_signer import TonSigner, get_ton_signer

logger = logging.getLogger(__name__)
settings = get_settings()


# ============================================================
# Callback Types
# ============================================================

# Callback for notifications (e.g., Telegram, email)
NotificationCallback = Callable[[str, dict], Awaitable[None]]


# ============================================================
# Withdrawal Monitor Service
# ============================================================

class WithdrawalMonitor:
    """Monitor withdrawal transactions for confirmation.

    Tracks transactions that have been broadcast and:
    - Verifies they are confirmed on the blockchain
    - Updates status to COMPLETED when confirmed
    - Handles timeout (FAILED) for stuck transactions
    - Triggers notifications for admin attention

    Configuration:
    - withdrawal_monitor_interval: Check interval in seconds
    - withdrawal_tx_timeout_minutes: Timeout for pending transactions
    """

    def __init__(
        self,
        session_factory: async_sessionmaker,
        signer: Optional[TonSigner] = None,
        notification_callback: Optional[NotificationCallback] = None,
    ):
        """Initialize withdrawal monitor.

        Args:
            session_factory: SQLAlchemy async session factory
            signer: TON signer for transaction verification
            notification_callback: Optional callback for notifications
        """
        self.session_factory = session_factory
        self._signer = signer or get_ton_signer()
        self._notification_callback = notification_callback
        self._running = False
        self._consecutive_errors = 0
        self._max_consecutive_errors = 5

        logger.info(
            f"WithdrawalMonitor initialized, "
            f"interval={settings.withdrawal_monitor_interval}s, "
            f"timeout={settings.withdrawal_tx_timeout_minutes}min"
        )

    async def close(self) -> None:
        """Close connections and cleanup."""
        self._running = False
        await self._signer.close()
        logger.info("WithdrawalMonitor closed")

    # ============================================================
    # Main Monitoring Loop
    # ============================================================

    async def start(self) -> None:
        """Start monitoring withdrawals in background.

        Runs until stopped, checking transactions at configured interval.
        """
        if not settings.withdrawal_auto_enabled:
            logger.warning(
                "Withdrawal automation is disabled. Monitor will not start."
            )
            return

        self._running = True
        logger.info("WithdrawalMonitor started")

        while self._running:
            try:
                await self.check_pending_transactions()
                self._consecutive_errors = 0  # Reset on success
            except Exception as e:
                self._consecutive_errors += 1
                logger.error(
                    f"Error in withdrawal monitor loop: {e}, "
                    f"consecutive errors: {self._consecutive_errors}"
                )

                # Send alert if too many errors
                if self._consecutive_errors >= self._max_consecutive_errors:
                    await self._send_alert(
                        "withdrawal_monitor_errors",
                        {
                            "error_count": self._consecutive_errors,
                            "last_error": str(e),
                        }
                    )

            # Wait before next check
            await asyncio.sleep(settings.withdrawal_monitor_interval)

    async def stop(self) -> None:
        """Stop the monitoring loop."""
        self._running = False
        logger.info("WithdrawalMonitor stopping...")

    # ============================================================
    # Transaction Monitoring
    # ============================================================

    async def check_pending_transactions(self) -> dict:
        """Check all pending transactions for confirmation.

        Returns:
            dict with counts of confirmed, failed, and still pending
        """
        async with self.session_factory() as session:
            # Get transactions that need monitoring
            transactions = await self._get_monitoring_targets(session)

            if not transactions:
                return {"confirmed": 0, "failed": 0, "pending": 0}

            confirmed = 0
            failed = 0
            still_pending = 0

            for withdrawal in transactions:
                try:
                    result = await self._check_transaction(session, withdrawal)
                    if result == "confirmed":
                        confirmed += 1
                    elif result == "failed":
                        failed += 1
                    else:
                        still_pending += 1
                except Exception as e:
                    logger.error(
                        f"Error checking withdrawal {withdrawal.id}: {e}"
                    )
                    still_pending += 1

            logger.info(
                f"Monitor check complete: "
                f"confirmed={confirmed}, failed={failed}, pending={still_pending}"
            )

            return {
                "confirmed": confirmed,
                "failed": failed,
                "pending": still_pending,
            }

    async def _check_transaction(
        self,
        session: AsyncSession,
        withdrawal: CryptoWithdrawal,
    ) -> str:
        """Check a single transaction status.

        Args:
            session: Database session
            withdrawal: Withdrawal record with tx_hash

        Returns:
            "confirmed", "failed", or "pending"
        """
        withdrawal_id = str(withdrawal.id)
        tx_hash = withdrawal.tx_hash

        if not tx_hash:
            logger.warning(f"Withdrawal {withdrawal_id} has no tx_hash, skipping")
            return "pending"

        # Check if transaction is confirmed
        is_confirmed = await self._signer.verify_transaction(tx_hash)

        if is_confirmed:
            # Transaction confirmed - update to COMPLETED
            withdrawal.status = TransactionStatus.COMPLETED
            withdrawal.processed_at = datetime.now(timezone.utc)

            await self._create_audit_log(
                session,
                action="withdrawal_completed",
                target_id=withdrawal_id,
                admin_id="system",
                details={
                    "tx_hash": tx_hash,
                    "amount_usdt": str(withdrawal.amount_usdt),
                    "to_address": withdrawal.to_address,
                    "confirmed_at": datetime.now(timezone.utc).isoformat(),
                },
            )

            await session.commit()

            logger.info(
                f"Withdrawal {withdrawal_id} confirmed: tx={tx_hash[:16]}..."
            )

            # Send success notification
            await self._send_notification(
                "withdrawal_confirmed",
                {
                    "withdrawal_id": withdrawal_id,
                    "amount_usdt": str(withdrawal.amount_usdt),
                    "to_address": withdrawal.to_address,
                    "tx_hash": tx_hash,
                }
            )

            return "confirmed"

        # Check for timeout
        timeout_threshold = datetime.now(timezone.utc) - timedelta(
            minutes=settings.withdrawal_tx_timeout_minutes
        )

        if withdrawal.approved_at and withdrawal.approved_at < timeout_threshold:
            # Transaction timed out - mark as failed
            withdrawal.status = TransactionStatus.FAILED
            withdrawal.rejection_reason = (
                f"트랜잭션 타임아웃: {settings.withdrawal_tx_timeout_minutes}분 경과"
            )
            withdrawal.processed_at = datetime.now(timezone.utc)

            await self._create_audit_log(
                session,
                action="withdrawal_timeout",
                target_id=withdrawal_id,
                admin_id="system",
                details={
                    "tx_hash": tx_hash,
                    "amount_usdt": str(withdrawal.amount_usdt),
                    "to_address": withdrawal.to_address,
                    "approved_at": withdrawal.approved_at.isoformat() if withdrawal.approved_at else None,
                    "timeout_minutes": settings.withdrawal_tx_timeout_minutes,
                },
            )

            await session.commit()

            logger.warning(
                f"Withdrawal {withdrawal_id} timed out after "
                f"{settings.withdrawal_tx_timeout_minutes} minutes"
            )

            # Send alert for timeout
            await self._send_alert(
                "withdrawal_timeout",
                {
                    "withdrawal_id": withdrawal_id,
                    "amount_usdt": str(withdrawal.amount_usdt),
                    "tx_hash": tx_hash,
                }
            )

            return "failed"

        # Still pending
        return "pending"

    # ============================================================
    # Helper Methods
    # ============================================================

    async def _get_monitoring_targets(
        self,
        session: AsyncSession,
        limit: int = 50,
    ) -> List[CryptoWithdrawal]:
        """Get withdrawals that need transaction monitoring.

        Criteria:
        - Status is PROCESSING (transaction was sent)
        - Has TX hash (transaction was broadcast)
        """
        query = (
            select(CryptoWithdrawal)
            .where(
                and_(
                    CryptoWithdrawal.status == TransactionStatus.PROCESSING,
                    CryptoWithdrawal.tx_hash.isnot(None),
                )
            )
            .order_by(CryptoWithdrawal.approved_at.asc())
            .limit(limit)
        )

        result = await session.execute(query)
        return list(result.scalars().all())

    async def _create_audit_log(
        self,
        session: AsyncSession,
        action: str,
        target_id: str,
        admin_id: str,
        details: dict,
    ) -> None:
        """Create audit log entry."""
        audit_log = AuditLog(
            action=action,
            target_type="crypto_withdrawal",
            target_id=target_id,
            admin_user_id=admin_id,
            ip_address="system",
            details=details,
        )
        session.add(audit_log)

    async def _send_notification(self, event_type: str, data: dict) -> None:
        """Send notification for important events.

        Args:
            event_type: Type of event (e.g., "withdrawal_confirmed")
            data: Event data
        """
        if self._notification_callback:
            try:
                await self._notification_callback(event_type, data)
            except Exception as e:
                logger.warning(f"Notification callback failed: {e}")

    async def _send_alert(self, alert_type: str, data: dict) -> None:
        """Send alert for critical issues.

        Args:
            alert_type: Type of alert (e.g., "withdrawal_timeout")
            data: Alert data
        """
        logger.warning(f"ALERT [{alert_type}]: {data}")

        if self._notification_callback:
            try:
                await self._notification_callback(f"alert:{alert_type}", data)
            except Exception as e:
                logger.warning(f"Alert callback failed: {e}")

    # ============================================================
    # Status Methods
    # ============================================================

    async def get_monitor_status(self) -> dict:
        """Get current monitor status.

        Returns:
            dict with status information
        """
        async with self.session_factory() as session:
            # Count transactions being monitored
            query = select(CryptoWithdrawal).where(
                and_(
                    CryptoWithdrawal.status == TransactionStatus.PROCESSING,
                    CryptoWithdrawal.tx_hash.isnot(None),
                )
            )
            result = await session.execute(query)
            monitoring_count = len(result.scalars().all())

            # Count today's completions
            today_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            completed_query = select(CryptoWithdrawal).where(
                and_(
                    CryptoWithdrawal.status == TransactionStatus.COMPLETED,
                    CryptoWithdrawal.processed_at >= today_start,
                )
            )
            result = await session.execute(completed_query)
            today_completed = len(result.scalars().all())

            return {
                "running": self._running,
                "monitoring_count": monitoring_count,
                "today_completed": today_completed,
                "consecutive_errors": self._consecutive_errors,
                "interval_seconds": settings.withdrawal_monitor_interval,
                "timeout_minutes": settings.withdrawal_tx_timeout_minutes,
            }


# ============================================================
# Factory Function
# ============================================================

def get_withdrawal_monitor(
    session_factory: async_sessionmaker,
    signer: Optional[TonSigner] = None,
    notification_callback: Optional[NotificationCallback] = None,
) -> WithdrawalMonitor:
    """Get WithdrawalMonitor instance.

    Args:
        session_factory: SQLAlchemy async session factory
        signer: Optional TonSigner instance
        notification_callback: Optional notification callback

    Returns:
        WithdrawalMonitor instance
    """
    return WithdrawalMonitor(
        session_factory=session_factory,
        signer=signer,
        notification_callback=notification_callback,
    )
