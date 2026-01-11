"""WebSocket gateway endpoint.

Main WebSocket entry point per realtime-protocol-v1 spec section 2.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.db import get_db
from app.utils.redis_client import get_redis, redis_client
from app.utils.security import verify_access_token
from app.ws.connection import WebSocketConnection, ConnectionState
from app.ws.events import EventType, CLIENT_TO_SERVER_EVENTS
from app.ws.manager import ConnectionManager
from app.ws.messages import MessageEnvelope, create_error_message
from app.ws.handlers.system import SystemHandler, create_connection_state_message
from app.ws.handlers.lobby import LobbyHandler
from app.ws.handlers.table import TableHandler
from app.ws.handlers.action import ActionHandler
from app.ws.handlers.chat import ChatHandler

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])

# Global connection manager (initialized on startup)
_manager: ConnectionManager | None = None


async def get_manager() -> ConnectionManager:
    """Get or create the global connection manager."""
    global _manager
    if _manager is None:
        if redis_client is None:
            raise RuntimeError("Redis client not initialized")
        _manager = ConnectionManager(redis_client)
        await _manager.start()
    return _manager


async def shutdown_manager() -> None:
    """Shutdown the connection manager."""
    global _manager
    if _manager:
        await _manager.stop()
        _manager = None


class HandlerRegistry:
    """Registry for event handlers."""

    def __init__(
        self,
        manager: ConnectionManager,
        db: AsyncSession,
    ):
        self.manager = manager
        self.db = db

        # Initialize handlers
        self._system = SystemHandler(manager)
        self._lobby = LobbyHandler(manager, db)
        self._table = TableHandler(manager, db)
        self._action = ActionHandler(manager, db, redis_client) if redis_client else None
        self._chat = ChatHandler(manager, db, redis_client)

        # Build event -> handler mapping
        self._handlers: dict[EventType, Any] = {}
        self._register_handler(self._system)
        self._register_handler(self._lobby)
        self._register_handler(self._table)
        if self._action:
            self._register_handler(self._action)
        self._register_handler(self._chat)

    def _register_handler(self, handler: Any) -> None:
        """Register a handler for its events."""
        for event_type in handler.handled_events:
            self._handlers[event_type] = handler

    def get_handler(self, event_type: EventType) -> Any | None:
        """Get handler for an event type."""
        return self._handlers.get(event_type)


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
):
    """Main WebSocket endpoint per spec section 2.1.

    Connection flow:
    1. Client connects with token in query params
    2. Server validates token
    3. Server sends CONNECTION_STATE(connected)
    4. Client subscribes to channels
    5. Bidirectional message exchange
    """
    # 1. Authenticate via JWT token
    payload = verify_access_token(token)
    if not payload:
        await websocket.close(4001, "Invalid or expired token")
        return

    user_id = payload.get("sub")
    if not user_id or not str(user_id).strip():
        await websocket.close(4001, "Invalid token payload")
        return

    # 2. Accept connection
    await websocket.accept()

    # 3. Create connection object
    manager = await get_manager()
    connection_id = str(uuid4())
    session_id = payload.get("sid", str(uuid4()))

    conn = WebSocketConnection(
        websocket=websocket,
        user_id=user_id,
        session_id=session_id,
        connection_id=connection_id,
        connected_at=datetime.utcnow(),
    )

    # 4. Register connection
    await manager.connect(conn)

    # 5. Send CONNECTION_STATE(connected)
    welcome_message = create_connection_state_message(
        state=ConnectionState.CONNECTED,
        user_id=user_id,
        session_id=session_id,
    )
    await conn.send(welcome_message.to_dict())

    logger.info(f"WebSocket connected: user={user_id}, conn={connection_id}")

    # 6. Get database session for handlers
    from app.utils.db import async_session_factory

    async with async_session_factory() as db:
        # 7. Initialize handler registry
        registry = HandlerRegistry(manager, db)

        # 8. Message loop
        try:
            while True:
                data = await websocket.receive_json()

                try:
                    # Parse message
                    event = MessageEnvelope.from_dict(data)

                    # Validate event direction
                    if event.type not in CLIENT_TO_SERVER_EVENTS:
                        error_msg = create_error_message(
                            error_code="INVALID_EVENT_DIRECTION",
                            error_message=f"Event {event.type.value} cannot be sent by client",
                            request_id=event.request_id,
                            trace_id=event.trace_id,
                        )
                        await conn.send(error_msg.to_dict())
                        continue

                    # Get handler
                    handler = registry.get_handler(event.type)

                    if handler:
                        # Process event
                        response = await handler.handle(conn, event)
                        if response:
                            await conn.send(response.to_dict())
                    else:
                        # Unknown event type
                        error_msg = create_error_message(
                            error_code="UNKNOWN_EVENT",
                            error_message=f"Unknown event type: {event.type.value}",
                            request_id=event.request_id,
                            trace_id=event.trace_id,
                        )
                        await conn.send(error_msg.to_dict())

                except ValueError as e:
                    # Invalid message format
                    logger.warning(f"Invalid message format: {e}")
                    error_msg = create_error_message(
                        error_code="INVALID_MESSAGE",
                        error_message=f"Invalid message format: {e}",
                    )
                    await conn.send(error_msg.to_dict())

                except Exception as e:
                    # Handler error
                    logger.exception(f"Handler error: {e}")
                    error_msg = create_error_message(
                        error_code="HANDLER_ERROR",
                        error_message="Internal handler error",
                    )
                    await conn.send(error_msg.to_dict())

        except WebSocketDisconnect as e:
            logger.info(
                f"WebSocket disconnected: user={user_id}, conn={connection_id}, "
                f"code={e.code}"
            )

        except Exception as e:
            logger.exception(f"WebSocket error: {e}")

        finally:
            # Store state for potential reconnection
            await manager.store_user_state(
                user_id,
                {
                    "subscribed_channels": list(conn.subscribed_channels),
                    "last_seen_versions": conn.last_seen_versions,
                    "disconnected_at": datetime.utcnow().isoformat(),
                },
            )

            # Cleanup connection
            await manager.disconnect(connection_id)
            logger.info(f"WebSocket cleanup complete: conn={connection_id}")


@router.get("/ws/stats")
async def websocket_stats() -> dict[str, Any]:
    """Get WebSocket connection statistics (for monitoring)."""
    try:
        manager = await get_manager()
        return {
            "connections": manager.connection_count,
            "status": "running",
        }
    except Exception as e:
        return {
            "connections": 0,
            "status": "error",
            "error": str(e),
        }
