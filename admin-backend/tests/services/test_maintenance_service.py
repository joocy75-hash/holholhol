"""
Maintenance Service Tests - 점검 모드 서비스 테스트

**Validates: Phase 3.1 - 서버 점검 모드 제어**
"""
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import pytest

from app.services.maintenance_service import (
    MaintenanceService,
    MaintenanceStatus,
    MAINTENANCE_MODE_KEY,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    return AsyncMock()


@pytest.fixture
def maintenance_service(mock_redis):
    """Create MaintenanceService with mock Redis."""
    return MaintenanceService(mock_redis)


# ============================================================================
# MaintenanceStatus Model Tests
# ============================================================================

class TestMaintenanceStatus:
    """MaintenanceStatus 모델 테스트."""

    def test_default_status(self):
        """기본 상태는 비활성화."""
        status = MaintenanceStatus()
        assert status.enabled is False
        assert status.message == ""
        assert status.start_time is None
        assert status.end_time is None
        assert status.started_by is None

    def test_enabled_status(self):
        """활성화 상태 생성."""
        now = datetime.now(timezone.utc).isoformat()
        status = MaintenanceStatus(
            enabled=True,
            message="점검 중입니다.",
            start_time=now,
            started_by="admin-123",
        )
        assert status.enabled is True
        assert status.message == "점검 중입니다."
        assert status.start_time == now
        assert status.started_by == "admin-123"

    def test_json_serialization(self):
        """JSON 직렬화 테스트."""
        status = MaintenanceStatus(
            enabled=True,
            message="서버 점검",
        )
        json_str = status.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["enabled"] is True
        assert parsed["message"] == "서버 점검"


# ============================================================================
# MaintenanceService Tests
# ============================================================================

class TestMaintenanceService:
    """MaintenanceService 테스트."""

    @pytest.mark.asyncio
    async def test_get_status_when_not_set(self, maintenance_service, mock_redis):
        """점검 모드가 설정되지 않은 경우 비활성화 상태 반환."""
        mock_redis.get.return_value = None

        status = await maintenance_service.get_status()

        assert status.enabled is False
        mock_redis.get.assert_called_once_with(MAINTENANCE_MODE_KEY)

    @pytest.mark.asyncio
    async def test_get_status_when_enabled(self, maintenance_service, mock_redis):
        """점검 모드가 활성화된 경우 상태 반환."""
        stored_data = json.dumps({
            "enabled": True,
            "message": "서버 점검 중",
            "start_time": "2026-01-17T10:00:00Z",
            "started_by": "admin-123",
        })
        mock_redis.get.return_value = stored_data

        status = await maintenance_service.get_status()

        assert status.enabled is True
        assert status.message == "서버 점검 중"
        assert status.start_time == "2026-01-17T10:00:00Z"
        assert status.started_by == "admin-123"

    @pytest.mark.asyncio
    async def test_get_status_redis_error(self, maintenance_service, mock_redis):
        """Redis 오류 시 비활성화 상태 반환."""
        mock_redis.get.side_effect = Exception("Redis connection error")

        status = await maintenance_service.get_status()

        assert status.enabled is False

    @pytest.mark.asyncio
    async def test_is_maintenance_mode_true(self, maintenance_service, mock_redis):
        """점검 모드 활성화 확인."""
        mock_redis.get.return_value = json.dumps({"enabled": True, "message": ""})

        result = await maintenance_service.is_maintenance_mode()

        assert result is True

    @pytest.mark.asyncio
    async def test_is_maintenance_mode_false(self, maintenance_service, mock_redis):
        """점검 모드 비활성화 확인."""
        mock_redis.get.return_value = None

        result = await maintenance_service.is_maintenance_mode()

        assert result is False

    @pytest.mark.asyncio
    async def test_enable_maintenance(self, maintenance_service, mock_redis):
        """점검 모드 활성화."""
        status = await maintenance_service.enable_maintenance(
            message="긴급 점검",
            end_time="2026-01-17T12:00:00Z",
            started_by="admin-456",
        )

        assert status.enabled is True
        assert status.message == "긴급 점검"
        assert status.end_time == "2026-01-17T12:00:00Z"
        assert status.started_by == "admin-456"
        assert status.start_time is not None

        # Redis에 저장 확인
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == MAINTENANCE_MODE_KEY

    @pytest.mark.asyncio
    async def test_disable_maintenance(self, maintenance_service, mock_redis):
        """점검 모드 비활성화."""
        status = await maintenance_service.disable_maintenance()

        assert status.enabled is False
        mock_redis.set.assert_called_once()


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestMaintenanceServiceEdgeCases:
    """경계 조건 테스트."""

    @pytest.mark.asyncio
    async def test_get_status_invalid_json(self, maintenance_service, mock_redis):
        """잘못된 JSON 데이터 처리."""
        mock_redis.get.return_value = "invalid json"

        status = await maintenance_service.get_status()

        # 오류 시 비활성화 상태 반환
        assert status.enabled is False

    @pytest.mark.asyncio
    async def test_enable_with_empty_message(self, maintenance_service, mock_redis):
        """빈 메시지로 활성화."""
        status = await maintenance_service.enable_maintenance(
            message="",
            started_by="admin",
        )

        assert status.enabled is True
        assert status.message == ""

    @pytest.mark.asyncio
    async def test_enable_with_long_message(self, maintenance_service, mock_redis):
        """긴 메시지로 활성화."""
        long_message = "점검" * 100
        status = await maintenance_service.enable_maintenance(
            message=long_message,
            started_by="admin",
        )

        assert status.enabled is True
        assert status.message == long_message
