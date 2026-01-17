"""
Announcement API Tests - 공지사항 API 테스트

**Validates: Phase 3.2 - 공지사항 발송 시스템**
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.models.announcement import (
    AnnouncementType,
    AnnouncementPriority,
    AnnouncementTarget,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_admin_user():
    """Mock supervisor admin user."""
    user = MagicMock()
    user.id = str(uuid4())
    user.username = "test_admin"
    user.role = "supervisor"
    return user


@pytest.fixture
def mock_announcement_service():
    """Mock AnnouncementService."""
    with patch("app.api.announcements.AnnouncementService") as MockService:
        service = AsyncMock()
        MockService.return_value = service
        yield service


@pytest.fixture
def mock_audit_service():
    """Mock AuditService."""
    with patch("app.api.announcements.AuditService") as MockService:
        service = AsyncMock()
        MockService.return_value = service
        yield service


# ============================================================================
# Create Announcement Tests
# ============================================================================

class TestCreateAnnouncement:
    """공지사항 생성 API 테스트."""

    def test_create_announcement_schema(self):
        """공지사항 생성 요청 스키마 검증."""
        from app.api.announcements import AnnouncementCreateRequest

        # 필수 필드만으로 생성
        request = AnnouncementCreateRequest(
            title="테스트 공지",
            content="테스트 내용",
        )
        assert request.title == "테스트 공지"
        assert request.content == "테스트 내용"
        assert request.announcement_type == AnnouncementType.NOTICE
        assert request.priority == AnnouncementPriority.NORMAL
        assert request.target == AnnouncementTarget.ALL

    def test_create_announcement_with_all_fields(self):
        """모든 필드를 포함한 공지 생성 요청."""
        from app.api.announcements import AnnouncementCreateRequest

        request = AnnouncementCreateRequest(
            title="이벤트 공지",
            content="이벤트 내용",
            announcement_type=AnnouncementType.EVENT,
            priority=AnnouncementPriority.HIGH,
            target=AnnouncementTarget.VIP,
            broadcast_immediately=True,
        )
        assert request.announcement_type == AnnouncementType.EVENT
        assert request.priority == AnnouncementPriority.HIGH
        assert request.target == AnnouncementTarget.VIP
        assert request.broadcast_immediately is True

    def test_create_announcement_title_validation(self):
        """제목 길이 검증."""
        from app.api.announcements import AnnouncementCreateRequest
        from pydantic import ValidationError

        # 빈 제목
        with pytest.raises(ValidationError):
            AnnouncementCreateRequest(title="", content="내용")

        # 200자 초과
        with pytest.raises(ValidationError):
            AnnouncementCreateRequest(title="a" * 201, content="내용")

    def test_specific_room_requires_room_id(self):
        """SPECIFIC_ROOM 타겟은 room_id 필요."""
        from app.api.announcements import AnnouncementCreateRequest

        # room_id 없이 생성은 가능 (API에서 검증)
        request = AnnouncementCreateRequest(
            title="방 공지",
            content="내용",
            target=AnnouncementTarget.SPECIFIC_ROOM,
        )
        assert request.target == AnnouncementTarget.SPECIFIC_ROOM
        assert request.target_room_id is None


# ============================================================================
# Update Announcement Tests
# ============================================================================

class TestUpdateAnnouncement:
    """공지사항 수정 API 테스트."""

    def test_update_request_partial(self):
        """부분 업데이트 요청."""
        from app.api.announcements import AnnouncementUpdateRequest

        # 제목만 업데이트
        request = AnnouncementUpdateRequest(title="새 제목")
        assert request.title == "새 제목"
        assert request.content is None

    def test_update_request_all_fields(self):
        """전체 필드 업데이트 요청."""
        from app.api.announcements import AnnouncementUpdateRequest

        request = AnnouncementUpdateRequest(
            title="수정된 제목",
            content="수정된 내용",
            announcement_type=AnnouncementType.URGENT,
            priority=AnnouncementPriority.CRITICAL,
        )
        assert request.title == "수정된 제목"
        assert request.announcement_type == AnnouncementType.URGENT


# ============================================================================
# Response Model Tests
# ============================================================================

class TestAnnouncementResponse:
    """공지사항 응답 모델 테스트."""

    def test_response_model(self):
        """응답 모델 필드 검증."""
        from app.api.announcements import AnnouncementResponse

        response = AnnouncementResponse(
            id="test-id",
            title="테스트",
            content="내용",
            announcement_type="notice",
            priority="normal",
            target="all",
            target_room_id=None,
            start_time=None,
            end_time=None,
            scheduled_at=None,
            broadcasted_at=None,
            broadcast_count=0,
            created_by="admin-id",
            created_at="2026-01-17T00:00:00",
            updated_at="2026-01-17T00:00:00",
            is_active=True,
        )
        assert response.id == "test-id"
        assert response.is_active is True


class TestPaginatedAnnouncements:
    """페이지네이션 응답 테스트."""

    def test_pagination_model(self):
        """페이지네이션 모델 검증."""
        from app.api.announcements import PaginatedAnnouncements, AnnouncementResponse

        response = PaginatedAnnouncements(
            items=[],
            total=0,
            page=1,
            page_size=20,
            total_pages=1,
        )
        assert response.total == 0
        assert response.total_pages == 1


# ============================================================================
# Broadcast Response Tests
# ============================================================================

class TestBroadcastResponse:
    """브로드캐스트 응답 테스트."""

    def test_broadcast_success_response(self):
        """브로드캐스트 성공 응답."""
        from app.api.announcements import BroadcastResponse

        response = BroadcastResponse(
            success=True,
            channel="lobby",
            broadcast_count=1,
        )
        assert response.success is True
        assert response.channel == "lobby"

    def test_broadcast_error_response(self):
        """브로드캐스트 실패 응답."""
        from app.api.announcements import BroadcastResponse

        response = BroadcastResponse(
            success=False,
            error="Redis 연결 실패",
        )
        assert response.success is False
        assert response.error == "Redis 연결 실패"


# ============================================================================
# Type List Endpoint Tests
# ============================================================================

class TestTypeListEndpoint:
    """유형 목록 엔드포인트 테스트."""

    def test_announcement_types_enum(self):
        """공지사항 유형 Enum 값 확인."""
        types = [t.value for t in AnnouncementType]
        assert "notice" in types
        assert "event" in types
        assert "maintenance" in types
        assert "urgent" in types

    def test_priority_enum(self):
        """우선순위 Enum 값 확인."""
        priorities = [p.value for p in AnnouncementPriority]
        assert "low" in priorities
        assert "normal" in priorities
        assert "high" in priorities
        assert "critical" in priorities

    def test_target_enum(self):
        """대상 Enum 값 확인."""
        targets = [t.value for t in AnnouncementTarget]
        assert "all" in targets
        assert "vip" in targets
        assert "specific_room" in targets


# ============================================================================
# Redis Dependency Tests
# ============================================================================

class TestRedisDependency:
    """Redis 의존성 테스트."""

    @pytest.mark.asyncio
    async def test_get_redis_returns_client(self):
        """Redis 클라이언트 반환 테스트."""
        from app.api.announcements import get_redis

        with patch("app.api.announcements.Redis") as MockRedis:
            mock_client = MagicMock()
            MockRedis.from_url.return_value = mock_client

            # 첫 호출 시 새 클라이언트 생성
            # (실제로는 global 변수라 테스트에서 격리 필요)
