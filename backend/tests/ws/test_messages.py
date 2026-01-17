"""Tests for WebSocket message handling."""

from datetime import datetime
import pytest

from app.ws.events import EventType, CLIENT_TO_SERVER_EVENTS, SERVER_TO_CLIENT_EVENTS
from app.ws.messages import MessageEnvelope, ErrorPayload, create_error_message


class TestEventType:
    """Tests for EventType enum."""

    def test_all_events_have_values(self):
        """Test all event types have string values."""
        for event in EventType:
            assert isinstance(event.value, str)
            assert len(event.value) > 0

    def test_client_to_server_events(self):
        """Test CLIENT_TO_SERVER_EVENTS contains correct events."""
        assert EventType.PING in CLIENT_TO_SERVER_EVENTS
        assert EventType.PONG in CLIENT_TO_SERVER_EVENTS  # 클라이언트가 서버 PING에 응답
        assert EventType.SUBSCRIBE_LOBBY in CLIENT_TO_SERVER_EVENTS
        assert EventType.ACTION_REQUEST in CLIENT_TO_SERVER_EVENTS

        # Server-only events should not be in this set
        assert EventType.LOBBY_SNAPSHOT not in CLIENT_TO_SERVER_EVENTS

    def test_server_to_client_events(self):
        """Test SERVER_TO_CLIENT_EVENTS contains correct events."""
        assert EventType.PING in SERVER_TO_CLIENT_EVENTS  # 서버가 클라이언트에게 하트비트 전송
        assert EventType.PONG in SERVER_TO_CLIENT_EVENTS
        assert EventType.CONNECTION_STATE in SERVER_TO_CLIENT_EVENTS
        assert EventType.TABLE_SNAPSHOT in SERVER_TO_CLIENT_EVENTS

        # Client-only events should not be in this set
        assert EventType.SUBSCRIBE_LOBBY not in SERVER_TO_CLIENT_EVENTS

    def test_ping_pong_is_bidirectional(self):
        """Test PING/PONG are bidirectional for heartbeat mechanism."""
        # PING: 양방향 (클라이언트 → 서버, 서버 → 클라이언트)
        assert EventType.PING in CLIENT_TO_SERVER_EVENTS
        assert EventType.PING in SERVER_TO_CLIENT_EVENTS

        # PONG: 양방향 (서버 → 클라이언트, 클라이언트 → 서버)
        assert EventType.PONG in CLIENT_TO_SERVER_EVENTS
        assert EventType.PONG in SERVER_TO_CLIENT_EVENTS

    def test_chat_message_is_bidirectional(self):
        """Test CHAT_MESSAGE is in both sets."""
        assert EventType.CHAT_MESSAGE in CLIENT_TO_SERVER_EVENTS
        assert EventType.CHAT_MESSAGE in SERVER_TO_CLIENT_EVENTS


class TestMessageEnvelope:
    """Tests for MessageEnvelope class."""

    def test_create_message(self):
        """Test creating a message envelope."""
        message = MessageEnvelope.create(
            event_type=EventType.PING,
            payload={"test": "data"},
            request_id="req-123",
            trace_id="trace-456",
        )

        assert message.type == EventType.PING
        assert message.payload == {"test": "data"}
        assert message.request_id == "req-123"
        assert message.trace_id == "trace-456"
        assert message.version == "v1"
        assert isinstance(message.ts, int)

    def test_create_message_without_optional_fields(self):
        """Test creating a message without optional fields."""
        message = MessageEnvelope.create(
            event_type=EventType.PONG,
            payload={},
        )

        assert message.type == EventType.PONG
        assert message.request_id is None
        assert message.trace_id is not None  # Auto-generated

    def test_to_dict_includes_all_fields(self):
        """Test to_dict includes all required fields."""
        message = MessageEnvelope.create(
            event_type=EventType.CONNECTION_STATE,
            payload={"state": "connected"},
            request_id="req-123",
        )

        result = message.to_dict()

        assert result["type"] == "CONNECTION_STATE"
        assert result["payload"] == {"state": "connected"}
        assert result["requestId"] == "req-123"
        assert "ts" in result
        assert "traceId" in result
        assert result["version"] == "v1"

    def test_to_dict_omits_null_request_id(self):
        """Test to_dict omits requestId when None."""
        message = MessageEnvelope.create(
            event_type=EventType.PONG,
            payload={},
        )

        result = message.to_dict()

        assert "requestId" not in result

    def test_from_dict_parses_message(self):
        """Test from_dict parses incoming messages."""
        data = {
            "type": "PING",
            "ts": 1704067200000,
            "traceId": "trace-123",
            "payload": {},
            "version": "v1",
            "requestId": "req-456",
        }

        message = MessageEnvelope.from_dict(data)

        assert message.type == EventType.PING
        assert message.ts == 1704067200000
        assert message.trace_id == "trace-123"
        assert message.request_id == "req-456"

    def test_from_dict_handles_missing_optional_fields(self):
        """Test from_dict handles missing optional fields."""
        data = {
            "type": "PING",
            "payload": {},
        }

        message = MessageEnvelope.from_dict(data)

        assert message.type == EventType.PING
        assert message.request_id is None
        assert message.version == "v1"

    def test_from_dict_raises_on_invalid_type(self):
        """Test from_dict raises on invalid event type."""
        data = {
            "type": "INVALID_TYPE",
            "payload": {},
        }

        with pytest.raises(ValueError):
            MessageEnvelope.from_dict(data)

    def test_message_is_frozen(self):
        """Test MessageEnvelope is immutable."""
        message = MessageEnvelope.create(
            event_type=EventType.PING,
            payload={},
        )

        with pytest.raises(AttributeError):
            message.type = EventType.PONG


class TestErrorPayload:
    """Tests for ErrorPayload class."""

    def test_create_error_payload(self):
        """Test creating an error payload."""
        error = ErrorPayload(
            error_code="INVALID_ACTION",
            error_message="Invalid action type",
            details={"action": "bet", "reason": "insufficient chips"},
        )

        assert error.error_code == "INVALID_ACTION"
        assert error.error_message == "Invalid action type"

    def test_error_payload_to_dict(self):
        """Test error payload serialization."""
        error = ErrorPayload(
            error_code="AUTH_REQUIRED",
            error_message="Authentication required",
        )

        result = error.to_dict()

        assert result["errorCode"] == "AUTH_REQUIRED"
        assert result["errorMessage"] == "Authentication required"
        assert result["details"] == {}


class TestCreateErrorMessage:
    """Tests for create_error_message helper."""

    def test_create_error_message(self):
        """Test creating an error message envelope."""
        message = create_error_message(
            error_code="NOT_YOUR_TURN",
            error_message="It is not your turn to act",
            request_id="req-123",
        )

        assert message.type == EventType.ERROR
        assert message.payload["errorCode"] == "NOT_YOUR_TURN"
        assert message.payload["errorMessage"] == "It is not your turn to act"
        assert message.request_id == "req-123"

    def test_create_error_message_with_details(self):
        """Test error message includes details."""
        message = create_error_message(
            error_code="INVALID_AMOUNT",
            error_message="Bet amount out of range",
            details={"min": 20, "max": 100, "requested": 200},
        )

        assert message.payload["details"]["min"] == 20
        assert message.payload["details"]["max"] == 100
