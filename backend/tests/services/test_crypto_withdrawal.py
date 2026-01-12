"""Tests for CryptoWithdrawalService.

Tests for cryptocurrency withdrawal operations.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.wallet import CryptoType, TransactionStatus, TransactionType
from app.services.crypto_withdrawal import (
    CryptoWithdrawalService,
    InsufficientBalanceError,
    InvalidAddressError,
    WithdrawalError,
    WithdrawalLimitError,
)


class TestCryptoWithdrawalServiceValidation:
    """Tests for withdrawal validation."""

    @pytest.fixture
    def withdrawal_service(self):
        """Create CryptoWithdrawalService with mocked dependencies."""
        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        service = CryptoWithdrawalService(mock_session)
        service._redis = AsyncMock()
        service._exchange = MagicMock()
        service._exchange.convert_krw_to_crypto = AsyncMock(
            return_value=("100.0", 1300)
        )
        return service

    @pytest.mark.asyncio
    async def test_request_withdrawal_below_minimum(self, withdrawal_service):
        """Should reject withdrawal below minimum."""
        with pytest.raises(WithdrawalError, match="Minimum withdrawal"):
            await withdrawal_service.request_withdrawal(
                user_id="user-123",
                krw_amount=5000,  # Below 10,000 minimum
                crypto_type=CryptoType.USDT,
                crypto_address="T" + "a" * 33,
            )

    @pytest.mark.asyncio
    async def test_request_withdrawal_above_maximum(self, withdrawal_service):
        """Should reject withdrawal above maximum."""
        with pytest.raises(WithdrawalError, match="Maximum withdrawal"):
            await withdrawal_service.request_withdrawal(
                user_id="user-123",
                krw_amount=200_000_000,  # Above 100,000,000 maximum
                crypto_type=CryptoType.USDT,
                crypto_address="T" + "a" * 33,
            )


class TestCryptoWithdrawalServiceAddressValidation:
    """Tests for address validation."""

    def test_validate_usdt_address_valid(self):
        """Should validate valid USDT (TRC-20) address."""
        # TRC-20 address: starts with T, 34 characters
        valid_address = "T" + "a" * 33
        result = CryptoWithdrawalService._validate_address(
            valid_address, CryptoType.USDT
        )
        assert result is True

    def test_validate_usdt_address_invalid_prefix(self):
        """Should reject USDT address with wrong prefix."""
        invalid_address = "0x" + "a" * 32
        result = CryptoWithdrawalService._validate_address(
            invalid_address, CryptoType.USDT
        )
        assert result is False

    def test_validate_usdt_address_invalid_length(self):
        """Should reject USDT address with wrong length."""
        invalid_address = "T" + "a" * 30  # Too short
        result = CryptoWithdrawalService._validate_address(
            invalid_address, CryptoType.USDT
        )
        assert result is False

    def test_validate_xrp_address_valid(self):
        """Should validate valid XRP address."""
        # XRP address: starts with r, 25-35 characters
        valid_address = "r" + "a" * 30
        result = CryptoWithdrawalService._validate_address(
            valid_address, CryptoType.XRP
        )
        assert result is True

    def test_validate_xrp_address_invalid_prefix(self):
        """Should reject XRP address with wrong prefix."""
        invalid_address = "x" + "a" * 30
        result = CryptoWithdrawalService._validate_address(
            invalid_address, CryptoType.XRP
        )
        assert result is False

    def test_validate_trx_address_valid(self):
        """Should validate valid TRX address."""
        # TRX address: starts with T, 34 characters
        valid_address = "T" + "a" * 33
        result = CryptoWithdrawalService._validate_address(
            valid_address, CryptoType.TRX
        )
        assert result is True

    def test_validate_sol_address_valid(self):
        """Should validate valid SOL address."""
        # SOL address: base58, 32-44 characters
        valid_address = "a" * 40
        result = CryptoWithdrawalService._validate_address(
            valid_address, CryptoType.SOL
        )
        assert result is True

    def test_validate_sol_address_too_short(self):
        """Should reject SOL address that's too short."""
        invalid_address = "a" * 20
        result = CryptoWithdrawalService._validate_address(
            invalid_address, CryptoType.SOL
        )
        assert result is False

    def test_validate_empty_address(self):
        """Should reject empty address."""
        result = CryptoWithdrawalService._validate_address("", CryptoType.USDT)
        assert result is False


class TestCryptoWithdrawalServiceRequest:
    """Tests for withdrawal request processing."""

    @pytest.fixture
    def withdrawal_service(self):
        """Create CryptoWithdrawalService with mocked dependencies."""
        from decimal import Decimal
        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        service = CryptoWithdrawalService(mock_session)
        service._redis = AsyncMock()
        service._exchange = MagicMock()
        service._exchange.convert_krw_to_crypto = AsyncMock(
            return_value=(Decimal("76.92"), 1300)
        )
        return service

    @pytest.mark.asyncio
    async def test_request_withdrawal_insufficient_balance(self, withdrawal_service):
        """Should reject withdrawal with insufficient balance."""
        mock_user = MagicMock()
        mock_user.krw_balance = 50000
        mock_user.pending_withdrawal_krw = 0
        withdrawal_service.session.get = AsyncMock(return_value=mock_user)

        # Mock address validator to return valid
        with patch.object(
            withdrawal_service,
            "_validate_address_with_checksum",
            return_value=MagicMock(is_valid=True),
        ):
            with pytest.raises(InsufficientBalanceError):
                await withdrawal_service.request_withdrawal(
                    user_id="user-123",
                    krw_amount=100000,
                    crypto_type=CryptoType.USDT,
                    crypto_address="T" + "a" * 33,
                )

    @pytest.mark.asyncio
    async def test_request_withdrawal_success(self, withdrawal_service):
        """Should create pending withdrawal successfully."""
        mock_user = MagicMock()
        mock_user.krw_balance = 500000
        mock_user.pending_withdrawal_krw = 0
        withdrawal_service.session.get = AsyncMock(return_value=mock_user)
        withdrawal_service._get_daily_withdrawal_total = AsyncMock(return_value=0)

        # Mock address validator to return valid
        with patch.object(
            withdrawal_service,
            "_validate_address_with_checksum",
            return_value=MagicMock(is_valid=True),
        ):
            tx = await withdrawal_service.request_withdrawal(
                user_id="user-123",
                krw_amount=100000,
                crypto_type=CryptoType.USDT,
                crypto_address="T" + "a" * 33,
            )

        assert tx.status == TransactionStatus.PENDING
        assert tx.tx_type == TransactionType.CRYPTO_WITHDRAWAL
        assert tx.krw_amount == -100000
        assert mock_user.pending_withdrawal_krw == 100000

    @pytest.mark.asyncio
    async def test_request_withdrawal_invalid_address(self, withdrawal_service):
        """Should reject withdrawal with invalid address."""
        mock_user = MagicMock()
        mock_user.krw_balance = 500000
        mock_user.pending_withdrawal_krw = 0
        withdrawal_service.session.get = AsyncMock(return_value=mock_user)

        # Mock address validator to return invalid
        with patch.object(
            withdrawal_service,
            "_validate_address_with_checksum",
            return_value=MagicMock(is_valid=False, error_message="Invalid checksum"),
        ):
            with pytest.raises(InvalidAddressError):
                await withdrawal_service.request_withdrawal(
                    user_id="user-123",
                    krw_amount=100000,
                    crypto_type=CryptoType.USDT,
                    crypto_address="invalid_address",
                )


class TestCryptoWithdrawalServiceCancel:
    """Tests for withdrawal cancellation."""

    @pytest.fixture
    def withdrawal_service(self):
        """Create CryptoWithdrawalService with mocked dependencies."""
        mock_session = MagicMock()
        mock_session.flush = AsyncMock()
        service = CryptoWithdrawalService(mock_session)
        service._redis = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_cancel_withdrawal_success(self, withdrawal_service):
        """Should cancel pending withdrawal."""
        mock_tx = MagicMock()
        mock_tx.user_id = "user-123"
        mock_tx.status = TransactionStatus.PENDING
        mock_tx.krw_amount = -100000
        mock_tx.description = "Withdrawal request"

        mock_user = MagicMock()
        mock_user.krw_balance = 400000
        mock_user.pending_withdrawal_krw = 100000

        withdrawal_service.session.get = AsyncMock(
            side_effect=lambda model, id: mock_tx if id == "tx-123" else mock_user
        )

        tx = await withdrawal_service.cancel_withdrawal(
            user_id="user-123",
            transaction_id="tx-123",
        )

        assert tx.status == TransactionStatus.CANCELLED
        assert mock_user.krw_balance == 500000
        assert mock_user.pending_withdrawal_krw == 0

    @pytest.mark.asyncio
    async def test_cancel_withdrawal_not_found(self, withdrawal_service):
        """Should reject cancellation of non-existent withdrawal."""
        withdrawal_service.session.get = AsyncMock(return_value=None)

        with pytest.raises(WithdrawalError, match="Transaction not found"):
            await withdrawal_service.cancel_withdrawal(
                user_id="user-123",
                transaction_id="nonexistent",
            )

    @pytest.mark.asyncio
    async def test_cancel_withdrawal_wrong_user(self, withdrawal_service):
        """Should reject cancellation by wrong user."""
        mock_tx = MagicMock()
        mock_tx.user_id = "other-user"
        mock_tx.status = TransactionStatus.PENDING

        withdrawal_service.session.get = AsyncMock(return_value=mock_tx)

        with pytest.raises(WithdrawalError, match="Permission denied"):
            await withdrawal_service.cancel_withdrawal(
                user_id="user-123",
                transaction_id="tx-123",
            )

    @pytest.mark.asyncio
    async def test_cancel_withdrawal_already_completed(self, withdrawal_service):
        """Should reject cancellation of completed withdrawal."""
        mock_tx = MagicMock()
        mock_tx.user_id = "user-123"
        mock_tx.status = TransactionStatus.COMPLETED

        withdrawal_service.session.get = AsyncMock(return_value=mock_tx)

        with pytest.raises(WithdrawalError, match="Cannot cancel"):
            await withdrawal_service.cancel_withdrawal(
                user_id="user-123",
                transaction_id="tx-123",
            )


class TestCryptoWithdrawalServiceIntegrity:
    """Tests for integrity hash computation."""

    def test_compute_integrity_hash(self):
        """Should compute consistent integrity hash."""
        hash1 = CryptoWithdrawalService._compute_integrity_hash(
            user_id="user-123",
            tx_type=TransactionType.CRYPTO_WITHDRAWAL,
            amount=-100000,
            balance_before=500000,
            balance_after=400000,
        )

        hash2 = CryptoWithdrawalService._compute_integrity_hash(
            user_id="user-123",
            tx_type=TransactionType.CRYPTO_WITHDRAWAL,
            amount=-100000,
            balance_before=500000,
            balance_after=400000,
        )

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex

    def test_integrity_hash_changes_with_data(self):
        """Different data should produce different hashes."""
        hash1 = CryptoWithdrawalService._compute_integrity_hash(
            user_id="user-123",
            tx_type=TransactionType.CRYPTO_WITHDRAWAL,
            amount=-100000,
            balance_before=500000,
            balance_after=400000,
        )

        hash2 = CryptoWithdrawalService._compute_integrity_hash(
            user_id="user-123",
            tx_type=TransactionType.CRYPTO_WITHDRAWAL,
            amount=-100001,  # Different amount
            balance_before=500000,
            balance_after=399999,
        )

        assert hash1 != hash2
