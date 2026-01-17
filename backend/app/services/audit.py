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

        # File verification - scan log files
        file_valid = await self._verify_from_file(tx.id, expected_hash)

        return {
            "database": db_valid,
            "redis": redis_valid,
            "file": file_valid,
        }

    async def _verify_from_file(
        self,
        tx_id: str,
        expected_hash: str,
    ) -> bool | None:
        """Verify transaction from file logs.

        Scans JSONL log files to find the transaction and verify its hash.

        Args:
            tx_id: Transaction ID to find
            expected_hash: Expected integrity hash

        Returns:
            True if found and valid, False if found but invalid, None if not found
        """
        # Get list of audit log files (newest first)
        log_files = sorted(
            self._log_dir.glob("audit_*.jsonl"),
            reverse=True,
        )

        for log_file in log_files:
            result = await self._scan_file_for_tx(log_file, tx_id, expected_hash)
            if result is not None:
                return result

        return None

    async def _scan_file_for_tx(
        self,
        file_path: Path,
        tx_id: str,
        expected_hash: str,
    ) -> bool | None:
        """Scan a single log file for transaction.

        Args:
            file_path: Path to log file
            tx_id: Transaction ID to find
            expected_hash: Expected integrity hash

        Returns:
            True if valid, False if invalid, None if not found
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("tx_id") == tx_id:
                            stored_hash = entry.get("integrity_hash", "")
                            # Use timing-safe comparison
                            return hmac.compare_digest(stored_hash, expected_hash)
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.error(f"Error scanning audit file {file_path}: {e}")

        return None

    async def scan_audit_logs(
        self,
        *,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        user_id: str | None = None,
        tx_type: TransactionType | None = None,
    ) -> list[dict[str, Any]]:
        """Scan audit log files with filters.

        Args:
            start_date: Start date filter (inclusive)
            end_date: End date filter (inclusive)
            user_id: Filter by user ID
            tx_type: Filter by transaction type

        Returns:
            List of matching audit entries
        """
        log_files = sorted(self._log_dir.glob("audit_*.jsonl"))

        # Filter files by date range
        if start_date or end_date:
            filtered_files = []
            for log_file in log_files:
                # Extract date from filename (audit_YYYY-MM-DD.jsonl)
                try:
                    date_str = log_file.stem.replace("audit_", "")
                    file_date = datetime.strptime(date_str, "%Y-%m-%d")

                    if start_date and file_date.date() < start_date.date():
                        continue
                    if end_date and file_date.date() > end_date.date():
                        continue

                    filtered_files.append(log_file)
                except ValueError:
                    continue
            log_files = filtered_files

        results = []
        for log_file in log_files:
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            entry = json.loads(line)

                            # Apply filters
                            if user_id and entry.get("user_id") != user_id:
                                continue
                            if tx_type and entry.get("tx_type") != tx_type.value:
                                continue

                            results.append(entry)
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                logger.error(f"Error reading audit file {log_file}: {e}")

        return results

    async def verify_audit_log_integrity(
        self,
        date: datetime | None = None,
    ) -> dict[str, Any]:
        """Verify integrity of audit log entries.

        Checks that all audit hashes are valid.

        Args:
            date: Specific date to verify (defaults to today)

        Returns:
            Verification report with counts and any invalid entries
        """
        if date is None:
            date = datetime.utcnow()

        date_str = date.strftime("%Y-%m-%d")
        file_path = self._log_dir / f"audit_{date_str}.jsonl"

        if not file_path.exists():
            return {
                "date": date_str,
                "status": "no_file",
                "total_entries": 0,
                "valid_entries": 0,
                "invalid_entries": 0,
                "invalid_details": [],
            }

        total = 0
        valid = 0
        invalid_details = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, 1):
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        total += 1

                        # Verify audit hash
                        stored_hash = entry.get("audit_hash", "")
                        # Remove audit_hash from entry for recomputation
                        entry_copy = {k: v for k, v in entry.items() if k != "audit_hash"}
                        computed_hash = self._compute_audit_hash(entry_copy)

                        if hmac.compare_digest(stored_hash, computed_hash):
                            valid += 1
                        else:
                            invalid_details.append({
                                "line": line_no,
                                "audit_id": entry.get("audit_id"),
                                "tx_id": entry.get("tx_id"),
                                "reason": "hash_mismatch",
                            })
                    except json.JSONDecodeError:
                        total += 1
                        invalid_details.append({
                            "line": line_no,
                            "reason": "json_parse_error",
                        })
        except Exception as e:
            return {
                "date": date_str,
                "status": "error",
                "error": str(e),
                "total_entries": total,
                "valid_entries": valid,
                "invalid_entries": len(invalid_details),
                "invalid_details": invalid_details,
            }

        return {
            "date": date_str,
            "status": "valid" if len(invalid_details) == 0 else "invalid",
            "total_entries": total,
            "valid_entries": valid,
            "invalid_entries": len(invalid_details),
            "invalid_details": invalid_details[:100],  # Limit to first 100
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
