"""서버 점검 모드 미들웨어.

점검 모드 활성화 시 신규 요청을 차단하고 503 응답을 반환합니다.
기존 WebSocket 연결은 유지되며, 새로운 연결만 차단됩니다.
"""

import json
import logging
from typing import Callable, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Redis 키 (admin-backend의 maintenance_service.py와 동일)
MAINTENANCE_MODE_KEY = "system:maintenance_mode"


class MaintenanceMiddleware(BaseHTTPMiddleware):
    """점검 모드 미들웨어.

    점검 모드 활성화 시:
    - HTTP 요청: 503 Service Unavailable 응답
    - WebSocket 신규 연결: 별도 처리 (gateway.py에서 처리)
    - 예외 경로: /health, /metrics, /docs 등은 허용
    """

    # 점검 모드에서도 허용되는 경로
    EXEMPT_PATHS: set[str] = {
        "/health",
        "/health/live",
        "/health/ready",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    def __init__(self, app: Callable, redis_client=None):
        """Initialize maintenance middleware.

        Args:
            app: ASGI application
            redis_client: Redis client instance (optional)
        """
        super().__init__(app)
        self._redis = redis_client

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check maintenance mode before processing request."""
        # Skip WebSocket upgrade requests - handled separately in gateway.py
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        # Skip if Redis not available
        if self._redis is None:
            return await call_next(request)

        # Skip exempt paths
        path = request.url.path
        if self._is_exempt_path(path):
            return await call_next(request)

        # Check maintenance mode
        try:
            is_maintenance, message = await self._check_maintenance_mode()

            if is_maintenance:
                logger.info(f"점검 모드로 요청 차단: {request.method} {path}")
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": {
                            "code": "SERVICE_UNAVAILABLE",
                            "message": message or "서버 점검 중입니다. 잠시 후 다시 시도해주세요.",
                        }
                    },
                    headers={
                        "Retry-After": "300",  # 5분 후 재시도 권장
                    },
                )
        except Exception as e:
            # Redis 오류 시 요청 허용 (fail-open)
            logger.warning(f"점검 모드 확인 실패, 요청 허용: {e}")

        return await call_next(request)

    def _is_exempt_path(self, path: str) -> bool:
        """Check if path is exempt from maintenance mode.

        Args:
            path: Request path

        Returns:
            True if exempt, False otherwise
        """
        # Exact match
        if path in self.EXEMPT_PATHS:
            return True

        # Prefix match for /health/* paths
        if path.startswith("/health"):
            return True

        return False

    async def _check_maintenance_mode(self) -> tuple[bool, Optional[str]]:
        """Check if maintenance mode is enabled.

        Returns:
            Tuple of (is_enabled, message)
        """
        try:
            data = await self._redis.get(MAINTENANCE_MODE_KEY)
            if data:
                parsed = json.loads(data)
                is_enabled = parsed.get("enabled", False)
                message = parsed.get("message", "")
                return is_enabled, message
        except Exception as e:
            logger.warning(f"점검 모드 상태 조회 실패: {e}")

        return False, None


async def check_maintenance_mode_for_websocket(redis_client) -> tuple[bool, Optional[str]]:
    """WebSocket 연결 시 점검 모드 확인.

    gateway.py에서 WebSocket 연결 수락 전에 호출됩니다.

    Args:
        redis_client: Redis client instance

    Returns:
        Tuple of (is_enabled, message)
    """
    if redis_client is None:
        return False, None

    try:
        data = await redis_client.get(MAINTENANCE_MODE_KEY)
        if data:
            parsed = json.loads(data)
            is_enabled = parsed.get("enabled", False)
            message = parsed.get("message", "")
            return is_enabled, message
    except Exception as e:
        logger.warning(f"WebSocket 점검 모드 확인 실패: {e}")

    return False, None
