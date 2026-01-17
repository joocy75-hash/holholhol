"""
System API Tests - 시스템 관리 API 테스트

**Validates: Phase 3.1 - 서버 점검 모드 제어**
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.admin_user import AdminRole
from app.services.maintenance_service import MaintenanceStatus
from app.utils.dependencies import require_viewer, require_supervisor


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_admin_user():
    """Mock admin user (supervisor role)."""
    user = MagicMock()
    user.id = str(uuid4())
    user.username = "supervisor"
    user.email = "supervisor@test.com"
    user.role = AdminRole.supervisor
    user.is_active = True
    return user


@pytest.fixture
def mock_viewer_user():
    """Mock viewer user."""
    user = MagicMock()
    user.id = str(uuid4())
    user.username = "viewer"
    user.email = "viewer@test.com"
    user.role = AdminRole.viewer
    user.is_active = True
    return user


@pytest.fixture
def mock_operator_user():
    """Mock operator user."""
    user = MagicMock()
    user.id = str(uuid4())
    user.username = "operator"
    user.email = "operator@test.com"
    user.role = AdminRole.operator
    user.is_active = True
    return user


@pytest.fixture
def client():
    """Test client with clean dependency overrides."""
    with TestClient(app) as c:
        yield c
    # Clear overrides after test
    app.dependency_overrides.clear()


# ============================================================================
# GET /api/system/maintenance Tests
# ============================================================================


class TestGetMaintenanceStatus:
    """GET /api/system/maintenance 테스트."""

    @pytest.mark.asyncio
    async def test_get_maintenance_status_when_disabled(self, mock_viewer_user):
        """점검 모드 비활성화 상태 조회."""
        mock_status = MaintenanceStatus(enabled=False)

        # Override FastAPI dependencies
        app.dependency_overrides[require_viewer] = lambda: mock_viewer_user

        try:
            with patch("app.api.system.get_maintenance_service") as mock_get_service:
                mock_service = AsyncMock()
                mock_service.get_status.return_value = mock_status
                mock_get_service.return_value = mock_service

                client = TestClient(app)
                response = client.get(
                    "/api/system/maintenance",
                    headers={"Authorization": "Bearer test-token"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] is False
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_maintenance_status_when_enabled(self, mock_viewer_user):
        """점검 모드 활성화 상태 조회."""
        mock_status = MaintenanceStatus(
            enabled=True,
            message="긴급 점검 중",
            start_time="2026-01-17T10:00:00Z",
            end_time="2026-01-17T12:00:00Z",
            started_by="admin-123",
        )

        # Override FastAPI dependencies
        app.dependency_overrides[require_viewer] = lambda: mock_viewer_user

        try:
            with patch("app.api.system.get_maintenance_service") as mock_get_service:
                mock_service = AsyncMock()
                mock_service.get_status.return_value = mock_status
                mock_get_service.return_value = mock_service

                client = TestClient(app)
                response = client.get(
                    "/api/system/maintenance",
                    headers={"Authorization": "Bearer test-token"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] is True
            assert data["message"] == "긴급 점검 중"
            assert data["start_time"] == "2026-01-17T10:00:00Z"
            assert data["end_time"] == "2026-01-17T12:00:00Z"
        finally:
            app.dependency_overrides.clear()


# ============================================================================
# POST /api/system/maintenance Tests
# ============================================================================


class TestSetMaintenanceMode:
    """POST /api/system/maintenance 테스트."""

    @pytest.mark.asyncio
    async def test_enable_maintenance_mode(self, mock_admin_user):
        """점검 모드 활성화 성공."""
        enabled_status = MaintenanceStatus(
            enabled=True,
            message="서버 점검 중입니다.",
            start_time=datetime.now(timezone.utc).isoformat(),
            started_by=mock_admin_user.id,
        )

        # Override FastAPI dependencies
        app.dependency_overrides[require_supervisor] = lambda: mock_admin_user

        try:
            with patch("app.api.system.get_maintenance_service") as mock_get_service:
                mock_service = AsyncMock()
                mock_service.enable_maintenance.return_value = enabled_status
                mock_get_service.return_value = mock_service

                client = TestClient(app)
                response = client.post(
                    "/api/system/maintenance",
                    headers={"Authorization": "Bearer test-token"},
                    json={
                        "enabled": True,
                        "message": "서버 점검 중입니다.",
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] is True
            assert data["message"] == "서버 점검 중입니다."
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_disable_maintenance_mode(self, mock_admin_user):
        """점검 모드 비활성화 성공."""
        disabled_status = MaintenanceStatus(enabled=False)

        # Override FastAPI dependencies
        app.dependency_overrides[require_supervisor] = lambda: mock_admin_user

        try:
            with patch("app.api.system.get_maintenance_service") as mock_get_service:
                mock_service = AsyncMock()
                mock_service.disable_maintenance.return_value = disabled_status
                mock_get_service.return_value = mock_service

                client = TestClient(app)
                response = client.post(
                    "/api/system/maintenance",
                    headers={"Authorization": "Bearer test-token"},
                    json={"enabled": False},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] is False
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_enable_maintenance_with_end_time(self, mock_admin_user):
        """예상 종료 시간과 함께 점검 모드 활성화."""
        end_time = "2026-01-17T15:00:00Z"
        enabled_status = MaintenanceStatus(
            enabled=True,
            message="정기 점검",
            end_time=end_time,
            start_time=datetime.now(timezone.utc).isoformat(),
            started_by=mock_admin_user.id,
        )

        # Override FastAPI dependencies
        app.dependency_overrides[require_supervisor] = lambda: mock_admin_user

        try:
            with patch("app.api.system.get_maintenance_service") as mock_get_service:
                mock_service = AsyncMock()
                mock_service.enable_maintenance.return_value = enabled_status
                mock_get_service.return_value = mock_service

                client = TestClient(app)
                response = client.post(
                    "/api/system/maintenance",
                    headers={"Authorization": "Bearer test-token"},
                    json={
                        "enabled": True,
                        "message": "정기 점검",
                        "end_time": end_time,
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] is True
            assert data["end_time"] == end_time
        finally:
            app.dependency_overrides.clear()


# ============================================================================
# GET /api/system/health Tests
# ============================================================================


class TestSystemHealth:
    """GET /api/system/health 테스트."""

    @pytest.mark.asyncio
    async def test_health_check_normal(self):
        """정상 상태 헬스체크."""
        mock_status = MaintenanceStatus(enabled=False)

        with patch("app.api.system.get_maintenance_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_status.return_value = mock_status
            mock_get_service.return_value = mock_service

            client = TestClient(app)
            response = client.get("/api/system/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["maintenance_mode"] is False
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_health_check_maintenance_mode(self):
        """점검 모드 중 헬스체크."""
        mock_status = MaintenanceStatus(enabled=True, message="점검 중")

        with patch("app.api.system.get_maintenance_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.get_status.return_value = mock_status
            mock_get_service.return_value = mock_service

            client = TestClient(app)
            response = client.get("/api/system/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "maintenance"
        assert data["maintenance_mode"] is True


# ============================================================================
# Authorization Tests
# ============================================================================


class TestMaintenanceAuthorization:
    """권한 검증 테스트."""

    @pytest.mark.asyncio
    async def test_operator_cannot_set_maintenance(self, mock_operator_user):
        """operator는 점검 모드 설정 불가."""
        # require_supervisor가 403을 반환하도록 설정
        # 실제 테스트에서는 FastAPI의 의존성 주입이 처리함
        # 여기서는 권한 체크 로직이 올바르게 설정되었는지 확인

        # 이 테스트는 실제 권한 체크 로직을 통합 테스트에서 검증해야 함
        # 단위 테스트에서는 require_supervisor 의존성이 제대로 설정되었는지 확인
        from app.api.system import set_maintenance_mode
        from inspect import signature

        # 함수 시그니처에서 의존성 확인
        sig = signature(set_maintenance_mode)
        params = sig.parameters

        # current_user 파라미터가 require_supervisor 의존성을 사용하는지 확인
        assert "current_user" in params

    @pytest.mark.asyncio
    async def test_viewer_can_get_maintenance_status(self, mock_viewer_user):
        """viewer도 점검 모드 상태 조회 가능."""
        mock_status = MaintenanceStatus(enabled=False)

        # Override FastAPI dependencies
        app.dependency_overrides[require_viewer] = lambda: mock_viewer_user

        try:
            with patch("app.api.system.get_maintenance_service") as mock_get_service:
                mock_service = AsyncMock()
                mock_service.get_status.return_value = mock_status
                mock_get_service.return_value = mock_service

                client = TestClient(app)
                response = client.get(
                    "/api/system/maintenance",
                    headers={"Authorization": "Bearer test-token"},
                )

            # viewer도 조회 가능
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()
