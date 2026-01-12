"""WebSocket message serialization with MessagePack support.

Phase 10: Binary WebSocket protocol for 50-70% bandwidth reduction.

Features:
- MessagePack binary serialization
- JSON fallback for clients without binary support
- Protocol negotiation
- Compression for large messages
"""

import gzip
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

import msgpack

from app.utils.json_utils import json_dumps_bytes, json_loads


# Compression threshold (bytes)
COMPRESSION_THRESHOLD = 1024  # Compress messages larger than 1KB


class SerializationProtocol(str, Enum):
    """Supported serialization protocols."""
    JSON = "json"
    MSGPACK = "msgpack"


def _msgpack_encoder(obj: Any) -> Any:
    """Custom encoder for MessagePack serialization."""
    if isinstance(obj, datetime):
        return {"__datetime__": True, "value": obj.isoformat()}
    if isinstance(obj, date):
        return {"__date__": True, "value": obj.isoformat()}
    if isinstance(obj, Decimal):
        return {"__decimal__": True, "value": str(obj)}
    if isinstance(obj, UUID):
        return {"__uuid__": True, "value": str(obj)}
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return obj


def _msgpack_decoder(obj: Any) -> Any:
    """Custom decoder for MessagePack deserialization."""
    if isinstance(obj, dict):
        if obj.get("__datetime__"):
            return datetime.fromisoformat(obj["value"])
        if obj.get("__date__"):
            return date.fromisoformat(obj["value"])
        if obj.get("__decimal__"):
            return Decimal(obj["value"])
        if obj.get("__uuid__"):
            return UUID(obj["value"])
    return obj


class MessageSerializer:
    """WebSocket message serializer with protocol negotiation.

    Usage:
        serializer = MessageSerializer(protocol="msgpack")

        # Encode
        data = serializer.encode({"type": "TABLE_STATE", "data": {...}})

        # Decode
        message = serializer.decode(raw_data)
    """

    def __init__(self, protocol: SerializationProtocol = SerializationProtocol.JSON):
        """Initialize serializer.

        Args:
            protocol: Serialization protocol to use
        """
        self._protocol = protocol

    @property
    def protocol(self) -> SerializationProtocol:
        """Get current protocol."""
        return self._protocol

    @property
    def is_binary(self) -> bool:
        """Check if using binary protocol."""
        return self._protocol == SerializationProtocol.MSGPACK

    def encode(self, data: dict, *, compress: bool = True) -> bytes:
        """Encode data to bytes.

        Args:
            data: Data to encode
            compress: Whether to compress large messages

        Returns:
            Encoded bytes
        """
        if self._protocol == SerializationProtocol.MSGPACK:
            encoded = msgpack.packb(data, default=_msgpack_encoder, use_bin_type=True)
        else:
            encoded = json_dumps_bytes(data)

        # Compress if enabled and message is large
        if compress and len(encoded) > COMPRESSION_THRESHOLD:
            compressed = gzip.compress(encoded, compresslevel=6)
            # Only use compression if it actually reduces size
            if len(compressed) < len(encoded):
                # Prepend compression marker
                return b"\x1f\x8b" + compressed[2:]  # gzip magic bytes

        return encoded

    def decode(self, data: bytes | str) -> dict:
        """Decode bytes/string to dict.

        Args:
            data: Encoded data

        Returns:
            Decoded dict
        """
        # Handle string input (JSON from text WebSocket)
        if isinstance(data, str):
            return json_loads(data)

        # Check for gzip compression
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)

        if self._protocol == SerializationProtocol.MSGPACK:
            return msgpack.unpackb(
                data,
                raw=False,
                object_hook=_msgpack_decoder,
            )
        else:
            return json_loads(data)

    @staticmethod
    def negotiate_protocol(accept_binary: bool = False) -> "MessageSerializer":
        """Negotiate serialization protocol based on client capabilities.

        Args:
            accept_binary: Whether client accepts binary messages

        Returns:
            Configured MessageSerializer instance
        """
        if accept_binary:
            return MessageSerializer(SerializationProtocol.MSGPACK)
        return MessageSerializer(SerializationProtocol.JSON)


# =============================================================================
# Convenience Functions
# =============================================================================

def encode_msgpack(data: dict) -> bytes:
    """Encode data to MessagePack bytes.

    Args:
        data: Data to encode

    Returns:
        MessagePack bytes (50-70% smaller than JSON)
    """
    return msgpack.packb(data, default=_msgpack_encoder, use_bin_type=True)


def decode_msgpack(data: bytes) -> dict:
    """Decode MessagePack bytes to dict.

    Args:
        data: MessagePack bytes

    Returns:
        Decoded dict
    """
    return msgpack.unpackb(data, raw=False, object_hook=_msgpack_decoder)


def encode_json(data: dict) -> bytes:
    """Encode data to JSON bytes.

    Args:
        data: Data to encode

    Returns:
        JSON bytes
    """
    return json_dumps_bytes(data)


def decode_json(data: bytes | str) -> dict:
    """Decode JSON bytes/string to dict.

    Args:
        data: JSON bytes or string

    Returns:
        Decoded dict
    """
    return json_loads(data)


# =============================================================================
# Size Comparison Utility
# =============================================================================

def compare_serialization_sizes(data: dict) -> dict[str, int]:
    """Compare serialization sizes for debugging.

    Args:
        data: Data to serialize

    Returns:
        Dict with sizes for each format
    """
    json_size = len(encode_json(data))
    msgpack_size = len(encode_msgpack(data))
    msgpack_compressed = len(gzip.compress(encode_msgpack(data), compresslevel=6))

    return {
        "json_bytes": json_size,
        "msgpack_bytes": msgpack_size,
        "msgpack_gzip_bytes": msgpack_compressed,
        "msgpack_reduction_pct": round((1 - msgpack_size / json_size) * 100, 1),
        "msgpack_gzip_reduction_pct": round((1 - msgpack_compressed / json_size) * 100, 1),
    }
