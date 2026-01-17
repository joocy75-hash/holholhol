"""WebSocket gateway endpoint.

Main WebSocket entry point per realtime-protocol-v1 spec section 2.

Security Enhancement:
- Token is no longer passed via query parameter (visible in logs/history)
- Client sends AUTH message as first message after connection
- Server validates token within 5 seconds or closes connection
- Periodic token validation (every 5 minutes) to detect expired tokens
- Automatic disconnection when token expires with re-auth request
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.db import get_db
from app.utils.redis_client import get_redis, redis_client
from app.utils.security import verify_access_token, TokenError
from app.ws.connection import WebSocketConnection, ConnectionState
from app.ws.events import EventType, CLIENT_TO_SERVER_EVENTS
from app.ws.manager import ConnectionManager
from app.ws.messages import MessageEnvelope, create_error_message
from app.ws.handlers.system import SystemHandler, create_connection_state_message
from app.ws.handlers.lobby import LobbyHandler
from app.ws.handlers.table import TableHandler
from app.ws.handlers.action import ActionHandler
from app.ws.handlers.chat import ChatHandler
from app.services.room import RoomService
from app.middleware.maintenance import check_maintenance_mode_for_websocket

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])

# Global connection manager (initialized on startup)
_manager: ConnectionManager | None = None


async def get_manager() -> ConnectionManager:
    """Get or create the global connection manager."""
    global _manager
    if _manager is None:
        # Import here to get the updated redis_client after init_redis()
        from app.utils.redis_client import redis_client as current_redis_client
        if current_redis_client is None:
            raise RuntimeError("Redis client not initialized")
        _manager = ConnectionManager(current_redis_client)
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

        # Import here to get the updated redis_client after init_redis()
        from app.utils.redis_client import redis_client as current_redis_client

        # Initialize handlers
        self._system = SystemHandler(manager)
        self._lobby = LobbyHandler(manager, db)
        self._table = TableHandler(manager, db)
        # ActionHandler uses GameManager (in-memory) instead of DB
        self._action = ActionHandler(manager, current_redis_client)
        self._chat = ChatHandler(manager, db, current_redis_client)

        if not current_redis_client:
            logger.warning("Redis client not available, some features may not work")

        # Build event -> handler mapping
        self._handlers: dict[EventType, Any] = {}
        self._register_handler(self._system)
        self._register_handler(self._lobby)
        self._register_handler(self._table)
        self._register_handler(self._action)  # Always register action handler
        self._register_handler(self._chat)

    def _register_handler(self, handler: Any) -> None:
        """Register a handler for its events."""
        for event_type in handler.handled_events:
            self._handlers[event_type] = handler

    def get_handler(self, event_type: EventType) -> Any | None:
        """Get handler for an event type."""
        return self._handlers.get(event_type)


# Authentication timeout in seconds
AUTH_TIMEOUT_SECONDS = 5.0

# Token validation interval in seconds (5 minutes)
TOKEN_VALIDATION_INTERVAL_SECONDS = 300.0


def create_reauth_required_message() -> dict[str, Any]:
    """Create a REAUTH_REQUIRED message to notify client of token expiration."""
    return {
        "type": "REAUTH_REQUIRED",
        "payload": {
            "reason": "token_expired",
            "message": "Your session has expired. Please re-authenticate.",
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


# Heartbeat configuration
HEARTBEAT_INTERVAL_SECONDS = 30.0  # 서버 → 클라이언트 PING 전송 주기
HEARTBEAT_TIMEOUT_SECONDS = 60.0   # PONG 응답 대기 시간
MAX_MISSED_PONGS = 2               # 최대 허용 미응답 횟수


class HeartbeatManager:
    """서버 → 클라이언트 하트비트 관리.

    - 30초마다 PING 전송
    - 60초 내에 PONG 응답 확인
    - 2회 연속 미응답 시 연결 종료
    """

    def __init__(self, connection: WebSocketConnection):
        self.connection = connection
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """하트비트 루프 시작."""
        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self) -> None:
        """하트비트 루프 중지."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def record_pong(self) -> None:
        """클라이언트로부터 PONG 수신 시 호출."""
        self.connection.last_pong_at = datetime.utcnow()
        self.connection.missed_pongs = 0

    async def _heartbeat_loop(self) -> None:
        """주기적으로 PING 전송하고 응답 확인."""
        while self._running:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)

                if not self._running:
                    break

                # PING 전송 전에 이전 PONG 응답 확인
                if self.connection.last_ping_at is not None:
                    # 마지막 PING 이후 PONG이 없으면 미응답 카운트 증가
                    if (self.connection.last_pong_at is None or
                        self.connection.last_pong_at < self.connection.last_ping_at):
                        self.connection.missed_pongs += 1
                        logger.warning(
                            f"하트비트 미응답: user={self.connection.user_id}, "
                            f"conn={self.connection.connection_id}, "
                            f"missed={self.connection.missed_pongs}/{MAX_MISSED_PONGS}"
                        )

                        # 최대 미응답 횟수 초과 시 연결 종료
                        if self.connection.missed_pongs >= MAX_MISSED_PONGS:
                            logger.info(
                                f"하트비트 타임아웃으로 연결 종료: "
                                f"user={self.connection.user_id}, "
                                f"conn={self.connection.connection_id}"
                            )
                            try:
                                await self.connection.websocket.close(
                                    4003, "Heartbeat timeout - connection closed"
                                )
                            except Exception as e:
                                logger.warning(f"연결 종료 실패: {e}")
                            self._running = False
                            break

                # PING 전송
                ping_message = {
                    "type": "PING",
                    "payload": {},
                    "timestamp": datetime.utcnow().isoformat(),
                }

                try:
                    sent = await self.connection.send(ping_message)
                    if sent:
                        self.connection.last_ping_at = datetime.utcnow()
                    else:
                        logger.warning(
                            f"PING 전송 실패: user={self.connection.user_id}"
                        )
                except Exception as e:
                    logger.warning(f"PING 전송 에러: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"하트비트 루프 에러: {e}")


class TokenValidator:
    """Handles periodic token validation for WebSocket connections."""

    def __init__(self, token: str, connection: WebSocketConnection):
        self.token = token
        self.connection = connection
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start periodic token validation."""
        self._running = True
        self._task = asyncio.create_task(self._validation_loop())

    async def stop(self) -> None:
        """Stop periodic token validation."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _validation_loop(self) -> None:
        """Periodically validate the token."""
        while self._running:
            try:
                await asyncio.sleep(TOKEN_VALIDATION_INTERVAL_SECONDS)
                
                if not self._running:
                    break

                # Validate token
                is_valid = await self._validate_token()
                
                if not is_valid:
                    logger.info(
                        f"Token expired for user={self.connection.user_id}, "
                        f"conn={self.connection.connection_id}"
                    )
                    # Send re-auth required message
                    try:
                        await self.connection.send(create_reauth_required_message())
                    except Exception as e:
                        logger.warning(f"Failed to send reauth message: {e}")
                    
                    # Close connection with specific code
                    try:
                        await self.connection.websocket.close(
                            4002, "Token expired - re-authentication required"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to close websocket: {e}")
                    
                    self._running = False
                    break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Token validation error: {e}")
                # Continue validation loop on non-fatal errors

    async def _validate_token(self) -> bool:
        """Validate the stored token.
        
        Returns:
            True if token is still valid, False otherwise
        """
        try:
            payload = verify_access_token(self.token)
            return payload is not None
        except TokenError:
            # Token has expired
            return False
        except Exception as e:
            logger.warning(f"Unexpected token validation error: {e}")
            return False


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint per spec section 2.1.

    Security-enhanced connection flow:
    1. Client connects (no token in URL)
    2. Server checks maintenance mode
    3. Server accepts connection
    4. Client sends AUTH message with token (within 5 seconds)
    5. Server validates token
    6. Server sends CONNECTION_STATE(connected)
    7. Client subscribes to channels
    8. Bidirectional message exchange
    """
    # 0. Check maintenance mode before accepting connection
    from app.utils.redis_client import redis_client as current_redis_client

    is_maintenance, maintenance_message = await check_maintenance_mode_for_websocket(
        current_redis_client
    )

    if is_maintenance:
        logger.info("WebSocket 연결 거부: 점검 모드 활성화")
        # Close with code 1013 (Try Again Later) per RFC 6455
        await websocket.close(
            code=1013,
            reason=maintenance_message or "서버 점검 중입니다."
        )
        return

    # 1. Accept connection first (token will be sent via message)
    await websocket.accept()

    # 2. Wait for AUTH message (5 second timeout)
    try:
        auth_data = await asyncio.wait_for(
            websocket.receive_json(),
            timeout=AUTH_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning("WebSocket auth timeout - no auth message received")
        await websocket.close(4001, "Authentication timeout")
        return
    except Exception as e:
        logger.warning(f"WebSocket auth error: {e}")
        await websocket.close(4001, "Authentication error")
        return

    # 3. Validate auth message format
    if auth_data.get("type") != "AUTH":
        logger.warning("WebSocket invalid auth message type")
        await websocket.close(4001, "Expected AUTH message")
        return

    token = auth_data.get("payload", {}).get("token") or auth_data.get("token")
    if not token:
        logger.warning("WebSocket auth message missing token")
        await websocket.close(4001, "Missing token in AUTH message")
        return

    # 4. Validate JWT token
    try:
        payload = verify_access_token(token)
    except TokenError as e:
        logger.warning(f"WebSocket token error: {e.code}")
        await websocket.close(4001, "Invalid or expired token")
        return
    
    if not payload:
        logger.warning("WebSocket invalid or expired token")
        await websocket.close(4001, "Invalid or expired token")
        return

    user_id = payload.get("sub")
    if not user_id or not str(user_id).strip():
        logger.warning("WebSocket invalid token payload")
        await websocket.close(4001, "Invalid token payload")
        return

    # 5. Create connection object
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

    # 6. Register connection
    await manager.connect(conn)

    # 7. Start periodic token validation
    token_validator = TokenValidator(token, conn)
    await token_validator.start()

    # 7.5. Start heartbeat manager (서버 → 클라이언트 PING)
    heartbeat_manager = HeartbeatManager(conn)
    await heartbeat_manager.start()

    # 8. Send CONNECTION_STATE(connected)
    welcome_message = create_connection_state_message(
        state=ConnectionState.CONNECTED,
        user_id=user_id,
        session_id=session_id,
    )
    await conn.send(welcome_message.to_dict())

    logger.info(f"WebSocket connected: user={user_id}, conn={connection_id}")

    # 9. Get database session for handlers
    from app.utils.db import async_session_factory

    async with async_session_factory() as db:
        # 10. Initialize handler registry
        registry = HandlerRegistry(manager, db)

        # 11. Message loop
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
            # Stop token validation and heartbeat
            await token_validator.stop()
            await heartbeat_manager.stop()

            # Store state for potential reconnection
            await manager.store_user_state(
                user_id,
                {
                    "subscribed_channels": list(conn.subscribed_channels),
                    "last_seen_versions": conn.last_seen_versions,
                    "disconnected_at": datetime.utcnow().isoformat(),
                },
            )

            # Auto-leave all rooms when WebSocket disconnects
            # Use a new session for cleanup to ensure it commits properly
            try:
                async with async_session_factory() as cleanup_db:
                    room_service = RoomService(cleanup_db)
                    left_count = await room_service.leave_all_rooms(user_id)
                    if left_count > 0:
                        await cleanup_db.commit()
                        logger.info(
                            f"WebSocket disconnect: user={user_id} auto-left {left_count} rooms"
                        )
            except Exception as e:
                logger.warning(f"Failed to auto-leave rooms for user={user_id}: {e}")

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
