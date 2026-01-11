"""WebSocket gateway module for real-time communication."""

from app.ws.events import EventType
from app.ws.messages import MessageEnvelope
from app.ws.connection import WebSocketConnection, ConnectionState
from app.ws.manager import ConnectionManager

__all__ = [
    "EventType",
    "MessageEnvelope",
    "WebSocketConnection",
    "ConnectionState",
    "ConnectionManager",
]
