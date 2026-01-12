"""
Secrets validation for production deployment.

This module validates that production secrets are properly configured
and do not contain development placeholders or weak patterns.
"""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationResult:
    """Result of secret validation."""
    is_valid: bool
    error_message: Optional[str] = None
    secret_name: Optional[str] = None


class SecretsValidator:
    """
    Validates production secrets at application startup.
    
    Ensures that:
    1. All required secrets are present
    2. No development placeholders are used
    3. Secrets meet minimum length requirements
    """
    
    # Development placeholder patterns to reject
    DEV_PATTERNS = [
        r"^dev[-_]",           # Starts with dev- or dev_
        r"^test[-_]",          # Starts with test- or test_
        r"^local[-_]",         # Starts with local- or local_
        r"changeme",           # Contains changeme
        r"^secret$",           # Exactly "secret"
        r"^password$",         # Exactly "password"
        r"placeholder",        # Contains placeholder
        r"example",            # Contains example
        r"^xxx+$",             # Only x characters
        r"^your[-_]?secret",   # Starts with your-secret or your_secret
        r"replace[-_]?me",     # Contains replace-me or replace_me
    ]
    
    # Weak patterns that indicate insufficient randomness
    WEAK_PATTERNS = [
        r"^(.)\1{7,}$",        # Same character repeated 8+ times
        r"^[0-9]+$",           # Only digits
        r"^[a-z]+$",           # Only lowercase letters
        r"12345",              # Sequential numbers
        r"qwerty",             # Keyboard pattern
        r"abcdef",             # Sequential letters
    ]
    
    # Minimum length for cryptographic secrets (32 bytes = 256 bits)
    MIN_SECRET_LENGTH = 32
    
    # Required secrets for production
    REQUIRED_SECRETS = [
        "JWT_SECRET_KEY",
        "SERIALIZATION_HMAC_KEY",
    ]
    
    # Optional but recommended secrets
    RECOMMENDED_SECRETS = [
        "SESSION_SECRET_KEY",
        "DEPOSIT_WEBHOOK_SECRET",
    ]
    
    def __init__(self, environment: str = "development"):
        """
        Initialize the validator.
        
        Args:
            environment: Current environment (development, staging, production)
        """
        self.environment = environment.lower()
        self._compiled_dev_patterns = [
            re.compile(pattern, re.IGNORECASE) 
            for pattern in self.DEV_PATTERNS
        ]
        self._compiled_weak_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.WEAK_PATTERNS
        ]
    
    def is_development_secret(self, secret: str) -> bool:
        """
        Check if a secret appears to be a development placeholder.
        
        Args:
            secret: The secret value to check
            
        Returns:
            True if the secret matches a development placeholder pattern
        """
        if not secret:
            return True
            
        for pattern in self._compiled_dev_patterns:
            if pattern.search(secret):
                return True
        return False
    
    def is_weak_secret(self, secret: str) -> bool:
        """
        Check if a secret appears to be weak or predictable.
        
        Args:
            secret: The secret value to check
            
        Returns:
            True if the secret matches a weak pattern
        """
        if not secret:
            return True
            
        for pattern in self._compiled_weak_patterns:
            if pattern.search(secret):
                return True
        return False
    
    def validate_secret_strength(
        self, 
        secret: str, 
        min_length: Optional[int] = None
    ) -> ValidationResult:
        """
        Validate that a secret meets minimum strength requirements.
        
        Args:
            secret: The secret value to validate
            min_length: Minimum required length (defaults to MIN_SECRET_LENGTH)
            
        Returns:
            ValidationResult with is_valid and error_message
        """
        min_len = min_length or self.MIN_SECRET_LENGTH
        
        if not secret:
            return ValidationResult(
                is_valid=False,
                error_message="Secret is empty or None"
            )
        
        if len(secret) < min_len:
            return ValidationResult(
                is_valid=False,
                error_message=f"Secret must be at least {min_len} characters (got {len(secret)})"
            )
        
        if self.is_development_secret(secret):
            return ValidationResult(
                is_valid=False,
                error_message="Secret appears to be a development placeholder"
            )
        
        if self.is_weak_secret(secret):
            return ValidationResult(
                is_valid=False,
                error_message="Secret appears to be weak or predictable"
            )
        
        return ValidationResult(is_valid=True)
    
    def validate_secret(
        self, 
        secret_name: str, 
        secret_value: Optional[str],
        required: bool = True
    ) -> ValidationResult:
        """
        Validate a single secret by name and value.
        
        Args:
            secret_name: Name of the secret (for error messages)
            secret_value: The secret value to validate
            required: Whether the secret is required
            
        Returns:
            ValidationResult with is_valid, error_message, and secret_name
        """
        if secret_value is None or secret_value == "":
            if required:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"{secret_name} is required but not configured",
                    secret_name=secret_name
                )
            return ValidationResult(is_valid=True, secret_name=secret_name)
        
        result = self.validate_secret_strength(secret_value)
        result.secret_name = secret_name
        
        if not result.is_valid:
            result.error_message = f"{secret_name}: {result.error_message}"
        
        return result
    
    def validate_all_secrets(
        self, 
        secrets: dict[str, Optional[str]],
        strict: bool = False
    ) -> tuple[bool, list[ValidationResult]]:
        """
        Validate all provided secrets.
        
        Args:
            secrets: Dictionary of secret_name -> secret_value
            strict: If True, also validate recommended secrets
            
        Returns:
            Tuple of (all_valid, list of ValidationResults)
        """
        results = []
        all_valid = True
        
        # Check required secrets
        for secret_name in self.REQUIRED_SECRETS:
            secret_value = secrets.get(secret_name)
            result = self.validate_secret(secret_name, secret_value, required=True)
            results.append(result)
            if not result.is_valid:
                all_valid = False
        
        # Check recommended secrets (only in strict mode or production)
        if strict or self.environment == "production":
            for secret_name in self.RECOMMENDED_SECRETS:
                secret_value = secrets.get(secret_name)
                if secret_value:  # Only validate if provided
                    result = self.validate_secret(secret_name, secret_value, required=False)
                    results.append(result)
                    if not result.is_valid:
                        all_valid = False
        
        # Validate any additional secrets provided
        all_secret_names = set(self.REQUIRED_SECRETS + self.RECOMMENDED_SECRETS)
        for secret_name, secret_value in secrets.items():
            if secret_name not in all_secret_names and secret_value:
                result = self.validate_secret(secret_name, secret_value, required=False)
                results.append(result)
                if not result.is_valid:
                    all_valid = False
        
        return all_valid, results
    
    def validate_for_production(
        self, 
        secrets: dict[str, Optional[str]]
    ) -> tuple[bool, list[str]]:
        """
        Validate secrets specifically for production deployment.
        
        This is a convenience method that returns a simple pass/fail
        with a list of error messages.
        
        Args:
            secrets: Dictionary of secret_name -> secret_value
            
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        all_valid, results = self.validate_all_secrets(secrets, strict=True)
        
        errors = [
            result.error_message 
            for result in results 
            if not result.is_valid and result.error_message
        ]
        
        return all_valid, errors


def validate_startup_secrets(
    jwt_secret_key: str,
    serialization_hmac_key: str,
    session_secret_key: Optional[str] = None,
    deposit_webhook_secret: Optional[str] = None,
    environment: str = "development"
) -> None:
    """
    Validate secrets at application startup.
    
    Raises ValueError if any required secret is invalid in production.
    
    Args:
        jwt_secret_key: JWT signing key
        serialization_hmac_key: HMAC key for state serialization
        session_secret_key: Optional session signing key
        deposit_webhook_secret: Optional webhook verification secret
        environment: Current environment
        
    Raises:
        ValueError: If any required secret is invalid in production
    """
    validator = SecretsValidator(environment=environment)
    
    secrets = {
        "JWT_SECRET_KEY": jwt_secret_key,
        "SERIALIZATION_HMAC_KEY": serialization_hmac_key,
        "SESSION_SECRET_KEY": session_secret_key,
        "DEPOSIT_WEBHOOK_SECRET": deposit_webhook_secret,
    }
    
    if environment.lower() == "production":
        is_valid, errors = validator.validate_for_production(secrets)
        
        if not is_valid:
            error_msg = "Production secrets validation failed:\n" + "\n".join(
                f"  - {error}" for error in errors
            )
            raise ValueError(error_msg)
    else:
        # In non-production, just warn about development secrets
        all_valid, results = validator.validate_all_secrets(secrets, strict=False)
        
        if not all_valid:
            import warnings
            for result in results:
                if not result.is_valid:
                    warnings.warn(
                        f"Secret validation warning: {result.error_message}",
                        UserWarning
                    )
