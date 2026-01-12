"""
Two-Factor Authentication Service using TOTP.

Provides TOTP-based 2FA for high-value withdrawals and account security.
"""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

import pyotp


@dataclass
class TOTPSetup:
    """TOTP setup information for user."""
    secret: str
    qr_code_uri: str
    backup_codes: list[str]


@dataclass
class TwoFactorConfig:
    """Configuration for 2FA service."""
    # Withdrawal threshold requiring 2FA (in KRW)
    required_threshold_krw: int = 1_000_000  # ₩1,000,000
    
    # TOTP settings
    time_step: int = 30  # seconds
    digits: int = 6
    algorithm: str = "SHA1"
    
    # Application info for QR code
    issuer: str = "PokerApp"
    
    # Backup codes
    backup_codes_count: int = 10
    backup_code_length: int = 8
    
    # Time window tolerance (number of time steps)
    # Allows for clock drift between server and authenticator
    valid_window: int = 1  # ±1 time step (±30 seconds)


class TwoFactorService:
    """
    TOTP-based two-factor authentication service.
    
    Features:
    - TOTP secret generation
    - QR code URI generation for authenticator apps
    - Code verification with time window tolerance
    - Backup codes for recovery
    - Threshold-based 2FA requirement for withdrawals
    """
    
    def __init__(self, config: Optional[TwoFactorConfig] = None):
        """
        Initialize the 2FA service.
        
        Args:
            config: Optional configuration, uses defaults if not provided
        """
        self.config = config or TwoFactorConfig()
    
    def generate_secret(self, user_id: str, user_email: str) -> TOTPSetup:
        """
        Generate a new TOTP secret for a user.
        
        Args:
            user_id: User's unique identifier
            user_email: User's email for QR code display
            
        Returns:
            TOTPSetup with secret, QR code URI, and backup codes
        """
        # Generate a secure random secret (160 bits = 20 bytes)
        # Base32 encoded for compatibility with authenticator apps
        secret = pyotp.random_base32(length=32)
        
        # Generate QR code URI
        qr_code_uri = self.get_qr_code_uri(user_email, secret)
        
        # Generate backup codes
        backup_codes = self._generate_backup_codes()
        
        return TOTPSetup(
            secret=secret,
            qr_code_uri=qr_code_uri,
            backup_codes=backup_codes
        )
    
    def get_qr_code_uri(self, user_email: str, secret: str) -> str:
        """
        Generate a QR code URI for authenticator apps.
        
        The URI follows the otpauth:// format:
        otpauth://totp/Issuer:account?secret=XXX&issuer=Issuer&algorithm=SHA1&digits=6&period=30
        
        Args:
            user_email: User's email for display in authenticator
            secret: The TOTP secret
            
        Returns:
            otpauth:// URI string
        """
        totp = pyotp.TOTP(
            secret,
            digits=self.config.digits,
            interval=self.config.time_step
        )
        
        return totp.provisioning_uri(
            name=user_email,
            issuer_name=self.config.issuer
        )
    
    def verify_code(
        self, 
        secret: str, 
        code: str,
        valid_window: Optional[int] = None
    ) -> bool:
        """
        Verify a TOTP code.
        
        Args:
            secret: The user's TOTP secret
            code: The code to verify
            valid_window: Optional override for time window tolerance
            
        Returns:
            True if the code is valid within the time window
        """
        if not secret or not code:
            return False
        
        # Clean the code (remove spaces, dashes)
        code = code.replace(" ", "").replace("-", "")
        
        # Validate code format
        if not code.isdigit() or len(code) != self.config.digits:
            return False
        
        window = valid_window if valid_window is not None else self.config.valid_window
        
        totp = pyotp.TOTP(
            secret,
            digits=self.config.digits,
            interval=self.config.time_step
        )
        
        return totp.verify(code, valid_window=window)
    
    def get_current_code(self, secret: str) -> str:
        """
        Get the current TOTP code for a secret.
        
        This is primarily for testing purposes.
        
        Args:
            secret: The TOTP secret
            
        Returns:
            The current TOTP code
        """
        totp = pyotp.TOTP(
            secret,
            digits=self.config.digits,
            interval=self.config.time_step
        )
        return totp.now()
    
    def is_2fa_required(self, amount_krw: int) -> bool:
        """
        Check if 2FA is required for a withdrawal amount.
        
        Args:
            amount_krw: The withdrawal amount in KRW
            
        Returns:
            True if 2FA is required for this amount
        """
        return amount_krw > self.config.required_threshold_krw
    
    def verify_backup_code(
        self, 
        code: str, 
        hashed_codes: list[str]
    ) -> tuple[bool, Optional[int]]:
        """
        Verify a backup code.
        
        Args:
            code: The backup code to verify
            hashed_codes: List of hashed backup codes
            
        Returns:
            Tuple of (is_valid, index_of_used_code)
            index_of_used_code is None if not valid
        """
        if not code or not hashed_codes:
            return False, None
        
        # Clean the code
        code = code.replace(" ", "").replace("-", "").upper()
        
        # Hash the provided code
        code_hash = self._hash_backup_code(code)
        
        # Check against stored hashes
        for i, stored_hash in enumerate(hashed_codes):
            if hmac.compare_digest(code_hash, stored_hash):
                return True, i
        
        return False, None
    
    def hash_backup_codes(self, codes: list[str]) -> list[str]:
        """
        Hash backup codes for secure storage.
        
        Args:
            codes: List of plaintext backup codes
            
        Returns:
            List of hashed backup codes
        """
        return [self._hash_backup_code(code) for code in codes]
    
    def _generate_backup_codes(self) -> list[str]:
        """
        Generate backup codes for account recovery.
        
        Returns:
            List of backup codes
        """
        codes = []
        for _ in range(self.config.backup_codes_count):
            # Generate random bytes and convert to alphanumeric
            code = secrets.token_hex(self.config.backup_code_length // 2).upper()
            # Format as XXXX-XXXX for readability
            formatted = f"{code[:4]}-{code[4:]}"
            codes.append(formatted)
        return codes
    
    def _hash_backup_code(self, code: str) -> str:
        """
        Hash a backup code for secure storage.
        
        Args:
            code: The backup code to hash
            
        Returns:
            SHA-256 hash of the code
        """
        # Remove formatting
        clean_code = code.replace(" ", "").replace("-", "").upper()
        return hashlib.sha256(clean_code.encode()).hexdigest()
    
    def validate_secret(self, secret: str) -> bool:
        """
        Validate that a secret is properly formatted.
        
        Args:
            secret: The TOTP secret to validate
            
        Returns:
            True if the secret is valid Base32
        """
        if not secret:
            return False
        
        try:
            # Try to decode as Base32
            # pyotp expects uppercase Base32
            decoded = base64.b32decode(secret.upper())
            # Should be at least 16 bytes (128 bits) for security
            return len(decoded) >= 16
        except Exception:
            return False


# Singleton instance
_two_factor_service: Optional[TwoFactorService] = None


def get_two_factor_service(config: Optional[TwoFactorConfig] = None) -> TwoFactorService:
    """
    Get the two-factor authentication service instance.
    
    Args:
        config: Optional configuration for the service
        
    Returns:
        TwoFactorService instance
    """
    global _two_factor_service
    
    if _two_factor_service is None:
        _two_factor_service = TwoFactorService(config)
    
    return _two_factor_service
