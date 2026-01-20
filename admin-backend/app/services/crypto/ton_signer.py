"""TON Blockchain Transaction Signer for Jetton (USDT) transfers.

Handles:
- Jetton transfer message building
- Transaction signing via KMS
- Transaction broadcasting to TON network

Security Notes:
- Private keys are managed by KMS, never exposed
- All transactions are logged for audit
- Supports both testnet and mainnet
"""

import asyncio
import base64
import hashlib
import logging
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Tuple
from enum import IntEnum

import httpx

from app.config import get_settings
from app.services.crypto.kms_service import (
    KeyManagementService,
    get_kms_service,
    KmsError,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Constants
USDT_JETTON_MASTER = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"
USDT_DECIMALS = 6
TON_DECIMALS = 9

# Jetton transfer op code
JETTON_TRANSFER_OP = 0x0f8a7ea5

# Minimum TON for gas (0.05 TON)
MIN_TON_FOR_GAS = 50_000_000  # nanoTON
JETTON_FORWARD_AMOUNT = 1  # nanoTON (minimal forward amount)


# ============================================================
# Exceptions
# ============================================================

class TonSignerError(Exception):
    """Base exception for TON signer operations."""
    pass


class TonSignerConfigError(TonSignerError):
    """Configuration error."""
    pass


class TonSignerBuildError(TonSignerError):
    """Transaction build error."""
    pass


class TonSignerBroadcastError(TonSignerError):
    """Transaction broadcast error."""
    pass


class InsufficientGasError(TonSignerError):
    """Insufficient TON for gas fees."""
    pass


# ============================================================
# Data Classes
# ============================================================

@dataclass(frozen=True)
class JettonTransferParams:
    """Parameters for Jetton transfer."""
    to_address: str  # Recipient's TON address
    amount: Decimal  # Amount in USDT (not nano)
    memo: Optional[str] = None  # Optional comment
    response_address: Optional[str] = None  # Where to return excess TON


@dataclass
class TransactionResult:
    """Result of a transaction operation."""
    success: bool
    tx_hash: Optional[str]
    message: str
    raw_result: Optional[dict] = None


# ============================================================
# Wallet Contract Versions
# ============================================================

class WalletVersion(IntEnum):
    """TON wallet contract versions."""
    V3R1 = 1
    V3R2 = 2
    V4R1 = 3
    V4R2 = 4


# ============================================================
# Cell Builder (Simplified)
# ============================================================

class CellBuilder:
    """Simplified Cell builder for TON transactions.

    TON uses Cell as the basic data structure.
    This is a minimal implementation for Jetton transfers.

    For production, consider using tonsdk or pytoniq libraries.
    """

    def __init__(self):
        self.bits: list[int] = []
        self.refs: list['CellBuilder'] = []

    def store_uint(self, value: int, bits: int) -> 'CellBuilder':
        """Store unsigned integer."""
        for i in range(bits - 1, -1, -1):
            self.bits.append((value >> i) & 1)
        return self

    def store_int(self, value: int, bits: int) -> 'CellBuilder':
        """Store signed integer."""
        if value < 0:
            value = (1 << bits) + value
        return self.store_uint(value, bits)

    def store_coins(self, amount: int) -> 'CellBuilder':
        """Store variable-length coins (nanoTON or nanoJetton)."""
        if amount == 0:
            return self.store_uint(0, 4)

        # Calculate bytes needed
        byte_len = (amount.bit_length() + 7) // 8
        self.store_uint(byte_len, 4)

        for i in range(byte_len - 1, -1, -1):
            self.store_uint((amount >> (i * 8)) & 0xFF, 8)

        return self

    def store_address(self, address: str) -> 'CellBuilder':
        """Store TON address.

        Supports formats:
        - EQ... or UQ... (user-friendly)
        - 0:... or -1:... (raw format)
        """
        if not address:
            # Store null address (addr_none)
            return self.store_uint(0, 2)

        workchain, hash_part = self._parse_address(address)

        # addr_std format: 10 + anycast(0) + workchain(8) + hash(256)
        self.store_uint(2, 2)  # addr_std
        self.store_uint(0, 1)  # no anycast
        self.store_int(workchain, 8)

        # Store 256-bit hash
        for byte in hash_part:
            self.store_uint(byte, 8)

        return self

    def _parse_address(self, address: str) -> Tuple[int, bytes]:
        """Parse TON address to workchain and hash."""
        if address.startswith(("EQ", "UQ", "Ef", "Uf", "kQ", "0Q")):
            # User-friendly format (base64url)
            # Decode base64url
            addr_bytes = self._base64url_decode(address)
            if len(addr_bytes) != 36:
                raise TonSignerBuildError(f"Invalid address length: {len(addr_bytes)}")

            # Format: 1 byte flags + 1 byte workchain + 32 bytes hash + 2 bytes CRC16
            workchain = struct.unpack('b', addr_bytes[1:2])[0]
            hash_part = addr_bytes[2:34]
            return workchain, hash_part

        elif ":" in address:
            # Raw format: workchain:hash
            parts = address.split(":")
            workchain = int(parts[0])
            hash_hex = parts[1]
            hash_part = bytes.fromhex(hash_hex)
            return workchain, hash_part

        else:
            raise TonSignerBuildError(f"Unknown address format: {address[:10]}...")

    def _base64url_decode(self, s: str) -> bytes:
        """Decode base64url string."""
        # Add padding if needed
        padding = 4 - len(s) % 4
        if padding != 4:
            s += "=" * padding
        # Replace URL-safe characters
        s = s.replace("-", "+").replace("_", "/")
        return base64.b64decode(s)

    def store_ref(self, cell: 'CellBuilder') -> 'CellBuilder':
        """Store reference to another cell."""
        if len(self.refs) >= 4:
            raise TonSignerBuildError("Cell can have at most 4 references")
        self.refs.append(cell)
        return self

    def store_string(self, text: str) -> 'CellBuilder':
        """Store text as snake format (op=0 + data)."""
        if not text:
            return self.store_uint(0, 32)  # Empty text marker

        self.store_uint(0, 32)  # Text op code

        # Store UTF-8 bytes
        text_bytes = text.encode('utf-8')
        for byte in text_bytes:
            self.store_uint(byte, 8)

        return self

    def store_maybe_ref(self, cell: Optional['CellBuilder']) -> 'CellBuilder':
        """Store optional reference."""
        if cell is None:
            return self.store_uint(0, 1)
        return self.store_uint(1, 1).store_ref(cell)

    def to_bytes(self) -> bytes:
        """Convert cell to bytes representation.

        This is a simplified serialization.
        Real BOC (Bag of Cells) serialization is more complex.
        """
        # Pad bits to byte boundary
        bits = self.bits.copy()
        while len(bits) % 8 != 0:
            bits.append(0)

        # Convert to bytes
        data = bytes(
            sum(bits[i + j] << (7 - j) for j in range(8))
            for i in range(0, len(bits), 8)
        )

        return data

    def to_boc(self) -> bytes:
        """Serialize cell to BOC (Bag of Cells) format.

        Simplified BOC serialization for single cell without references.
        For full BOC support, use tonsdk library.
        """
        # This is a simplified implementation
        # Real BOC has complex structure for multiple cells and references

        data = self.to_bytes()

        # Simple BOC header for single cell
        # Format: magic(4) + flags(1) + cells_count(1) + ... + data
        boc = bytearray()

        # BOC magic number
        boc.extend(b'\xb5\xee\x9c\x72')

        # Flags and size info (simplified)
        boc.append(0x01)  # has_idx = 0, hash_crc32 = 0, has_cache_bits = 0, flags = 0, size_bytes = 1
        boc.append(0x01)  # off_bytes = 1
        boc.append(0x01)  # cells_count = 1
        boc.append(0x01)  # roots_count = 1
        boc.append(0x00)  # absent_count = 0
        boc.append(len(data))  # tot_cells_size

        # Root index
        boc.append(0x00)

        # Cell data
        d1 = (len(self.refs) << 5) | (0 if len(self.bits) % 8 == 0 else 1)
        d2 = (len(self.bits) + 7) // 8

        boc.append(d1)
        boc.append(d2)
        boc.extend(data)

        return bytes(boc)

    def hash(self) -> bytes:
        """Calculate cell hash (SHA256)."""
        return hashlib.sha256(self.to_bytes()).digest()


# ============================================================
# TON Signer Service
# ============================================================

class TonSigner:
    """TON blockchain transaction signer.

    Builds and signs Jetton transfer transactions.
    Uses KMS for secure key management.
    """

    # API endpoints
    TONCENTER_MAINNET = "https://toncenter.com/api/v2"
    TONCENTER_TESTNET = "https://testnet.toncenter.com/api/v2"
    TONAPI_MAINNET = "https://tonapi.io/v2"
    TONAPI_TESTNET = "https://testnet.tonapi.io/v2"

    def __init__(
        self,
        kms: Optional[KeyManagementService] = None,
        wallet_address: Optional[str] = None,
        network: Optional[str] = None,
        api_key: Optional[str] = None,
        wallet_version: WalletVersion = WalletVersion.V4R2,
    ):
        """Initialize TON signer.

        Args:
            kms: Key management service (auto-created if None)
            wallet_address: Hot wallet address
            network: "mainnet" or "testnet"
            api_key: TON Center API key
            wallet_version: Wallet contract version
        """
        self.kms = kms or get_kms_service()
        self.wallet_address = wallet_address or settings.ton_hot_wallet_address
        self.network = network or settings.ton_network
        self.api_key = api_key or settings.ton_center_api_key
        self.wallet_version = wallet_version

        # Set API URLs based on network
        if self.network == "mainnet":
            self.toncenter_url = self.TONCENTER_MAINNET
            self.tonapi_url = self.TONAPI_MAINNET
        else:
            self.toncenter_url = self.TONCENTER_TESTNET
            self.tonapi_url = self.TONAPI_TESTNET

        self._http_client: Optional[httpx.AsyncClient] = None
        self._seqno_cache: dict[str, Tuple[int, datetime]] = {}
        self._jetton_wallet_cache: dict[str, str] = {}

        logger.info(
            f"TonSigner initialized for {self.network}, "
            f"wallet={self.wallet_address[:10] if self.wallet_address else 'not set'}..."
        )

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            headers = {}
            if self.api_key:
                headers["X-API-Key"] = self.api_key
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                headers=headers,
            )
        return self._http_client

    async def close(self) -> None:
        """Close connections and cleanup."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
        await self.kms.close()

    # ============================================================
    # Public Methods
    # ============================================================

    async def transfer_jetton(
        self,
        params: JettonTransferParams,
        jetton_master: str = USDT_JETTON_MASTER,
    ) -> TransactionResult:
        """Transfer Jetton (USDT) to recipient.

        Args:
            params: Transfer parameters
            jetton_master: Jetton master contract address

        Returns:
            TransactionResult with tx_hash on success
        """
        try:
            # Validate parameters
            if not params.to_address:
                raise TonSignerBuildError("Recipient address is required")

            if params.amount <= 0:
                raise TonSignerBuildError("Amount must be positive")

            # Get our Jetton wallet address
            jetton_wallet = await self._get_jetton_wallet_address(
                self.wallet_address,
                jetton_master
            )

            if not jetton_wallet:
                raise TonSignerBuildError(
                    "Failed to get Jetton wallet address. "
                    "Ensure hot wallet has USDT balance."
                )

            # Check TON balance for gas
            ton_balance = await self._get_ton_balance()
            if ton_balance < MIN_TON_FOR_GAS:
                raise InsufficientGasError(
                    f"Insufficient TON for gas: {ton_balance / 1e9:.4f} TON, "
                    f"need {MIN_TON_FOR_GAS / 1e9:.4f} TON"
                )

            # Get current seqno
            seqno = await self._get_seqno()

            # Build transaction
            body = self._build_jetton_transfer_body(params)
            external_message = await self._build_external_message(
                to_address=jetton_wallet,
                amount=MIN_TON_FOR_GAS,
                body=body,
                seqno=seqno,
            )

            # Broadcast transaction
            result = await self._broadcast_message(external_message)

            if result.success:
                logger.info(
                    f"Jetton transfer sent: {params.amount} USDT to "
                    f"{params.to_address[:10]}..., tx={result.tx_hash}"
                )
            else:
                logger.error(f"Jetton transfer failed: {result.message}")

            return result

        except TonSignerError:
            raise
        except Exception as e:
            logger.error(f"Jetton transfer error: {type(e).__name__}: {e}")
            raise TonSignerError(f"Transfer failed: {e}") from e

    async def get_balance(self, address: Optional[str] = None) -> Decimal:
        """Get USDT balance of an address.

        Args:
            address: Address to check (defaults to hot wallet)

        Returns:
            USDT balance as Decimal
        """
        target = address or self.wallet_address
        if not target:
            raise TonSignerConfigError("No address specified")

        try:
            client = await self._get_http_client()

            url = f"{self.tonapi_url}/accounts/{target}/jettons"
            response = await client.get(url)

            if response.status_code == 200:
                data = response.json()
                for balance in data.get("balances", []):
                    jetton = balance.get("jetton", {})
                    if jetton.get("address") == USDT_JETTON_MASTER:
                        amount_nano = int(balance.get("balance", 0))
                        return Decimal(amount_nano) / Decimal(10 ** USDT_DECIMALS)

            return Decimal("0")

        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            raise TonSignerError(f"Balance check failed: {e}") from e

    async def verify_transaction(self, tx_hash: str) -> bool:
        """Verify if a transaction is confirmed.

        Args:
            tx_hash: Transaction hash to verify

        Returns:
            True if confirmed, False otherwise
        """
        try:
            client = await self._get_http_client()

            url = f"{self.tonapi_url}/blockchain/transactions/{tx_hash}"
            response = await client.get(url)

            if response.status_code == 200:
                data = response.json()
                return data.get("success", False)

            return False

        except Exception as e:
            logger.warning(f"Transaction verification failed: {e}")
            return False

    # ============================================================
    # Internal Methods
    # ============================================================

    def _build_jetton_transfer_body(
        self,
        params: JettonTransferParams,
    ) -> CellBuilder:
        """Build Jetton transfer message body.

        Jetton transfer message format:
        - op: uint32 = 0x0f8a7ea5 (transfer)
        - query_id: uint64
        - amount: Coins (jetton amount in nano)
        - destination: Address (recipient)
        - response_destination: Address (where to return excess)
        - custom_payload: Maybe Cell
        - forward_ton_amount: Coins
        - forward_payload: Either Cell (comment/data)
        """
        cell = CellBuilder()

        # Operation code: transfer
        cell.store_uint(JETTON_TRANSFER_OP, 32)

        # Query ID (timestamp-based for uniqueness)
        query_id = int(datetime.now(timezone.utc).timestamp() * 1000)
        cell.store_uint(query_id, 64)

        # Amount in nano-jetton
        amount_nano = int(params.amount * (10 ** USDT_DECIMALS))
        cell.store_coins(amount_nano)

        # Destination address
        cell.store_address(params.to_address)

        # Response destination (hot wallet to receive excess)
        response_addr = params.response_address or self.wallet_address
        cell.store_address(response_addr)

        # Custom payload: empty (0 bit)
        cell.store_uint(0, 1)

        # Forward TON amount (minimal for notification)
        cell.store_coins(JETTON_FORWARD_AMOUNT)

        # Forward payload (comment or empty)
        if params.memo:
            # Store memo as forward payload
            comment_cell = CellBuilder()
            comment_cell.store_string(params.memo)
            cell.store_uint(1, 1)  # has payload
            cell.store_ref(comment_cell)
        else:
            cell.store_uint(0, 1)  # no payload

        return cell

    async def _build_external_message(
        self,
        to_address: str,
        amount: int,
        body: CellBuilder,
        seqno: int,
    ) -> bytes:
        """Build and sign external message.

        External message format for wallet v4:
        - signature: bits512
        - subwallet_id: uint32 (usually 698983191)
        - valid_until: uint32
        - seqno: uint32
        - op: uint8 (0 for simple transfer)
        - mode: uint8 (message send mode)
        - internal_message: Cell
        """
        # Build internal message
        internal_msg = self._build_internal_message(to_address, amount, body)

        # Build signing message
        signing_cell = CellBuilder()

        # Subwallet ID (default for v4r2)
        signing_cell.store_uint(698983191, 32)

        # Valid until (30 minutes from now)
        valid_until = int(datetime.now(timezone.utc).timestamp()) + 1800
        signing_cell.store_uint(valid_until, 32)

        # Seqno
        signing_cell.store_uint(seqno, 32)

        # Op code (0 = simple send)
        signing_cell.store_uint(0, 8)

        # Send mode (3 = PAY_GAS_SEPARATELY + IGNORE_ERRORS)
        signing_cell.store_uint(3, 8)

        # Internal message as reference
        signing_cell.store_ref(internal_msg)

        # Sign the message
        message_hash = signing_cell.hash()
        signature_result = await self.kms.sign(message_hash)

        # Build external message with signature
        external_cell = CellBuilder()

        # Signature (512 bits = 64 bytes)
        for byte in signature_result.signature:
            external_cell.store_uint(byte, 8)

        # Copy signing message content
        for bit in signing_cell.bits:
            external_cell.bits.append(bit)

        for ref in signing_cell.refs:
            external_cell.refs.append(ref)

        return external_cell.to_boc()

    def _build_internal_message(
        self,
        to_address: str,
        amount: int,
        body: CellBuilder,
    ) -> CellBuilder:
        """Build internal message.

        Internal message format:
        - ihr_disabled: bit (1)
        - bounce: bit (1 for bounceable)
        - bounced: bit (0)
        - src: Address (none for external)
        - dest: Address
        - value: Coins
        - ihr_fee: Coins (0)
        - fwd_fee: Coins (0)
        - created_lt: uint64 (0)
        - created_at: uint32 (0)
        - init: Maybe StateInit (none)
        - body: Either Cell (the transfer body)
        """
        cell = CellBuilder()

        # Message flags
        cell.store_uint(0, 1)  # ihr_disabled = false
        cell.store_uint(1, 1)  # bounce = true
        cell.store_uint(0, 1)  # bounced = false

        # Source: addr_none
        cell.store_uint(0, 2)

        # Destination
        cell.store_address(to_address)

        # Value
        cell.store_coins(amount)

        # Extra currency collection: empty
        cell.store_uint(0, 1)

        # IHR fee, fwd_fee, created_lt, created_at
        cell.store_coins(0)  # ihr_fee
        cell.store_coins(0)  # fwd_fee
        cell.store_uint(0, 64)  # created_lt
        cell.store_uint(0, 32)  # created_at

        # State init: none
        cell.store_uint(0, 1)

        # Body as reference
        cell.store_uint(1, 1)  # body in ref
        cell.store_ref(body)

        return cell

    async def _broadcast_message(self, boc: bytes) -> TransactionResult:
        """Broadcast message to TON network.

        Args:
            boc: Serialized message (Bag of Cells)

        Returns:
            TransactionResult
        """
        try:
            client = await self._get_http_client()

            # Base64 encode the BOC
            boc_b64 = base64.b64encode(boc).decode()

            # Send to TON Center
            url = f"{self.toncenter_url}/sendBoc"
            response = await client.post(
                url,
                json={"boc": boc_b64},
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    # TON Center returns hash in result
                    result = data.get("result", {})
                    tx_hash = result.get("hash") or hashlib.sha256(boc).hexdigest()

                    return TransactionResult(
                        success=True,
                        tx_hash=tx_hash,
                        message="Transaction sent successfully",
                        raw_result=data,
                    )
                else:
                    error = data.get("error", "Unknown error")
                    return TransactionResult(
                        success=False,
                        tx_hash=None,
                        message=f"TON Center error: {error}",
                        raw_result=data,
                    )
            else:
                return TransactionResult(
                    success=False,
                    tx_hash=None,
                    message=f"HTTP error: {response.status_code}",
                    raw_result={"status_code": response.status_code},
                )

        except Exception as e:
            logger.error(f"Broadcast failed: {e}")
            return TransactionResult(
                success=False,
                tx_hash=None,
                message=f"Broadcast error: {e}",
            )

    async def _get_seqno(self) -> int:
        """Get current wallet seqno (sequence number).

        Seqno is incremented with each outgoing transaction.
        Cached for 10 seconds to reduce API calls.
        """
        cache_key = self.wallet_address
        now = datetime.now(timezone.utc)

        # Check cache
        if cache_key in self._seqno_cache:
            cached_seqno, cached_at = self._seqno_cache[cache_key]
            if (now - cached_at).total_seconds() < 10:
                return cached_seqno

        try:
            client = await self._get_http_client()

            url = f"{self.toncenter_url}/runGetMethod"
            response = await client.post(
                url,
                json={
                    "address": self.wallet_address,
                    "method": "seqno",
                    "stack": [],
                },
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    stack = data.get("result", {}).get("stack", [])
                    if stack:
                        seqno = int(stack[0][1], 16)
                        self._seqno_cache[cache_key] = (seqno, now)
                        return seqno

            # Default to 0 if cannot get seqno
            logger.warning(f"Could not get seqno, using 0")
            return 0

        except Exception as e:
            logger.error(f"Failed to get seqno: {e}")
            return 0

    async def _get_ton_balance(self) -> int:
        """Get TON balance in nanoTON."""
        try:
            client = await self._get_http_client()

            url = f"{self.toncenter_url}/getAddressInformation"
            response = await client.get(
                url,
                params={"address": self.wallet_address},
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    return int(data.get("result", {}).get("balance", 0))

            return 0

        except Exception as e:
            logger.error(f"Failed to get TON balance: {e}")
            return 0

    async def _get_jetton_wallet_address(
        self,
        owner_address: str,
        jetton_master: str,
    ) -> Optional[str]:
        """Get Jetton wallet address for owner.

        Each address has a unique Jetton wallet derived from
        the Jetton master contract.
        """
        cache_key = f"{owner_address}:{jetton_master}"

        if cache_key in self._jetton_wallet_cache:
            return self._jetton_wallet_cache[cache_key]

        try:
            client = await self._get_http_client()

            # Use TonAPI
            url = f"{self.tonapi_url}/accounts/{owner_address}/jettons/{jetton_master}"
            response = await client.get(url)

            if response.status_code == 200:
                data = response.json()
                wallet_address = data.get("wallet_address", {}).get("address")
                if wallet_address:
                    self._jetton_wallet_cache[cache_key] = wallet_address
                    return wallet_address

            return None

        except Exception as e:
            logger.error(f"Failed to get Jetton wallet address: {e}")
            return None


# ============================================================
# Factory Function
# ============================================================

def get_ton_signer(kms: Optional[KeyManagementService] = None) -> TonSigner:
    """Get TonSigner instance.

    Args:
        kms: Optional KMS service (auto-created if None)

    Returns:
        TonSigner instance
    """
    return TonSigner(kms=kms)
