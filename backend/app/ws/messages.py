"""Message envelope schemas per realtime-protocol-v1 spec section 3."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.ws.events import EventType


@dataclass(frozen=True)
class MessageEnvelope:
    """Standard message envelope per spec section 3."""

    type: EventType
    ts: int  # Unix timestamp in milliseconds
    trace_id: str
    payload: dict[str, Any]
    version: str = "v1"
    request_id: str | None = None

    @classmethod
    def create(
        cls,
        event_type: EventType,
        payload: dict[str, Any],
        request_id: str | None = None,
        trace_id: str | None = None,
    ) -> MessageEnvelope:
        """Factory method to create a new message envelope."""
        return cls(
            type=event_type,
            ts=int(datetime.utcnow().timestamp() * 1000),
            trace_id=trace_id or str(uuid.uuid4()),
            payload=payload,
            request_id=request_id,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MessageEnvelope:
        """Parse incoming message to MessageEnvelope."""
        return cls(
            type=EventType(data["type"]),
            ts=data.get("ts", int(datetime.utcnow().timestamp() * 1000)),
            trace_id=data.get("traceId", str(uuid.uuid4())),
            payload=data.get("payload", {}),
            version=data.get("version", "v1"),
            request_id=data.get("requestId"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        result = {
            "type": self.type.value,
            "ts": self.ts,
            "traceId": self.trace_id,
            "payload": self.payload,
            "version": self.version,
        }
        if self.request_id:
            result["requestId"] = self.request_id
        return result


@dataclass
class ErrorPayload:
    """Error response payload per spec section 5.9."""

    error_code: str
    error_message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "errorCode": self.error_code,
            "errorMessage": self.error_message,
            "details": self.details,
        }


def create_error_message(
    error_code: str,
    error_message: str,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
    trace_id: str | None = None,
) -> MessageEnvelope:
    """Helper to create an ERROR message envelope."""
    return MessageEnvelope.create(
        event_type=EventType.ERROR,
        payload=ErrorPayload(
            error_code=error_code,
            error_message=error_message,
            details=details or {},
        ).to_dict(),
        request_id=request_id,
        trace_id=trace_id,
    )
