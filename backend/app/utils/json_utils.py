"""High-performance JSON utilities using orjson.

Phase 11: orjson integration for 3-10x JSON serialization speedup.

Usage:
    from app.utils.json_utils import json_dumps, json_loads, ORJSONResponse

    # Direct usage
    data = json_loads('{"key": "value"}')
    json_str = json_dumps({"key": "value"})

    # FastAPI response
    return ORJSONResponse(content={"status": "ok"})
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Any
from uuid import UUID

import orjson
from fastapi.responses import JSONResponse


def _default_serializer(obj: Any) -> Any:
    """Custom serializer for types not natively supported by orjson."""
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.decode("utf-8")
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def json_dumps(data: Any, *, pretty: bool = False) -> str:
    """Serialize data to JSON string using orjson.

    Args:
        data: Data to serialize
        pretty: If True, format with indentation

    Returns:
        JSON string

    Performance:
        3-10x faster than standard json.dumps()
    """
    options = orjson.OPT_UTC_Z | orjson.OPT_SERIALIZE_NUMPY
    if pretty:
        options |= orjson.OPT_INDENT_2

    return orjson.dumps(data, default=_default_serializer, option=options).decode("utf-8")


def json_dumps_bytes(data: Any) -> bytes:
    """Serialize data to JSON bytes using orjson.

    Args:
        data: Data to serialize

    Returns:
        JSON bytes (useful for WebSocket binary messages)
    """
    return orjson.dumps(
        data,
        default=_default_serializer,
        option=orjson.OPT_UTC_Z | orjson.OPT_SERIALIZE_NUMPY,
    )


def json_loads(data: str | bytes) -> Any:
    """Deserialize JSON string/bytes to Python object.

    Args:
        data: JSON string or bytes

    Returns:
        Deserialized Python object
    """
    return orjson.loads(data)


class ORJSONResponse(JSONResponse):
    """FastAPI response class using orjson for serialization.

    Usage:
        from app.utils.json_utils import ORJSONResponse

        @app.get("/", response_class=ORJSONResponse)
        async def root():
            return {"status": "ok"}
    """

    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        """Render content to JSON bytes."""
        return orjson.dumps(
            content,
            default=_default_serializer,
            option=orjson.OPT_UTC_Z | orjson.OPT_SERIALIZE_NUMPY,
        )
