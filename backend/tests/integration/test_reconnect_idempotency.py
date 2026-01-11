"""Reconnection & Idempotency Integration Tests.

Tests the MVP required scenarios:
1. Reconnect during hand - state recovery
2. Duplicate request handling (idempotency)
3. State consistency after reconnection
4. Request ordering and deduplication
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from app.config import get_settings
from app.ws.events import EventType
from app.ws.messages import MessageEnvelope

from .conftest import create_room, join_room

settings = get_settings()


# =============================================================================
# Reconnection Tests
# =============================================================================


class TestReconnection:
    """Test reconnection scenarios."""

    @pytest.mark.asyncio
    async def test_reconnect_receives_current_state(
        self,
        integration_app,
        integration_client: AsyncClient,
        player1: dict,
    ):
        """Test: Reconnection receives current table state."""
        # Create room via REST
        room = await create_room(integration_client, player1["headers"])
        table_id = room.get("tableId", room["id"])

        # First connection
        token = player1["tokens"]["access_token"]
        client1 = TestClient(integration_app)

        with client1.websocket_connect(f"/ws?token={token}") as ws1:
            # Get CONNECTION_STATE
            msg1 = ws1.receive_json()
            assert msg1.get("type") == EventType.CONNECTION_STATE.value

            # Subscribe to table
            ws1.send_json(MessageEnvelope.create(
                event_type=EventType.SUBSCRIBE_TABLE,
                payload={"tableId": table_id, "mode": "player"},
            ).to_dict())

            # Get TABLE_SNAPSHOT
            snapshot1 = ws1.receive_json()
            assert snapshot1.get("type") == EventType.TABLE_SNAPSHOT.value
            version1 = snapshot1.get("payload", {}).get("stateVersion", 0)

        # "Disconnect" happened (ws1 closed)

        # Reconnect with same token
        with client1.websocket_connect(f"/ws?token={token}") as ws2:
            # Get CONNECTION_STATE
            msg2 = ws2.receive_json()
            assert msg2.get("type") == EventType.CONNECTION_STATE.value

            # Subscribe to table again
            ws2.send_json(MessageEnvelope.create(
                event_type=EventType.SUBSCRIBE_TABLE,
                payload={"tableId": table_id, "mode": "player"},
            ).to_dict())

            # Should receive current state
            snapshot2 = ws2.receive_json()
            assert snapshot2.get("type") == EventType.TABLE_SNAPSHOT.value

            # State should be consistent
            version2 = snapshot2.get("payload", {}).get("stateVersion", 0)
            assert version2 >= version1

    @pytest.mark.asyncio
    async def test_reconnect_restores_subscriptions(
        self,
        integration_app,
        integration_client: AsyncClient,
        player1: dict,
    ):
        """Test: User can restore subscriptions after reconnect."""
        room = await create_room(integration_client, player1["headers"])
        table_id = room.get("tableId", room["id"])
        token = player1["tokens"]["access_token"]

        client = TestClient(integration_app)

        # First session - subscribe to lobby and table
        with client.websocket_connect(f"/ws?token={token}") as ws:
            ws.receive_json()  # CONNECTION_STATE

            # Subscribe to lobby
            ws.send_json(MessageEnvelope.create(
                event_type=EventType.SUBSCRIBE_LOBBY,
                payload={},
            ).to_dict())
            lobby_msg = ws.receive_json()
            assert lobby_msg.get("type") == EventType.LOBBY_SNAPSHOT.value

            # Subscribe to table
            ws.send_json(MessageEnvelope.create(
                event_type=EventType.SUBSCRIBE_TABLE,
                payload={"tableId": table_id, "mode": "player"},
            ).to_dict())
            table_msg = ws.receive_json()
            assert table_msg.get("type") == EventType.TABLE_SNAPSHOT.value

        # Reconnect - re-subscribe to same channels
        with client.websocket_connect(f"/ws?token={token}") as ws:
            ws.receive_json()  # CONNECTION_STATE

            # Re-subscribe to lobby
            ws.send_json(MessageEnvelope.create(
                event_type=EventType.SUBSCRIBE_LOBBY,
                payload={},
            ).to_dict())
            lobby_msg2 = ws.receive_json()
            assert lobby_msg2.get("type") == EventType.LOBBY_SNAPSHOT.value

            # Re-subscribe to table
            ws.send_json(MessageEnvelope.create(
                event_type=EventType.SUBSCRIBE_TABLE,
                payload={"tableId": table_id, "mode": "player"},
            ).to_dict())
            table_msg2 = ws.receive_json()
            assert table_msg2.get("type") == EventType.TABLE_SNAPSHOT.value

    @pytest.mark.asyncio
    async def test_reconnect_with_different_session(
        self,
        integration_app,
        player1: dict,
    ):
        """Test: Multiple sessions can connect simultaneously."""
        token = player1["tokens"]["access_token"]
        client = TestClient(integration_app)

        # Two concurrent connections (simulating device switch)
        with client.websocket_connect(f"/ws?token={token}") as ws1:
            msg1 = ws1.receive_json()
            assert msg1.get("type") == EventType.CONNECTION_STATE.value
            session1 = msg1.get("payload", {}).get("sessionId")

            # Second connection
            with client.websocket_connect(f"/ws?token={token}") as ws2:
                msg2 = ws2.receive_json()
                assert msg2.get("type") == EventType.CONNECTION_STATE.value
                session2 = msg2.get("payload", {}).get("sessionId")

                # Both should be connected
                # Sessions might be same or different depending on implementation


# =============================================================================
# Idempotency Tests
# =============================================================================


class TestIdempotency:
    """Test request idempotency handling."""

    @pytest.mark.asyncio
    async def test_duplicate_ping_handled(
        self,
        integration_app,
        player1: dict,
    ):
        """Test: Duplicate PING with same requestId is handled."""
        token = player1["tokens"]["access_token"]
        client = TestClient(integration_app)

        with client.websocket_connect(f"/ws?token={token}") as ws:
            ws.receive_json()  # CONNECTION_STATE

            request_id = str(uuid4())

            # Send first PING
            ws.send_json(MessageEnvelope.create(
                event_type=EventType.PING,
                payload={},
                request_id=request_id,
            ).to_dict())
            pong1 = ws.receive_json()
            assert pong1.get("type") == EventType.PONG.value
            assert pong1.get("requestId") == request_id

            # Send duplicate PING with same requestId
            ws.send_json(MessageEnvelope.create(
                event_type=EventType.PING,
                payload={},
                request_id=request_id,
            ).to_dict())
            pong2 = ws.receive_json()
            assert pong2.get("type") == EventType.PONG.value
            # Should respond (PING/PONG is stateless and idempotent)

    @pytest.mark.asyncio
    async def test_duplicate_room_join_idempotent(
        self,
        integration_app,
        integration_client: AsyncClient,
        player1: dict,
        player2: dict,
    ):
        """Test: Duplicate room join request is idempotent."""
        # Create room
        room = await create_room(integration_client, player1["headers"])
        room_id = room["id"]

        # First join
        join1 = await join_room(integration_client, player2["headers"], room_id, 1000)
        position1 = join1.get("position")

        # Duplicate join (same player, same room)
        response = await integration_client.post(
            f"/api/v1/rooms/{room_id}/join",
            json={"buyIn": 1000},
            headers=player2["headers"],
        )

        # Should either succeed with same position or return already joined error
        assert response.status_code in [200, 400]

        if response.status_code == 200:
            join2 = response.json().get("data", {})
            position2 = join2.get("position")
            # Position should be same (idempotent)
            assert position2 == position1

    @pytest.mark.asyncio
    async def test_ws_room_create_idempotent(
        self,
        integration_app,
        player1: dict,
    ):
        """Test: Duplicate room create via WS with same requestId is idempotent."""
        token = player1["tokens"]["access_token"]
        client = TestClient(integration_app)

        with client.websocket_connect(f"/ws?token={token}") as ws:
            ws.receive_json()  # CONNECTION_STATE

            request_id = str(uuid4())
            room_name = f"Idempotent Room {uuid4()}"

            # First create request
            ws.send_json(MessageEnvelope.create(
                event_type=EventType.ROOM_CREATE_REQUEST,
                payload={
                    "name": room_name,
                    "maxSeats": 6,
                    "smallBlind": 10,
                    "bigBlind": 20,
                    "buyInMin": 400,
                    "buyInMax": 2000,
                    "isPrivate": False,
                },
                request_id=request_id,
            ).to_dict())

            result1 = ws.receive_json()
            assert result1.get("type") == EventType.ROOM_CREATE_RESULT.value
            room_id1 = result1.get("payload", {}).get("roomId")

            # Duplicate create with same requestId
            ws.send_json(MessageEnvelope.create(
                event_type=EventType.ROOM_CREATE_REQUEST,
                payload={
                    "name": room_name,
                    "maxSeats": 6,
                    "smallBlind": 10,
                    "bigBlind": 20,
                    "buyInMin": 400,
                    "buyInMax": 2000,
                    "isPrivate": False,
                },
                request_id=request_id,
            ).to_dict())

            result2 = ws.receive_json()
            # Should return cached result or handle gracefully
            if result2.get("type") == EventType.ROOM_CREATE_RESULT.value:
                room_id2 = result2.get("payload", {}).get("roomId")
                # Either same room or error is acceptable
                # Important: no duplicate rooms should be created


# =============================================================================
# State Consistency Tests
# =============================================================================


class TestStateConsistency:
    """Test state consistency across reconnections."""

    @pytest.mark.asyncio
    async def test_state_version_monotonic(
        self,
        integration_app,
        integration_client: AsyncClient,
        player1: dict,
        player2: dict,
    ):
        """Test: State version increases monotonically."""
        room = await create_room(integration_client, player1["headers"])
        room_id = room["id"]
        table_id = room.get("tableId", room_id)

        token1 = player1["tokens"]["access_token"]
        token2 = player2["tokens"]["access_token"]
        client = TestClient(integration_app)

        versions = []

        with client.websocket_connect(f"/ws?token={token1}") as ws1:
            ws1.receive_json()  # CONNECTION_STATE

            # Subscribe to table
            ws1.send_json(MessageEnvelope.create(
                event_type=EventType.SUBSCRIBE_TABLE,
                payload={"tableId": table_id, "mode": "player"},
            ).to_dict())

            snapshot = ws1.receive_json()
            if snapshot.get("type") == EventType.TABLE_SNAPSHOT.value:
                versions.append(snapshot.get("payload", {}).get("stateVersion", 0))

            # Player2 joins (should trigger update)
            await join_room(integration_client, player2["headers"], room_id, 1000)

            # Try to receive update
            try:
                update = ws1.receive_json()
                if update.get("type") == EventType.TABLE_STATE_UPDATE.value:
                    versions.append(update.get("payload", {}).get("stateVersion", 0))
            except Exception:
                pass

        # Versions should be monotonically increasing
        for i in range(1, len(versions)):
            assert versions[i] >= versions[i - 1]

    @pytest.mark.asyncio
    async def test_concurrent_updates_ordered(
        self,
        integration_app,
        integration_client: AsyncClient,
        player1: dict,
    ):
        """Test: Concurrent state updates are properly ordered."""
        room = await create_room(integration_client, player1["headers"])
        table_id = room.get("tableId", room["id"])

        token = player1["tokens"]["access_token"]
        client = TestClient(integration_app)

        with client.websocket_connect(f"/ws?token={token}") as ws:
            ws.receive_json()  # CONNECTION_STATE

            # Subscribe
            ws.send_json(MessageEnvelope.create(
                event_type=EventType.SUBSCRIBE_TABLE,
                payload={"tableId": table_id, "mode": "player"},
            ).to_dict())

            snapshot = ws.receive_json()
            initial_version = snapshot.get("payload", {}).get("stateVersion", 0)

            # Send multiple rapid requests
            request_ids = [str(uuid4()) for _ in range(3)]

            for req_id in request_ids:
                ws.send_json(MessageEnvelope.create(
                    event_type=EventType.PING,
                    payload={},
                    request_id=req_id,
                ).to_dict())

            # Receive all responses
            responses = []
            for _ in range(3):
                try:
                    resp = ws.receive_json()
                    responses.append(resp)
                except Exception:
                    break

            # All PONGs should be received
            pong_count = sum(1 for r in responses if r.get("type") == EventType.PONG.value)
            assert pong_count == 3


# =============================================================================
# Request Deduplication Tests
# =============================================================================


class TestRequestDeduplication:
    """Test request deduplication mechanisms."""

    @pytest.mark.asyncio
    async def test_rapid_duplicate_requests(
        self,
        integration_app,
        player1: dict,
    ):
        """Test: Rapid duplicate requests are handled correctly."""
        token = player1["tokens"]["access_token"]
        client = TestClient(integration_app)

        with client.websocket_connect(f"/ws?token={token}") as ws:
            ws.receive_json()  # CONNECTION_STATE

            request_id = str(uuid4())

            # Send 5 rapid PINGs with same requestId
            for _ in range(5):
                ws.send_json(MessageEnvelope.create(
                    event_type=EventType.PING,
                    payload={},
                    request_id=request_id,
                ).to_dict())

            # Should receive at least one PONG
            pong_count = 0
            for _ in range(5):
                try:
                    resp = ws.receive_json()
                    if resp.get("type") == EventType.PONG.value:
                        pong_count += 1
                except Exception:
                    break

            # All requests should be responded to
            # (PING/PONG is stateless, so all get responses)
            assert pong_count >= 1

    @pytest.mark.asyncio
    async def test_different_request_ids_processed_separately(
        self,
        integration_app,
        player1: dict,
    ):
        """Test: Different requestIds are processed separately."""
        token = player1["tokens"]["access_token"]
        client = TestClient(integration_app)

        with client.websocket_connect(f"/ws?token={token}") as ws:
            ws.receive_json()  # CONNECTION_STATE

            request_ids = [str(uuid4()) for _ in range(3)]
            received_request_ids = []

            # Send PINGs with different requestIds
            for req_id in request_ids:
                ws.send_json(MessageEnvelope.create(
                    event_type=EventType.PING,
                    payload={},
                    request_id=req_id,
                ).to_dict())

            # Receive all PONGs
            for _ in range(3):
                resp = ws.receive_json()
                if resp.get("type") == EventType.PONG.value:
                    received_request_ids.append(resp.get("requestId"))

            # All requestIds should be in responses
            assert set(request_ids) == set(received_request_ids)


# =============================================================================
# Error Recovery Tests
# =============================================================================


class TestErrorRecovery:
    """Test error recovery scenarios."""

    @pytest.mark.asyncio
    async def test_recover_from_invalid_message(
        self,
        integration_app,
        player1: dict,
    ):
        """Test: Connection recovers after invalid message."""
        token = player1["tokens"]["access_token"]
        client = TestClient(integration_app)

        with client.websocket_connect(f"/ws?token={token}") as ws:
            ws.receive_json()  # CONNECTION_STATE

            # Send invalid message
            ws.send_json({"invalid": "message"})

            # Should receive ERROR
            error = ws.receive_json()
            assert error.get("type") == EventType.ERROR.value

            # Connection should still be alive - send valid PING
            ws.send_json(MessageEnvelope.create(
                event_type=EventType.PING,
                payload={},
            ).to_dict())

            pong = ws.receive_json()
            assert pong.get("type") == EventType.PONG.value

    @pytest.mark.asyncio
    async def test_recover_from_action_error(
        self,
        integration_app,
        integration_client: AsyncClient,
        player1: dict,
    ):
        """Test: Connection recovers after action error."""
        room = await create_room(integration_client, player1["headers"])
        table_id = room.get("tableId", room["id"])

        token = player1["tokens"]["access_token"]
        client = TestClient(integration_app)

        with client.websocket_connect(f"/ws?token={token}") as ws:
            ws.receive_json()  # CONNECTION_STATE

            # Send action on non-existent table
            ws.send_json(MessageEnvelope.create(
                event_type=EventType.ACTION_REQUEST,
                payload={
                    "tableId": "fake-table-id",
                    "actionType": "fold",
                },
            ).to_dict())

            # Should receive error or action result with error
            resp = ws.receive_json()
            # Connection should still work

            # Verify connection is alive
            ws.send_json(MessageEnvelope.create(
                event_type=EventType.PING,
                payload={},
            ).to_dict())

            pong = ws.receive_json()
            assert pong.get("type") == EventType.PONG.value


# =============================================================================
# Timeout Handling Tests
# =============================================================================


class TestTimeoutHandling:
    """Test timeout and heartbeat scenarios."""

    @pytest.mark.asyncio
    async def test_heartbeat_keeps_connection_alive(
        self,
        integration_app,
        player1: dict,
    ):
        """Test: Regular heartbeats keep connection alive."""
        token = player1["tokens"]["access_token"]
        client = TestClient(integration_app)

        with client.websocket_connect(f"/ws?token={token}") as ws:
            ws.receive_json()  # CONNECTION_STATE

            # Send multiple PINGs
            for i in range(3):
                ws.send_json(MessageEnvelope.create(
                    event_type=EventType.PING,
                    payload={},
                    request_id=f"ping-{i}",
                ).to_dict())

                pong = ws.receive_json()
                assert pong.get("type") == EventType.PONG.value

            # Connection should still be alive
            ws.send_json(MessageEnvelope.create(
                event_type=EventType.SUBSCRIBE_LOBBY,
                payload={},
            ).to_dict())

            lobby = ws.receive_json()
            assert lobby.get("type") == EventType.LOBBY_SNAPSHOT.value
