"""Tests for WebSocket event handlers."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio

from app.ws.connection import WebSocketConnection, ConnectionState
from app.ws.events import EventType
from app.ws.handlers.system import SystemHandler, create_connection_state_message
from app.ws.handlers.lobby import LobbyHandler, LOBBY_CHANNEL
from app.ws.handlers.table import TableHandler
from app.ws.handlers.chat import ChatHandler
from app.ws.manager import ConnectionManager
from app.ws.messages import MessageEnvelope
from tests.ws.conftest import MockWebSocket, MockRedis


class TestSystemHandler:
    """Tests for SystemHandler."""

    @pytest_asyncio.fixture
    async def handler(self) -> SystemHandler:
        """Create a system handler."""
        redis = MockRedis()
        manager = ConnectionManager(redis)
        await manager.start()
        yield SystemHandler(manager)
        await manager.stop()

    @pytest_asyncio.fixture
    async def connection(self) -> WebSocketConnection:
        """Create a test connection."""
        return WebSocketConnection(
            websocket=MockWebSocket(),
            user_id="user-1",
            session_id="session-1",
            connection_id=str(uuid4()),
            connected_at=datetime.utcnow(),
        )

    def test_handled_events(self, handler: SystemHandler):
        """Test handler handles PING and PONG events (bidirectional heartbeat)."""
        assert EventType.PING in handler.handled_events
        assert EventType.PONG in handler.handled_events  # 서버도 클라이언트 PONG 수신
        assert handler.can_handle(EventType.PING) is True
        assert handler.can_handle(EventType.PONG) is True

    @pytest.mark.asyncio
    async def test_ping_returns_pong(
        self,
        handler: SystemHandler,
        connection: WebSocketConnection,
    ):
        """Test PING event returns PONG response."""
        event = MessageEnvelope.create(
            event_type=EventType.PING,
            payload={},
            request_id="req-1",
            trace_id="trace-1",
        )

        response = await handler.handle(connection, event)

        assert response is not None
        assert response.type == EventType.PONG
        assert response.request_id == "req-1"
        assert response.trace_id == "trace-1"

    @pytest.mark.asyncio
    async def test_ping_updates_last_ping_at(
        self,
        handler: SystemHandler,
        connection: WebSocketConnection,
    ):
        """Test PING updates connection's last_ping_at."""
        assert connection.last_ping_at is None

        event = MessageEnvelope.create(
            event_type=EventType.PING,
            payload={},
        )

        await handler.handle(connection, event)

        assert connection.last_ping_at is not None


class TestConnectionStateMessage:
    """Tests for connection state message creation."""

    def test_create_connected_message(self):
        """Test creating CONNECTION_STATE(connected) message."""
        message = create_connection_state_message(
            state=ConnectionState.CONNECTED,
            user_id="user-1",
            session_id="session-1",
        )

        assert message.type == EventType.CONNECTION_STATE
        assert message.payload["state"] == "connected"
        assert message.payload["userId"] == "user-1"
        assert message.payload["sessionId"] == "session-1"

    def test_create_reconnecting_message(self):
        """Test creating CONNECTION_STATE(reconnecting) message."""
        message = create_connection_state_message(
            state=ConnectionState.RECONNECTING,
            user_id="user-1",
            session_id="session-1",
        )

        assert message.payload["state"] == "reconnecting"


class TestLobbyHandler:
    """Tests for LobbyHandler."""

    @pytest_asyncio.fixture
    async def manager(self) -> ConnectionManager:
        """Create connection manager."""
        redis = MockRedis()
        mgr = ConnectionManager(redis)
        await mgr.start()
        yield mgr
        await mgr.stop()

    @pytest_asyncio.fixture
    async def mock_db(self):
        """Create mock database session."""
        mock = AsyncMock()
        mock.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
        mock.commit = AsyncMock()
        mock.flush = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        return mock

    @pytest_asyncio.fixture
    async def handler(self, manager, mock_db) -> LobbyHandler:
        """Create lobby handler."""
        return LobbyHandler(manager, mock_db)

    @pytest_asyncio.fixture
    async def connection(self, manager) -> WebSocketConnection:
        """Create and register a test connection."""
        conn = WebSocketConnection(
            websocket=MockWebSocket(),
            user_id="user-1",
            session_id="session-1",
            connection_id=str(uuid4()),
            connected_at=datetime.utcnow(),
        )
        await manager.connect(conn)
        return conn

    def test_handled_events(self, handler: LobbyHandler):
        """Test handler handles lobby events."""
        assert EventType.SUBSCRIBE_LOBBY in handler.handled_events
        assert EventType.UNSUBSCRIBE_LOBBY in handler.handled_events
        assert EventType.ROOM_CREATE_REQUEST in handler.handled_events
        assert EventType.ROOM_JOIN_REQUEST in handler.handled_events

    @pytest.mark.asyncio
    async def test_subscribe_lobby_returns_snapshot(
        self,
        handler: LobbyHandler,
        connection: WebSocketConnection,
    ):
        """Test SUBSCRIBE_LOBBY returns LOBBY_SNAPSHOT."""
        event = MessageEnvelope.create(
            event_type=EventType.SUBSCRIBE_LOBBY,
            payload={},
            request_id="req-1",
        )

        response = await handler.handle(connection, event)

        assert response is not None
        assert response.type == EventType.LOBBY_SNAPSHOT
        assert response.request_id == "req-1"
        assert "rooms" in response.payload

    @pytest.mark.asyncio
    async def test_subscribe_lobby_adds_to_channel(
        self,
        handler: LobbyHandler,
        connection: WebSocketConnection,
        manager: ConnectionManager,
    ):
        """Test SUBSCRIBE_LOBBY adds connection to lobby channel."""
        event = MessageEnvelope.create(
            event_type=EventType.SUBSCRIBE_LOBBY,
            payload={},
        )

        await handler.handle(connection, event)

        assert LOBBY_CHANNEL in connection.subscribed_channels

    @pytest.mark.asyncio
    async def test_unsubscribe_lobby_removes_from_channel(
        self,
        handler: LobbyHandler,
        connection: WebSocketConnection,
        manager: ConnectionManager,
    ):
        """Test UNSUBSCRIBE_LOBBY removes from lobby channel."""
        # First subscribe
        await manager.subscribe(connection.connection_id, LOBBY_CHANNEL)

        event = MessageEnvelope.create(
            event_type=EventType.UNSUBSCRIBE_LOBBY,
            payload={},
        )

        response = await handler.handle(connection, event)

        assert response is None  # No response for unsubscribe
        assert LOBBY_CHANNEL not in connection.subscribed_channels


class TestTableHandler:
    """Tests for TableHandler."""

    @pytest_asyncio.fixture
    async def manager(self) -> ConnectionManager:
        """Create connection manager."""
        redis = MockRedis()
        mgr = ConnectionManager(redis)
        await mgr.start()
        yield mgr
        await mgr.stop()

    @pytest_asyncio.fixture
    async def mock_db(self):
        """Create mock database session."""
        mock = AsyncMock()
        mock.execute = AsyncMock()
        mock.commit = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        return mock

    @pytest_asyncio.fixture
    async def handler(self, manager, mock_db) -> TableHandler:
        """Create table handler."""
        return TableHandler(manager, mock_db)

    @pytest_asyncio.fixture
    async def connection(self, manager) -> WebSocketConnection:
        """Create and register a test connection."""
        conn = WebSocketConnection(
            websocket=MockWebSocket(),
            user_id="user-1",
            session_id="session-1",
            connection_id=str(uuid4()),
            connected_at=datetime.utcnow(),
        )
        await manager.connect(conn)
        return conn

    def test_handled_events(self, handler: TableHandler):
        """Test handler handles table events."""
        assert EventType.SUBSCRIBE_TABLE in handler.handled_events
        assert EventType.UNSUBSCRIBE_TABLE in handler.handled_events
        assert EventType.SEAT_REQUEST in handler.handled_events
        assert EventType.LEAVE_REQUEST in handler.handled_events

    @pytest.mark.asyncio
    async def test_subscribe_table_adds_to_channel(
        self,
        handler: TableHandler,
        connection: WebSocketConnection,
        manager: ConnectionManager,
        mock_db,
    ):
        """Test SUBSCRIBE_TABLE adds connection to table channel."""
        # Use valid UUID format for table_id (this will be used as room_id)
        table_id = str(uuid4())
        room_id = str(uuid4())

        # Create mock table with room
        mock_table = MagicMock()
        mock_table.room_id = room_id
        mock_table.seats = {}
        mock_table.state_version = 1
        mock_table.updated_at = None
        mock_room = MagicMock()
        mock_room.config = {"max_seats": 6, "small_blind": 10, "big_blind": 20}
        mock_room.name = "Test Room"
        mock_table.room = mock_room

        # Mock table query result - return mock_table
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_table
        mock_db.execute.return_value = mock_result

        event = MessageEnvelope.create(
            event_type=EventType.SUBSCRIBE_TABLE,
            payload={
                "tableId": table_id,
                "mode": "player",
            },
        )

        await handler.handle(connection, event)

        # Channel is based on room_id, not table_id
        assert f"table:{room_id}" in connection.subscribed_channels

    @pytest.mark.asyncio
    async def test_unsubscribe_table_removes_from_channel(
        self,
        handler: TableHandler,
        connection: WebSocketConnection,
        manager: ConnectionManager,
        mock_db,
    ):
        """Test UNSUBSCRIBE_TABLE removes from table channel."""
        # Use valid UUID format for table_id and room_id
        table_id = str(uuid4())
        room_id = str(uuid4())
        channel = f"table:{room_id}"

        # Create mock table
        mock_table = MagicMock()
        mock_table.room_id = room_id

        # Mock table query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_table
        mock_db.execute.return_value = mock_result

        # First subscribe using room_id based channel
        await manager.subscribe(connection.connection_id, channel)

        event = MessageEnvelope.create(
            event_type=EventType.UNSUBSCRIBE_TABLE,
            payload={"tableId": table_id},
        )

        response = await handler.handle(connection, event)

        assert response is None
        assert channel not in connection.subscribed_channels


class TestChatHandler:
    """Tests for ChatHandler."""

    @pytest_asyncio.fixture
    async def manager(self) -> ConnectionManager:
        """Create connection manager."""
        redis = MockRedis()
        mgr = ConnectionManager(redis)
        await mgr.start()
        yield mgr
        await mgr.stop()

    @pytest_asyncio.fixture
    async def mock_db(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest_asyncio.fixture
    async def handler(self, manager, mock_db) -> ChatHandler:
        """Create chat handler."""
        redis = MockRedis()
        return ChatHandler(manager, mock_db, redis)

    @pytest_asyncio.fixture
    async def connection(self, manager) -> WebSocketConnection:
        """Create and register a test connection."""
        conn = WebSocketConnection(
            websocket=MockWebSocket(),
            user_id="user-1",
            session_id="session-1",
            connection_id=str(uuid4()),
            connected_at=datetime.utcnow(),
        )
        await manager.connect(conn)
        await manager.subscribe(conn.connection_id, "table:123")
        return conn

    def test_handled_events(self, handler: ChatHandler):
        """Test handler handles chat events."""
        assert EventType.CHAT_MESSAGE in handler.handled_events

    @pytest.mark.asyncio
    async def test_chat_message_broadcasts_to_channel(
        self,
        handler: ChatHandler,
        connection: WebSocketConnection,
        manager: ConnectionManager,
    ):
        """Test CHAT_MESSAGE broadcasts to table channel."""
        # Note: connection is subscribed to "table:123", so tableId must be "123"
        event = MessageEnvelope.create(
            event_type=EventType.CHAT_MESSAGE,
            payload={
                "tableId": "123",  # Channel becomes "table:123"
                "message": "Hello, world!",
                "nickname": "Player1",
            },
        )

        response = await handler.handle(connection, event)

        # No direct response (message is broadcast)
        assert response is None

        # Check message was broadcast
        assert len(connection.websocket.sent_messages) == 1
        sent = connection.websocket.sent_messages[0]
        assert sent["type"] == EventType.CHAT_MESSAGE.value
        assert sent["payload"]["message"] == "Hello, world!"

    @pytest.mark.asyncio
    async def test_chat_message_truncates_long_messages(
        self,
        handler: ChatHandler,
        connection: WebSocketConnection,
    ):
        """Test long chat messages are truncated."""
        long_message = "x" * 1000  # 1000 characters

        event = MessageEnvelope.create(
            event_type=EventType.CHAT_MESSAGE,
            payload={
                "tableId": "123",  # Channel becomes "table:123"
                "message": long_message,
            },
        )

        await handler.handle(connection, event)

        sent = connection.websocket.sent_messages[0]
        assert len(sent["payload"]["message"]) == 500

    @pytest.mark.asyncio
    async def test_empty_chat_message_ignored(
        self,
        handler: ChatHandler,
        connection: WebSocketConnection,
    ):
        """Test empty chat messages are ignored."""
        event = MessageEnvelope.create(
            event_type=EventType.CHAT_MESSAGE,
            payload={
                "tableId": "table-123",
                "message": "   ",  # Whitespace only
            },
        )

        response = await handler.handle(connection, event)

        assert response is None
        assert len(connection.websocket.sent_messages) == 0
