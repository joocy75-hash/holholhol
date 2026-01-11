"""System event handlers (PING/PONG, CONNECTION_STATE)."""

from datetime import datetime

from app.ws.connection import WebSocketConnection, ConnectionState
from app.ws.events import EventType
from app.ws.handlers.base import BaseHandler
from app.ws.messages import MessageEnvelope


class SystemHandler(BaseHandler):
    """Handles PING/PONG system events.

    Per spec section 2.3:
    - Client sends PING every 15 seconds
    - Server responds with PONG
    - Server closes connection if no PING for 60 seconds
    """

    @property
    def handled_events(self) -> tuple[EventType, ...]:
        return (EventType.PING,)

    async def handle(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope | None:
        if event.type == EventType.PING:
            # Update last ping timestamp
            conn.update_ping()

            # Respond with PONG
            return MessageEnvelope.create(
                event_type=EventType.PONG,
                payload={},
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

        return None


def create_connection_state_message(
    state: ConnectionState,
    user_id: str,
    session_id: str,
    trace_id: str | None = None,
) -> MessageEnvelope:
    """Create a CONNECTION_STATE message."""
    return MessageEnvelope.create(
        event_type=EventType.CONNECTION_STATE,
        payload={
            "state": state.value,
            "userId": user_id,
            "sessionId": session_id,
        },
        trace_id=trace_id,
    )
