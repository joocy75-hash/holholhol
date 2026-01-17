"""시스템 관리 API.

서버 점검 모드, 시스템 설정 등을 관리합니다.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.models.admin_user import AdminUser
from app.utils.dependencies import require_viewer, require_supervisor
from app.services.maintenance_service import (
    get_maintenance_service,
    MaintenanceService,
    MaintenanceStatus,
)

router = APIRouter()


class MaintenanceModeRequest(BaseModel):
    """점검 모드 설정 요청"""
    enabled: bool = Field(..., description="점검 모드 활성화 여부")
    message: str = Field(
        default="서버 점검 중입니다. 잠시 후 다시 시도해주세요.",
        description="점검 안내 메시지",
        max_length=500,
    )
    end_time: Optional[str] = Field(
        default=None,
        description="예상 종료 시간 (ISO 8601 format, e.g. 2026-01-17T15:00:00Z)",
    )


class MaintenanceStatusResponse(BaseModel):
    """점검 모드 상태 응답"""
    enabled: bool
    message: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    started_by: Optional[str] = None

    class Config:
        from_attributes = True


class SystemHealthResponse(BaseModel):
    """시스템 상태 응답"""
    status: str
    maintenance_mode: bool
    timestamp: str


@router.get("/maintenance", response_model=MaintenanceStatusResponse)
async def get_maintenance_status(
    _: AdminUser = Depends(require_viewer),
):
    """점검 모드 상태 조회

    모든 관리자가 조회할 수 있습니다.

    Returns:
        MaintenanceStatusResponse: 현재 점검 모드 상태
    """
    service = await get_maintenance_service()
    status = await service.get_status()

    return MaintenanceStatusResponse(
        enabled=status.enabled,
        message=status.message,
        start_time=status.start_time,
        end_time=status.end_time,
        started_by=status.started_by,
    )


@router.post("/maintenance", response_model=MaintenanceStatusResponse)
async def set_maintenance_mode(
    request: MaintenanceModeRequest,
    current_user: AdminUser = Depends(require_supervisor),
):
    """점검 모드 설정

    supervisor 이상의 권한이 필요합니다.

    Args:
        request: 점검 모드 설정 요청
        current_user: 현재 로그인한 관리자

    Returns:
        MaintenanceStatusResponse: 업데이트된 점검 모드 상태
    """
    service = await get_maintenance_service()

    if request.enabled:
        # 점검 모드 활성화
        status = await service.enable_maintenance(
            message=request.message,
            end_time=request.end_time,
            started_by=current_user.id,
        )
    else:
        # 점검 모드 비활성화
        status = await service.disable_maintenance()

    return MaintenanceStatusResponse(
        enabled=status.enabled,
        message=status.message,
        start_time=status.start_time,
        end_time=status.end_time,
        started_by=status.started_by,
    )


@router.get("/health", response_model=SystemHealthResponse)
async def system_health():
    """시스템 상태 확인 (인증 불필요)

    점검 모드 여부와 기본적인 시스템 상태를 반환합니다.
    로드밸런서 헬스체크 등에 사용됩니다.

    Returns:
        SystemHealthResponse: 시스템 상태
    """
    try:
        service = await get_maintenance_service()
        maintenance_status = await service.get_status()

        return SystemHealthResponse(
            status="ok" if not maintenance_status.enabled else "maintenance",
            maintenance_mode=maintenance_status.enabled,
            timestamp=datetime.utcnow().isoformat(),
        )
    except Exception:
        return SystemHealthResponse(
            status="ok",
            maintenance_mode=False,
            timestamp=datetime.utcnow().isoformat(),
        )
