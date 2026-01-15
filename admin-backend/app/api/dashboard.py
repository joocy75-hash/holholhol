"""
Dashboard API - 대시보드 메트릭 및 통계 엔드포인트
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.utils.dependencies import get_current_user, require_viewer
from app.models.admin_user import AdminUser
from app.services.metrics_service import get_metrics_service, MetricsService


router = APIRouter()


# Response Models
class ServerHealthResponse(BaseModel):
    cpu: float
    memory: float
    latency: float
    status: str  # healthy, warning, critical, unknown


class RoomStatsResponse(BaseModel):
    active_rooms: int
    total_players: int
    avg_players_per_room: float


class DashboardSummaryResponse(BaseModel):
    ccu: int
    dau: int
    active_rooms: int
    total_players: int
    server_health: ServerHealthResponse


class CCUHistoryItem(BaseModel):
    timestamp: str
    hour: str
    ccu: int


class DAUHistoryItem(BaseModel):
    date: str
    dau: int


class RoomDistributionItem(BaseModel):
    type: str
    count: int


# Endpoints
@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    current_user: AdminUser = Depends(require_viewer),
):
    """대시보드 요약 데이터 조회"""
    service = await get_metrics_service()
    data = await service.get_dashboard_summary()
    
    return DashboardSummaryResponse(
        ccu=data["ccu"],
        dau=data["dau"],
        active_rooms=data["active_rooms"],
        total_players=data["total_players"],
        server_health=ServerHealthResponse(**data["server_health"])
    )


@router.get("/ccu")
async def get_ccu(
    current_user: AdminUser = Depends(require_viewer),
):
    """현재 동시 접속자 수 조회"""
    service = await get_metrics_service()
    ccu = await service.get_ccu()
    return {"ccu": ccu, "timestamp": datetime.utcnow().isoformat()}


@router.get("/dau")
async def get_dau(
    date: Optional[str] = Query(None, description="조회 날짜 (YYYY-MM-DD)"),
    current_user: AdminUser = Depends(require_viewer),
):
    """일일 활성 사용자 수 조회"""
    service = await get_metrics_service()
    
    target_date = None
    if date:
        target_date = datetime.strptime(date, "%Y-%m-%d")
    
    dau = await service.get_dau(target_date)
    return {
        "dau": dau,
        "date": date or datetime.utcnow().strftime("%Y-%m-%d")
    }


@router.get("/ccu/history", response_model=list[CCUHistoryItem])
async def get_ccu_history(
    hours: int = Query(24, ge=1, le=168, description="조회 시간 범위"),
    current_user: AdminUser = Depends(require_viewer),
):
    """CCU 히스토리 조회"""
    service = await get_metrics_service()
    history = await service.get_ccu_history(hours)
    return [CCUHistoryItem(**item) for item in history]


@router.get("/dau/history", response_model=list[DAUHistoryItem])
async def get_dau_history(
    days: int = Query(30, ge=1, le=365, description="조회 일수"),
    current_user: AdminUser = Depends(require_viewer),
):
    """DAU 히스토리 조회"""
    service = await get_metrics_service()
    history = await service.get_dau_history(days)
    return [DAUHistoryItem(**item) for item in history]


@router.get("/rooms", response_model=RoomStatsResponse)
async def get_room_stats(
    current_user: AdminUser = Depends(require_viewer),
):
    """활성 방 통계 조회"""
    service = await get_metrics_service()
    stats = await service.get_active_rooms()
    return RoomStatsResponse(**stats)


@router.get("/rooms/distribution", response_model=list[RoomDistributionItem])
async def get_room_distribution(
    current_user: AdminUser = Depends(require_viewer),
):
    """방 유형별 분포 조회"""
    service = await get_metrics_service()
    distribution = await service.get_room_distribution()
    return [RoomDistributionItem(**item) for item in distribution]


@router.get("/server/health", response_model=ServerHealthResponse)
async def get_server_health(
    current_user: AdminUser = Depends(require_viewer),
):
    """서버 상태 조회"""
    service = await get_metrics_service()
    health = await service.get_server_health()
    return ServerHealthResponse(**health)
