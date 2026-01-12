"""Audit Service for triple-logging financial transactions.

Phase 5.8: Triple recording system for financial integrity.

Features:
- Database (PostgreSQL) - Primary record
- Redis Stream - Real-time audit trail
- File logging - Backup and compliance
"""

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models.wallet import TransactionType, WalletTransaction
from app.utils.redis_client import get_redis

logger = logging.getLogger(__name__)


class AuditService:
    """Triple-logging audit service for financial transactions.

    Implements triple-recording pattern:
    1. Database (via WalletTransaction model) - Already handled by wallet service
    2. Redis Stream - For real-time monitoring and event sourcing
    3. File - For compliance and backup

    All entries include integrity hashes for tamper detection.
    """

    REDIS_STREAM_KEY = "audit:transactions"
    REDIS_STREAM_MAX_LEN = 100000  # Keep last 100k entries

    # File logging directory (relative to project root)
    AUDIT_LOG_DIR = "audit_logs"

    def __init__(self) -> None:
        """Initialize audit service."""
        self._redis = get_redis()
        self._log_dir = self._ensure_log_dir()

    def _ensure_log_dir(self) -> Path:
        """Ensure audit log directory exists."""
        # Get project root (backend directory)
        log_dir = Path(__file__).parent.parent.parent / self.AUDIT_LOG_DIR
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir

    async def log_transaction(
        self,
        tx: WalletTransaction,
        *,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Log transaction to all three destinations.

        Args:
            tx: WalletTransaction to log
            context: Additional context (IP, user agent, etc.)

        Returns:
            Audit entry ID
        """
        audit_id = str(uuid4())
        timestamp = datetime.utcnow().isoformat()

        # Build audit entry
        entry = {
            "audit_id": audit_id,
            "timestamp": timestamp,
            "tx_id": tx.id,
            "user_id": tx.user_id,
            "tx_type": tx.tx_type.value,
            "status": tx.status.value,
            "krw_amount": tx.krw_amount,
            "krw_balance_before": tx.krw_balance_before,
            "krw_balance_after": tx.krw_balance_after,
            "crypto_type": tx.crypto_type.value if tx.crypto_type else None,
            "crypto_amount": tx.crypto_amount,
            "crypto_tx_hash": tx.crypto_tx_hash,
            "crypto_address": tx.crypto_address,
            "exchange_rate_krw": tx.exchange_rate_krw,
            "integrity_hash": tx.integrity_hash,
            "context": context or {},
        }

        # Add audit entry hash
        entry["audit_hash"] = self._compute_audit_hash(entry)

        # Log to all three destinations
        await self._log_to_redis(entry)
        await self._log_to_file(entry)

        logger.info(
            f"Audit logged: id={audit_id} tx={tx.id[:8]}... "
            f"type={tx.tx_type.value} amount={tx.krw_amount:+,}"
        )

        return audit_id

    async def _log_to_redis(self, entry: dict[str, Any]) -> str:
        """Log to Redis Stream.

        Returns stream entry ID.
        """
        # Convert entry to flat dict for Redis
        flat_entry = {
            k: json.dumps(v) if isinstance(v, (dict, list)) else str(v or "")
            for k, v in entry.items()
        }

        entry_id = await self._redis.xadd(
            self.REDIS_STREAM_KEY,
            flat_entry,
            maxlen=self.REDIS_STREAM_MAX_LEN,
        )

        return entry_id

    async def _log_to_file(self, entry: dict[str, Any]) -> None:
        """Log to daily file.

        Files are named: audit_YYYY-MM-DD.jsonl
        Each line is a JSON object.
        """
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        file_path = self._log_dir / f"audit_{date_str}.jsonl"

        line = json.dumps(entry, ensure_ascii=False, default=str) + "\n"

        # Append to file (async would be better for production)
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(line)

    async def get_recent_entries(
        self,
        count: int = 100,
        *,
        user_id: str | None = None,
        tx_type: TransactionType | None = None,
    ) -> list[dict[str, Any]]:
        """Get recent audit entries from Redis Stream.

        Args:
            count: Number of entries to return
            user_id: Filter by user ID
            tx_type: Filter by transaction type

        Returns:
            List of audit entries (newest first)
        """
        # Read from Redis stream
        entries = await self._redis.xrevrange(
            self.REDIS_STREAM_KEY,
            count=count * 2 if user_id or tx_type else count,
        )

        result = []
        for entry_id, data in entries:
            # Parse JSON fields
            parsed = {}
            for k, v in data.items():
                key = k.decode() if isinstance(k, bytes) else k
                val = v.decode() if isinstance(v, bytes) else v
                try:
                    parsed[key] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    parsed[key] = val

            # Apply filters
            if user_id and parsed.get("user_id") != user_id:
                continue
            if tx_type and parsed.get("tx_type") != tx_type.value:
                continue

            result.append(parsed)

            if len(result) >= count:
                break

        return result

    async def verify_transaction_integrity(
        self,
        tx: WalletTransaction,
    ) -> dict[str, bool]:
        """Verify transaction integrity across all logs.

        Returns:
            Dict with verification status for each log type
        """
        expected_hash = tx.integrity_hash

        # Verify database record (transaction itself)
        db_valid = self._verify_integrity_hash(
            tx.user_id,
            tx.tx_type,
            tx.krw_amount,
            tx.krw_balance_before,
            tx.krw_balance_after,
            expected_hash,
        )

        # Check Redis stream
        redis_valid = False
        redis_entries = await self._redis.xrevrange(
            self.REDIS_STREAM_KEY,
            count=1000,
        )
        for _, data in redis_entries:
            tx_id = data.get(b"tx_id", b"").decode()
            if tx_id == tx.id:
                stored_hash = data.get(b"integrity_hash", b"").decode()
                # Use timing-safe comparison
                redis_valid = hmac.compare_digest(stored_hash, expected_hash)
                break

        # TODO: File verification would require scanning log files

        return {
            "database": db_valid,
            "redis": redis_valid,
            "file": None,  # Not implemented
        }

    @staticmethod
    def _compute_audit_hash(entry: dict[str, Any]) -> str:
        """Compute SHA-256 hash of audit entry."""
        # Create deterministic string from key fields
        data = (
            f"{entry['audit_id']}:"
            f"{entry['tx_id']}:"
            f"{entry['user_id']}:"
            f"{entry['tx_type']}:"
            f"{entry['krw_amount']}:"
            f"{entry['integrity_hash']}"
        )
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    def _verify_integrity_hash(
        user_id: str,
        tx_type: TransactionType,
        amount: int,
        balance_before: int,
        balance_after: int,
        expected_hash: str,
    ) -> bool:
        """Verify integrity hash using timing-safe comparison."""
        data = f"{user_id}:{tx_type.value}:{amount}:{balance_before}:{balance_after}"
        computed = hashlib.sha256(data.encode()).hexdigest()
        # Use timing-safe comparison to prevent timing attacks
        return hmac.compare_digest(computed, expected_hash)


# Singleton instance
_audit_service: AuditService | None = None


def get_audit_service() -> AuditService:
    """Get audit service singleton."""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service
