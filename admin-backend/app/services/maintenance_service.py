"""서버 점검 모드 관리 서비스.

Redis를 사용하여 점검 모드 상태를 저장하고 조회합니다.
게임 서버(backend)와 관리자 서버(admin-backend) 모두에서 사용합니다.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# Redis 키
MAINTENANCE_MODE_KEY = "system:maintenance_mode"


class MaintenanceStatus(BaseModel):
    """점검 모드 상태 모델"""
    enabled: bool = False
    message: str = ""
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    started_by: Optional[str] = None


class MaintenanceService:
    """점검 모드 관리 서비스"""

    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    async def get_status(self) -> MaintenanceStatus:
        """현재 점검 모드 상태 조회

        Returns:
            MaintenanceStatus: 점검 모드 상태 객체
        """
        try:
            data = await self.redis.get(MAINTENANCE_MODE_KEY)
            if data:
                parsed = json.loads(data)
                return MaintenanceStatus(**parsed)
        except Exception as e:
            logger.warning(f"점검 모드 상태 조회 실패: {e}")

        return MaintenanceStatus(enabled=False)

    async def is_maintenance_mode(self) -> bool:
        """점검 모드 활성화 여부 확인

        Returns:
            bool: 점검 모드 활성화 여부
        """
        status = await self.get_status()
        return status.enabled

    async def enable_maintenance(
        self,
        message: str = "서버 점검 중입니다.",
        end_time: Optional[str] = None,
        started_by: Optional[str] = None,
    ) -> MaintenanceStatus:
        """점검 모드 활성화

        Args:
            message: 점검 안내 메시지
            end_time: 예상 종료 시간 (ISO format)
            started_by: 점검 모드 활성화한 관리자 ID

        Returns:
            MaintenanceStatus: 업데이트된 점검 모드 상태
        """
        status = MaintenanceStatus(
            enabled=True,
            message=message,
            start_time=datetime.now(timezone.utc).isoformat(),
            end_time=end_time,
            started_by=started_by,
        )

        await self.redis.set(
            MAINTENANCE_MODE_KEY,
            status.model_dump_json(),
        )

        logger.info(f"점검 모드 활성화: {message} (by {started_by})")
        return status

    async def disable_maintenance(self) -> MaintenanceStatus:
        """점검 모드 비활성화

        Returns:
            MaintenanceStatus: 비활성화된 상태
        """
        status = MaintenanceStatus(enabled=False)

        await self.redis.set(
            MAINTENANCE_MODE_KEY,
            status.model_dump_json(),
        )

        logger.info("점검 모드 비활성화")
        return status


# 싱글톤 인스턴스
_maintenance_service: Optional[MaintenanceService] = None


async def get_maintenance_service() -> MaintenanceService:
    """MaintenanceService 싱글톤 인스턴스 반환"""
    global _maintenance_service

    if _maintenance_service is None:
        from redis.asyncio import Redis
        from app.config import get_settings

        settings = get_settings()
        redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
        _maintenance_service = MaintenanceService(redis_client)

    return _maintenance_service


def init_maintenance_service(redis_client: Redis) -> MaintenanceService:
    """MaintenanceService 초기화 (외부에서 Redis 클라이언트 주입)

    Args:
        redis_client: Redis 클라이언트 인스턴스

    Returns:
        MaintenanceService: 초기화된 서비스 인스턴스
    """
    global _maintenance_service
    _maintenance_service = MaintenanceService(redis_client)
    return _maintenance_service
