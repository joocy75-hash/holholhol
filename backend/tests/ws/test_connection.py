"""Tests for WebSocket connection management."""

import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio

from app.ws.connection import WebSocketConnection, ConnectionState
from app.ws.manager import ConnectionManager
from tests.ws.conftest import MockWebSocket, MockRedis


class TestWebSocketConnection:
    """Tests for WebSocketConnection class."""

    @pytest_asyncio.fixture
    async def connection(self) -> WebSocketConnection:
        """Create a test connection."""
        mock_ws = MockWebSocket()
        return WebSocketConnection(
            websocket=mock_ws,
            user_id="user-1",
            session_id="session-1",
            connection_id="conn-1",
            connected_at=datetime.utcnow(),
        )

    @pytest.mark.asyncio
    async def test_connection_initial_state(self, connection: WebSocketConnection):
        """Test connection has correct initial state."""
        assert connection.state == ConnectionState.CONNECTED
        assert connection.user_id == "user-1"
        assert connection.connection_id == "conn-1"
        assert connection.subscribed_channels == set()
        assert connection.last_ping_at is None

    @pytest.mark.asyncio
    async def test_send_message(self, connection: WebSocketConnection):
        """Test sending a message."""
        result = await connection.send({"type": "TEST", "data": "hello"})

        assert result is True
        assert len(connection.websocket.sent_messages) == 1
        assert connection.websocket.sent_messages[0]["type"] == "TEST"

    @pytest.mark.asyncio
    async def test_send_message_after_close(self, connection: WebSocketConnection):
        """Test sending fails after connection is closed."""
        await connection.close()

        result = await connection.send({"type": "TEST"})

        assert result is False

    @pytest.mark.asyncio
    async def test_update_ping(self, connection: WebSocketConnection):
        """Test ping timestamp update."""
        assert connection.last_ping_at is None

        connection.update_ping()

        assert connection.last_ping_at is not None
        assert connection.missed_pongs == 0

    @pytest.mark.asyncio
    async def test_subscription_tracking(self, connection: WebSocketConnection):
        """Test channel subscription tracking."""
        connection.subscribed_channels.add("lobby")
        connection.subscribed_channels.add("table:123")

        assert connection.is_subscribed("lobby") is True
        assert connection.is_subscribed("table:123") is True
        assert connection.is_subscribed("table:456") is False

    @pytest.mark.asyncio
    async def test_state_version_tracking(self, connection: WebSocketConnection):
        """Test state version tracking."""
        connection.update_state_version("table:123", 5)
        connection.update_state_version("table:123", 10)

        assert connection.last_seen_versions["table:123"] == 10


class TestConnectionManager:
    """Tests for ConnectionManager class."""

    @pytest_asyncio.fixture
    async def manager(self) -> ConnectionManager:
        """Create a connection manager with mock Redis."""
        redis = MockRedis()
        mgr = ConnectionManager(redis)
        await mgr.start()
        yield mgr
        await mgr.stop()

    @pytest_asyncio.fixture
    async def connection(self) -> WebSocketConnection:
        """Create a test connection."""
        mock_ws = MockWebSocket()
        return WebSocketConnection(
            websocket=mock_ws,
            user_id="user-1",
            session_id="session-1",
            connection_id=str(uuid4()),
            connected_at=datetime.utcnow(),
        )

    @pytest.mark.asyncio
    async def test_connect_registers_connection(
        self,
        manager: ConnectionManager,
        connection: WebSocketConnection,
    ):
        """Test that connect registers the connection."""
        await manager.connect(connection)

        assert manager.get_connection(connection.connection_id) is connection
        assert manager.connection_count == 1

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(
        self,
        manager: ConnectionManager,
        connection: WebSocketConnection,
    ):
        """Test that disconnect removes the connection."""
        await manager.connect(connection)
        await manager.disconnect(connection.connection_id)

        assert manager.get_connection(connection.connection_id) is None
        assert manager.connection_count == 0

    @pytest.mark.asyncio
    async def test_multiple_connections_per_user(
        self,
        manager: ConnectionManager,
    ):
        """Test multiple connections for the same user."""
        user_id = "user-1"

        conn1 = WebSocketConnection(
            websocket=MockWebSocket(),
            user_id=user_id,
            session_id="session-1",
            connection_id=str(uuid4()),
            connected_at=datetime.utcnow(),
        )
        conn2 = WebSocketConnection(
            websocket=MockWebSocket(),
            user_id=user_id,
            session_id="session-2",
            connection_id=str(uuid4()),
            connected_at=datetime.utcnow(),
        )

        await manager.connect(conn1)
        await manager.connect(conn2)

        connections = manager.get_user_connections(user_id)
        assert len(connections) == 2

    @pytest.mark.asyncio
    async def test_subscribe_to_channel(
        self,
        manager: ConnectionManager,
        connection: WebSocketConnection,
    ):
        """Test subscribing to a channel."""
        await manager.connect(connection)
        result = await manager.subscribe(connection.connection_id, "lobby")

        assert result is True
        assert "lobby" in connection.subscribed_channels
        assert connection.connection_id in manager.get_channel_subscribers("lobby")

    @pytest.mark.asyncio
    async def test_unsubscribe_from_channel(
        self,
        manager: ConnectionManager,
        connection: WebSocketConnection,
    ):
        """Test unsubscribing from a channel."""
        await manager.connect(connection)
        await manager.subscribe(connection.connection_id, "lobby")
        result = await manager.unsubscribe(connection.connection_id, "lobby")

        assert result is True
        assert "lobby" not in connection.subscribed_channels

    @pytest.mark.asyncio
    async def test_send_to_connection(
        self,
        manager: ConnectionManager,
        connection: WebSocketConnection,
    ):
        """Test sending to a specific connection."""
        await manager.connect(connection)
        result = await manager.send_to_connection(
            connection.connection_id,
            {"type": "TEST", "data": "hello"},
        )

        assert result is True
        assert len(connection.websocket.sent_messages) == 1

    @pytest.mark.asyncio
    async def test_send_to_user(
        self,
        manager: ConnectionManager,
    ):
        """Test sending to all user connections."""
        user_id = "user-1"

        conn1 = WebSocketConnection(
            websocket=MockWebSocket(),
            user_id=user_id,
            session_id="session-1",
            connection_id=str(uuid4()),
            connected_at=datetime.utcnow(),
        )
        conn2 = WebSocketConnection(
            websocket=MockWebSocket(),
            user_id=user_id,
            session_id="session-2",
            connection_id=str(uuid4()),
            connected_at=datetime.utcnow(),
        )

        await manager.connect(conn1)
        await manager.connect(conn2)

        count = await manager.send_to_user(user_id, {"type": "TEST"})

        assert count == 2
        assert len(conn1.websocket.sent_messages) == 1
        assert len(conn2.websocket.sent_messages) == 1

    @pytest.mark.asyncio
    async def test_broadcast_to_channel(
        self,
        manager: ConnectionManager,
    ):
        """Test broadcasting to all channel subscribers."""
        conn1 = WebSocketConnection(
            websocket=MockWebSocket(),
            user_id="user-1",
            session_id="session-1",
            connection_id=str(uuid4()),
            connected_at=datetime.utcnow(),
        )
        conn2 = WebSocketConnection(
            websocket=MockWebSocket(),
            user_id="user-2",
            session_id="session-2",
            connection_id=str(uuid4()),
            connected_at=datetime.utcnow(),
        )

        await manager.connect(conn1)
        await manager.connect(conn2)
        await manager.subscribe(conn1.connection_id, "table:123")
        await manager.subscribe(conn2.connection_id, "table:123")

        count = await manager.broadcast_to_channel(
            "table:123",
            {"type": "TABLE_UPDATE"},
        )

        assert count == 2

    @pytest.mark.asyncio
    async def test_broadcast_excludes_connection(
        self,
        manager: ConnectionManager,
    ):
        """Test broadcasting can exclude a connection."""
        conn1 = WebSocketConnection(
            websocket=MockWebSocket(),
            user_id="user-1",
            session_id="session-1",
            connection_id=str(uuid4()),
            connected_at=datetime.utcnow(),
        )
        conn2 = WebSocketConnection(
            websocket=MockWebSocket(),
            user_id="user-2",
            session_id="session-2",
            connection_id=str(uuid4()),
            connected_at=datetime.utcnow(),
        )

        await manager.connect(conn1)
        await manager.connect(conn2)
        await manager.subscribe(conn1.connection_id, "table:123")
        await manager.subscribe(conn2.connection_id, "table:123")

        count = await manager.broadcast_to_channel(
            "table:123",
            {"type": "TABLE_UPDATE"},
            exclude_connection=conn1.connection_id,
        )

        assert count == 1
        assert len(conn1.websocket.sent_messages) == 0
        assert len(conn2.websocket.sent_messages) == 1

    @pytest.mark.asyncio
    async def test_user_state_storage(
        self,
        manager: ConnectionManager,
    ):
        """Test storing and retrieving user state."""
        user_id = "user-1"
        state = {
            "subscribed_channels": ["lobby", "table:123"],
            "last_seen_versions": {"table:123": 10},
        }

        await manager.store_user_state(user_id, state)
        retrieved = await manager.get_user_state(user_id)

        assert retrieved is not None
        assert retrieved["subscribed_channels"] == ["lobby", "table:123"]

    @pytest.mark.asyncio
    async def test_get_previous_subscriptions(
        self,
        manager: ConnectionManager,
    ):
        """Test getting previous subscriptions for reconnection."""
        user_id = "user-1"
        state = {
            "subscribed_channels": ["lobby", "table:123"],
        }

        await manager.store_user_state(user_id, state)
        channels = await manager.get_previous_subscriptions(user_id)

        assert channels == ["lobby", "table:123"]

    @pytest.mark.asyncio
    async def test_disconnect_cleans_up_subscriptions(
        self,
        manager: ConnectionManager,
        connection: WebSocketConnection,
    ):
        """Test that disconnect cleans up all subscriptions."""
        await manager.connect(connection)
        await manager.subscribe(connection.connection_id, "lobby")
        await manager.subscribe(connection.connection_id, "table:123")

        await manager.disconnect(connection.connection_id)

        assert connection.connection_id not in manager.get_channel_subscribers("lobby")
        assert connection.connection_id not in manager.get_channel_subscribers("table:123")
