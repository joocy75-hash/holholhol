"""
Room API Tests - 방 관리 API 테스트

**Validates: Phase 3.3 - 방 강제 종료 기능**
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.admin_user import AdminRole
from app.utils.dependencies import get_current_user, require_supervisor


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture
def mock_supervisor_user():
    """Mock supervisor user."""
    user = MagicMock()
    user.id = str(uuid4())
    user.username = "supervisor"
    user.email = "supervisor@test.com"
    user.role = AdminRole.supervisor
    user.is_active = True
    return user


@pytest.fixture
def mock_admin_user():
    """Mock admin user."""
    user = MagicMock()
    user.id = str(uuid4())
    user.username = "admin"
    user.email = "admin@test.com"
    user.role = AdminRole.admin
    user.is_active = True
    return user


@pytest.fixture
def mock_viewer_user():
    """Mock viewer user (no force-close permission)."""
    user = MagicMock()
    user.id = str(uuid4())
    user.username = "viewer"
    user.email = "viewer@test.com"
    user.role = AdminRole.viewer
    user.is_active = True
    return user


@pytest.fixture
def mock_operator_user():
    """Mock operator user (no force-close permission)."""
    user = MagicMock()
    user.id = str(uuid4())
    user.username = "operator"
    user.email = "operator@test.com"
    user.role = AdminRole.operator
    user.is_active = True
    return user


@pytest.fixture
def sample_force_close_response():
    """Sample successful force close response from Game Backend."""
    return {
        "success": True,
        "room_id": "room-123",
        "room_name": "테스트 방",
        "reason": "관리자 강제 종료",
        "refunds": [
            {"user_id": "user-1", "nickname": "Player1", "amount": 5000, "seat": 0},
            {"user_id": "user-2", "nickname": "Player2", "amount": 3000, "seat": 2},
        ],
        "total_refunded": 8000,
        "players_affected": 2,
    }


# ============================================================================
# POST /api/rooms/{room_id}/force-close Tests
# ============================================================================


class TestForceCloseRoom:
    """POST /api/rooms/{room_id}/force-close 테스트."""

    def test_force_close_success_as_supervisor(
        self, client, mock_supervisor_user, sample_force_close_response
    ):
        """Supervisor 권한으로 방 강제 종료 성공."""
        room_id = "room-123"

        app.dependency_overrides[require_supervisor] = lambda: mock_supervisor_user

        try:
            with patch("app.api.rooms._call_game_backend") as mock_call:
                mock_call.return_value = sample_force_close_response

                response = client.post(
                    f"/api/rooms/{room_id}/force-close",
                    json={"reason": "관리자 강제 종료"},
                    headers={"Authorization": "Bearer test-token"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["roomId"] == room_id
            assert data["totalRefunded"] == 8000
            assert data["playersAffected"] == 2
            assert len(data["refunds"]) == 2
        finally:
            app.dependency_overrides.clear()

    def test_force_close_success_as_admin(
        self, client, mock_admin_user, sample_force_close_response
    ):
        """Admin 권한으로 방 강제 종료 성공."""
        room_id = "room-456"

        app.dependency_overrides[require_supervisor] = lambda: mock_admin_user

        try:
            with patch("app.api.rooms._call_game_backend") as mock_call:
                mock_call.return_value = sample_force_close_response

                response = client.post(
                    f"/api/rooms/{room_id}/force-close",
                    json={"reason": "긴급 점검"},
                    headers={"Authorization": "Bearer test-token"},
                )

            assert response.status_code == 200
            assert response.json()["success"] is True
        finally:
            app.dependency_overrides.clear()

    def test_force_close_no_players(self, client, mock_supervisor_user):
        """플레이어가 없는 방 강제 종료."""
        room_id = "empty-room"
        mock_response = {
            "success": True,
            "room_id": room_id,
            "room_name": "빈 방",
            "reason": "테스트",
            "refunds": [],
            "total_refunded": 0,
            "players_affected": 0,
        }

        app.dependency_overrides[require_supervisor] = lambda: mock_supervisor_user

        try:
            with patch("app.api.rooms._call_game_backend") as mock_call:
                mock_call.return_value = mock_response

                response = client.post(
                    f"/api/rooms/{room_id}/force-close",
                    json={"reason": "테스트"},
                    headers={"Authorization": "Bearer test-token"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["totalRefunded"] == 0
            assert data["playersAffected"] == 0
            assert len(data["refunds"]) == 0
        finally:
            app.dependency_overrides.clear()

    def test_force_close_reason_validation(self, client, mock_supervisor_user):
        """사유 필드 유효성 검사."""
        room_id = "room-123"

        app.dependency_overrides[require_supervisor] = lambda: mock_supervisor_user

        try:
            # 빈 사유
            response = client.post(
                f"/api/rooms/{room_id}/force-close",
                json={"reason": ""},
                headers={"Authorization": "Bearer test-token"},
            )
            assert response.status_code == 422

            # 사유 없음
            response = client.post(
                f"/api/rooms/{room_id}/force-close",
                json={},
                headers={"Authorization": "Bearer test-token"},
            )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()


# ============================================================================
# Permission Tests
# ============================================================================


class TestForceClosePermissions:
    """방 강제 종료 권한 테스트."""

    def test_viewer_cannot_force_close(self, client):
        """Viewer는 방 강제 종료 불가 (인증 실패)."""
        room_id = "room-123"

        # 의존성 오버라이드 없이 호출하면 401 반환
        response = client.post(
            f"/api/rooms/{room_id}/force-close",
            json={"reason": "테스트"},
        )

        # 인증 토큰이 없으므로 401 또는 403
        assert response.status_code in [401, 403]

    def test_operator_cannot_force_close_via_permission_check(self, client, mock_operator_user):
        """Operator는 FORCE_CLOSE_ROOM 권한이 없음."""
        room_id = "room-123"

        # require_supervisor가 operator를 반환해도 has_permission 검사에서 실패
        app.dependency_overrides[require_supervisor] = lambda: mock_operator_user

        try:
            with patch("app.api.rooms._call_game_backend") as mock_call:
                mock_call.return_value = {"success": True}

                response = client.post(
                    f"/api/rooms/{room_id}/force-close",
                    json={"reason": "테스트"},
                    headers={"Authorization": "Bearer test-token"},
                )

            # operator는 FORCE_CLOSE_ROOM 권한이 없으므로 403
            assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestForceCloseErrorHandling:
    """방 강제 종료 에러 처리 테스트."""

    def test_room_not_found(self, client, mock_supervisor_user):
        """존재하지 않는 방 강제 종료 시도."""
        room_id = "nonexistent-room"

        app.dependency_overrides[require_supervisor] = lambda: mock_supervisor_user

        try:
            with patch("app.api.rooms._call_game_backend") as mock_call:
                from fastapi import HTTPException

                mock_call.side_effect = HTTPException(
                    status_code=404,
                    detail={"error": {"code": "ROOM_NOT_FOUND", "message": "Room not found"}},
                )

                response = client.post(
                    f"/api/rooms/{room_id}/force-close",
                    json={"reason": "테스트"},
                    headers={"Authorization": "Bearer test-token"},
                )

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_room_already_closed(self, client, mock_supervisor_user):
        """이미 종료된 방 강제 종료 시도."""
        room_id = "closed-room"

        app.dependency_overrides[require_supervisor] = lambda: mock_supervisor_user

        try:
            with patch("app.api.rooms._call_game_backend") as mock_call:
                from fastapi import HTTPException

                mock_call.side_effect = HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "ROOM_ALREADY_CLOSED",
                            "message": "Room is already closed",
                        }
                    },
                )

                response = client.post(
                    f"/api/rooms/{room_id}/force-close",
                    json={"reason": "테스트"},
                    headers={"Authorization": "Bearer test-token"},
                )

            assert response.status_code == 400
        finally:
            app.dependency_overrides.clear()

    def test_game_backend_connection_error(self, client, mock_supervisor_user):
        """Game Backend 연결 실패."""
        room_id = "room-123"

        app.dependency_overrides[require_supervisor] = lambda: mock_supervisor_user

        try:
            with patch("app.api.rooms._call_game_backend") as mock_call:
                from fastapi import HTTPException

                mock_call.side_effect = HTTPException(
                    status_code=502, detail="Game server connection failed"
                )

                response = client.post(
                    f"/api/rooms/{room_id}/force-close",
                    json={"reason": "테스트"},
                    headers={"Authorization": "Bearer test-token"},
                )

            assert response.status_code == 502
        finally:
            app.dependency_overrides.clear()

    def test_game_backend_timeout(self, client, mock_supervisor_user):
        """Game Backend 타임아웃."""
        room_id = "room-123"

        app.dependency_overrides[require_supervisor] = lambda: mock_supervisor_user

        try:
            with patch("app.api.rooms._call_game_backend") as mock_call:
                from fastapi import HTTPException

                mock_call.side_effect = HTTPException(status_code=504, detail="Game server timeout")

                response = client.post(
                    f"/api/rooms/{room_id}/force-close",
                    json={"reason": "테스트"},
                    headers={"Authorization": "Bearer test-token"},
                )

            assert response.status_code == 504
        finally:
            app.dependency_overrides.clear()


# ============================================================================
# _call_game_backend Unit Tests
# ============================================================================


class TestCallGameBackend:
    """_call_game_backend 헬퍼 함수 단위 테스트."""

    @pytest.mark.asyncio
    async def test_successful_post_request(self):
        """POST 요청 성공."""
        from app.api.rooms import _call_game_backend

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await _call_game_backend(method="POST", path="/test", data={"key": "value"})

        assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_timeout_error(self):
        """타임아웃 에러 처리."""
        from app.api.rooms import _call_game_backend
        from fastapi import HTTPException

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.TimeoutException("Timeout")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(HTTPException) as exc_info:
                await _call_game_backend(method="POST", path="/test", data={"key": "value"})

        assert exc_info.value.status_code == 504

    @pytest.mark.asyncio
    async def test_connection_error(self):
        """연결 에러 처리."""
        from app.api.rooms import _call_game_backend
        from fastapi import HTTPException

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(HTTPException) as exc_info:
                await _call_game_backend(method="POST", path="/test", data={"key": "value"})

        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_401_unauthorized(self):
        """API 키 인증 실패."""
        from app.api.rooms import _call_game_backend
        from fastapi import HTTPException

        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(HTTPException) as exc_info:
                await _call_game_backend(method="POST", path="/test", data={"key": "value"})

        assert exc_info.value.status_code == 502
        assert "authentication failed" in exc_info.value.detail


# ============================================================================
# GET /api/rooms Tests
# ============================================================================


class TestListRooms:
    """GET /api/rooms 테스트."""

    def test_list_rooms_viewer_access(self, client, mock_viewer_user):
        """Viewer도 방 목록 조회 가능."""
        app.dependency_overrides[get_current_user] = lambda: mock_viewer_user

        try:
            with patch("app.api.rooms._call_game_backend") as mock_call:
                mock_call.return_value = {
                    "items": [],
                    "total": 0,
                    "page": 1,
                    "pageSize": 20,
                    "totalPages": 0,
                }

                response = client.get(
                    "/api/rooms",
                    headers={"Authorization": "Bearer test-token"},
                )

            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert "page" in data
        finally:
            app.dependency_overrides.clear()

    def test_list_rooms_pagination(self, client, mock_viewer_user):
        """방 목록 페이지네이션."""
        app.dependency_overrides[get_current_user] = lambda: mock_viewer_user

        try:
            with patch("app.api.rooms._call_game_backend") as mock_call:
                mock_call.return_value = {
                    "items": [],
                    "total": 0,
                    "page": 2,
                    "pageSize": 10,
                    "totalPages": 0,
                }

                response = client.get(
                    "/api/rooms?page=2&page_size=10",
                    headers={"Authorization": "Bearer test-token"},
                )

            assert response.status_code == 200
            data = response.json()
            assert data["page"] == 2
            assert data["pageSize"] == 10
        finally:
            app.dependency_overrides.clear()


# ============================================================================
# GET /api/rooms/{room_id} Tests
# ============================================================================


class TestGetRoom:
    """GET /api/rooms/{room_id} 테스트."""

    def test_get_room_not_implemented(self, client, mock_viewer_user):
        """방 상세 조회 (현재 404 반환)."""
        room_id = "room-123"

        app.dependency_overrides[get_current_user] = lambda: mock_viewer_user

        try:
            response = client.get(
                f"/api/rooms/{room_id}",
                headers={"Authorization": "Bearer test-token"},
            )

            # TODO 상태이므로 404 반환
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


# ============================================================================
# POST /api/rooms/{room_id}/message Tests
# ============================================================================


class TestSendSystemMessage:
    """POST /api/rooms/{room_id}/message 테스트."""

    def test_send_message_as_operator(self, client, mock_operator_user):
        """Operator로 시스템 메시지 전송."""
        room_id = "room-123"

        app.dependency_overrides[get_current_user] = lambda: mock_operator_user

        try:
            response = client.post(
                f"/api/rooms/{room_id}/message",
                json={"message": "점검 예정입니다"},
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["roomId"] == room_id
        finally:
            app.dependency_overrides.clear()

    def test_send_message_viewer_forbidden(self, client, mock_viewer_user):
        """Viewer는 시스템 메시지 전송 불가."""
        room_id = "room-123"

        app.dependency_overrides[get_current_user] = lambda: mock_viewer_user

        try:
            response = client.post(
                f"/api/rooms/{room_id}/message",
                json={"message": "테스트"},
                headers={"Authorization": "Bearer test-token"},
            )

            assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()
