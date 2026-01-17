"""Tests for Phase 4.2: Group subscription and broadcasting.

Tests ConnectionManager's group subscription methods:
- subscribe_as_player / subscribe_as_spectator
- upgrade_to_player / downgrade_to_spectator
- broadcast_to_players / broadcast_to_spectators / broadcast_to_table
- get_player_count / get_spectator_count
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio

from app.ws.connection import WebSocketConnection
from app.ws.manager import ConnectionManager
from tests.ws.conftest import MockRedis, MockWebSocket


# =============================================================================
# Helper Functions
# =============================================================================


def create_test_connection(user_id: str | None = None) -> tuple[WebSocketConnection, MockWebSocket]:
    """Create a test WebSocket connection with mock socket."""
    mock_ws = MockWebSocket()
    user_id = user_id or f"user_{uuid4().hex[:8]}"
    conn = WebSocketConnection(
        websocket=mock_ws,
        user_id=user_id,
        session_id=str(uuid4()),
        connection_id=str(uuid4()),
        connected_at=datetime.utcnow(),
    )
    return conn, mock_ws


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def manager(mock_redis: MockRedis) -> AsyncGenerator[ConnectionManager, None]:
    """Create a connection manager for testing."""
    mgr = ConnectionManager(mock_redis)
    await mgr.start()
    yield mgr
    await mgr.stop()


# =============================================================================
# subscribe_as_player / subscribe_as_spectator Tests
# =============================================================================


@pytest.mark.asyncio
async def test_subscribe_as_player(manager: ConnectionManager):
    """플레이어로 구독하면 메인 채널과 players 서브채널에 모두 구독됨."""
    conn, mock_ws = create_test_connection()
    await manager.connect(conn)

    room_id = "test-room-1"
    result = await manager.subscribe_as_player(conn.connection_id, room_id)

    assert result is True
    # 메인 채널 구독 확인
    assert f"table:{room_id}" in conn.subscribed_channels
    # players 서브채널 구독 확인
    assert f"table:{room_id}:players" in conn.subscribed_channels
    # spectators 서브채널은 구독 안 됨
    assert f"table:{room_id}:spectators" not in conn.subscribed_channels


@pytest.mark.asyncio
async def test_subscribe_as_spectator(manager: ConnectionManager):
    """관전자로 구독하면 메인 채널과 spectators 서브채널에 모두 구독됨."""
    conn, mock_ws = create_test_connection()
    await manager.connect(conn)

    room_id = "test-room-1"
    result = await manager.subscribe_as_spectator(conn.connection_id, room_id)

    assert result is True
    # 메인 채널 구독 확인
    assert f"table:{room_id}" in conn.subscribed_channels
    # spectators 서브채널 구독 확인
    assert f"table:{room_id}:spectators" in conn.subscribed_channels
    # players 서브채널은 구독 안 됨
    assert f"table:{room_id}:players" not in conn.subscribed_channels


@pytest.mark.asyncio
async def test_subscribe_as_player_removes_spectator(manager: ConnectionManager):
    """플레이어로 구독하면 기존 spectators 구독은 제거됨."""
    conn, mock_ws = create_test_connection()
    await manager.connect(conn)

    room_id = "test-room-1"

    # 먼저 관전자로 구독
    await manager.subscribe_as_spectator(conn.connection_id, room_id)
    assert f"table:{room_id}:spectators" in conn.subscribed_channels

    # 그 다음 플레이어로 구독
    await manager.subscribe_as_player(conn.connection_id, room_id)

    # spectators에서 제거되고 players에 추가됨
    assert f"table:{room_id}:players" in conn.subscribed_channels
    assert f"table:{room_id}:spectators" not in conn.subscribed_channels


# =============================================================================
# upgrade_to_player / downgrade_to_spectator Tests
# =============================================================================


@pytest.mark.asyncio
async def test_upgrade_to_player(manager: ConnectionManager):
    """관전자에서 플레이어로 업그레이드 시 채널이 전환됨."""
    conn, mock_ws = create_test_connection()
    await manager.connect(conn)

    room_id = "test-room-1"

    # 관전자로 시작
    await manager.subscribe_as_spectator(conn.connection_id, room_id)
    assert f"table:{room_id}:spectators" in conn.subscribed_channels

    # 플레이어로 업그레이드
    result = await manager.upgrade_to_player(conn.connection_id, room_id)

    assert result is True
    assert f"table:{room_id}:players" in conn.subscribed_channels
    assert f"table:{room_id}:spectators" not in conn.subscribed_channels
    # 메인 채널은 유지됨
    assert f"table:{room_id}" in conn.subscribed_channels


@pytest.mark.asyncio
async def test_downgrade_to_spectator(manager: ConnectionManager):
    """플레이어에서 관전자로 다운그레이드 시 채널이 전환됨."""
    conn, mock_ws = create_test_connection()
    await manager.connect(conn)

    room_id = "test-room-1"

    # 플레이어로 시작
    await manager.subscribe_as_player(conn.connection_id, room_id)
    assert f"table:{room_id}:players" in conn.subscribed_channels

    # 관전자로 다운그레이드
    result = await manager.downgrade_to_spectator(conn.connection_id, room_id)

    assert result is True
    assert f"table:{room_id}:spectators" in conn.subscribed_channels
    assert f"table:{room_id}:players" not in conn.subscribed_channels
    # 메인 채널은 유지됨
    assert f"table:{room_id}" in conn.subscribed_channels


# =============================================================================
# unsubscribe_from_table Tests
# =============================================================================


@pytest.mark.asyncio
async def test_unsubscribe_from_table_as_player(manager: ConnectionManager):
    """플레이어가 테이블에서 구독 해제하면 모든 관련 채널에서 제거됨."""
    conn, mock_ws = create_test_connection()
    await manager.connect(conn)

    room_id = "test-room-1"

    # 플레이어로 구독
    await manager.subscribe_as_player(conn.connection_id, room_id)

    # 구독 해제
    result = await manager.unsubscribe_from_table(conn.connection_id, room_id)

    assert result is True
    assert f"table:{room_id}" not in conn.subscribed_channels
    assert f"table:{room_id}:players" not in conn.subscribed_channels
    assert f"table:{room_id}:spectators" not in conn.subscribed_channels


@pytest.mark.asyncio
async def test_unsubscribe_from_table_as_spectator(manager: ConnectionManager):
    """관전자가 테이블에서 구독 해제하면 모든 관련 채널에서 제거됨."""
    conn, mock_ws = create_test_connection()
    await manager.connect(conn)

    room_id = "test-room-1"

    # 관전자로 구독
    await manager.subscribe_as_spectator(conn.connection_id, room_id)

    # 구독 해제
    result = await manager.unsubscribe_from_table(conn.connection_id, room_id)

    assert result is True
    assert f"table:{room_id}" not in conn.subscribed_channels
    assert f"table:{room_id}:players" not in conn.subscribed_channels
    assert f"table:{room_id}:spectators" not in conn.subscribed_channels


# =============================================================================
# broadcast_to_players / broadcast_to_spectators / broadcast_to_table Tests
# =============================================================================


@pytest.mark.asyncio
async def test_broadcast_to_players_only(manager: ConnectionManager):
    """broadcast_to_players는 플레이어에게만 메시지를 전송함."""
    player_conn, player_ws = create_test_connection("player1")
    spectator_conn, spectator_ws = create_test_connection("spectator1")

    await manager.connect(player_conn)
    await manager.connect(spectator_conn)

    room_id = "test-room-1"

    await manager.subscribe_as_player(player_conn.connection_id, room_id)
    await manager.subscribe_as_spectator(spectator_conn.connection_id, room_id)

    # 플레이어에게만 브로드캐스트
    message = {"type": "TEST", "data": "player_only"}
    count = await manager.broadcast_to_players(room_id, message)

    assert count == 1
    assert len(player_ws.sent_messages) == 1
    assert player_ws.sent_messages[0] == message
    assert len(spectator_ws.sent_messages) == 0


@pytest.mark.asyncio
async def test_broadcast_to_spectators_only(manager: ConnectionManager):
    """broadcast_to_spectators는 관전자에게만 메시지를 전송함."""
    player_conn, player_ws = create_test_connection("player1")
    spectator_conn, spectator_ws = create_test_connection("spectator1")

    await manager.connect(player_conn)
    await manager.connect(spectator_conn)

    room_id = "test-room-1"

    await manager.subscribe_as_player(player_conn.connection_id, room_id)
    await manager.subscribe_as_spectator(spectator_conn.connection_id, room_id)

    # 관전자에게만 브로드캐스트
    message = {"type": "TEST", "data": "spectator_only"}
    count = await manager.broadcast_to_spectators(room_id, message)

    assert count == 1
    assert len(spectator_ws.sent_messages) == 1
    assert spectator_ws.sent_messages[0] == message
    assert len(player_ws.sent_messages) == 0


@pytest.mark.asyncio
async def test_broadcast_to_table_reaches_all(manager: ConnectionManager):
    """broadcast_to_table은 플레이어와 관전자 모두에게 메시지를 전송함."""
    player_conn, player_ws = create_test_connection("player1")
    spectator_conn, spectator_ws = create_test_connection("spectator1")

    await manager.connect(player_conn)
    await manager.connect(spectator_conn)

    room_id = "test-room-1"

    await manager.subscribe_as_player(player_conn.connection_id, room_id)
    await manager.subscribe_as_spectator(spectator_conn.connection_id, room_id)

    # 전체 테이블에 브로드캐스트
    message = {"type": "TEST", "data": "everyone"}
    count = await manager.broadcast_to_table(room_id, message)

    assert count == 2
    assert len(player_ws.sent_messages) == 1
    assert player_ws.sent_messages[0] == message
    assert len(spectator_ws.sent_messages) == 1
    assert spectator_ws.sent_messages[0] == message


@pytest.mark.asyncio
async def test_broadcast_with_exclude(manager: ConnectionManager):
    """exclude_connection 파라미터로 특정 연결을 제외할 수 있음."""
    player1_conn, player1_ws = create_test_connection("player1")
    player2_conn, player2_ws = create_test_connection("player2")

    await manager.connect(player1_conn)
    await manager.connect(player2_conn)

    room_id = "test-room-1"

    await manager.subscribe_as_player(player1_conn.connection_id, room_id)
    await manager.subscribe_as_player(player2_conn.connection_id, room_id)

    # player1 제외하고 브로드캐스트
    message = {"type": "TEST", "data": "exclude_test"}
    count = await manager.broadcast_to_players(room_id, message, exclude_connection=player1_conn.connection_id)

    assert count == 1
    assert len(player1_ws.sent_messages) == 0
    assert len(player2_ws.sent_messages) == 1


# =============================================================================
# get_player_count / get_spectator_count Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_player_count(manager: ConnectionManager):
    """get_player_count는 플레이어 수를 정확히 반환함."""
    conn1, _ = create_test_connection("player1")
    conn2, _ = create_test_connection("player2")
    conn3, _ = create_test_connection("spectator1")

    await manager.connect(conn1)
    await manager.connect(conn2)
    await manager.connect(conn3)

    room_id = "test-room-1"

    await manager.subscribe_as_player(conn1.connection_id, room_id)
    await manager.subscribe_as_player(conn2.connection_id, room_id)
    await manager.subscribe_as_spectator(conn3.connection_id, room_id)

    assert manager.get_player_count(room_id) == 2


@pytest.mark.asyncio
async def test_get_spectator_count(manager: ConnectionManager):
    """get_spectator_count는 관전자 수를 정확히 반환함."""
    conn1, _ = create_test_connection("player1")
    conn2, _ = create_test_connection("spectator1")
    conn3, _ = create_test_connection("spectator2")

    await manager.connect(conn1)
    await manager.connect(conn2)
    await manager.connect(conn3)

    room_id = "test-room-1"

    await manager.subscribe_as_player(conn1.connection_id, room_id)
    await manager.subscribe_as_spectator(conn2.connection_id, room_id)
    await manager.subscribe_as_spectator(conn3.connection_id, room_id)

    assert manager.get_spectator_count(room_id) == 2


@pytest.mark.asyncio
async def test_counts_after_upgrade_downgrade(manager: ConnectionManager):
    """업그레이드/다운그레이드 후 카운트가 정확히 업데이트됨."""
    conn, _ = create_test_connection("user1")
    await manager.connect(conn)

    room_id = "test-room-1"

    # 관전자로 시작
    await manager.subscribe_as_spectator(conn.connection_id, room_id)
    assert manager.get_player_count(room_id) == 0
    assert manager.get_spectator_count(room_id) == 1

    # 플레이어로 업그레이드
    await manager.upgrade_to_player(conn.connection_id, room_id)
    assert manager.get_player_count(room_id) == 1
    assert manager.get_spectator_count(room_id) == 0

    # 관전자로 다운그레이드
    await manager.downgrade_to_spectator(conn.connection_id, room_id)
    assert manager.get_player_count(room_id) == 0
    assert manager.get_spectator_count(room_id) == 1


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_multiple_rooms_isolation(manager: ConnectionManager):
    """다른 방의 플레이어/관전자는 서로 메시지를 받지 않음."""
    room1_player, room1_player_ws = create_test_connection("room1_player")
    room2_player, room2_player_ws = create_test_connection("room2_player")

    await manager.connect(room1_player)
    await manager.connect(room2_player)

    await manager.subscribe_as_player(room1_player.connection_id, "room-1")
    await manager.subscribe_as_player(room2_player.connection_id, "room-2")

    # room-1에 브로드캐스트
    message = {"type": "TEST", "data": "room1_only"}
    count = await manager.broadcast_to_players("room-1", message)

    assert count == 1
    assert len(room1_player_ws.sent_messages) == 1
    assert len(room2_player_ws.sent_messages) == 0


@pytest.mark.asyncio
async def test_full_player_lifecycle(manager: ConnectionManager):
    """플레이어의 전체 라이프사이클: 구독 -> 게임 참여 -> 나가기 -> 관전 -> 퇴장."""
    conn, ws = create_test_connection("user1")
    await manager.connect(conn)

    room_id = "test-room-1"

    # 1. 처음에 관전자로 입장
    await manager.subscribe_as_spectator(conn.connection_id, room_id)
    assert manager.get_spectator_count(room_id) == 1
    assert manager.get_player_count(room_id) == 0

    # 2. 자리에 앉음 (플레이어로 업그레이드)
    await manager.upgrade_to_player(conn.connection_id, room_id)
    assert manager.get_spectator_count(room_id) == 0
    assert manager.get_player_count(room_id) == 1

    # 3. 자리에서 일어남 (관전자로 다운그레이드)
    await manager.downgrade_to_spectator(conn.connection_id, room_id)
    assert manager.get_spectator_count(room_id) == 1
    assert manager.get_player_count(room_id) == 0

    # 4. 테이블 떠남
    await manager.unsubscribe_from_table(conn.connection_id, room_id)
    assert manager.get_spectator_count(room_id) == 0
    assert manager.get_player_count(room_id) == 0


@pytest.mark.asyncio
async def test_broadcast_order_preserved(manager: ConnectionManager):
    """메시지 순서가 보존됨."""
    conn, ws = create_test_connection("user1")
    await manager.connect(conn)

    room_id = "test-room-1"
    await manager.subscribe_as_player(conn.connection_id, room_id)

    # 여러 메시지 전송
    for i in range(5):
        await manager.broadcast_to_players(room_id, {"seq": i})

    assert len(ws.sent_messages) == 5
    for i, msg in enumerate(ws.sent_messages):
        assert msg["seq"] == i
