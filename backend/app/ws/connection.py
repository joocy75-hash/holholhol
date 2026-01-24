"""WebSocket connection model."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionState(str, Enum):
    """Connection states per spec section 5.1."""

    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    RECOVERED = "recovered"
    DISCONNECTED = "disconnected"


@dataclass
class WebSocketConnection:
    """Represents a single WebSocket connection."""

    websocket: WebSocket
    user_id: str
    session_id: str
    connection_id: str
    connected_at: datetime
    state: ConnectionState = ConnectionState.CONNECTED

    # Channel subscriptions
    subscribed_channels: set[str] = field(default_factory=set)

    # Heartbeat tracking
    last_ping_at: datetime | None = None
    last_pong_at: datetime | None = None
    missed_pongs: int = 0

    # State recovery - track last seen stateVersion per channel
    last_seen_versions: dict[str, int] = field(default_factory=dict)

    async def send(self, message: dict[str, Any]) -> bool:
        """Send message to client. Returns False if failed."""
        try:
            await self.websocket.send_json(message)
            return True
        except Exception as e:
            logger.warning(f"Failed to send message to {self.connection_id}: {e}")
            return False

    async def close(self, code: int = 1000, reason: str = "") -> None:
        """Close the connection."""
        try:
            self.state = ConnectionState.DISCONNECTED
            await self.websocket.close(code, reason)
        except Exception as e:
            logger.debug(f"Error closing connection {self.connection_id}: {e}")

    def update_ping(self) -> None:
        """Update last ping timestamp."""
        self.last_ping_at = datetime.now(timezone.utc)
        self.missed_pongs = 0

    def update_state_version(self, channel: str, version: int) -> None:
        """Update last seen state version for a channel."""
        self.last_seen_versions[channel] = version

    def is_subscribed(self, channel: str) -> bool:
        """Check if connection is subscribed to a channel."""
        return channel in self.subscribed_channels
