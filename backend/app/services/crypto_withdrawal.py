"""Crypto Withdrawal Service for handling cryptocurrency withdrawals.

Phase 5.4: Cryptocurrency withdrawal processing.

Features:
- 24-hour pending period for security
- Withdrawal limits and validation
- Automatic crypto amount calculation
- Status tracking and processing
"""

import hashlib
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.wallet import (
    CryptoType,
    TransactionStatus,
    TransactionType,
    WalletTransaction,
)
from app.services.exchange_rate import (
    ExchangeRateService,
    get_exchange_rate_service,
)
from app.utils.redis_client import get_redis

logger = logging.getLogger(__name__)


class WithdrawalError(Exception):
    """Withdrawal processing error."""

    pass


class InsufficientBalanceError(WithdrawalError):
    """Insufficient balance for withdrawal."""

    pass


class WithdrawalLimitError(WithdrawalError):
    """Withdrawal limit exceeded."""

    pass


class CryptoWithdrawalService:
    """Cryptocurrency withdrawal service.

    Features:
    - 24-hour security pending period
    - Minimum/maximum withdrawal limits
    - Automatic crypto conversion
    - Cancellation support
    """

    PENDING_HOURS = 24  # Withdrawal pending period
    MIN_WITHDRAWAL_KRW = 10000  # Minimum ₩10,000
    MAX_WITHDRAWAL_KRW = 100000000  # Maximum ₩100,000,000 per transaction
    MAX_DAILY_WITHDRAWAL_KRW = 500000000  # Daily limit ₩500,000,000

    # Auto-approve threshold (no manual review needed)
    AUTO_APPROVE_LIMIT_KRW = 1000000  # ₩1,000,000

    def __init__(self, session: AsyncSession) -> None:
        """Initialize withdrawal service."""
        self.session = session
        self._redis = get_redis()
        self._exchange = get_exchange_rate_service()

    async def request_withdrawal(
        self,
        user_id: str,
        krw_amount: int,
        crypto_type: CryptoType,
        crypto_address: str,
    ) -> WalletTransaction:
        """Request cryptocurrency withdrawal.

        Args:
            user_id: User ID
            krw_amount: Amount to withdraw in KRW
            crypto_type: Target cryptocurrency
            crypto_address: Destination wallet address

        Returns:
            WalletTransaction in PENDING status

        Raises:
            InsufficientBalanceError: Not enough balance
            WithdrawalLimitError: Limit exceeded
            WithdrawalError: Other errors
        """
        # Validate amount
        if krw_amount < self.MIN_WITHDRAWAL_KRW:
            raise WithdrawalError(f"Minimum withdrawal is ₩{self.MIN_WITHDRAWAL_KRW:,}")

        if krw_amount > self.MAX_WITHDRAWAL_KRW:
            raise WithdrawalError(f"Maximum withdrawal is ₩{self.MAX_WITHDRAWAL_KRW:,}")

        # Validate address format
        if not self._validate_address(crypto_address, crypto_type):
            raise WithdrawalError(f"Invalid {crypto_type.value} address")

        # Get user and check balance
        user = await self.session.get(User, user_id)
        if not user:
            raise WithdrawalError(f"User not found: {user_id}")

        available = user.krw_balance - user.pending_withdrawal_krw
        if available < krw_amount:
            raise InsufficientBalanceError(
                f"Insufficient balance: available ₩{available:,}, "
                f"requested ₩{krw_amount:,}"
            )

        # Check daily limit
        daily_total = await self._get_daily_withdrawal_total(user_id)
        if daily_total + krw_amount > self.MAX_DAILY_WITHDRAWAL_KRW:
            raise WithdrawalLimitError(
                f"Daily limit exceeded: ₩{daily_total:,} + ₩{krw_amount:,} > "
                f"₩{self.MAX_DAILY_WITHDRAWAL_KRW:,}"
            )

        # Convert KRW to crypto
        crypto_amount, exchange_rate = await self._exchange.convert_krw_to_crypto(
            crypto_type, krw_amount
        )

        # Lock the amount (move to pending)
        balance_before = user.krw_balance
        user.krw_balance -= krw_amount
        user.pending_withdrawal_krw += krw_amount
        balance_after = user.krw_balance

        # Create pending transaction
        tx = WalletTransaction(
            id=str(uuid4()),
            user_id=user_id,
            tx_type=TransactionType.CRYPTO_WITHDRAWAL,
            status=TransactionStatus.PENDING,
            krw_amount=-krw_amount,  # Negative for withdrawal
            krw_balance_before=balance_before,
            krw_balance_after=balance_after,
            crypto_type=crypto_type,
            crypto_amount=str(crypto_amount),
            crypto_address=crypto_address,
            exchange_rate_krw=exchange_rate,
            withdrawal_requested_at=datetime.utcnow(),
            description=(
                f"Withdrawal request: ₩{krw_amount:,} → "
                f"{crypto_amount:.8f} {crypto_type.value.upper()}"
            ),
            integrity_hash=self._compute_integrity_hash(
                user_id,
                TransactionType.CRYPTO_WITHDRAWAL,
                -krw_amount,
                balance_before,
                balance_after,
            ),
        )

        self.session.add(tx)
        await self.session.flush()

        # Invalidate balance cache
        await self._redis.delete(f"wallet:balance:{user_id}")

        logger.info(
            f"Withdrawal requested: user={user_id[:8]}... "
            f"krw={krw_amount:,} crypto={crypto_amount:.8f} {crypto_type.value}"
        )

        return tx

    async def cancel_withdrawal(
        self,
        user_id: str,
        transaction_id: str,
    ) -> WalletTransaction:
        """Cancel a pending withdrawal.

        Args:
            user_id: User ID
            transaction_id: Transaction ID to cancel

        Returns:
            Cancelled WalletTransaction

        Raises:
            WithdrawalError: If cancellation not allowed
        """
        # Get the transaction
        tx = await self.session.get(WalletTransaction, transaction_id)
        if not tx:
            raise WithdrawalError(f"Transaction not found: {transaction_id}")

        if tx.user_id != user_id:
            raise WithdrawalError("Permission denied")

        if tx.status != TransactionStatus.PENDING:
            raise WithdrawalError(f"Cannot cancel {tx.status.value} withdrawal")

        # Restore the balance
        user = await self.session.get(User, user_id)
        amount = abs(tx.krw_amount)
        user.krw_balance += amount
        user.pending_withdrawal_krw -= amount

        # Update transaction status
        tx.status = TransactionStatus.CANCELLED
        tx.description = f"{tx.description} [CANCELLED by user]"

        await self.session.flush()

        # Invalidate balance cache
        await self._redis.delete(f"wallet:balance:{user_id}")

        logger.info(
            f"Withdrawal cancelled: user={user_id[:8]}... "
            f"tx={transaction_id[:8]}... amount=₩{amount:,}"
        )

        return tx

    async def process_pending_withdrawals(self) -> list[WalletTransaction]:
        """Process pending withdrawals past the security period.

        This should be called by a scheduled job.

        Returns:
            List of processed transactions
        """
        cutoff = datetime.utcnow() - timedelta(hours=self.PENDING_HOURS)

        # Get pending withdrawals older than 24 hours
        query = select(WalletTransaction).where(
            WalletTransaction.tx_type == TransactionType.CRYPTO_WITHDRAWAL,
            WalletTransaction.status == TransactionStatus.PENDING,
            WalletTransaction.withdrawal_requested_at <= cutoff,
        )
        result = await self.session.execute(query)
        pending = list(result.scalars().all())

        processed = []
        for tx in pending:
            try:
                await self._execute_withdrawal(tx)
                processed.append(tx)
            except Exception as e:
                logger.error(f"Failed to process withdrawal {tx.id}: {e}")
                tx.status = TransactionStatus.FAILED
                tx.admin_note = f"Processing failed: {e}"

        await self.session.flush()
        return processed

    async def _execute_withdrawal(self, tx: WalletTransaction) -> None:
        """Execute a withdrawal to the blockchain.

        NOTE: In production, this would call the crypto wallet service.
        """
        # Mark as processing
        tx.status = TransactionStatus.PROCESSING

        # Simulate blockchain transaction
        # In production: call wallet API, get tx_hash
        fake_tx_hash = f"0x{hashlib.sha256(tx.id.encode()).hexdigest()}"
        tx.crypto_tx_hash = fake_tx_hash

        # Mark as completed
        tx.status = TransactionStatus.COMPLETED
        tx.withdrawal_processed_at = datetime.utcnow()

        # Release from pending
        user = await self.session.get(User, tx.user_id)
        if user:
            user.pending_withdrawal_krw -= abs(tx.krw_amount)

        logger.info(
            f"Withdrawal executed: tx={tx.id[:8]}... " f"hash={fake_tx_hash[:16]}..."
        )

    async def _get_daily_withdrawal_total(self, user_id: str) -> int:
        """Get total withdrawals in the last 24 hours."""
        cutoff = datetime.utcnow() - timedelta(hours=24)

        query = select(WalletTransaction).where(
            WalletTransaction.user_id == user_id,
            WalletTransaction.tx_type == TransactionType.CRYPTO_WITHDRAWAL,
            WalletTransaction.status.in_(
                [
                    TransactionStatus.PENDING,
                    TransactionStatus.PROCESSING,
                    TransactionStatus.COMPLETED,
                ]
            ),
            WalletTransaction.created_at >= cutoff,
        )
        result = await self.session.execute(query)
        transactions = result.scalars().all()

        return sum(abs(tx.krw_amount) for tx in transactions)

    @staticmethod
    def _validate_address(address: str, crypto_type: CryptoType) -> bool:
        """Validate cryptocurrency address format."""
        if not address:
            return False

        if crypto_type == CryptoType.BTC:
            # Basic Bitcoin address validation
            return address.startswith(("1", "3", "bc1")) and 26 <= len(address) <= 62
        elif crypto_type in (CryptoType.ETH, CryptoType.USDT, CryptoType.USDC):
            # Basic Ethereum address validation
            return address.startswith("0x") and len(address) == 42

        return False

    @staticmethod
    def _compute_integrity_hash(
        user_id: str,
        tx_type: TransactionType,
        amount: int,
        balance_before: int,
        balance_after: int,
    ) -> str:
        """Compute SHA-256 integrity hash."""
        data = f"{user_id}:{tx_type.value}:{amount}:{balance_before}:{balance_after}"
        return hashlib.sha256(data.encode()).hexdigest()
