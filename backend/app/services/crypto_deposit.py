"""Crypto Deposit Service for handling cryptocurrency deposits.

Phase 5.3: Cryptocurrency deposit processing.

Features:
- User deposit address management
- Deposit detection via webhook
- Automatic KRW conversion using real-time exchange rates
- Transaction confirmation tracking
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.wallet import (
    CryptoAddress,
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


class DepositError(Exception):
    """Deposit processing error."""

    pass


class CryptoDepositService:
    """Cryptocurrency deposit service.

    Handles:
    - Deposit address generation/lookup
    - Deposit webhook processing
    - KRW conversion and balance credit
    """

    # Minimum confirmations required for each crypto
    # 빠른 송금 코인들은 확인 수가 적음
    MIN_CONFIRMATIONS = {
        CryptoType.USDT: 20,   # TRC-20 (Tron network)
        CryptoType.XRP: 1,     # Ripple - 거의 즉시
        CryptoType.TRX: 20,    # Tron
        CryptoType.SOL: 32,    # Solana - 약 12초
    }

    # Minimum deposit amounts (in crypto)
    MIN_DEPOSIT = {
        CryptoType.USDT: "10",    # $10 상당
        CryptoType.XRP: "20",     # ~$10 상당
        CryptoType.TRX: "100",    # ~$10 상당
        CryptoType.SOL: "0.1",    # ~$15 상당
    }

    def __init__(self, session: AsyncSession) -> None:
        """Initialize deposit service."""
        self.session = session
        self._redis = get_redis()
        self._exchange = get_exchange_rate_service()

    async def get_deposit_address(
        self,
        user_id: str,
        crypto_type: CryptoType,
    ) -> str:
        """Get or create user's deposit address.

        Args:
            user_id: User ID
            crypto_type: Cryptocurrency type

        Returns:
            Deposit address string
        """
        # Check cache first
        cache_key = f"deposit_addr:{user_id}:{crypto_type.value}"
        cached = await self._redis.get(cache_key)
        if cached:
            return cached.decode()

        # Check database
        query = select(CryptoAddress).where(
            CryptoAddress.user_id == user_id,
            CryptoAddress.crypto_type == crypto_type,
            CryptoAddress.is_active == True,  # noqa: E712
        )
        result = await self.session.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            # Cache and return
            await self._redis.setex(cache_key, 3600, existing.address)
            return existing.address

        # Generate new address
        # NOTE: In production, this would call a crypto wallet service
        # For now, generate a deterministic test address
        address = self._generate_address(user_id, crypto_type)

        # Save to database
        crypto_addr = CryptoAddress(
            id=str(uuid4()),
            user_id=user_id,
            crypto_type=crypto_type,
            address=address,
            is_active=True,
        )
        self.session.add(crypto_addr)
        await self.session.flush()

        # Cache
        await self._redis.setex(cache_key, 3600, address)

        logger.info(
            f"Generated deposit address: user={user_id[:8]}... "
            f"crypto={crypto_type.value} addr={address[:16]}..."
        )

        return address

    async def handle_deposit_webhook(
        self,
        crypto_type: CryptoType,
        tx_hash: str,
        address: str,
        amount: str,
        confirmations: int,
    ) -> WalletTransaction | None:
        """Process deposit notification from payment gateway.

        Args:
            crypto_type: Cryptocurrency type
            tx_hash: Blockchain transaction hash
            address: Deposit address
            amount: Deposit amount (string for precision)
            confirmations: Number of blockchain confirmations

        Returns:
            WalletTransaction if deposit completed, None if pending
        """
        # Validate confirmations
        min_conf = self.MIN_CONFIRMATIONS[crypto_type]
        if confirmations < min_conf:
            logger.info(
                f"Deposit pending confirmations: {tx_hash[:16]}... "
                f"{confirmations}/{min_conf}"
            )
            return None

        # Check if already processed
        existing = await self._check_processed(tx_hash)
        if existing:
            logger.warning(f"Duplicate deposit webhook: {tx_hash}")
            return existing

        # Find user by deposit address
        query = select(CryptoAddress).where(
            CryptoAddress.address == address,
            CryptoAddress.crypto_type == crypto_type,
            CryptoAddress.is_active == True,  # noqa: E712
        )
        result = await self.session.execute(query)
        crypto_addr = result.scalar_one_or_none()

        if not crypto_addr:
            logger.error(f"Unknown deposit address: {address}")
            raise DepositError(f"Unknown deposit address: {address}")

        user_id = crypto_addr.user_id

        # Get user
        user = await self.session.get(User, user_id)
        if not user:
            raise DepositError(f"User not found: {user_id}")

        # Convert to KRW
        krw_amount, exchange_rate = await self._exchange.convert_crypto_to_krw(
            crypto_type, amount
        )

        # Update user balance
        balance_before = user.krw_balance
        user.krw_balance += krw_amount
        balance_after = user.krw_balance

        # Create transaction record
        tx = WalletTransaction(
            id=str(uuid4()),
            user_id=user_id,
            tx_type=TransactionType.CRYPTO_DEPOSIT,
            status=TransactionStatus.COMPLETED,
            krw_amount=krw_amount,
            krw_balance_before=balance_before,
            krw_balance_after=balance_after,
            crypto_type=crypto_type,
            crypto_amount=amount,
            crypto_tx_hash=tx_hash,
            crypto_address=address,
            exchange_rate_krw=exchange_rate,
            description=(
                f"Crypto deposit: {amount} {crypto_type.value.upper()} "
                f"@ {exchange_rate:,} KRW"
            ),
            integrity_hash=self._compute_integrity_hash(
                user_id,
                TransactionType.CRYPTO_DEPOSIT,
                krw_amount,
                balance_before,
                balance_after,
            ),
        )

        self.session.add(tx)

        # Update deposit address stats
        crypto_addr.total_deposits += 1
        crypto_addr.last_deposit_at = datetime.now(timezone.utc)

        await self.session.flush()

        # Invalidate balance cache
        await self._redis.delete(f"wallet:balance:{user_id}")

        logger.info(
            f"Deposit processed: user={user_id[:8]}... "
            f"crypto={amount} {crypto_type.value.upper()} "
            f"krw={krw_amount:,} rate={exchange_rate:,}"
        )

        return tx

    async def _check_processed(self, tx_hash: str) -> WalletTransaction | None:
        """Check if transaction was already processed."""
        query = select(WalletTransaction).where(
            WalletTransaction.crypto_tx_hash == tx_hash,
            WalletTransaction.tx_type == TransactionType.CRYPTO_DEPOSIT,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    def _generate_address(user_id: str, crypto_type: CryptoType) -> str:
        """Generate test deposit address.

        NOTE: In production, call actual wallet service API.
        This is for testing/development only.
        """
        # Create deterministic address based on user and crypto type
        data = f"{user_id}:{crypto_type.value}:deposit"
        hash_val = hashlib.sha256(data.encode()).hexdigest()

        # Format based on crypto type
        if crypto_type == CryptoType.USDT:
            # TRC-20 address (Tron network)
            return f"T{hash_val[:33]}"
        elif crypto_type == CryptoType.XRP:
            # Ripple address
            return f"r{hash_val[:33]}"
        elif crypto_type == CryptoType.TRX:
            # Tron address
            return f"T{hash_val[:33]}"
        elif crypto_type == CryptoType.SOL:
            # Solana address (base58)
            return f"{hash_val[:44]}"
        else:
            return f"0x{hash_val[:40]}"

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
