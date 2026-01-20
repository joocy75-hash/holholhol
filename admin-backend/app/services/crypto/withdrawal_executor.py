"""Withdrawal Executor Service for automated crypto withdrawals.

Processes approved withdrawals by:
1. Building and signing Jetton transfer transactions
2. Broadcasting to TON network
3. Recording transaction hashes
4. Handling retries on failure

Security Notes:
- Only processes PROCESSING status withdrawals (admin-approved)
- Uses KMS for transaction signing (no key exposure)
- All operations are logged for audit trail
- Automatic retry with exponential backoff
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.models.crypto import CryptoWithdrawal, TransactionStatus
from app.models.audit_log import AuditLog
from app.services.crypto.ton_signer import (
    TonSigner,
    JettonTransferParams,
    TonSignerError,
    InsufficientGasError,
    get_ton_signer,
)
from app.services.crypto.kms_service import KeyManagementService, get_kms_service

logger = logging.getLogger(__name__)
settings = get_settings()


# ============================================================
# Exceptions
# ============================================================

class WithdrawalExecutorError(Exception):
    """Base exception for withdrawal executor."""
    pass


class WithdrawalExecutionFailed(WithdrawalExecutorError):
    """Withdrawal execution failed."""
    pass


# ============================================================
# Withdrawal Executor Service
# ============================================================

class WithdrawalExecutor:
    """Automated withdrawal executor service.

    Processes approved (PROCESSING status) withdrawals by:
    1. Fetching pending withdrawals
    2. Building Jetton transfer transactions
    3. Signing via KMS
    4. Broadcasting to TON network
    5. Recording TX hash and updating status

    Configuration:
    - withdrawal_auto_enabled: Enable/disable auto execution
    - withdrawal_auto_threshold_usdt: Max amount for auto processing
    - withdrawal_max_retry: Maximum retry attempts
    """

    def __init__(
        self,
        session_factory: async_sessionmaker,
        signer: Optional[TonSigner] = None,
        kms: Optional[KeyManagementService] = None,
    ):
        """Initialize withdrawal executor.

        Args:
            session_factory: SQLAlchemy async session factory
            signer: TON signer instance (auto-created if None)
            kms: KMS instance (passed to signer if provided)
        """
        self.session_factory = session_factory
        self._kms = kms or get_kms_service()
        self._signer = signer or get_ton_signer(self._kms)
        self._running = False
        self._retry_counts: dict[str, int] = {}  # withdrawal_id -> retry count

        logger.info(
            f"WithdrawalExecutor initialized, "
            f"auto_enabled={settings.withdrawal_auto_enabled}, "
            f"threshold={settings.withdrawal_auto_threshold_usdt} USDT"
        )

    async def close(self) -> None:
        """Close connections and cleanup."""
        self._running = False
        await self._signer.close()
        logger.info("WithdrawalExecutor closed")

    # ============================================================
    # Main Processing Loop
    # ============================================================

    async def start(self) -> None:
        """Start processing withdrawals in background.

        This is the main entry point for automated withdrawal processing.
        Runs until stopped.
        """
        if not settings.withdrawal_auto_enabled:
            logger.warning(
                "Withdrawal automation is disabled. "
                "Set WITHDRAWAL_AUTO_ENABLED=true to enable."
            )
            return

        self._running = True
        logger.info("WithdrawalExecutor started")

        while self._running:
            try:
                await self.process_pending_withdrawals()
            except Exception as e:
                logger.error(f"Error in withdrawal processing loop: {e}")

            # Wait before next iteration
            await asyncio.sleep(10)  # 10 seconds between batches

    async def stop(self) -> None:
        """Stop the processing loop."""
        self._running = False
        logger.info("WithdrawalExecutor stopping...")

    # ============================================================
    # Processing Methods
    # ============================================================

    async def process_pending_withdrawals(self) -> List[CryptoWithdrawal]:
        """Process all pending (PROCESSING status) withdrawals.

        Returns:
            List of processed withdrawals
        """
        async with self.session_factory() as session:
            # Get PROCESSING withdrawals without TX hash
            withdrawals = await self._get_pending_withdrawals(session)

            if not withdrawals:
                return []

            processed = []
            for withdrawal in withdrawals:
                try:
                    result = await self._execute_withdrawal(session, withdrawal)
                    if result:
                        processed.append(withdrawal)
                except Exception as e:
                    logger.error(
                        f"Failed to process withdrawal {withdrawal.id}: {e}"
                    )

            return processed

    async def execute_single(
        self,
        withdrawal_id: UUID,
        admin_id: str = "system",
    ) -> bool:
        """Execute a single withdrawal by ID.

        Called when admin triggers manual execution.

        Args:
            withdrawal_id: Withdrawal UUID
            admin_id: Admin user ID (for audit)

        Returns:
            True if successful
        """
        async with self.session_factory() as session:
            # Get withdrawal
            result = await session.execute(
                select(CryptoWithdrawal).where(
                    CryptoWithdrawal.id == withdrawal_id
                )
            )
            withdrawal = result.scalar_one_or_none()

            if not withdrawal:
                raise WithdrawalExecutorError(f"Withdrawal not found: {withdrawal_id}")

            if withdrawal.status != TransactionStatus.PROCESSING:
                raise WithdrawalExecutorError(
                    f"Invalid status for execution: {withdrawal.status}"
                )

            if withdrawal.tx_hash:
                raise WithdrawalExecutorError(
                    f"Transaction already sent: {withdrawal.tx_hash}"
                )

            return await self._execute_withdrawal(session, withdrawal, admin_id)

    async def _execute_withdrawal(
        self,
        session: AsyncSession,
        withdrawal: CryptoWithdrawal,
        admin_id: str = "system",
    ) -> bool:
        """Execute a single withdrawal.

        Args:
            session: Database session
            withdrawal: Withdrawal record
            admin_id: Admin ID for audit

        Returns:
            True if successful
        """
        withdrawal_id = str(withdrawal.id)

        # Check retry count
        retry_count = self._retry_counts.get(withdrawal_id, 0)
        if retry_count >= settings.withdrawal_max_retry:
            logger.warning(
                f"Withdrawal {withdrawal_id} exceeded max retries ({retry_count}), marking failed"
            )
            await self._mark_failed(
                session,
                withdrawal,
                f"최대 재시도 횟수 초과 ({retry_count}회)",
                admin_id,
            )
            return False

        try:
            # Check threshold for auto-processing
            if float(withdrawal.amount_usdt) > settings.withdrawal_auto_threshold_usdt:
                logger.info(
                    f"Withdrawal {withdrawal_id} exceeds auto threshold "
                    f"({withdrawal.amount_usdt} > {settings.withdrawal_auto_threshold_usdt}), "
                    f"requires manual approval"
                )
                return False

            # Build transfer parameters
            params = JettonTransferParams(
                to_address=withdrawal.to_address,
                amount=Decimal(str(withdrawal.amount_usdt)),
                memo=f"Withdrawal:{withdrawal_id[:8]}",
            )

            # Execute transfer
            logger.info(
                f"Executing withdrawal {withdrawal_id}: "
                f"{withdrawal.amount_usdt} USDT to {withdrawal.to_address[:10]}..."
            )

            result = await self._signer.transfer_jetton(params)

            if result.success and result.tx_hash:
                # Update withdrawal with TX hash
                withdrawal.tx_hash = result.tx_hash
                withdrawal.processed_at = datetime.now(timezone.utc)

                # Create audit log
                await self._create_audit_log(
                    session,
                    action="withdrawal_executed",
                    target_id=withdrawal_id,
                    admin_id=admin_id,
                    details={
                        "tx_hash": result.tx_hash,
                        "amount_usdt": str(withdrawal.amount_usdt),
                        "to_address": withdrawal.to_address,
                        "retry_count": retry_count,
                    },
                )

                await session.commit()

                # Clear retry count on success
                self._retry_counts.pop(withdrawal_id, None)

                logger.info(
                    f"Withdrawal {withdrawal_id} executed successfully, "
                    f"tx_hash={result.tx_hash}"
                )
                return True

            else:
                # Transaction failed
                self._retry_counts[withdrawal_id] = retry_count + 1
                logger.error(
                    f"Withdrawal {withdrawal_id} failed: {result.message}, "
                    f"retry {retry_count + 1}/{settings.withdrawal_max_retry}"
                )
                return False

        except InsufficientGasError as e:
            # Not enough TON for gas - critical error
            logger.error(f"Insufficient gas for withdrawal {withdrawal_id}: {e}")
            await self._mark_failed(
                session,
                withdrawal,
                f"가스비 부족: {e}",
                admin_id,
            )
            return False

        except TonSignerError as e:
            # Signer error - retry
            self._retry_counts[withdrawal_id] = retry_count + 1
            logger.error(
                f"Signer error for withdrawal {withdrawal_id}: {e}, "
                f"retry {retry_count + 1}/{settings.withdrawal_max_retry}"
            )
            return False

        except Exception as e:
            # Unexpected error
            self._retry_counts[withdrawal_id] = retry_count + 1
            logger.error(
                f"Unexpected error for withdrawal {withdrawal_id}: {e}",
                exc_info=True,
            )
            return False

    # ============================================================
    # Helper Methods
    # ============================================================

    async def _get_pending_withdrawals(
        self,
        session: AsyncSession,
        limit: int = 10,
    ) -> List[CryptoWithdrawal]:
        """Get withdrawals ready for execution.

        Criteria:
        - Status is PROCESSING (admin approved)
        - No TX hash yet (not sent)
        - Amount within auto threshold
        """
        query = (
            select(CryptoWithdrawal)
            .where(
                and_(
                    CryptoWithdrawal.status == TransactionStatus.PROCESSING,
                    CryptoWithdrawal.tx_hash.is_(None),
                    CryptoWithdrawal.amount_usdt <= settings.withdrawal_auto_threshold_usdt,
                )
            )
            .order_by(CryptoWithdrawal.approved_at.asc())
            .limit(limit)
        )

        result = await session.execute(query)
        return list(result.scalars().all())

    async def _mark_failed(
        self,
        session: AsyncSession,
        withdrawal: CryptoWithdrawal,
        reason: str,
        admin_id: str,
    ) -> None:
        """Mark withdrawal as failed.

        Args:
            session: Database session
            withdrawal: Withdrawal record
            reason: Failure reason
            admin_id: Admin ID for audit
        """
        withdrawal.status = TransactionStatus.FAILED
        withdrawal.rejection_reason = reason
        withdrawal.processed_at = datetime.now(timezone.utc)

        await self._create_audit_log(
            session,
            action="withdrawal_failed",
            target_id=str(withdrawal.id),
            admin_id=admin_id,
            details={
                "reason": reason,
                "amount_usdt": str(withdrawal.amount_usdt),
                "to_address": withdrawal.to_address,
            },
        )

        await session.commit()

        # Clear retry count
        self._retry_counts.pop(str(withdrawal.id), None)

        logger.warning(
            f"Withdrawal {withdrawal.id} marked as FAILED: {reason}"
        )

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

    # ============================================================
    # Status Methods
    # ============================================================

    async def get_executor_status(self) -> dict:
        """Get current executor status.

        Returns:
            dict with status information
        """
        async with self.session_factory() as session:
            # Count pending withdrawals
            pending_query = select(CryptoWithdrawal).where(
                and_(
                    CryptoWithdrawal.status == TransactionStatus.PROCESSING,
                    CryptoWithdrawal.tx_hash.is_(None),
                )
            )
            result = await session.execute(pending_query)
            pending_count = len(result.scalars().all())

            # Get hot wallet USDT balance
            try:
                usdt_balance = await self._signer.get_balance()
            except Exception:
                usdt_balance = Decimal("0")

            return {
                "enabled": settings.withdrawal_auto_enabled,
                "running": self._running,
                "pending_count": pending_count,
                "retry_queue_size": len(self._retry_counts),
                "auto_threshold_usdt": settings.withdrawal_auto_threshold_usdt,
                "max_retry": settings.withdrawal_max_retry,
                "hot_wallet_usdt": float(usdt_balance),
            }


# ============================================================
# Factory Function
# ============================================================

def get_withdrawal_executor(
    session_factory: async_sessionmaker,
    signer: Optional[TonSigner] = None,
) -> WithdrawalExecutor:
    """Get WithdrawalExecutor instance.

    Args:
        session_factory: SQLAlchemy async session factory
        signer: Optional TonSigner instance

    Returns:
        WithdrawalExecutor instance
    """
    return WithdrawalExecutor(session_factory=session_factory, signer=signer)
