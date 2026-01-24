"""Admin Backend API 클라이언트 (쪽지 시스템 연동용).

Room 관리, Crypto 입출금과 동일한 HTTP API 패턴을 사용합니다.
"""
import logging
from typing import Optional

import httpx
from fastapi import HTTPException, status

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def call_admin_backend(
    method: str,
    path: str,
    data: Optional[dict] = None,
    params: Optional[dict] = None,
) -> dict:
    """Admin Backend API 호출 (서비스 분리 패턴).

    Args:
        method: HTTP 메서드 (GET, POST, DELETE 등)
        path: API 경로 (/api/v1/internal/messages/...)
        data: 요청 바디 (POST에서 사용)
        params: 쿼리 파라미터 (GET에서 사용)

    Returns:
        API 응답 JSON

    Raises:
        HTTPException: API 호출 실패 시

    Note:
        - Room 관리 (admin-backend/app/api/rooms.py) 패턴 참고
        - Timeout: 10초 (쪽지 조회는 빠르게 처리되어야 함)
        - X-API-Key 헤더로 인증 (INTERNAL_API_KEY 사용)
    """
    # ADMIN_BACKEND_URL 환경변수 (기본값: http://localhost:8001)
    admin_url = getattr(settings, "admin_backend_url", "http://localhost:8001")
    url = f"{admin_url}{path}"

    # Admin Backend는 INTERNAL_API_KEY로 Game Backend 인증
    # (admin-backend/app/config.py:32-35의 main_api_key와 동일)
    headers = {"X-API-Key": settings.internal_api_key}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if method.upper() == "GET":
                response = await client.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                response = await client.post(url, json=data, headers=headers)
            elif method.upper() == "DELETE":
                response = await client.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if response.status_code in (200, 201):
                return response.json()
            elif response.status_code == 401:
                logger.error("Admin Backend API key authentication failed")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Admin server authentication failed",
                )
            elif response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=response.json().get("detail", "리소스를 찾을 수 없습니다"),
                )
            else:
                logger.error(
                    f"Admin Backend API error: {response.status_code} - {response.text}"
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Admin server error",
                )

    except httpx.TimeoutException:
        logger.error(f"Admin Backend API timeout: {url}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Admin server timeout",
        )
    except httpx.RequestError as e:
        logger.error(f"Admin Backend API connection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Admin server connection failed",
        )
