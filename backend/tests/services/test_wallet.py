"""Tests for WalletService.

Tests for KRW balance operations, transfers, and integrity verification.
"""

import hashlib
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.wallet import TransactionStatus, TransactionType, WalletTransaction
from app.services.wallet import (
    InsufficientBalanceError,
    WalletError,
    WalletService,
)


class TestWalletServiceGetBalance:
    """Tests for balance retrieval."""

    @pytest.fixture
    def wallet_service(self):
        """Create WalletService with mocked dependencies."""
        mock_session = MagicMock()
        service = WalletService(mock_session)
        service._redis = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_get_balance_from_cache(self, wallet_service):
        """Should return cached balance when available."""
        wallet_service._redis.get.return_value = b"1000000"

        balance = await wallet_service.get_balance("user-123")

        assert balance == 1000000
        wallet_service._redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_balance_from_db_when_cache_miss(self, wallet_service):
        """Should fetch from DB and cache when cache miss."""
        wallet_service._redis.get.return_value = None

        mock_user = MagicMock()
        mock_user.krw_balance = 500000
        wallet_service.session.get = AsyncMock(return_value=mock_user)

        balance = await wallet_service.get_balance("user-123")

        assert balance == 500000
        wallet_service._redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_balance_user_not_found(self, wallet_service):
        """Should raise error when user not found."""
        wallet_service._redis.get.return_value = None
        wallet_service.session.get = AsyncMock(return_value=None)

        with pytest.raises(WalletError, match="User not found"):
            await wallet_service.get_balance("nonexistent-user")


class TestWalletServiceTransfer:
    """Tests for KRW transfer operations."""

    @pytest.fixture
    def wallet_service(self):
        """Create WalletService with mocked dependencies."""
        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        service = WalletService(mock_session)
        service._redis = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_transfer_credit(self, wallet_service):
        """Should credit balance correctly."""
        mock_user = MagicMock()
        mock_user.krw_balance = 100000
        wallet_service.session.get = AsyncMock(return_value=mock_user)
        wallet_service._redis.set.return_value = True

        tx = await wallet_service.transfer_krw(
            user_id="user-123",
            amount=50000,
            tx_type=TransactionType.WIN,
        )

        assert tx.krw_amount == 50000
        assert tx.krw_balance_before == 100000
        assert tx.krw_balance_after == 150000
        assert mock_user.krw_balance == 150000

    @pytest.mark.asyncio
    async def test_transfer_debit(self, wallet_service):
        """Should debit balance correctly."""
        mock_user = MagicMock()
        mock_user.krw_balance = 100000
        wallet_service.session.get = AsyncMock(return_value=mock_user)
        wallet_service._redis.set.return_value = True

        tx = await wallet_service.transfer_krw(
            user_id="user-123",
            amount=-30000,
            tx_type=TransactionType.BUY_IN,
        )

        assert tx.krw_amount == -30000
        assert tx.krw_balance_before == 100000
        assert tx.krw_balance_after == 70000
        assert mock_user.krw_balance == 70000

    @pytest.mark.asyncio
    async def test_transfer_insufficient_balance(self, wallet_service):
        """Should raise error when insufficient balance."""
        mock_user = MagicMock()
        mock_user.krw_balance = 10000
        wallet_service.session.get = AsyncMock(return_value=mock_user)
        wallet_service._redis.set.return_value = True

        with pytest.raises(InsufficientBalanceError):
            await wallet_service.transfer_krw(
                user_id="user-123",
                amount=-50000,
                tx_type=TransactionType.BUY_IN,
            )

    @pytest.mark.asyncio
    async def test_transfer_zero_amount_rejected(self, wallet_service):
        """Should reject zero amount transfer."""
        wallet_service._redis.set.return_value = True

        with pytest.raises(WalletError, match="Amount cannot be zero"):
            await wallet_service.transfer_krw(
                user_id="user-123",
                amount=0,
                tx_type=TransactionType.WIN,
            )

    @pytest.mark.asyncio
    async def test_transfer_lock_failure(self, wallet_service):
        """Should raise error when lock cannot be acquired."""
        wallet_service._redis.set.return_value = False

        with pytest.raises(WalletError, match="Could not acquire wallet lock"):
            await wallet_service.transfer_krw(
                user_id="user-123",
                amount=10000,
                tx_type=TransactionType.WIN,
            )


class TestWalletServiceBuyInCashOut:
    """Tests for table buy-in and cash-out."""

    @pytest.fixture
    def wallet_service(self):
        """Create WalletService with mocked dependencies."""
        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        service = WalletService(mock_session)
        service._redis = AsyncMock()
        service._redis.set.return_value = True
        return service

    @pytest.mark.asyncio
    async def test_buy_in_success(self, wallet_service):
        """Should process buy-in correctly."""
        mock_user = MagicMock()
        mock_user.krw_balance = 500000
        wallet_service.session.get = AsyncMock(return_value=mock_user)

        tx = await wallet_service.buy_in(
            user_id="user-123",
            amount=100000,
            table_id="table-456",
        )

        assert tx.tx_type == TransactionType.BUY_IN
        assert tx.krw_amount == -100000
        assert tx.table_id == "table-456"

    @pytest.mark.asyncio
    async def test_buy_in_negative_amount_rejected(self, wallet_service):
        """Should reject negative buy-in amount."""
        with pytest.raises(WalletError, match="Buy-in amount must be positive"):
            await wallet_service.buy_in(
                user_id="user-123",
                amount=-10000,
                table_id="table-456",
            )

    @pytest.mark.asyncio
    async def test_cash_out_success(self, wallet_service):
        """Should process cash-out correctly."""
        mock_user = MagicMock()
        mock_user.krw_balance = 100000
        wallet_service.session.get = AsyncMock(return_value=mock_user)

        tx = await wallet_service.cash_out(
            user_id="user-123",
            amount=200000,
            table_id="table-456",
        )

        assert tx.tx_type == TransactionType.CASH_OUT
        assert tx.krw_amount == 200000
        assert tx.table_id == "table-456"

    @pytest.mark.asyncio
    async def test_cash_out_negative_amount_rejected(self, wallet_service):
        """Should reject negative cash-out amount."""
        with pytest.raises(WalletError, match="Cash-out amount must be positive"):
            await wallet_service.cash_out(
                user_id="user-123",
                amount=-10000,
                table_id="table-456",
            )


class TestWalletServiceIntegrity:
    """Tests for transaction integrity verification."""

    def test_compute_integrity_hash(self):
        """Should compute consistent integrity hash."""
        hash1 = WalletService._compute_integrity_hash(
            user_id="user-123",
            tx_type=TransactionType.WIN,
            amount=50000,
            balance_before=100000,
            balance_after=150000,
        )

        hash2 = WalletService._compute_integrity_hash(
            user_id="user-123",
            tx_type=TransactionType.WIN,
            amount=50000,
            balance_before=100000,
            balance_after=150000,
        )

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex

    def test_integrity_hash_changes_with_data(self):
        """Different data should produce different hashes."""
        hash1 = WalletService._compute_integrity_hash(
            user_id="user-123",
            tx_type=TransactionType.WIN,
            amount=50000,
            balance_before=100000,
            balance_after=150000,
        )

        hash2 = WalletService._compute_integrity_hash(
            user_id="user-123",
            tx_type=TransactionType.WIN,
            amount=50001,  # Different amount
            balance_before=100000,
            balance_after=150001,
        )

        assert hash1 != hash2

    def test_verify_integrity_valid(self):
        """Should verify valid transaction integrity."""
        tx = MagicMock()
        tx.user_id = "user-123"
        tx.tx_type = TransactionType.WIN
        tx.krw_amount = 50000
        tx.krw_balance_before = 100000
        tx.krw_balance_after = 150000
        tx.integrity_hash = WalletService._compute_integrity_hash(
            "user-123", TransactionType.WIN, 50000, 100000, 150000
        )

        assert WalletService.verify_integrity(tx) is True

    def test_verify_integrity_tampered(self):
        """Should detect tampered transaction."""
        tx = MagicMock()
        tx.user_id = "user-123"
        tx.tx_type = TransactionType.WIN
        tx.krw_amount = 50000
        tx.krw_balance_before = 100000
        tx.krw_balance_after = 150000
        tx.integrity_hash = "tampered_hash_value"

        assert WalletService.verify_integrity(tx) is False


class TestWalletServiceRake:
    """Tests for rake deduction."""

    @pytest.fixture
    def wallet_service(self):
        """Create WalletService with mocked dependencies."""
        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        service = WalletService(mock_session)
        service._redis = AsyncMock()
        service._redis.set.return_value = True
        return service

    @pytest.mark.asyncio
    async def test_deduct_rake_updates_total(self, wallet_service):
        """Should update user's total rake paid."""
        mock_user = MagicMock()
        mock_user.krw_balance = 100000
        mock_user.total_rake_paid_krw = 50000
        wallet_service.session.get = AsyncMock(return_value=mock_user)

        tx = await wallet_service.deduct_rake(
            user_id="user-123",
            amount=5000,
            table_id="table-456",
            hand_id="hand-789",
        )

        assert tx.tx_type == TransactionType.RAKE
        assert tx.krw_amount == -5000
        assert mock_user.total_rake_paid_krw == 55000

    @pytest.mark.asyncio
    async def test_deduct_rake_zero_returns_none(self, wallet_service):
        """Should return None for zero rake."""
        result = await wallet_service.deduct_rake(
            user_id="user-123",
            amount=0,
            table_id="table-456",
            hand_id="hand-789",
        )

        assert result is None
