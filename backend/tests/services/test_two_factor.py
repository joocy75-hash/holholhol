"""Tests for TwoFactorService.

Tests for TOTP-based two-factor authentication.
"""

import hashlib
import time
from unittest.mock import MagicMock, patch

import pytest

from app.services.two_factor import (
    TOTPSetup,
    TwoFactorConfig,
    TwoFactorService,
    get_two_factor_service,
)


class TestTwoFactorServiceSetup:
    """Tests for 2FA setup and secret generation."""

    @pytest.fixture
    def two_factor_service(self):
        """Create TwoFactorService with default config."""
        return TwoFactorService()

    def test_generate_secret_returns_totp_setup(self, two_factor_service):
        """Should return TOTPSetup with all required fields."""
        setup = two_factor_service.generate_secret(
            user_id="user-123",
            user_email="test@example.com",
        )

        assert isinstance(setup, TOTPSetup)
        assert setup.secret is not None
        assert len(setup.secret) == 32  # Base32 encoded
        assert setup.qr_code_uri is not None
        assert len(setup.backup_codes) == 10

    def test_generate_secret_unique_per_call(self, two_factor_service):
        """Each call should generate unique secret."""
        setup1 = two_factor_service.generate_secret("user-1", "user1@test.com")
        setup2 = two_factor_service.generate_secret("user-2", "user2@test.com")

        assert setup1.secret != setup2.secret

    def test_qr_code_uri_format(self, two_factor_service):
        """QR code URI should follow otpauth format."""
        setup = two_factor_service.generate_secret(
            user_id="user-123",
            user_email="test@example.com",
        )

        assert setup.qr_code_uri.startswith("otpauth://totp/")
        # Email is URL-encoded (@ becomes %40)
        assert "test%40example.com" in setup.qr_code_uri or "test@example.com" in setup.qr_code_uri
        assert "secret=" in setup.qr_code_uri
        assert "issuer=PokerApp" in setup.qr_code_uri

    def test_backup_codes_format(self, two_factor_service):
        """Backup codes should be properly formatted."""
        setup = two_factor_service.generate_secret("user-123", "test@example.com")

        for code in setup.backup_codes:
            # Format: XXXX-XXXX
            assert len(code) == 9
            assert code[4] == "-"
            assert code[:4].isalnum()
            assert code[5:].isalnum()


class TestTwoFactorServiceVerification:
    """Tests for TOTP code verification."""

    @pytest.fixture
    def two_factor_service(self):
        """Create TwoFactorService with default config."""
        return TwoFactorService()

    def test_verify_valid_code(self, two_factor_service):
        """Should verify valid TOTP code."""
        setup = two_factor_service.generate_secret("user-123", "test@example.com")
        current_code = two_factor_service.get_current_code(setup.secret)

        result = two_factor_service.verify_code(setup.secret, current_code)

        assert result is True

    def test_verify_invalid_code(self, two_factor_service):
        """Should reject invalid TOTP code."""
        setup = two_factor_service.generate_secret("user-123", "test@example.com")

        result = two_factor_service.verify_code(setup.secret, "000000")

        assert result is False

    def test_verify_empty_code(self, two_factor_service):
        """Should reject empty code."""
        setup = two_factor_service.generate_secret("user-123", "test@example.com")

        assert two_factor_service.verify_code(setup.secret, "") is False
        assert two_factor_service.verify_code(setup.secret, None) is False

    def test_verify_empty_secret(self, two_factor_service):
        """Should reject empty secret."""
        assert two_factor_service.verify_code("", "123456") is False
        assert two_factor_service.verify_code(None, "123456") is False

    def test_verify_code_with_spaces(self, two_factor_service):
        """Should handle codes with spaces."""
        setup = two_factor_service.generate_secret("user-123", "test@example.com")
        current_code = two_factor_service.get_current_code(setup.secret)
        spaced_code = f"{current_code[:3]} {current_code[3:]}"

        result = two_factor_service.verify_code(setup.secret, spaced_code)

        assert result is True

    def test_verify_code_with_dashes(self, two_factor_service):
        """Should handle codes with dashes."""
        setup = two_factor_service.generate_secret("user-123", "test@example.com")
        current_code = two_factor_service.get_current_code(setup.secret)
        dashed_code = f"{current_code[:3]}-{current_code[3:]}"

        result = two_factor_service.verify_code(setup.secret, dashed_code)

        assert result is True

    def test_verify_wrong_length_code(self, two_factor_service):
        """Should reject codes with wrong length."""
        setup = two_factor_service.generate_secret("user-123", "test@example.com")

        assert two_factor_service.verify_code(setup.secret, "12345") is False
        assert two_factor_service.verify_code(setup.secret, "1234567") is False

    def test_verify_non_numeric_code(self, two_factor_service):
        """Should reject non-numeric codes."""
        setup = two_factor_service.generate_secret("user-123", "test@example.com")

        assert two_factor_service.verify_code(setup.secret, "abcdef") is False


class TestTwoFactorServiceThreshold:
    """Tests for 2FA requirement threshold."""

    def test_default_threshold(self):
        """Default threshold should be 1,000,000 KRW."""
        service = TwoFactorService()
        assert service.config.required_threshold_krw == 1_000_000

    def test_custom_threshold(self):
        """Should accept custom threshold."""
        config = TwoFactorConfig(required_threshold_krw=500_000)
        service = TwoFactorService(config)
        assert service.config.required_threshold_krw == 500_000

    def test_is_2fa_required_below_threshold(self):
        """Should not require 2FA below threshold."""
        service = TwoFactorService()

        assert service.is_2fa_required(500_000) is False
        assert service.is_2fa_required(1_000_000) is False

    def test_is_2fa_required_above_threshold(self):
        """Should require 2FA above threshold."""
        service = TwoFactorService()

        assert service.is_2fa_required(1_000_001) is True
        assert service.is_2fa_required(5_000_000) is True


class TestTwoFactorServiceBackupCodes:
    """Tests for backup code functionality."""

    @pytest.fixture
    def two_factor_service(self):
        """Create TwoFactorService with default config."""
        return TwoFactorService()

    def test_hash_backup_codes(self, two_factor_service):
        """Should hash backup codes for storage."""
        codes = ["ABCD-1234", "EFGH-5678"]
        hashed = two_factor_service.hash_backup_codes(codes)

        assert len(hashed) == 2
        assert all(len(h) == 64 for h in hashed)  # SHA-256 hex
        assert hashed[0] != hashed[1]

    def test_verify_backup_code_valid(self, two_factor_service):
        """Should verify valid backup code."""
        codes = ["ABCD-1234", "EFGH-5678"]
        hashed = two_factor_service.hash_backup_codes(codes)

        is_valid, index = two_factor_service.verify_backup_code("ABCD-1234", hashed)

        assert is_valid is True
        assert index == 0

    def test_verify_backup_code_case_insensitive(self, two_factor_service):
        """Should verify backup code case-insensitively."""
        codes = ["ABCD-1234"]
        hashed = two_factor_service.hash_backup_codes(codes)

        is_valid, index = two_factor_service.verify_backup_code("abcd-1234", hashed)

        assert is_valid is True
        assert index == 0

    def test_verify_backup_code_without_dash(self, two_factor_service):
        """Should verify backup code without dash."""
        codes = ["ABCD-1234"]
        hashed = two_factor_service.hash_backup_codes(codes)

        is_valid, index = two_factor_service.verify_backup_code("ABCD1234", hashed)

        assert is_valid is True
        assert index == 0

    def test_verify_backup_code_invalid(self, two_factor_service):
        """Should reject invalid backup code."""
        codes = ["ABCD-1234"]
        hashed = two_factor_service.hash_backup_codes(codes)

        is_valid, index = two_factor_service.verify_backup_code("WRONG-CODE", hashed)

        assert is_valid is False
        assert index is None

    def test_verify_backup_code_empty(self, two_factor_service):
        """Should reject empty backup code."""
        codes = ["ABCD-1234"]
        hashed = two_factor_service.hash_backup_codes(codes)

        is_valid, index = two_factor_service.verify_backup_code("", hashed)
        assert is_valid is False

        is_valid, index = two_factor_service.verify_backup_code("ABCD-1234", [])
        assert is_valid is False


class TestTwoFactorServiceSecretValidation:
    """Tests for secret validation."""

    @pytest.fixture
    def two_factor_service(self):
        """Create TwoFactorService with default config."""
        return TwoFactorService()

    def test_validate_valid_secret(self, two_factor_service):
        """Should validate properly formatted secret."""
        setup = two_factor_service.generate_secret("user-123", "test@example.com")

        assert two_factor_service.validate_secret(setup.secret) is True

    def test_validate_empty_secret(self, two_factor_service):
        """Should reject empty secret."""
        assert two_factor_service.validate_secret("") is False
        assert two_factor_service.validate_secret(None) is False

    def test_validate_invalid_base32(self, two_factor_service):
        """Should reject invalid Base32 secret."""
        assert two_factor_service.validate_secret("not-valid-base32!@#") is False

    def test_validate_short_secret(self, two_factor_service):
        """Should reject too short secret."""
        # Less than 16 bytes when decoded
        assert two_factor_service.validate_secret("AAAA") is False


class TestTwoFactorServiceSingleton:
    """Tests for singleton pattern."""

    def test_get_two_factor_service_returns_instance(self):
        """Should return TwoFactorService instance."""
        service = get_two_factor_service()
        assert isinstance(service, TwoFactorService)

    def test_get_two_factor_service_singleton(self):
        """Should return same instance on multiple calls."""
        # Reset singleton for test
        import app.services.two_factor as tf_module
        tf_module._two_factor_service = None

        service1 = get_two_factor_service()
        service2 = get_two_factor_service()

        assert service1 is service2
