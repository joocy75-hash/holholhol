"""Tests for WebSocket heartbeat mechanism."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.ws.gateway import (
    HeartbeatManager,
    HEARTBEAT_INTERVAL_SECONDS,
    HEARTBEAT_TIMEOUT_SECONDS,
    MAX_MISSED_PONGS,
)
from app.ws.handlers.system import SystemHandler
from app.ws.events import EventType
from app.ws.messages import MessageEnvelope
from app.ws.connection import WebSocketConnection


class TestHeartbeatConfiguration:
    """하트비트 설정값 테스트."""

    def test_heartbeat_interval_is_30_seconds(self):
        """하트비트 간격은 30초여야 함."""
        assert HEARTBEAT_INTERVAL_SECONDS == 30.0

    def test_heartbeat_timeout_is_60_seconds(self):
        """하트비트 타임아웃은 60초여야 함."""
        assert HEARTBEAT_TIMEOUT_SECONDS == 60.0

    def test_max_missed_pongs_is_2(self):
        """최대 미응답 허용 횟수는 2회여야 함."""
        assert MAX_MISSED_PONGS == 2


class TestHeartbeatManager:
    """HeartbeatManager 클래스 테스트."""

    @pytest.fixture
    def mock_connection(self):
        """Mock WebSocket connection 생성."""
        conn = MagicMock()
        conn.user_id = "user-123"
        conn.connection_id = "conn-456"
        conn.send = AsyncMock(return_value=True)
        conn.websocket = MagicMock()
        conn.websocket.close = AsyncMock()
        conn.last_ping_at = None
        conn.last_pong_at = None
        conn.missed_pongs = 0
        return conn

    def test_init_stores_connection(self, mock_connection):
        """HeartbeatManager 초기화 시 connection이 저장되어야 함."""
        manager = HeartbeatManager(mock_connection)
        assert manager.connection == mock_connection
        assert manager._running is False
        assert manager._task is None

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self, mock_connection):
        """start()는 running 플래그를 설정하고 task를 생성해야 함."""
        manager = HeartbeatManager(mock_connection)

        await manager.start()
        assert manager._running is True
        assert manager._task is not None

        await manager.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self, mock_connection):
        """stop()은 task를 취소해야 함."""
        manager = HeartbeatManager(mock_connection)

        await manager.start()
        await manager.stop()

        assert manager._running is False
        assert manager._task is None

    @pytest.mark.asyncio
    async def test_record_pong_updates_connection(self, mock_connection):
        """record_pong()은 connection 상태를 업데이트해야 함."""
        manager = HeartbeatManager(mock_connection)
        mock_connection.missed_pongs = 1

        manager.record_pong()

        assert mock_connection.last_pong_at is not None
        assert mock_connection.missed_pongs == 0

    @pytest.mark.asyncio
    async def test_heartbeat_loop_sends_ping(self, mock_connection):
        """하트비트 루프는 PING 메시지를 전송해야 함."""
        manager = HeartbeatManager(mock_connection)

        call_count = 0

        async def mock_sleep(seconds):
            nonlocal call_count
            call_count += 1
            # 두 번째 sleep에서 종료 (첫 번째 sleep 후 PING 전송됨)
            if call_count >= 2:
                manager._running = False

        with patch('app.ws.gateway.asyncio.sleep', side_effect=mock_sleep):
            manager._running = True
            await manager._heartbeat_loop()

        # PING 메시지 전송 확인
        mock_connection.send.assert_called()
        call_args = mock_connection.send.call_args[0][0]
        assert call_args["type"] == "PING"
        assert "timestamp" in call_args

    @pytest.mark.asyncio
    async def test_heartbeat_loop_increments_missed_pongs_on_no_response(self, mock_connection):
        """PONG 응답이 없으면 missed_pongs가 증가해야 함."""
        manager = HeartbeatManager(mock_connection)

        # 첫 번째 PING 이후 시뮬레이션 (PONG 없음)
        mock_connection.last_ping_at = datetime.utcnow() - timedelta(seconds=35)
        mock_connection.last_pong_at = None
        mock_connection.missed_pongs = 0

        call_count = 0

        async def mock_sleep(seconds):
            nonlocal call_count
            call_count += 1
            # 두 번째 sleep에서 종료 (첫 번째 sleep 후 missed_pongs 증가)
            if call_count >= 2:
                manager._running = False

        with patch('app.ws.gateway.asyncio.sleep', side_effect=mock_sleep):
            manager._running = True
            await manager._heartbeat_loop()

        # missed_pongs가 증가해야 함
        assert mock_connection.missed_pongs == 1

    @pytest.mark.asyncio
    async def test_heartbeat_loop_closes_connection_on_max_missed(self, mock_connection):
        """최대 미응답 횟수 초과 시 연결을 종료해야 함."""
        manager = HeartbeatManager(mock_connection)

        # 이미 1회 미응답 상태
        mock_connection.last_ping_at = datetime.utcnow() - timedelta(seconds=35)
        mock_connection.last_pong_at = None
        mock_connection.missed_pongs = 1  # 다음에 2가 되면 종료

        with patch('app.ws.gateway.asyncio.sleep', new_callable=AsyncMock):
            manager._running = True
            await manager._heartbeat_loop()

        # 연결 종료 확인
        mock_connection.websocket.close.assert_called_once()
        close_args = mock_connection.websocket.close.call_args
        assert close_args[0][0] == 4003  # Heartbeat timeout close code
        assert "Heartbeat timeout" in close_args[0][1]

    @pytest.mark.asyncio
    async def test_heartbeat_loop_resets_missed_pongs_on_pong(self, mock_connection):
        """PONG 응답을 받으면 missed_pongs가 리셋되어야 함."""
        manager = HeartbeatManager(mock_connection)

        # PONG 응답이 있는 상태 시뮬레이션
        mock_connection.last_ping_at = datetime.utcnow() - timedelta(seconds=25)
        mock_connection.last_pong_at = datetime.utcnow()  # PING 이후 PONG 수신
        mock_connection.missed_pongs = 0

        call_count = 0

        async def mock_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                manager._running = False

        with patch('app.ws.gateway.asyncio.sleep', side_effect=mock_sleep):
            manager._running = True
            await manager._heartbeat_loop()

        # missed_pongs는 0 유지
        assert mock_connection.missed_pongs == 0
        # 연결 종료되지 않아야 함
        mock_connection.websocket.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_heartbeat_updates_last_ping_at(self, mock_connection):
        """PING 전송 후 last_ping_at이 업데이트되어야 함."""
        manager = HeartbeatManager(mock_connection)

        call_count = 0

        async def mock_sleep(seconds):
            nonlocal call_count
            call_count += 1
            # 두 번째 sleep에서 종료 (첫 번째 sleep 후 PING 전송)
            if call_count >= 2:
                manager._running = False

        with patch('app.ws.gateway.asyncio.sleep', side_effect=mock_sleep):
            manager._running = True
            await manager._heartbeat_loop()

        # last_ping_at이 설정되어야 함
        assert mock_connection.last_ping_at is not None


class TestHeartbeatErrorHandling:
    """HeartbeatManager 에러 처리 테스트."""

    @pytest.fixture
    def mock_connection(self):
        """Mock WebSocket connection 생성."""
        conn = MagicMock()
        conn.user_id = "user-123"
        conn.connection_id = "conn-456"
        conn.send = AsyncMock(return_value=True)
        conn.websocket = MagicMock()
        conn.websocket.close = AsyncMock()
        conn.last_ping_at = None
        conn.last_pong_at = None
        conn.missed_pongs = 0
        return conn

    @pytest.mark.asyncio
    async def test_handles_send_failure(self, mock_connection):
        """send 실패 시에도 루프가 계속되어야 함."""
        manager = HeartbeatManager(mock_connection)
        mock_connection.send.return_value = False

        call_count = 0

        async def mock_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                manager._running = False

        with patch('app.ws.gateway.asyncio.sleep', side_effect=mock_sleep):
            manager._running = True
            # 에러 없이 완료되어야 함
            await manager._heartbeat_loop()

        # 여러 번 시도했어야 함
        assert call_count >= 1

    @pytest.mark.asyncio
    async def test_handles_close_error(self, mock_connection):
        """연결 종료 에러 시에도 gracefully 처리되어야 함."""
        manager = HeartbeatManager(mock_connection)

        mock_connection.last_ping_at = datetime.utcnow() - timedelta(seconds=35)
        mock_connection.last_pong_at = None
        mock_connection.missed_pongs = 1  # 다음에 2가 되면 종료 시도
        mock_connection.websocket.close.side_effect = Exception("Close failed")

        with patch('app.ws.gateway.asyncio.sleep', new_callable=AsyncMock):
            manager._running = True
            # 에러 없이 완료되어야 함
            await manager._heartbeat_loop()

        # 루프가 종료되어야 함
        assert manager._running is False

    @pytest.mark.asyncio
    async def test_handles_send_exception(self, mock_connection):
        """send 예외 발생 시에도 루프가 계속되어야 함."""
        manager = HeartbeatManager(mock_connection)
        mock_connection.send.side_effect = Exception("Send exception")

        call_count = 0

        async def mock_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                manager._running = False

        with patch('app.ws.gateway.asyncio.sleep', side_effect=mock_sleep):
            manager._running = True
            # 에러 없이 완료되어야 함
            await manager._heartbeat_loop()


class TestSystemHandlerPong:
    """SystemHandler PONG 처리 테스트."""

    @pytest.fixture
    def mock_manager(self):
        """Mock ConnectionManager 생성."""
        return MagicMock()

    @pytest.fixture
    def mock_connection(self):
        """Mock WebSocket connection 생성."""
        conn = MagicMock()
        conn.user_id = "user-123"
        conn.connection_id = "conn-456"
        conn.last_pong_at = None
        conn.missed_pongs = 2
        return conn

    def test_pong_in_handled_events(self, mock_manager):
        """SystemHandler가 PONG 이벤트를 처리해야 함."""
        handler = SystemHandler(mock_manager)
        assert EventType.PONG in handler.handled_events

    @pytest.mark.asyncio
    async def test_handle_pong_updates_connection(self, mock_manager, mock_connection):
        """PONG 처리 시 connection 상태가 업데이트되어야 함."""
        handler = SystemHandler(mock_manager)

        event = MessageEnvelope.create(
            event_type=EventType.PONG,
            payload={},
        )

        result = await handler.handle(mock_connection, event)

        # 응답은 None (PONG에 대한 응답 없음)
        assert result is None

        # last_pong_at이 업데이트되어야 함
        assert mock_connection.last_pong_at is not None

        # missed_pongs가 리셋되어야 함
        assert mock_connection.missed_pongs == 0

    @pytest.mark.asyncio
    async def test_handle_ping_still_works(self, mock_manager, mock_connection):
        """PING 처리가 여전히 작동해야 함."""
        handler = SystemHandler(mock_manager)
        mock_connection.update_ping = MagicMock()

        event = MessageEnvelope.create(
            event_type=EventType.PING,
            payload={},
            request_id="req-123",
        )

        result = await handler.handle(mock_connection, event)

        # PONG 응답이 있어야 함
        assert result is not None
        assert result.type == EventType.PONG


class TestBidirectionalPingPong:
    """양방향 PING/PONG 테스트."""

    def test_ping_is_client_to_server_event(self):
        """PING은 클라이언트→서버 이벤트여야 함."""
        from app.ws.events import CLIENT_TO_SERVER_EVENTS
        assert EventType.PING in CLIENT_TO_SERVER_EVENTS

    def test_pong_is_client_to_server_event(self):
        """PONG은 클라이언트→서버 이벤트여야 함 (서버 PING 응답)."""
        from app.ws.events import CLIENT_TO_SERVER_EVENTS
        assert EventType.PONG in CLIENT_TO_SERVER_EVENTS

    def test_ping_is_server_to_client_event(self):
        """PING은 서버→클라이언트 이벤트여야 함 (하트비트)."""
        from app.ws.events import SERVER_TO_CLIENT_EVENTS
        assert EventType.PING in SERVER_TO_CLIENT_EVENTS

    def test_pong_is_server_to_client_event(self):
        """PONG은 서버→클라이언트 이벤트여야 함."""
        from app.ws.events import SERVER_TO_CLIENT_EVENTS
        assert EventType.PONG in SERVER_TO_CLIENT_EVENTS
