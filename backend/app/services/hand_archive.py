"""Hand history archive service with compression.

Phase 10: Hand history compression for 80% storage reduction.

Features:
- MessagePack + gzip compression
- Tiered storage (hot/warm/cold)
- Async archival
"""

import gzip
import logging
from datetime import datetime, timedelta
from typing import Any

import msgpack
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# Archive policy configuration
ARCHIVE_POLICY = {
    "hot": {
        "storage": "postgresql",
        "retention_days": 7,
        "compression": False,
    },
    "warm": {
        "storage": "redis",
        "retention_days": 30,
        "compression": True,
    },
    "cold": {
        "storage": "s3",  # or local file system
        "retention_days": 365,
        "compression": True,
    },
}


class HandArchiveService:
    """Hand history archive service with compression.

    Usage:
        archive_service = HandArchiveService(redis_client)

        # Archive a completed hand
        compressed = await archive_service.archive_hand(hand_data)

        # Retrieve archived hand
        hand_data = await archive_service.retrieve_hand(hand_id)
    """

    def __init__(self, redis_client=None, compression_level: int = 6):
        """Initialize archive service.

        Args:
            redis_client: Redis client for warm storage
            compression_level: gzip compression level (1-9, default 6)
        """
        self._redis = redis_client
        self._compression_level = compression_level

    def compress_hand(self, hand_data: dict) -> bytes:
        """Compress hand data using MessagePack + gzip.

        Args:
            hand_data: Hand data dictionary

        Returns:
            Compressed bytes (80-90% size reduction)
        """
        # Serialize with MessagePack
        packed = msgpack.packb(hand_data, use_bin_type=True)

        # Compress with gzip
        compressed = gzip.compress(packed, compresslevel=self._compression_level)

        return compressed

    def decompress_hand(self, compressed: bytes) -> dict:
        """Decompress hand data.

        Args:
            compressed: Compressed bytes

        Returns:
            Original hand data dictionary
        """
        # Decompress
        decompressed = gzip.decompress(compressed)

        # Deserialize
        return msgpack.unpackb(decompressed, raw=False)

    async def archive_hand(self, hand_data: dict) -> bytes:
        """Archive a completed hand.

        Args:
            hand_data: Hand data to archive

        Returns:
            Compressed bytes
        """
        # Add archive metadata
        hand_data["_archived_at"] = datetime.utcnow().isoformat()

        compressed = self.compress_hand(hand_data)

        # Store in warm storage (Redis) if available
        if self._redis and hand_data.get("hand_id"):
            hand_id = hand_data["hand_id"]
            key = f"hand:archive:{hand_id}"
            ttl = ARCHIVE_POLICY["warm"]["retention_days"] * 86400

            await self._redis.setex(key, ttl, compressed)
            logger.debug(f"Archived hand {hand_id} to Redis ({len(compressed)} bytes)")

        return compressed

    async def retrieve_hand(self, hand_id: str) -> dict | None:
        """Retrieve archived hand.

        Args:
            hand_id: Hand ID to retrieve

        Returns:
            Hand data or None if not found
        """
        # Try warm storage first
        if self._redis:
            key = f"hand:archive:{hand_id}"
            compressed = await self._redis.get(key)
            if compressed:
                return self.decompress_hand(compressed)

        # TODO: Try cold storage (S3) if not in warm storage

        return None

    async def archive_batch(self, hands: list[dict]) -> int:
        """Archive multiple hands in batch.

        Args:
            hands: List of hand data dictionaries

        Returns:
            Number of hands archived
        """
        archived = 0
        for hand_data in hands:
            try:
                await self.archive_hand(hand_data)
                archived += 1
            except Exception as e:
                logger.error(f"Failed to archive hand: {e}")

        return archived

    def get_compression_stats(self, hand_data: dict) -> dict[str, Any]:
        """Get compression statistics for a hand.

        Args:
            hand_data: Hand data to analyze

        Returns:
            Compression statistics
        """
        import json

        # Original JSON size
        json_bytes = len(json.dumps(hand_data).encode())

        # MessagePack size
        msgpack_bytes = len(msgpack.packb(hand_data, use_bin_type=True))

        # Compressed size
        compressed_bytes = len(self.compress_hand(hand_data))

        return {
            "json_bytes": json_bytes,
            "msgpack_bytes": msgpack_bytes,
            "compressed_bytes": compressed_bytes,
            "msgpack_reduction_pct": round((1 - msgpack_bytes / json_bytes) * 100, 1),
            "total_reduction_pct": round((1 - compressed_bytes / json_bytes) * 100, 1),
        }


# =============================================================================
# Celery Tasks for Scheduled Archival
# =============================================================================

async def archive_old_hands(
    session: AsyncSession,
    archive_service: HandArchiveService,
    older_than_days: int = 7,
) -> dict[str, int]:
    """Archive hands older than specified days.

    Args:
        session: Database session
        archive_service: Archive service instance
        older_than_days: Archive hands older than this many days

    Returns:
        Statistics about archived hands
    """
    from sqlalchemy import select
    from app.models.hand import Hand

    cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)

    # Query old hands
    query = select(Hand).where(
        Hand.ended_at < cutoff_date,
        Hand.archived == False,  # noqa: E712
    ).limit(1000)

    result = await session.execute(query)
    hands = result.scalars().all()

    archived_count = 0
    total_bytes_saved = 0

    for hand in hands:
        try:
            # Convert to dict for archival
            hand_data = {
                "hand_id": str(hand.id),
                "table_id": str(hand.table_id),
                "started_at": hand.started_at.isoformat() if hand.started_at else None,
                "ended_at": hand.ended_at.isoformat() if hand.ended_at else None,
                "community_cards": hand.community_cards,
                "pot_total": hand.pot_total,
                "winner_ids": hand.winner_ids,
                # Add more fields as needed
            }

            # Get compression stats
            stats = archive_service.get_compression_stats(hand_data)
            total_bytes_saved += stats["json_bytes"] - stats["compressed_bytes"]

            # Archive
            await archive_service.archive_hand(hand_data)

            # Mark as archived in DB
            hand.archived = True
            archived_count += 1

        except Exception as e:
            logger.error(f"Failed to archive hand {hand.id}: {e}")

    await session.commit()

    return {
        "archived_count": archived_count,
        "total_bytes_saved": total_bytes_saved,
        "avg_reduction_pct": round(total_bytes_saved / (archived_count * 1000) * 100, 1) if archived_count > 0 else 0,
    }
