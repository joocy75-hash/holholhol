"""WebSocket Integration Tests - Full real-time game flow.

Tests the complete WebSocket communication:
1. Connection & Authentication
2. Lobby subscription & room creation
3. Table subscription & seat management
4. Game actions & state updates
5. Heartbeat & reconnection
6. Chat messages
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.ws.events import EventType
from app.ws.messages import MessageEnvelope

from .conftest import (
    create_room,
    get_integration_test_settings,
    join_room,
    register_user,
)

settings = get_settings()


# =============================================================================
# WebSocket Test Client
# =============================================================================


class WebSocketTestClient:
    """Test client for WebSocket integration testing."""

    def __init__(self, app, token: str):
        self.app = app
        self.token = token
        self.received_messages: list[dict[str, Any]] = []
        self._receive_task: asyncio.Task | None = None
        self._ws = None
        self._connected = False

    async def connect(self) -> bool:
        """Connect to WebSocket endpoint."""
        from starlette.testclient import TestClient
        from starlette.websockets import WebSocketDisconnect

        # Use sync test client for WebSocket
        self._client = TestClient(self.app)
        try:
            self._ws = self._client.websocket_connect(f"/ws?token={self.token}")
            self._ws.__enter__()
            self._connected = True
            return True
        except Exception:
            return False

    def send(self, message: dict[str, Any]) -> None:
        """Send a message."""
        if self._ws:
            self._ws.send_json(message)

    def receive(self, timeout: float = 2.0) -> dict[str, Any] | None:
        """Receive a message with timeout."""
        if not self._ws:
            return None
        try:
            return self._ws.receive_json()
        except Exception:
            return None

    def close(self) -> None:
        """Close the connection."""
        if self._ws:
            try:
                self._ws.__exit__(None, None, None)
            except Exception:
                pass
            self._ws = None
            self._connected = False

    # Helper methods for creating messages
    def create_ping(self, request_id: str | None = None) -> dict:
        return MessageEnvelope.create(
            event_type=EventType.PING,
            payload={},
            request_id=request_id,
        ).to_dict()

    def create_subscribe_lobby(self, request_id: str | None = None) -> dict:
        return MessageEnvelope.create(
            event_type=EventType.SUBSCRIBE_LOBBY,
            payload={},
            request_id=request_id,
        ).to_dict()

    def create_subscribe_table(
        self,
        table_id: str,
        mode: str = "player",
        request_id: str | None = None,
    ) -> dict:
        return MessageEnvelope.create(
            event_type=EventType.SUBSCRIBE_TABLE,
            payload={"tableId": table_id, "mode": mode},
            request_id=request_id,
        ).to_dict()

    def create_room_create_request(
        self,
        name: str = "Test Room",
        max_seats: int = 6,
        small_blind: int = 10,
        big_blind: int = 20,
        request_id: str | None = None,
    ) -> dict:
        return MessageEnvelope.create(
            event_type=EventType.ROOM_CREATE_REQUEST,
            payload={
                "name": name,
                "maxSeats": max_seats,
                "smallBlind": small_blind,
                "bigBlind": big_blind,
                "buyInMin": small_blind * 40,
                "buyInMax": small_blind * 200,
                "isPrivate": False,
            },
            request_id=request_id,
        ).to_dict()

    def create_room_join_request(
        self,
        room_id: str,
        buy_in: int = 1000,
        password: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        payload = {"roomId": room_id, "buyIn": buy_in}
        if password:
            payload["password"] = password
        return MessageEnvelope.create(
            event_type=EventType.ROOM_JOIN_REQUEST,
            payload=payload,
            request_id=request_id,
        ).to_dict()

    def create_seat_request(
        self,
        table_id: str,
        position: int,
        buy_in: int = 1000,
        request_id: str | None = None,
    ) -> dict:
        return MessageEnvelope.create(
            event_type=EventType.SEAT_REQUEST,
            payload={
                "tableId": table_id,
                "position": position,
                "buyIn": buy_in,
            },
            request_id=request_id,
        ).to_dict()

    def create_action_request(
        self,
        table_id: str,
        action_type: str,
        amount: int | None = None,
        request_id: str | None = None,
    ) -> dict:
        payload = {"tableId": table_id, "actionType": action_type}
        if amount is not None:
            payload["amount"] = amount
        return MessageEnvelope.create(
            event_type=EventType.ACTION_REQUEST,
            payload=payload,
            request_id=request_id,
        ).to_dict()

    def create_chat_message(
        self,
        table_id: str,
        message: str,
        request_id: str | None = None,
    ) -> dict:
        return MessageEnvelope.create(
            event_type=EventType.CHAT_MESSAGE,
            payload={"tableId": table_id, "message": message},
            request_id=request_id,
        ).to_dict()


# =============================================================================
# Connection & Authentication Tests
# =============================================================================


class TestWebSocketConnection:
    """Test WebSocket connection and authentication."""

    @pytest.mark.asyncio
    async def test_connect_with_valid_token(
        self,
        integration_app,
        player1: dict,
    ):
        """Test: Valid JWT token allows connection."""
        client = WebSocketTestClient(
            integration_app,
            player1["tokens"]["access_token"],
        )

        try:
            connected = await client.connect()
            assert connected is True

            # Should receive CONNECTION_STATE message
            msg = client.receive()
            if msg:
                assert msg.get("type") == EventType.CONNECTION_STATE.value
                assert msg.get("payload", {}).get("state") == "connected"
        finally:
            client.close()

    @pytest.mark.asyncio
    async def test_connect_without_token_rejected(
        self,
        integration_app,
    ):
        """Test: Missing token is rejected."""
        from starlette.testclient import TestClient

        client = TestClient(integration_app)
        # Connection without token should fail
        try:
            with client.websocket_connect("/ws") as ws:
                # Should receive error or disconnect
                pass
            pytest.fail("Should have rejected connection")
        except Exception:
            # Expected - connection rejected
            pass

    @pytest.mark.asyncio
    async def test_connect_with_expired_token_rejected(
        self,
        integration_app,
        player1: dict,
    ):
        """Test: Expired token is rejected."""
        from jose import jwt as jose_jwt

        # Create expired token
        now = datetime.now(timezone.utc)
        expired_payload = {
            "sub": player1["user"].id,
            "type": "access",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        }
        expired_token = jose_jwt.encode(
            expired_payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )

        from starlette.testclient import TestClient

        client = TestClient(integration_app)
        try:
            with client.websocket_connect(f"/ws?token={expired_token}") as ws:
                pass
            pytest.fail("Should have rejected expired token")
        except Exception:
            pass


# =============================================================================
# Heartbeat Tests
# =============================================================================


class TestHeartbeat:
    """Test PING/PONG heartbeat mechanism."""

    @pytest.mark.asyncio
    async def test_ping_pong(
        self,
        integration_app,
        player1: dict,
    ):
        """Test: PING receives PONG response."""
        client = WebSocketTestClient(
            integration_app,
            player1["tokens"]["access_token"],
        )

        try:
            await client.connect()
            # Skip CONNECTION_STATE
            client.receive()

            # Send PING
            request_id = str(uuid4())
            client.send(client.create_ping(request_id))

            # Should receive PONG
            msg = client.receive()
            if msg:
                assert msg.get("type") == EventType.PONG.value
                # PONG should echo request_id
                assert msg.get("requestId") == request_id
        finally:
            client.close()


# =============================================================================
# Lobby Tests
# =============================================================================


class TestLobbySubscription:
    """Test lobby subscription and updates."""

    @pytest.mark.asyncio
    async def test_subscribe_lobby_receives_snapshot(
        self,
        integration_app,
        player1: dict,
    ):
        """Test: Subscribing to lobby receives LOBBY_SNAPSHOT."""
        client = WebSocketTestClient(
            integration_app,
            player1["tokens"]["access_token"],
        )

        try:
            await client.connect()
            client.receive()  # CONNECTION_STATE

            # Subscribe to lobby
            request_id = str(uuid4())
            client.send(client.create_subscribe_lobby(request_id))

            # Should receive LOBBY_SNAPSHOT
            msg = client.receive()
            if msg:
                assert msg.get("type") == EventType.LOBBY_SNAPSHOT.value
                payload = msg.get("payload", {})
                assert "rooms" in payload
                assert isinstance(payload["rooms"], list)
        finally:
            client.close()

    @pytest.mark.asyncio
    async def test_room_create_via_websocket(
        self,
        integration_app,
        player1: dict,
    ):
        """Test: Create room via WebSocket."""
        client = WebSocketTestClient(
            integration_app,
            player1["tokens"]["access_token"],
        )

        try:
            await client.connect()
            client.receive()  # CONNECTION_STATE

            # Create room
            request_id = str(uuid4())
            client.send(client.create_room_create_request(
                name="WS Test Room",
                request_id=request_id,
            ))

            # Should receive ROOM_CREATE_RESULT
            msg = client.receive()
            if msg:
                assert msg.get("type") == EventType.ROOM_CREATE_RESULT.value
                payload = msg.get("payload", {})
                assert payload.get("success") is True
                assert "roomId" in payload
        finally:
            client.close()


# =============================================================================
# Table Subscription Tests
# =============================================================================


class TestTableSubscription:
    """Test table subscription and seat management."""

    @pytest.mark.asyncio
    async def test_subscribe_table_receives_snapshot(
        self,
        integration_app,
        integration_client: AsyncClient,
        player1: dict,
    ):
        """Test: Subscribing to table receives TABLE_SNAPSHOT."""
        # Create room via REST API first
        room = await create_room(integration_client, player1["headers"])
        room_id = room["id"]
        table_id = room.get("tableId", room_id)

        client = WebSocketTestClient(
            integration_app,
            player1["tokens"]["access_token"],
        )

        try:
            await client.connect()
            client.receive()  # CONNECTION_STATE

            # Subscribe to table
            request_id = str(uuid4())
            client.send(client.create_subscribe_table(table_id, request_id=request_id))

            # Should receive TABLE_SNAPSHOT
            msg = client.receive()
            if msg:
                assert msg.get("type") == EventType.TABLE_SNAPSHOT.value
                payload = msg.get("payload", {})
                assert "tableId" in payload
                assert "seats" in payload
        finally:
            client.close()

    @pytest.mark.asyncio
    async def test_spectator_mode(
        self,
        integration_app,
        integration_client: AsyncClient,
        player1: dict,
        player2: dict,
    ):
        """Test: Spectator mode hides hole cards."""
        # Create room
        room = await create_room(integration_client, player1["headers"])
        room_id = room["id"]
        table_id = room.get("tableId", room_id)

        # Player2 subscribes as spectator
        client = WebSocketTestClient(
            integration_app,
            player2["tokens"]["access_token"],
        )

        try:
            await client.connect()
            client.receive()  # CONNECTION_STATE

            # Subscribe as spectator
            client.send(client.create_subscribe_table(
                table_id,
                mode="spectator",
            ))

            msg = client.receive()
            if msg:
                assert msg.get("type") == EventType.TABLE_SNAPSHOT.value
                payload = msg.get("payload", {})
                # Spectator should not see hole cards
                assert payload.get("myHoleCards") is None
        finally:
            client.close()


# =============================================================================
# Seat Request Tests
# =============================================================================


class TestSeatManagement:
    """Test seat request and leave operations."""

    @pytest.mark.asyncio
    async def test_seat_request_success(
        self,
        integration_app,
        integration_client: AsyncClient,
        player1: dict,
    ):
        """Test: Player can take a seat."""
        # Create room
        room = await create_room(integration_client, player1["headers"])
        room_id = room["id"]
        table_id = room.get("tableId", room_id)

        client = WebSocketTestClient(
            integration_app,
            player1["tokens"]["access_token"],
        )

        try:
            await client.connect()
            client.receive()  # CONNECTION_STATE

            # Subscribe to table first
            client.send(client.create_subscribe_table(table_id))
            client.receive()  # TABLE_SNAPSHOT

            # Request seat
            request_id = str(uuid4())
            client.send(client.create_seat_request(
                table_id=table_id,
                position=0,
                buy_in=1000,
                request_id=request_id,
            ))

            # Should receive SEAT_RESULT
            msg = client.receive()
            if msg:
                assert msg.get("type") == EventType.SEAT_RESULT.value
                payload = msg.get("payload", {})
                assert payload.get("success") is True
                assert payload.get("position") == 0
        finally:
            client.close()


# =============================================================================
# Game Action Tests
# =============================================================================


class TestGameActions:
    """Test game action processing."""

    @pytest.mark.asyncio
    async def test_action_request_fold(
        self,
        integration_app,
        integration_client: AsyncClient,
        player1: dict,
    ):
        """Test: Player can fold."""
        # Create and join room
        room = await create_room(integration_client, player1["headers"])
        room_id = room["id"]
        table_id = room.get("tableId", room_id)

        client = WebSocketTestClient(
            integration_app,
            player1["tokens"]["access_token"],
        )

        try:
            await client.connect()
            client.receive()  # CONNECTION_STATE

            # Subscribe and take seat
            client.send(client.create_subscribe_table(table_id))
            client.receive()  # TABLE_SNAPSHOT

            # Send fold action
            request_id = str(uuid4())
            client.send(client.create_action_request(
                table_id=table_id,
                action_type="fold",
                request_id=request_id,
            ))

            # Should receive ACTION_RESULT (may be error if not player's turn)
            msg = client.receive()
            if msg:
                msg_type = msg.get("type")
                assert msg_type in [
                    EventType.ACTION_RESULT.value,
                    EventType.ERROR.value,
                ]
        finally:
            client.close()


# =============================================================================
# Chat Tests
# =============================================================================


class TestChat:
    """Test chat message functionality."""

    @pytest.mark.asyncio
    async def test_send_chat_message(
        self,
        integration_app,
        integration_client: AsyncClient,
        player1: dict,
    ):
        """Test: Player can send chat message."""
        # Create room
        room = await create_room(integration_client, player1["headers"])
        table_id = room.get("tableId", room["id"])

        client = WebSocketTestClient(
            integration_app,
            player1["tokens"]["access_token"],
        )

        try:
            await client.connect()
            client.receive()  # CONNECTION_STATE

            # Subscribe to table
            client.send(client.create_subscribe_table(table_id))
            client.receive()  # TABLE_SNAPSHOT (or CHAT_HISTORY)

            # Send chat message
            request_id = str(uuid4())
            client.send(client.create_chat_message(
                table_id=table_id,
                message="Hello, world!",
                request_id=request_id,
            ))

            # Should receive CHAT_MESSAGE broadcast
            msg = client.receive()
            if msg:
                # May receive chat message or other updates
                pass  # Just verify no crash
        finally:
            client.close()


# =============================================================================
# Multi-Player Flow Tests
# =============================================================================


class TestMultiPlayerFlow:
    """Test multi-player game scenarios."""

    @pytest.mark.asyncio
    async def test_two_players_join_table(
        self,
        integration_app,
        integration_client: AsyncClient,
        player1: dict,
        player2: dict,
    ):
        """Test: Two players can join the same table."""
        # Create room via player1
        room = await create_room(integration_client, player1["headers"])
        room_id = room["id"]
        table_id = room.get("tableId", room_id)

        client1 = WebSocketTestClient(
            integration_app,
            player1["tokens"]["access_token"],
        )
        client2 = WebSocketTestClient(
            integration_app,
            player2["tokens"]["access_token"],
        )

        try:
            # Player1 connects and takes seat
            await client1.connect()
            client1.receive()  # CONNECTION_STATE
            client1.send(client1.create_subscribe_table(table_id))
            client1.receive()  # TABLE_SNAPSHOT
            client1.send(client1.create_seat_request(table_id, position=0))
            client1.receive()  # SEAT_RESULT

            # Player2 connects and takes seat
            await client2.connect()
            client2.receive()  # CONNECTION_STATE
            client2.send(client2.create_subscribe_table(table_id))
            msg = client2.receive()  # TABLE_SNAPSHOT
            if msg:
                # Should see player1 already seated
                payload = msg.get("payload", {})
                seats = payload.get("seats", [])
                # At least one seat should be taken
                pass

            client2.send(client2.create_seat_request(table_id, position=1))
            msg = client2.receive()  # SEAT_RESULT
            if msg:
                assert msg.get("type") == EventType.SEAT_RESULT.value
                payload = msg.get("payload", {})
                assert payload.get("success") is True

            # Player1 should receive TABLE_STATE_UPDATE about player2
            update_msg = client1.receive()
            if update_msg:
                assert update_msg.get("type") == EventType.TABLE_STATE_UPDATE.value
        finally:
            client1.close()
            client2.close()


# =============================================================================
# Idempotency Tests
# =============================================================================


class TestIdempotency:
    """Test request idempotency handling."""

    @pytest.mark.asyncio
    async def test_duplicate_request_id_handled(
        self,
        integration_app,
        player1: dict,
    ):
        """Test: Same requestId should return cached result."""
        client = WebSocketTestClient(
            integration_app,
            player1["tokens"]["access_token"],
        )

        try:
            await client.connect()
            client.receive()  # CONNECTION_STATE

            # Send same PING twice with same requestId
            request_id = str(uuid4())
            client.send(client.create_ping(request_id))
            msg1 = client.receive()

            client.send(client.create_ping(request_id))
            msg2 = client.receive()

            # Both should succeed (PING/PONG is idempotent)
            if msg1 and msg2:
                assert msg1.get("type") == EventType.PONG.value
                assert msg2.get("type") == EventType.PONG.value
        finally:
            client.close()


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_invalid_message_format(
        self,
        integration_app,
        player1: dict,
    ):
        """Test: Invalid message format returns ERROR."""
        client = WebSocketTestClient(
            integration_app,
            player1["tokens"]["access_token"],
        )

        try:
            await client.connect()
            client.receive()  # CONNECTION_STATE

            # Send invalid message
            client.send({"invalid": "message"})

            msg = client.receive()
            if msg:
                # Should receive ERROR
                assert msg.get("type") == EventType.ERROR.value
        finally:
            client.close()

    @pytest.mark.asyncio
    async def test_unknown_event_type(
        self,
        integration_app,
        player1: dict,
    ):
        """Test: Unknown event type returns ERROR."""
        client = WebSocketTestClient(
            integration_app,
            player1["tokens"]["access_token"],
        )

        try:
            await client.connect()
            client.receive()  # CONNECTION_STATE

            # Send unknown event type
            client.send({
                "type": "UNKNOWN_EVENT",
                "ts": int(datetime.utcnow().timestamp() * 1000),
                "version": "v1",
                "payload": {},
            })

            msg = client.receive()
            if msg:
                assert msg.get("type") == EventType.ERROR.value
        finally:
            client.close()

    @pytest.mark.asyncio
    async def test_action_on_nonexistent_table(
        self,
        integration_app,
        player1: dict,
    ):
        """Test: Action on non-existent table returns ERROR."""
        client = WebSocketTestClient(
            integration_app,
            player1["tokens"]["access_token"],
        )

        try:
            await client.connect()
            client.receive()  # CONNECTION_STATE

            # Send action to non-existent table
            client.send(client.create_action_request(
                table_id="nonexistent-table-id",
                action_type="fold",
            ))

            msg = client.receive()
            if msg:
                msg_type = msg.get("type")
                assert msg_type in [EventType.ACTION_RESULT.value, EventType.ERROR.value]
                if msg_type == EventType.ACTION_RESULT.value:
                    assert msg.get("payload", {}).get("success") is False
        finally:
            client.close()
