"""
Announcement Service Tests - 공지사항 서비스 테스트

**Validates: Phase 3.2 - 공지사항 발송 시스템**
"""
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from uuid import uuid4

from app.services.announcement_service import AnnouncementService
from app.models.announcement import (
    Announcement,
    AnnouncementType,
    AnnouncementPriority,
    AnnouncementTarget,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock AsyncSession."""
    return AsyncMock()


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = AsyncMock()
    redis.publish = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def announcement_service(mock_db, mock_redis):
    """Create AnnouncementService with mocks."""
    return AnnouncementService(mock_db, mock_redis)


@pytest.fixture
def sample_announcement():
    """샘플 공지사항 생성."""
    ann = MagicMock(spec=Announcement)
    ann.id = str(uuid4())
    ann.title = "테스트 공지"
    ann.content = "테스트 내용입니다."
    ann.announcement_type = AnnouncementType.NOTICE
    ann.priority = AnnouncementPriority.NORMAL
    ann.target = AnnouncementTarget.ALL
    ann.target_room_id = None
    ann.start_time = None
    ann.end_time = None
    ann.scheduled_at = None
    ann.broadcasted_at = None
    ann.broadcast_count = 0
    ann.created_by = str(uuid4())
    ann.created_at = datetime.now(timezone.utc)
    ann.updated_at = datetime.now(timezone.utc)
    ann.is_active = True
    return ann


# ============================================================================
# AnnouncementService Tests
# ============================================================================

class TestAnnouncementService:
    """AnnouncementService 테스트."""

    @pytest.mark.asyncio
    async def test_create_announcement(self, announcement_service, mock_db):
        """공지사항 생성 테스트."""
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await announcement_service.create_announcement(
            title="새 공지",
            content="공지 내용",
            created_by="admin-123",
            announcement_type=AnnouncementType.EVENT,
            priority=AnnouncementPriority.HIGH,
        )

        # DB에 추가되었는지 확인
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

        # 결과 확인
        assert result.title == "새 공지"
        assert result.content == "공지 내용"
        assert result.announcement_type == AnnouncementType.EVENT
        assert result.priority == AnnouncementPriority.HIGH

    @pytest.mark.asyncio
    async def test_create_announcement_with_schedule(self, announcement_service, mock_db):
        """예약 공지 생성 테스트."""
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        start_time = datetime.now(timezone.utc) + timedelta(hours=1)
        end_time = datetime.now(timezone.utc) + timedelta(hours=2)

        result = await announcement_service.create_announcement(
            title="예약 공지",
            content="예약된 내용",
            created_by="admin-123",
            start_time=start_time,
            end_time=end_time,
        )

        assert result.start_time == start_time
        assert result.end_time == end_time


class TestAnnouncementBroadcast:
    """공지사항 브로드캐스트 테스트."""

    @pytest.mark.asyncio
    async def test_broadcast_to_lobby(
        self, announcement_service, mock_db, mock_redis, sample_announcement
    ):
        """전체 사용자 브로드캐스트 테스트."""
        # get_announcement mock 설정
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=sample_announcement)
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        result = await announcement_service.broadcast_announcement(sample_announcement.id)

        # Redis publish 확인
        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        assert call_args[0][0] == "ws:pubsub:lobby"

        # 결과 확인
        assert result["success"] is True
        assert result["channel"] == "lobby"

    @pytest.mark.asyncio
    async def test_broadcast_to_specific_room(
        self, announcement_service, mock_db, mock_redis, sample_announcement
    ):
        """특정 방 브로드캐스트 테스트."""
        room_id = str(uuid4())
        sample_announcement.target = AnnouncementTarget.SPECIFIC_ROOM
        sample_announcement.target_room_id = room_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=sample_announcement)
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        result = await announcement_service.broadcast_announcement(sample_announcement.id)

        # Redis publish 확인 - 특정 방 채널로 발송
        call_args = mock_redis.publish.call_args
        assert call_args[0][0] == f"ws:pubsub:table:{room_id}"

        assert result["success"] is True
        assert result["channel"] == f"table:{room_id}"

    @pytest.mark.asyncio
    async def test_broadcast_not_found(self, announcement_service, mock_db):
        """존재하지 않는 공지 브로드캐스트 테스트."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await announcement_service.broadcast_announcement("invalid-id")

        assert result["success"] is False
        assert "찾을 수 없습니다" in result["error"]

    @pytest.mark.asyncio
    async def test_broadcast_without_redis(self, mock_db, sample_announcement):
        """Redis 없이 브로드캐스트 시도 테스트."""
        service = AnnouncementService(mock_db, redis=None)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=sample_announcement)
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.broadcast_announcement(sample_announcement.id)

        assert result["success"] is False
        assert "Redis" in result["error"]

    @pytest.mark.asyncio
    async def test_broadcast_increments_count(
        self, announcement_service, mock_db, mock_redis, sample_announcement
    ):
        """브로드캐스트 횟수 증가 테스트."""
        sample_announcement.broadcast_count = 2

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=sample_announcement)
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        result = await announcement_service.broadcast_announcement(sample_announcement.id)

        assert result["broadcast_count"] == 3
        assert sample_announcement.broadcasted_at is not None


class TestAnnouncementMessageFormat:
    """브로드캐스트 메시지 포맷 테스트."""

    @pytest.mark.asyncio
    async def test_message_format(
        self, announcement_service, mock_db, mock_redis, sample_announcement
    ):
        """WebSocket 메시지 포맷 검증."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=sample_announcement)
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()

        await announcement_service.broadcast_announcement(sample_announcement.id)

        # Redis publish 호출 인자 확인
        call_args = mock_redis.publish.call_args
        message_json = call_args[0][1]
        message_data = json.loads(message_json)

        # pub/sub 래퍼 구조 확인
        assert "source_instance" in message_data
        assert "message" in message_data

        # 실제 WebSocket 메시지 구조 확인
        ws_message = message_data["message"]
        assert ws_message["type"] == "ANNOUNCEMENT"
        assert "ts" in ws_message
        assert "traceId" in ws_message
        assert "payload" in ws_message

        # payload 내용 확인
        payload = ws_message["payload"]
        assert payload["id"] == sample_announcement.id
        assert payload["title"] == sample_announcement.title
        assert payload["content"] == sample_announcement.content
        assert payload["type"] == "notice"
        assert payload["priority"] == "normal"
        assert payload["target"] == "all"


class TestAnnouncementToDict:
    """_to_dict 메서드 테스트."""

    def test_to_dict_basic(self, announcement_service, sample_announcement):
        """기본 변환 테스트."""
        result = announcement_service._to_dict(sample_announcement)

        assert result["id"] == sample_announcement.id
        assert result["title"] == sample_announcement.title
        assert result["content"] == sample_announcement.content
        assert result["announcement_type"] == "notice"
        assert result["priority"] == "normal"
        assert result["target"] == "all"
        assert result["is_active"] is True

    def test_to_dict_with_times(self, announcement_service, sample_announcement):
        """시간 필드 포함 변환 테스트."""
        now = datetime.now(timezone.utc)
        sample_announcement.start_time = now
        sample_announcement.end_time = now + timedelta(hours=1)
        sample_announcement.broadcasted_at = now

        result = announcement_service._to_dict(sample_announcement)

        assert result["start_time"] is not None
        assert result["end_time"] is not None
        assert result["broadcasted_at"] is not None


class TestAnnouncementPriority:
    """공지사항 우선순위 테스트."""

    @pytest.mark.parametrize(
        "priority,expected",
        [
            (AnnouncementPriority.LOW, "low"),
            (AnnouncementPriority.NORMAL, "normal"),
            (AnnouncementPriority.HIGH, "high"),
            (AnnouncementPriority.CRITICAL, "critical"),
        ],
    )
    def test_priority_values(self, priority, expected):
        """우선순위 값 확인."""
        assert priority.value == expected


class TestAnnouncementType:
    """공지사항 유형 테스트."""

    @pytest.mark.parametrize(
        "ann_type,expected",
        [
            (AnnouncementType.NOTICE, "notice"),
            (AnnouncementType.EVENT, "event"),
            (AnnouncementType.MAINTENANCE, "maintenance"),
            (AnnouncementType.URGENT, "urgent"),
        ],
    )
    def test_type_values(self, ann_type, expected):
        """유형 값 확인."""
        assert ann_type.value == expected
