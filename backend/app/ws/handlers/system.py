"""System event handlers (PING/PONG, CONNECTION_STATE, RECOVERY)."""

from datetime import datetime
import logging

from app.ws.connection import WebSocketConnection, ConnectionState
from app.ws.events import EventType
from app.ws.handlers.base import BaseHandler
from app.ws.messages import MessageEnvelope

logger = logging.getLogger(__name__)


class SystemHandler(BaseHandler):
    """Handles PING/PONG system events.

    양방향 하트비트 지원:
    - 클라이언트 → 서버: PING 전송, 서버가 PONG 응답
    - 서버 → 클라이언트: PING 전송 (30초 주기), 클라이언트가 PONG 응답
    - 2회 연속 미응답 시 연결 종료
    """

    @property
    def handled_events(self) -> tuple[EventType, ...]:
        return (EventType.PING, EventType.PONG, EventType.RECOVERY_REQUEST)

    async def handle(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope | None:
        if event.type == EventType.PING:
            return await self._handle_ping(conn, event)
        elif event.type == EventType.PONG:
            return await self._handle_pong(conn, event)
        elif event.type == EventType.RECOVERY_REQUEST:
            return await self._handle_recovery_request(conn, event)

        return None

    async def _handle_ping(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope:
        """Handle PING from client - update timestamp and respond with PONG."""
        conn.update_ping()

        return MessageEnvelope.create(
            event_type=EventType.PONG,
            payload={},
            request_id=event.request_id,
            trace_id=event.trace_id,
        )

    async def _handle_pong(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope | None:
        """Handle PONG from client - update heartbeat state.

        클라이언트가 서버 PING에 응답한 PONG 처리.
        missed_pongs 카운터를 리셋하여 연결 유지.
        """
        conn.last_pong_at = datetime.utcnow()
        conn.missed_pongs = 0

        logger.debug(
            f"PONG received from user={conn.user_id}, conn={conn.connection_id}"
        )

        # PONG에 대한 응답은 필요 없음
        return None

    async def _handle_recovery_request(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope:
        """Handle RECOVERY_REQUEST - restore client state after reconnection.

        Payload:
        - tableId: Optional table ID to recover state for
        - lastStateVersion: Client's last known state version
        - lastActionId: Client's last processed action ID
        """
        payload = event.payload or {}
        table_id = payload.get("tableId")
        last_state_version = payload.get("lastStateVersion", 0)
        last_action_id = payload.get("lastActionId")

        logger.info(
            f"Recovery request from user {conn.user_id}: "
            f"tableId={table_id}, lastStateVersion={last_state_version}"
        )

        try:
            # If no table_id specified, just acknowledge the recovery
            if not table_id:
                return MessageEnvelope.create(
                    event_type=EventType.RECOVERY_RESPONSE,
                    payload={
                        "success": True,
                        "message": "No table state to recover",
                    },
                    request_id=event.request_id,
                    trace_id=event.trace_id,
                )

            # Get table state from connection manager
            from app.ws.manager import connection_manager

            # Check if user was subscribed to this table
            table_state = await connection_manager.get_table_state(table_id)

            if not table_state:
                return MessageEnvelope.create(
                    event_type=EventType.RECOVERY_RESPONSE,
                    payload={
                        "success": False,
                        "errorMessage": "Table not found or inactive",
                    },
                    request_id=event.request_id,
                    trace_id=event.trace_id,
                )

            current_version = table_state.get("stateVersion", 0)

            # If client is up to date, no recovery needed
            if last_state_version >= current_version:
                return MessageEnvelope.create(
                    event_type=EventType.RECOVERY_RESPONSE,
                    payload={
                        "success": True,
                        "message": "State is up to date",
                        "stateVersion": current_version,
                    },
                    request_id=event.request_id,
                    trace_id=event.trace_id,
                )

            # Re-subscribe user to table
            await connection_manager.subscribe_to_table(conn.connection_id, table_id)

            # Send full snapshot for recovery
            return MessageEnvelope.create(
                event_type=EventType.RECOVERY_RESPONSE,
                payload={
                    "success": True,
                    "recoveredState": table_state,
                    "stateVersion": current_version,
                    "message": "State recovered successfully",
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

        except Exception as e:
            logger.error(f"Recovery request failed: {e}")
            return MessageEnvelope.create(
                event_type=EventType.RECOVERY_RESPONSE,
                payload={
                    "success": False,
                    "errorMessage": "Recovery failed due to server error",
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )


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
