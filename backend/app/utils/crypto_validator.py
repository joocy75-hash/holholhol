"""
Cryptocurrency address validation with checksum verification.

Supports:
- USDT (TRC-20 on Tron network)
- XRP (Ripple)
- TRX (Tron)
- SOL (Solana)
"""
import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import base58


class CryptoType(str, Enum):
    """Supported cryptocurrency types."""
    USDT = "usdt"  # TRC-20 (Tron network)
    XRP = "xrp"    # Ripple
    TRX = "trx"    # Tron
    SOL = "sol"    # Solana


@dataclass
class ValidationResult:
    """Result of address validation."""
    is_valid: bool
    error_message: Optional[str] = None
    normalized_address: Optional[str] = None
    crypto_type: Optional[CryptoType] = None


class CryptoAddressValidator:
    """
    Validates cryptocurrency addresses with checksum verification.
    
    Supports USDT (TRC-20), XRP, TRX, and SOL addresses.
    """
    
    # Tron address constants (used for USDT TRC-20 and TRX)
    TRON_ADDRESS_PREFIX = "T"
    TRON_ADDRESS_LENGTH = 34
    TRON_DECODED_LENGTH = 21  # 1 byte prefix + 20 bytes address
    
    # XRP address constants
    XRP_ADDRESS_PREFIX = "r"
    XRP_ADDRESS_MIN_LENGTH = 25
    XRP_ADDRESS_MAX_LENGTH = 35
    XRP_DECODED_LENGTH = 21  # 1 byte type + 20 bytes hash
    
    # Solana address constants
    SOL_ADDRESS_LENGTH = 44  # Base58 encoded 32 bytes
    SOL_DECODED_LENGTH = 32
    
    # Base58 alphabet for Tron (same as Bitcoin)
    TRON_ALPHABET = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    
    # Base58 alphabet for XRP (different from Bitcoin)
    XRP_ALPHABET = b"rpshnaf39wBUDNEGHJKLM4PQRST7VWXYZ2bcdeCg65jkm8oFqi1tuvAxyz"
    
    def validate_address(
        self, 
        address: str, 
        crypto_type: CryptoType
    ) -> ValidationResult:
        """
        Validate a cryptocurrency address.
        
        Args:
            address: The address to validate
            crypto_type: The type of cryptocurrency
            
        Returns:
            ValidationResult with validation status and details
        """
        if not address:
            return ValidationResult(
                is_valid=False,
                error_message="Address is empty",
                crypto_type=crypto_type
            )
        
        # Strip whitespace
        address = address.strip()
        
        # Route to appropriate validator
        validators = {
            CryptoType.USDT: self.validate_tron_address,
            CryptoType.TRX: self.validate_tron_address,
            CryptoType.XRP: self.validate_xrp_address,
            CryptoType.SOL: self.validate_sol_address,
        }
        
        validator = validators.get(crypto_type)
        if not validator:
            return ValidationResult(
                is_valid=False,
                error_message=f"Unsupported cryptocurrency type: {crypto_type}",
                crypto_type=crypto_type
            )
        
        result = validator(address)
        result.crypto_type = crypto_type
        return result
    
    def validate_tron_address(self, address: str) -> ValidationResult:
        """
        Validate a Tron address (used for USDT TRC-20 and TRX).
        
        Tron addresses:
        - Start with 'T'
        - Are 34 characters long
        - Use Base58Check encoding
        - Decode to 21 bytes (1 prefix + 20 address)
        
        Args:
            address: The Tron address to validate
            
        Returns:
            ValidationResult with validation status
        """
        # Check prefix
        if not address.startswith(self.TRON_ADDRESS_PREFIX):
            return ValidationResult(
                is_valid=False,
                error_message=f"Tron address must start with '{self.TRON_ADDRESS_PREFIX}'"
            )
        
        # Check length
        if len(address) != self.TRON_ADDRESS_LENGTH:
            return ValidationResult(
                is_valid=False,
                error_message=f"Tron address must be {self.TRON_ADDRESS_LENGTH} characters (got {len(address)})"
            )
        
        # Validate Base58Check encoding
        try:
            decoded = self._base58check_decode(address, alphabet=self.TRON_ALPHABET)
            
            if len(decoded) != self.TRON_DECODED_LENGTH:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Invalid Tron address: decoded length is {len(decoded)}, expected {self.TRON_DECODED_LENGTH}"
                )
            
            return ValidationResult(
                is_valid=True,
                normalized_address=address
            )
            
        except ValueError as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid Tron address: {str(e)}"
            )
    
    def validate_xrp_address(self, address: str) -> ValidationResult:
        """
        Validate an XRP (Ripple) address.
        
        XRP addresses:
        - Start with 'r'
        - Are 25-35 characters long
        - Use Base58Check encoding with XRP alphabet
        - Decode to 21 bytes
        
        Args:
            address: The XRP address to validate
            
        Returns:
            ValidationResult with validation status
        """
        # Check prefix
        if not address.startswith(self.XRP_ADDRESS_PREFIX):
            return ValidationResult(
                is_valid=False,
                error_message=f"XRP address must start with '{self.XRP_ADDRESS_PREFIX}'"
            )
        
        # Check length
        if not (self.XRP_ADDRESS_MIN_LENGTH <= len(address) <= self.XRP_ADDRESS_MAX_LENGTH):
            return ValidationResult(
                is_valid=False,
                error_message=f"XRP address must be {self.XRP_ADDRESS_MIN_LENGTH}-{self.XRP_ADDRESS_MAX_LENGTH} characters (got {len(address)})"
            )
        
        # Validate Base58Check encoding with XRP alphabet
        try:
            decoded = self._base58check_decode(address, alphabet=self.XRP_ALPHABET)
            
            if len(decoded) != self.XRP_DECODED_LENGTH:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Invalid XRP address: decoded length is {len(decoded)}, expected {self.XRP_DECODED_LENGTH}"
                )
            
            return ValidationResult(
                is_valid=True,
                normalized_address=address
            )
            
        except ValueError as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid XRP address: {str(e)}"
            )
    
    def validate_sol_address(self, address: str) -> ValidationResult:
        """
        Validate a Solana address.
        
        Solana addresses:
        - Are Base58 encoded (no checksum)
        - Decode to exactly 32 bytes
        - Typically 44 characters long
        
        Args:
            address: The Solana address to validate
            
        Returns:
            ValidationResult with validation status
        """
        # Check for valid characters (Base58 alphabet)
        try:
            # Solana uses standard Base58 (same as Bitcoin)
            decoded = base58.b58decode(address)
            
            if len(decoded) != self.SOL_DECODED_LENGTH:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Invalid Solana address: decoded length is {len(decoded)}, expected {self.SOL_DECODED_LENGTH}"
                )
            
            return ValidationResult(
                is_valid=True,
                normalized_address=address
            )
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid Solana address: {str(e)}"
            )
    
    def _base58check_decode(self, address: str, alphabet: bytes) -> bytes:
        """
        Decode a Base58Check encoded address.
        
        Base58Check format:
        - Payload + 4-byte checksum
        - Checksum = first 4 bytes of double SHA256(payload)
        
        Args:
            address: The Base58Check encoded address
            alphabet: The Base58 alphabet to use
            
        Returns:
            The decoded payload (without checksum)
            
        Raises:
            ValueError: If decoding fails or checksum is invalid
        """
        # Decode from Base58
        try:
            decoded = self._base58_decode(address, alphabet)
        except Exception as e:
            raise ValueError(f"Base58 decode failed: {e}")
        
        if len(decoded) < 5:
            raise ValueError("Decoded data too short for Base58Check")
        
        # Split payload and checksum
        payload = decoded[:-4]
        checksum = decoded[-4:]
        
        # Verify checksum (double SHA256)
        expected_checksum = self._double_sha256(payload)[:4]
        
        if checksum != expected_checksum:
            raise ValueError("Checksum verification failed")
        
        return payload
    
    def _base58_decode(self, data: str, alphabet: bytes) -> bytes:
        """
        Decode a Base58 encoded string.
        
        Args:
            data: The Base58 encoded string
            alphabet: The Base58 alphabet to use
            
        Returns:
            The decoded bytes
        """
        # Build alphabet lookup
        alphabet_map = {char: i for i, char in enumerate(alphabet)}
        
        # Convert to integer
        n = 0
        for char in data.encode('ascii'):
            if char not in alphabet_map:
                raise ValueError(f"Invalid character in Base58 string: {chr(char)}")
            n = n * 58 + alphabet_map[char]
        
        # Convert to bytes
        result = []
        while n > 0:
            result.append(n % 256)
            n //= 256
        result.reverse()
        
        # Handle leading zeros (represented as '1' in standard Base58)
        leading_zeros = 0
        for char in data.encode('ascii'):
            if char == alphabet[0]:
                leading_zeros += 1
            else:
                break
        
        return bytes([0] * leading_zeros) + bytes(result)
    
    def _double_sha256(self, data: bytes) -> bytes:
        """
        Compute double SHA256 hash.
        
        Args:
            data: The data to hash
            
        Returns:
            The double SHA256 hash
        """
        return hashlib.sha256(hashlib.sha256(data).digest()).digest()


# Convenience function for quick validation
def validate_crypto_address(
    address: str, 
    crypto_type: CryptoType | str
) -> ValidationResult:
    """
    Validate a cryptocurrency address.
    
    Args:
        address: The address to validate
        crypto_type: The cryptocurrency type (CryptoType enum or string)
        
    Returns:
        ValidationResult with validation status
    """
    validator = CryptoAddressValidator()
    
    if isinstance(crypto_type, str):
        try:
            crypto_type = CryptoType(crypto_type.lower())
        except ValueError:
            return ValidationResult(
                is_valid=False,
                error_message=f"Unknown cryptocurrency type: {crypto_type}"
            )
    
    return validator.validate_address(address, crypto_type)
