"""Key Management Service for secure cryptographic key handling.

Provides abstraction for different key storage backends:
- LocalKmsProvider: Development/testing with environment variables
- VaultKmsProvider: Production with HashiCorp Vault Transit
- SecretsKmsProvider: AWS Secrets Manager with local signing

TON blockchain uses Ed25519 for transaction signing.
AWS KMS doesn't support Ed25519, so we use Vault or local signing.

Security Notes:
- Private keys are NEVER exposed in logs or error messages
- Keys are loaded lazily and cached in memory
- All signing operations are audited
"""

import base64
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ============================================================
# Exceptions
# ============================================================

class KmsError(Exception):
    """Base exception for KMS operations."""
    pass


class KmsConfigError(KmsError):
    """Configuration error."""
    pass


class KmsSigningError(KmsError):
    """Signing operation failed."""
    pass


class KmsKeyNotFoundError(KmsError):
    """Key not found in KMS."""
    pass


# ============================================================
# Data Classes
# ============================================================

@dataclass(frozen=True)
class SignatureResult:
    """Result of a signing operation."""
    signature: bytes
    public_key: bytes
    algorithm: str = "Ed25519"


# ============================================================
# Abstract Base Class
# ============================================================

class KeyManagementService(ABC):
    """Abstract base class for key management services.

    All implementations must:
    - Never expose private keys
    - Support Ed25519 signing (required for TON)
    - Provide public key retrieval
    """

    @abstractmethod
    async def get_public_key(self, key_id: str = "hot_wallet") -> bytes:
        """Get the public key for a key identifier.

        Args:
            key_id: Key identifier (e.g., "hot_wallet")

        Returns:
            bytes: 32-byte Ed25519 public key

        Raises:
            KmsKeyNotFoundError: Key not found
            KmsError: Other errors
        """
        pass

    @abstractmethod
    async def sign(self, data: bytes, key_id: str = "hot_wallet") -> SignatureResult:
        """Sign data using the specified key.

        Args:
            data: Data to sign
            key_id: Key identifier

        Returns:
            SignatureResult with signature and public key

        Raises:
            KmsSigningError: Signing failed
            KmsKeyNotFoundError: Key not found
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close any connections and cleanup resources."""
        pass

    def _mask_key_id(self, key_id: str) -> str:
        """Mask key ID for logging."""
        if len(key_id) <= 8:
            return "***"
        return f"{key_id[:4]}...{key_id[-4:]}"


# ============================================================
# Local KMS Provider (Development)
# ============================================================

class LocalKmsProvider(KeyManagementService):
    """Local key management using environment variables.

    For development and testing only.
    Keys are stored as base64-encoded environment variables.

    Environment Variables:
    - TON_HOT_WALLET_PRIVATE_KEY: Base64-encoded 32-byte Ed25519 seed

    Security Warning:
    - Do NOT use in production
    - Keys in environment variables can be exposed
    """

    def __init__(self):
        """Initialize local KMS provider."""
        self._keys: dict[str, Ed25519PrivateKey] = {}
        self._loaded = False
        logger.warning(
            "LocalKmsProvider initialized - FOR DEVELOPMENT ONLY. "
            "Use VaultKmsProvider in production."
        )

    def _load_keys(self) -> None:
        """Load keys from environment variables."""
        if self._loaded:
            return

        # Load hot wallet key
        key_b64 = getattr(settings, 'ton_hot_wallet_private_key', None)
        if key_b64:
            try:
                key_bytes = base64.b64decode(key_b64)
                if len(key_bytes) != 32:
                    raise KmsConfigError(
                        f"Invalid key length: expected 32 bytes, got {len(key_bytes)}"
                    )
                self._keys["hot_wallet"] = Ed25519PrivateKey.from_private_bytes(key_bytes)
                logger.info("Loaded hot_wallet key from environment")
            except Exception as e:
                logger.error(f"Failed to load hot_wallet key: {type(e).__name__}")
                raise KmsConfigError("Failed to load hot wallet private key") from e

        self._loaded = True

    async def get_public_key(self, key_id: str = "hot_wallet") -> bytes:
        """Get public key from loaded private key."""
        self._load_keys()

        if key_id not in self._keys:
            raise KmsKeyNotFoundError(f"Key not found: {self._mask_key_id(key_id)}")

        private_key = self._keys[key_id]
        public_key = private_key.public_key()

        return public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

    async def sign(self, data: bytes, key_id: str = "hot_wallet") -> SignatureResult:
        """Sign data using local private key."""
        self._load_keys()

        if key_id not in self._keys:
            raise KmsKeyNotFoundError(f"Key not found: {self._mask_key_id(key_id)}")

        try:
            private_key = self._keys[key_id]
            signature = private_key.sign(data)

            public_key = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )

            # Log signing operation (without exposing data)
            data_hash = hashlib.sha256(data).hexdigest()[:16]
            logger.debug(
                f"Signed data with key {self._mask_key_id(key_id)}, "
                f"data_hash={data_hash}..."
            )

            return SignatureResult(
                signature=signature,
                public_key=public_key,
            )

        except Exception as e:
            logger.error(f"Signing failed: {type(e).__name__}")
            raise KmsSigningError(f"Failed to sign data: {type(e).__name__}") from e

    async def close(self) -> None:
        """Clear keys from memory."""
        self._keys.clear()
        self._loaded = False
        logger.debug("LocalKmsProvider closed")


# ============================================================
# Vault KMS Provider (Production)
# ============================================================

class VaultKmsProvider(KeyManagementService):
    """HashiCorp Vault Transit engine for key management.

    Uses Vault Transit secrets engine for:
    - Secure key storage (keys never leave Vault)
    - Ed25519 signing operations
    - Key versioning and rotation

    Environment Variables:
    - VAULT_ADDR: Vault server address
    - VAULT_TOKEN: Vault authentication token
    - VAULT_TRANSIT_MOUNT: Transit engine mount path (default: "transit")

    Required Vault Setup:
    1. Enable Transit engine: vault secrets enable transit
    2. Create key: vault write transit/keys/ton-hot-wallet type=ed25519
    """

    def __init__(
        self,
        vault_addr: Optional[str] = None,
        vault_token: Optional[str] = None,
        transit_mount: str = "transit",
    ):
        """Initialize Vault KMS provider.

        Args:
            vault_addr: Vault server address (overrides env)
            vault_token: Vault token (overrides env)
            transit_mount: Transit engine mount path
        """
        self.vault_addr = vault_addr or getattr(settings, 'vault_addr', None)
        self.vault_token = vault_token or getattr(settings, 'vault_token', None)
        self.transit_mount = transit_mount

        self._client: Optional[object] = None  # hvac.Client
        self._public_keys: dict[str, bytes] = {}

        # Key name mapping
        self._key_names = {
            "hot_wallet": "ton-hot-wallet",
        }

        if not self.vault_addr:
            raise KmsConfigError(
                "Vault address not configured. Set VAULT_ADDR environment variable."
            )

        logger.info(
            f"VaultKmsProvider initialized, "
            f"vault_addr={self.vault_addr[:20]}..., "
            f"transit_mount={transit_mount}"
        )

    async def _get_client(self):
        """Get or create Vault client."""
        if self._client is None:
            try:
                import hvac
                self._client = hvac.Client(
                    url=self.vault_addr,
                    token=self.vault_token,
                )

                if not self._client.is_authenticated():
                    raise KmsConfigError("Vault authentication failed")

            except ImportError:
                raise KmsConfigError(
                    "hvac package not installed. Install with: pip install hvac"
                )

        return self._client

    def _get_vault_key_name(self, key_id: str) -> str:
        """Map key ID to Vault key name."""
        return self._key_names.get(key_id, key_id)

    async def get_public_key(self, key_id: str = "hot_wallet") -> bytes:
        """Get public key from Vault."""
        # Check cache
        if key_id in self._public_keys:
            return self._public_keys[key_id]

        try:
            client = await self._get_client()
            vault_key = self._get_vault_key_name(key_id)

            # Read key info from Vault
            response = client.secrets.transit.read_key(
                name=vault_key,
                mount_point=self.transit_mount,
            )

            if not response or "data" not in response:
                raise KmsKeyNotFoundError(f"Key not found in Vault: {vault_key}")

            # Get latest key version's public key
            keys = response["data"].get("keys", {})
            if not keys:
                raise KmsKeyNotFoundError(f"No key versions found: {vault_key}")

            # Get the latest version
            latest_version = max(int(v) for v in keys.keys())
            key_data = keys[str(latest_version)]

            # Decode public key (base64)
            public_key_b64 = key_data.get("public_key")
            if not public_key_b64:
                raise KmsError(f"Public key not available for: {vault_key}")

            public_key = base64.b64decode(public_key_b64)

            # Cache the public key
            self._public_keys[key_id] = public_key

            return public_key

        except KmsError:
            raise
        except Exception as e:
            logger.error(f"Failed to get public key from Vault: {type(e).__name__}")
            raise KmsError(f"Vault error: {type(e).__name__}") from e

    async def sign(self, data: bytes, key_id: str = "hot_wallet") -> SignatureResult:
        """Sign data using Vault Transit."""
        try:
            client = await self._get_client()
            vault_key = self._get_vault_key_name(key_id)

            # Base64 encode the data for Vault API
            data_b64 = base64.b64encode(data).decode()

            # Sign using Vault Transit
            response = client.secrets.transit.sign_data(
                name=vault_key,
                hash_input=data_b64,
                marshaling_algorithm="jws",  # For Ed25519
                mount_point=self.transit_mount,
            )

            if not response or "data" not in response:
                raise KmsSigningError("Empty response from Vault")

            # Extract signature
            signature_data = response["data"].get("signature", "")

            # Vault returns signature in format: vault:v1:base64_signature
            parts = signature_data.split(":")
            if len(parts) < 3:
                raise KmsSigningError("Invalid signature format from Vault")

            signature = base64.b64decode(parts[2])

            # Get public key
            public_key = await self.get_public_key(key_id)

            # Log signing operation
            data_hash = hashlib.sha256(data).hexdigest()[:16]
            logger.debug(
                f"Signed data with Vault key {vault_key}, "
                f"data_hash={data_hash}..."
            )

            return SignatureResult(
                signature=signature,
                public_key=public_key,
            )

        except KmsError:
            raise
        except Exception as e:
            logger.error(f"Vault signing failed: {type(e).__name__}")
            raise KmsSigningError(f"Vault signing error: {type(e).__name__}") from e

    async def close(self) -> None:
        """Close Vault client."""
        self._client = None
        self._public_keys.clear()
        logger.debug("VaultKmsProvider closed")


# ============================================================
# AWS Secrets Manager Provider (Hybrid)
# ============================================================

class SecretsKmsProvider(KeyManagementService):
    """AWS Secrets Manager for key storage with local signing.

    Since AWS KMS doesn't support Ed25519, this provider:
    1. Loads encrypted private key from Secrets Manager
    2. Decrypts and keeps in memory
    3. Signs locally using the key

    Environment Variables:
    - AWS_REGION: AWS region
    - AWS_ACCESS_KEY_ID: AWS access key (or use IAM role)
    - AWS_SECRET_ACCESS_KEY: AWS secret key (or use IAM role)

    Secret Format:
    - Name: ton-hot-wallet-key
    - Value: {"private_key": "base64_encoded_32_bytes"}
    """

    def __init__(
        self,
        region_name: Optional[str] = None,
    ):
        """Initialize AWS Secrets Manager provider.

        Args:
            region_name: AWS region (overrides env)
        """
        self.region_name = region_name or getattr(settings, 'aws_region', 'ap-northeast-2')

        self._client = None
        self._keys: dict[str, Ed25519PrivateKey] = {}

        # Secret name mapping
        self._secret_names = {
            "hot_wallet": "ton-hot-wallet-key",
        }

        logger.info(
            f"SecretsKmsProvider initialized, region={self.region_name}"
        )

    async def _get_client(self):
        """Get or create AWS Secrets Manager client."""
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client(
                    'secretsmanager',
                    region_name=self.region_name,
                )
            except ImportError:
                raise KmsConfigError(
                    "boto3 package not installed. Install with: pip install boto3"
                )

        return self._client

    async def _load_key(self, key_id: str) -> Ed25519PrivateKey:
        """Load key from Secrets Manager."""
        if key_id in self._keys:
            return self._keys[key_id]

        try:
            import json
            client = await self._get_client()
            secret_name = self._secret_names.get(key_id, key_id)

            response = client.get_secret_value(SecretId=secret_name)
            secret_string = response.get('SecretString')

            if not secret_string:
                raise KmsKeyNotFoundError(f"Secret not found: {secret_name}")

            secret_data = json.loads(secret_string)
            private_key_b64 = secret_data.get('private_key')

            if not private_key_b64:
                raise KmsKeyNotFoundError(f"private_key not found in secret: {secret_name}")

            key_bytes = base64.b64decode(private_key_b64)
            if len(key_bytes) != 32:
                raise KmsConfigError(f"Invalid key length: {len(key_bytes)}")

            private_key = Ed25519PrivateKey.from_private_bytes(key_bytes)
            self._keys[key_id] = private_key

            logger.info(f"Loaded key from Secrets Manager: {secret_name}")
            return private_key

        except KmsError:
            raise
        except Exception as e:
            logger.error(f"Failed to load key from Secrets Manager: {type(e).__name__}")
            raise KmsError(f"Secrets Manager error: {type(e).__name__}") from e

    async def get_public_key(self, key_id: str = "hot_wallet") -> bytes:
        """Get public key from loaded private key."""
        private_key = await self._load_key(key_id)

        return private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

    async def sign(self, data: bytes, key_id: str = "hot_wallet") -> SignatureResult:
        """Sign data using key from Secrets Manager."""
        try:
            private_key = await self._load_key(key_id)
            signature = private_key.sign(data)

            public_key = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )

            # Log signing operation
            data_hash = hashlib.sha256(data).hexdigest()[:16]
            logger.debug(
                f"Signed data with Secrets Manager key {self._mask_key_id(key_id)}, "
                f"data_hash={data_hash}..."
            )

            return SignatureResult(
                signature=signature,
                public_key=public_key,
            )

        except KmsError:
            raise
        except Exception as e:
            logger.error(f"Signing failed: {type(e).__name__}")
            raise KmsSigningError(f"Failed to sign data: {type(e).__name__}") from e

    async def close(self) -> None:
        """Clear keys from memory."""
        self._keys.clear()
        self._client = None
        logger.debug("SecretsKmsProvider closed")


# ============================================================
# Factory Function
# ============================================================

def get_kms_service(provider: Optional[str] = None) -> KeyManagementService:
    """Get KMS service based on configuration.

    Args:
        provider: Force specific provider ("local", "vault", "secrets")
                  If None, auto-detect based on environment

    Returns:
        KeyManagementService instance

    Priority (if provider is None):
    1. Vault (if VAULT_ADDR is set)
    2. Secrets Manager (if AWS_REGION is set)
    3. Local (fallback for development)
    """
    # Force specific provider
    if provider:
        if provider == "local":
            return LocalKmsProvider()
        elif provider == "vault":
            return VaultKmsProvider()
        elif provider == "secrets":
            return SecretsKmsProvider()
        else:
            raise KmsConfigError(f"Unknown KMS provider: {provider}")

    # Auto-detect
    kms_provider = getattr(settings, 'kms_provider', None)

    if kms_provider:
        return get_kms_service(kms_provider)

    # Check Vault
    if getattr(settings, 'vault_addr', None):
        logger.info("Auto-selected VaultKmsProvider (VAULT_ADDR detected)")
        return VaultKmsProvider()

    # Check AWS
    if getattr(settings, 'aws_region', None) and getattr(settings, 'use_secrets_manager', False):
        logger.info("Auto-selected SecretsKmsProvider (AWS_REGION detected)")
        return SecretsKmsProvider()

    # Fallback to local
    logger.warning(
        "Auto-selected LocalKmsProvider (no Vault/AWS configured). "
        "This is suitable for development only."
    )
    return LocalKmsProvider()
