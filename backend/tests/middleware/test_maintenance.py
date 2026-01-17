"""
Maintenance Middleware Tests - 점검 모드 미들웨어 테스트

**Validates: Phase 3.1 - 서버 점검 모드 제어 (게임 서버)**
"""
import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.maintenance import (
    MaintenanceMiddleware,
    check_maintenance_mode_for_websocket,
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
def app_with_middleware(mock_redis):
    """Create FastAPI app with MaintenanceMiddleware."""
    app = FastAPI()
    app.add_middleware(MaintenanceMiddleware, redis_client=mock_redis)

    @app.get("/api/v1/test")
    async def test_endpoint():
        return {"status": "ok"}

    @app.get("/health")
    async def health_endpoint():
        return {"status": "healthy"}

    @app.get("/health/live")
    async def liveness_endpoint():
        return {"status": "alive"}

    @app.get("/metrics")
    async def metrics_endpoint():
        return {"metrics": "data"}

    @app.get("/docs")
    async def docs_endpoint():
        return {"docs": "data"}

    return app


# ============================================================================
# MaintenanceMiddleware Tests
# ============================================================================

class TestMaintenanceMiddleware:
    """MaintenanceMiddleware 테스트."""

    @pytest.mark.asyncio
    async def test_request_allowed_when_maintenance_disabled(
        self, app_with_middleware, mock_redis
    ):
        """점검 모드 비활성화 시 요청 허용."""
        mock_redis.get.return_value = json.dumps({"enabled": False})

        client = TestClient(app_with_middleware)
        response = client.get("/api/v1/test")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_request_blocked_when_maintenance_enabled(
        self, app_with_middleware, mock_redis
    ):
        """점검 모드 활성화 시 요청 차단 (503)."""
        mock_redis.get.return_value = json.dumps({
            "enabled": True,
            "message": "서버 점검 중입니다.",
        })

        client = TestClient(app_with_middleware)
        response = client.get("/api/v1/test")

        assert response.status_code == 503
        data = response.json()
        assert data["error"]["code"] == "SERVICE_UNAVAILABLE"
        assert "점검" in data["error"]["message"]
        assert response.headers.get("Retry-After") == "300"

    @pytest.mark.asyncio
    async def test_health_endpoint_allowed_during_maintenance(
        self, app_with_middleware, mock_redis
    ):
        """점검 모드 중에도 /health 엔드포인트 허용."""
        mock_redis.get.return_value = json.dumps({"enabled": True})

        client = TestClient(app_with_middleware)
        response = client.get("/health")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_liveness_endpoint_allowed_during_maintenance(
        self, app_with_middleware, mock_redis
    ):
        """점검 모드 중에도 /health/live 엔드포인트 허용."""
        mock_redis.get.return_value = json.dumps({"enabled": True})

        client = TestClient(app_with_middleware)
        response = client.get("/health/live")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_metrics_endpoint_allowed_during_maintenance(
        self, app_with_middleware, mock_redis
    ):
        """점검 모드 중에도 /metrics 엔드포인트 허용."""
        mock_redis.get.return_value = json.dumps({"enabled": True})

        client = TestClient(app_with_middleware)
        response = client.get("/metrics")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_docs_endpoint_allowed_during_maintenance(
        self, app_with_middleware, mock_redis
    ):
        """점검 모드 중에도 /docs 엔드포인트 허용."""
        mock_redis.get.return_value = json.dumps({"enabled": True})

        client = TestClient(app_with_middleware)
        response = client.get("/docs")

        assert response.status_code == 200


# ============================================================================
# Fail-Open Tests
# ============================================================================

class TestMaintenanceMiddlewareFailOpen:
    """장애 시 요청 허용 (fail-open) 테스트."""

    @pytest.mark.asyncio
    async def test_request_allowed_when_redis_error(
        self, app_with_middleware, mock_redis
    ):
        """Redis 오류 시 요청 허용."""
        mock_redis.get.side_effect = Exception("Redis connection error")

        client = TestClient(app_with_middleware)
        response = client.get("/api/v1/test")

        # Redis 오류 시에도 요청 허용 (fail-open)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_request_allowed_when_redis_none(self):
        """Redis 클라이언트가 None인 경우 요청 허용."""
        app = FastAPI()
        app.add_middleware(MaintenanceMiddleware, redis_client=None)

        @app.get("/api/v1/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/api/v1/test")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_request_allowed_when_invalid_json(
        self, app_with_middleware, mock_redis
    ):
        """잘못된 JSON 데이터인 경우 요청 허용."""
        mock_redis.get.return_value = "invalid json"

        client = TestClient(app_with_middleware)
        response = client.get("/api/v1/test")

        # 파싱 오류 시에도 요청 허용
        assert response.status_code == 200


# ============================================================================
# WebSocket Maintenance Check Tests
# ============================================================================

class TestWebSocketMaintenanceCheck:
    """WebSocket 점검 모드 체크 테스트."""

    @pytest.mark.asyncio
    async def test_check_returns_false_when_disabled(self, mock_redis):
        """점검 모드 비활성화 시 False 반환."""
        mock_redis.get.return_value = json.dumps({"enabled": False})

        is_maintenance, message = await check_maintenance_mode_for_websocket(mock_redis)

        assert is_maintenance is False
        assert message is None or message == ""

    @pytest.mark.asyncio
    async def test_check_returns_true_when_enabled(self, mock_redis):
        """점검 모드 활성화 시 True와 메시지 반환."""
        mock_redis.get.return_value = json.dumps({
            "enabled": True,
            "message": "긴급 점검",
        })

        is_maintenance, message = await check_maintenance_mode_for_websocket(mock_redis)

        assert is_maintenance is True
        assert message == "긴급 점검"

    @pytest.mark.asyncio
    async def test_check_returns_false_when_redis_none(self):
        """Redis 클라이언트가 None인 경우 False 반환."""
        is_maintenance, message = await check_maintenance_mode_for_websocket(None)

        assert is_maintenance is False
        assert message is None

    @pytest.mark.asyncio
    async def test_check_returns_false_when_redis_error(self, mock_redis):
        """Redis 오류 시 False 반환."""
        mock_redis.get.side_effect = Exception("Redis error")

        is_maintenance, message = await check_maintenance_mode_for_websocket(mock_redis)

        assert is_maintenance is False

    @pytest.mark.asyncio
    async def test_check_returns_false_when_not_set(self, mock_redis):
        """점검 모드가 설정되지 않은 경우 False 반환."""
        mock_redis.get.return_value = None

        is_maintenance, message = await check_maintenance_mode_for_websocket(mock_redis)

        assert is_maintenance is False


# ============================================================================
# Custom Message Tests
# ============================================================================

class TestMaintenanceCustomMessage:
    """커스텀 메시지 테스트."""

    @pytest.mark.asyncio
    async def test_custom_maintenance_message(self, app_with_middleware, mock_redis):
        """커스텀 점검 메시지 반환."""
        custom_message = "긴급 보안 패치를 적용 중입니다."
        mock_redis.get.return_value = json.dumps({
            "enabled": True,
            "message": custom_message,
        })

        client = TestClient(app_with_middleware)
        response = client.get("/api/v1/test")

        assert response.status_code == 503
        data = response.json()
        assert data["error"]["message"] == custom_message

    @pytest.mark.asyncio
    async def test_empty_message_uses_default(self, app_with_middleware, mock_redis):
        """빈 메시지인 경우 기본 메시지 사용."""
        mock_redis.get.return_value = json.dumps({
            "enabled": True,
            "message": "",
        })

        client = TestClient(app_with_middleware)
        response = client.get("/api/v1/test")

        assert response.status_code == 503
        data = response.json()
        # 기본 메시지 확인
        assert "점검" in data["error"]["message"] or "서버" in data["error"]["message"]
