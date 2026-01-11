"""Chat event handlers."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.ws.connection import WebSocketConnection
from app.ws.events import EventType
from app.ws.handlers.base import BaseHandler
from app.ws.messages import MessageEnvelope

if TYPE_CHECKING:
    from app.ws.manager import ConnectionManager

logger = logging.getLogger(__name__)

# Chat history settings
CHAT_HISTORY_LIMIT = 50
CHAT_MESSAGE_TTL = 3600  # 1 hour


class ChatHandler(BaseHandler):
    """Handles chat message events.

    Events:
    - CHAT_MESSAGE: Send/receive chat messages

    Also broadcasts:
    - CHAT_HISTORY: Historical messages on subscription
    """

    def __init__(
        self,
        manager: "ConnectionManager",
        db: AsyncSession,
        redis: Redis | None = None,
    ):
        super().__init__(manager)
        self.db = db
        self.redis = redis

    @property
    def handled_events(self) -> tuple[EventType, ...]:
        return (EventType.CHAT_MESSAGE,)

    async def handle(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope | None:
        if event.type == EventType.CHAT_MESSAGE:
            return await self._handle_chat_message(conn, event)
        return None

    async def _handle_chat_message(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope | None:
        """Handle CHAT_MESSAGE event."""
        payload = event.payload
        table_id = payload.get("tableId")
        message_text = payload.get("message", "").strip()

        # Validate message
        if not message_text:
            return None

        if len(message_text) > 500:
            message_text = message_text[:500]

        # Build chat message
        # Note: Ignore client-provided nickname to prevent impersonation
        # In production, fetch actual nickname from user profile
        chat_message = {
            "messageId": str(uuid4()),
            "tableId": table_id,
            "userId": conn.user_id,
            "nickname": f"User-{conn.user_id[:8]}",  # Server-generated nickname
            "message": message_text,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Store in Redis if available
        if self.redis and table_id:
            await self._store_chat_message(table_id, chat_message)

        # Broadcast to table channel
        if table_id:
            channel = f"table:{table_id}"
            broadcast_message = MessageEnvelope.create(
                event_type=EventType.CHAT_MESSAGE,
                payload=chat_message,
            )
            await self.manager.broadcast_to_channel(channel, broadcast_message.to_dict())

        # No direct response needed (message is broadcast)
        return None

    async def _store_chat_message(
        self,
        table_id: str,
        message: dict[str, Any],
    ) -> None:
        """Store chat message in Redis for history."""
        if not self.redis:
            return

        import json

        key = f"chat:history:{table_id}"

        # Add to list (newest first)
        await self.redis.lpush(key, json.dumps(message))

        # Trim to limit
        await self.redis.ltrim(key, 0, CHAT_HISTORY_LIMIT - 1)

        # Set TTL
        await self.redis.expire(key, CHAT_MESSAGE_TTL)

    async def get_chat_history(
        self,
        table_id: str,
        limit: int = CHAT_HISTORY_LIMIT,
    ) -> list[dict[str, Any]]:
        """Get chat history for a table."""
        if not self.redis:
            return []

        import json

        key = f"chat:history:{table_id}"
        messages = await self.redis.lrange(key, 0, limit - 1)

        return [json.loads(m) for m in messages]


async def send_chat_history(
    manager: "ConnectionManager",
    conn: WebSocketConnection,
    chat_handler: ChatHandler,
    table_id: str,
) -> None:
    """Send chat history to a newly subscribed connection."""
    history = await chat_handler.get_chat_history(table_id)

    if history:
        message = MessageEnvelope.create(
            event_type=EventType.CHAT_HISTORY,
            payload={
                "tableId": table_id,
                "messages": history,
            },
        )
        await conn.send(message.to_dict())
