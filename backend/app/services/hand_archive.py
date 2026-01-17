"""Hand history archive service with compression.

Phase 10: Hand history compression for 80% storage reduction.

Features:
- MessagePack + gzip compression
- Tiered storage (hot/warm/cold)
- Async archival
- S3 cold storage integration
"""

import gzip
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import msgpack
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings

logger = logging.getLogger(__name__)

# S3 클라이언트 초기화 (optional)
_s3_client = None


def _get_s3_client():
    """S3 클라이언트를 lazy initialization으로 가져옵니다."""
    global _s3_client
    if _s3_client is not None:
        return _s3_client

    settings = get_settings()
    if not settings.s3_bucket_name:
        return None

    try:
        import aioboto3
        session = aioboto3.Session(
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
        )
        _s3_client = session
        return _s3_client
    except ImportError:
        logger.warning("aioboto3 not installed, S3 cold storage disabled")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize S3 client: {e}")
        return None


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
        self._settings = get_settings()

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

        # Try cold storage (S3) if not in warm storage
        s3_data = await self._retrieve_from_s3(hand_id)
        if s3_data:
            return s3_data

        return None

    async def upload_to_cold_storage(self, hand_id: str, hand_data: dict) -> bool:
        """Upload hand to S3 cold storage.

        Args:
            hand_id: Hand ID
            hand_data: Hand data to upload

        Returns:
            True if uploaded successfully
        """
        session = _get_s3_client()
        if not session or not self._settings.s3_bucket_name:
            return False

        try:
            # 날짜 기반 파티셔닝 (YYYY/MM/DD/hand_id.msgpack.gz)
            archived_at = hand_data.get("_archived_at", datetime.utcnow().isoformat())
            if isinstance(archived_at, str):
                dt = datetime.fromisoformat(archived_at.replace("Z", "+00:00"))
            else:
                dt = archived_at
            key = f"hands/{dt.year}/{dt.month:02d}/{dt.day:02d}/{hand_id}.msgpack.gz"

            compressed = self.compress_hand(hand_data)

            async with session.client(
                "s3",
                endpoint_url=self._settings.s3_endpoint_url,
            ) as s3:
                await s3.put_object(
                    Bucket=self._settings.s3_bucket_name,
                    Key=key,
                    Body=compressed,
                    ContentType="application/x-msgpack",
                    ContentEncoding="gzip",
                )

            logger.info(f"Uploaded hand {hand_id} to S3 ({len(compressed)} bytes)")
            return True

        except Exception as e:
            logger.error(f"Failed to upload hand {hand_id} to S3: {e}")
            return False

    async def _retrieve_from_s3(self, hand_id: str) -> Optional[dict]:
        """Retrieve hand from S3 cold storage.

        Args:
            hand_id: Hand ID to retrieve

        Returns:
            Hand data or None if not found
        """
        session = _get_s3_client()
        if not session or not self._settings.s3_bucket_name:
            return None

        try:
            async with session.client(
                "s3",
                endpoint_url=self._settings.s3_endpoint_url,
            ) as s3:
                # S3 객체 검색 (날짜 파티션을 모르므로 prefix 검색)
                paginator = s3.get_paginator("list_objects_v2")
                async for page in paginator.paginate(
                    Bucket=self._settings.s3_bucket_name,
                    Prefix="hands/",
                ):
                    for obj in page.get("Contents", []):
                        if hand_id in obj["Key"]:
                            response = await s3.get_object(
                                Bucket=self._settings.s3_bucket_name,
                                Key=obj["Key"],
                            )
                            body = await response["Body"].read()
                            return self.decompress_hand(body)

            return None

        except Exception as e:
            logger.error(f"Failed to retrieve hand {hand_id} from S3: {e}")
            return None

    async def migrate_to_cold_storage(self, hand_id: str) -> bool:
        """Migrate hand from warm (Redis) to cold (S3) storage.

        Args:
            hand_id: Hand ID to migrate

        Returns:
            True if migrated successfully
        """
        # Get from Redis
        if not self._redis:
            return False

        key = f"hand:archive:{hand_id}"
        compressed = await self._redis.get(key)
        if not compressed:
            return False

        # Decompress and upload to S3
        hand_data = self.decompress_hand(compressed)
        if await self.upload_to_cold_storage(hand_id, hand_data):
            # Delete from Redis after successful upload
            await self._redis.delete(key)
            logger.info(f"Migrated hand {hand_id} from Redis to S3")
            return True

        return False

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
