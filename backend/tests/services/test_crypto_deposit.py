"""Tests for CryptoDepositService.

Tests for cryptocurrency deposit operations.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.wallet import CryptoType, TransactionStatus, TransactionType
from app.services.crypto_deposit import CryptoDepositService, DepositError


class TestCryptoDepositServiceAddressGeneration:
    """Tests for deposit address generation."""

    @pytest.fixture
    def deposit_service(self):
        """Create CryptoDepositService with mocked dependencies."""
        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        service = CryptoDepositService(mock_session)
        service._redis = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_get_deposit_address_from_cache(self, deposit_service):
        """Should return cached address when available."""
        deposit_service._redis.get.return_value = b"Tcached_address_12345678901234"

        address = await deposit_service.get_deposit_address(
            user_id="user-123",
            crypto_type=CryptoType.USDT,
        )

        assert address == "Tcached_address_12345678901234"
        deposit_service._redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_deposit_address_from_db(self, deposit_service):
        """Should return address from DB when cache miss."""
        deposit_service._redis.get.return_value = None

        mock_addr = MagicMock()
        mock_addr.address = "Tdb_address_123456789012345678"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_addr
        deposit_service.session.execute = AsyncMock(return_value=mock_result)

        address = await deposit_service.get_deposit_address(
            user_id="user-123",
            crypto_type=CryptoType.USDT,
        )

        assert address == "Tdb_address_123456789012345678"
        deposit_service._redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_deposit_address_generates_new(self, deposit_service):
        """Should generate new address when not found."""
        deposit_service._redis.get.return_value = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        deposit_service.session.execute = AsyncMock(return_value=mock_result)

        address = await deposit_service.get_deposit_address(
            user_id="user-123",
            crypto_type=CryptoType.USDT,
        )

        assert address.startswith("T")
        assert len(address) == 34
        deposit_service.session.add.assert_called_once()


class TestCryptoDepositServiceAddressFormat:
    """Tests for address format generation."""

    def test_generate_usdt_address_format(self):
        """USDT address should start with T and be 34 chars."""
        address = CryptoDepositService._generate_address("user-123", CryptoType.USDT)
        assert address.startswith("T")
        assert len(address) == 34

    def test_generate_xrp_address_format(self):
        """XRP address should start with r and be 34 chars."""
        address = CryptoDepositService._generate_address("user-123", CryptoType.XRP)
        assert address.startswith("r")
        assert len(address) == 34

    def test_generate_trx_address_format(self):
        """TRX address should start with T and be 34 chars."""
        address = CryptoDepositService._generate_address("user-123", CryptoType.TRX)
        assert address.startswith("T")
        assert len(address) == 34

    def test_generate_sol_address_format(self):
        """SOL address should be 44 chars."""
        address = CryptoDepositService._generate_address("user-123", CryptoType.SOL)
        assert len(address) == 44

    def test_generate_address_deterministic(self):
        """Same user and crypto should generate same address."""
        addr1 = CryptoDepositService._generate_address("user-123", CryptoType.USDT)
        addr2 = CryptoDepositService._generate_address("user-123", CryptoType.USDT)
        assert addr1 == addr2

    def test_generate_address_different_users(self):
        """Different users should get different addresses."""
        addr1 = CryptoDepositService._generate_address("user-123", CryptoType.USDT)
        addr2 = CryptoDepositService._generate_address("user-456", CryptoType.USDT)
        assert addr1 != addr2

    def test_generate_address_different_crypto(self):
        """Same user, different crypto should get different addresses."""
        addr1 = CryptoDepositService._generate_address("user-123", CryptoType.USDT)
        addr2 = CryptoDepositService._generate_address("user-123", CryptoType.XRP)
        assert addr1 != addr2


class TestCryptoDepositServiceWebhook:
    """Tests for deposit webhook processing."""

    @pytest.fixture
    def deposit_service(self):
        """Create CryptoDepositService with mocked dependencies."""
        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        service = CryptoDepositService(mock_session)
        service._redis = AsyncMock()
        service._exchange = MagicMock()
        service._exchange.convert_crypto_to_krw = AsyncMock(
            return_value=(130000, 1300)  # 100 USDT @ 1300 KRW
        )
        return service

    @pytest.mark.asyncio
    async def test_handle_deposit_pending_confirmations(self, deposit_service):
        """Should return None when confirmations insufficient."""
        result = await deposit_service.handle_deposit_webhook(
            crypto_type=CryptoType.USDT,
            tx_hash="0x123",
            address="T" + "a" * 33,
            amount="100",
            confirmations=5,  # Below 20 required for USDT
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_handle_deposit_duplicate(self, deposit_service):
        """Should return existing transaction for duplicate webhook."""
        mock_existing = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_existing
        deposit_service.session.execute = AsyncMock(return_value=mock_result)

        result = await deposit_service.handle_deposit_webhook(
            crypto_type=CryptoType.USDT,
            tx_hash="0x123",
            address="T" + "a" * 33,
            amount="100",
            confirmations=25,
        )

        assert result is mock_existing

    @pytest.mark.asyncio
    async def test_handle_deposit_unknown_address(self, deposit_service):
        """Should raise error for unknown deposit address."""
        # First call returns None (no duplicate), second returns None (no address)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        deposit_service.session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(DepositError, match="Unknown deposit address"):
            await deposit_service.handle_deposit_webhook(
                crypto_type=CryptoType.USDT,
                tx_hash="0x123",
                address="Tunknown_address_1234567890123",
                amount="100",
                confirmations=25,
            )

    @pytest.mark.asyncio
    async def test_handle_deposit_success(self, deposit_service):
        """Should process deposit and credit balance."""
        # Mock no duplicate
        mock_no_dup = MagicMock()
        mock_no_dup.scalar_one_or_none.return_value = None

        # Mock address found
        mock_addr = MagicMock()
        mock_addr.user_id = "user-123"
        mock_addr.total_deposits = 0
        mock_addr_result = MagicMock()
        mock_addr_result.scalar_one_or_none.return_value = mock_addr

        # Mock user
        mock_user = MagicMock()
        mock_user.krw_balance = 100000

        call_count = 0

        async def mock_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_no_dup
            return mock_addr_result

        deposit_service.session.execute = mock_execute
        deposit_service.session.get = AsyncMock(return_value=mock_user)

        tx = await deposit_service.handle_deposit_webhook(
            crypto_type=CryptoType.USDT,
            tx_hash="0x123456789",
            address="T" + "a" * 33,
            amount="100",
            confirmations=25,
        )

        assert tx.tx_type == TransactionType.CRYPTO_DEPOSIT
        assert tx.status == TransactionStatus.COMPLETED
        assert tx.krw_amount == 130000
        assert mock_user.krw_balance == 230000
        assert mock_addr.total_deposits == 1


class TestCryptoDepositServiceMinimumConfirmations:
    """Tests for minimum confirmation requirements."""

    def test_usdt_min_confirmations(self):
        """USDT should require 20 confirmations."""
        assert CryptoDepositService.MIN_CONFIRMATIONS[CryptoType.USDT] == 20

    def test_xrp_min_confirmations(self):
        """XRP should require 1 confirmation."""
        assert CryptoDepositService.MIN_CONFIRMATIONS[CryptoType.XRP] == 1

    def test_trx_min_confirmations(self):
        """TRX should require 20 confirmations."""
        assert CryptoDepositService.MIN_CONFIRMATIONS[CryptoType.TRX] == 20

    def test_sol_min_confirmations(self):
        """SOL should require 32 confirmations."""
        assert CryptoDepositService.MIN_CONFIRMATIONS[CryptoType.SOL] == 32


class TestCryptoDepositServiceMinimumDeposit:
    """Tests for minimum deposit amounts."""

    def test_usdt_min_deposit(self):
        """USDT minimum should be 10."""
        assert CryptoDepositService.MIN_DEPOSIT[CryptoType.USDT] == "10"

    def test_xrp_min_deposit(self):
        """XRP minimum should be 20."""
        assert CryptoDepositService.MIN_DEPOSIT[CryptoType.XRP] == "20"

    def test_trx_min_deposit(self):
        """TRX minimum should be 100."""
        assert CryptoDepositService.MIN_DEPOSIT[CryptoType.TRX] == "100"

    def test_sol_min_deposit(self):
        """SOL minimum should be 0.1."""
        assert CryptoDepositService.MIN_DEPOSIT[CryptoType.SOL] == "0.1"


class TestCryptoDepositServiceIntegrity:
    """Tests for integrity hash computation."""

    def test_compute_integrity_hash(self):
        """Should compute consistent integrity hash."""
        hash1 = CryptoDepositService._compute_integrity_hash(
            user_id="user-123",
            tx_type=TransactionType.CRYPTO_DEPOSIT,
            amount=130000,
            balance_before=100000,
            balance_after=230000,
        )

        hash2 = CryptoDepositService._compute_integrity_hash(
            user_id="user-123",
            tx_type=TransactionType.CRYPTO_DEPOSIT,
            amount=130000,
            balance_before=100000,
            balance_after=230000,
        )

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex
