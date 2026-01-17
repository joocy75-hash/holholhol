"""
Dashboard API - 대시보드 메트릭 및 통계 엔드포인트

Phase 5: 운영 도구
- 5.1 CCU 실시간 모니터링
- 5.2 DAU/MAU 통계
- 5.3 매출 현황 대시보드
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.utils.dependencies import get_current_user, require_viewer
from app.models.admin_user import AdminUser
from app.services.metrics_service import get_metrics_service, MetricsService
from app.services.statistics_service import StatisticsService
from app.database import get_main_db
from sqlalchemy.ext.asyncio import AsyncSession


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


class MAUHistoryItem(BaseModel):
    month: str
    mau: int


class UserStatisticsSummary(BaseModel):
    ccu: int
    dau: int
    wau: int
    mau: int
    timestamp: str


class RoomDistributionItem(BaseModel):
    type: str
    count: int


# Revenue Response Models
class RevenueSummaryResponse(BaseModel):
    total_rake: float
    total_hands: int
    unique_rooms: int
    period: dict


class DailyRevenueItem(BaseModel):
    date: str
    rake: float
    hands: int


class WeeklyRevenueItem(BaseModel):
    week_start: str
    rake: float
    hands: int


class MonthlyRevenueItem(BaseModel):
    month: str
    rake: float
    hands: int


class GameStatisticsResponse(BaseModel):
    today: dict
    total: dict


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


# =========================================================================
# Phase 5.2: MAU 통계 API
# =========================================================================

@router.get("/mau")
async def get_mau(
    month: Optional[str] = Query(None, description="조회 월 (YYYY-MM)"),
    current_user: AdminUser = Depends(require_viewer),
):
    """월간 활성 사용자 수 조회"""
    service = await get_metrics_service()
    mau = await service.get_mau(month)
    return {
        "mau": mau,
        "month": month or datetime.utcnow().strftime("%Y-%m")
    }


@router.get("/mau/history", response_model=list[MAUHistoryItem])
async def get_mau_history(
    months: int = Query(12, ge=1, le=24, description="조회 개월 수"),
    current_user: AdminUser = Depends(require_viewer),
):
    """MAU 히스토리 조회"""
    service = await get_metrics_service()
    history = await service.get_mau_history(months)
    return [MAUHistoryItem(**item) for item in history]


@router.get("/users/summary", response_model=UserStatisticsSummary)
async def get_user_statistics_summary(
    current_user: AdminUser = Depends(require_viewer),
):
    """사용자 통계 요약 (CCU, DAU, WAU, MAU)"""
    service = await get_metrics_service()
    summary = await service.get_user_statistics_summary()
    return UserStatisticsSummary(**summary)


# =========================================================================
# Phase 5.3: 매출 현황 대시보드 API
# =========================================================================

@router.get("/revenue/summary", response_model=RevenueSummaryResponse)
async def get_revenue_summary(
    days: int = Query(30, ge=1, le=365, description="조회 기간 (일)"),
    current_user: AdminUser = Depends(require_viewer),
    main_db: AsyncSession = Depends(get_main_db),
):
    """매출 요약 조회"""
    service = StatisticsService(main_db)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    summary = await service.get_revenue_summary(start_date, end_date)
    return RevenueSummaryResponse(**summary)


@router.get("/revenue/daily", response_model=list[DailyRevenueItem])
async def get_daily_revenue(
    days: int = Query(30, ge=1, le=90, description="조회 일수"),
    current_user: AdminUser = Depends(require_viewer),
    main_db: AsyncSession = Depends(get_main_db),
):
    """일별 매출 조회"""
    service = StatisticsService(main_db)
    revenue = await service.get_daily_revenue(days)
    return [DailyRevenueItem(**item) for item in revenue]


@router.get("/revenue/weekly", response_model=list[WeeklyRevenueItem])
async def get_weekly_revenue(
    weeks: int = Query(12, ge=1, le=52, description="조회 주 수"),
    current_user: AdminUser = Depends(require_viewer),
    main_db: AsyncSession = Depends(get_main_db),
):
    """주별 매출 조회"""
    service = StatisticsService(main_db)
    revenue = await service.get_weekly_revenue(weeks)
    return [WeeklyRevenueItem(**item) for item in revenue]


@router.get("/revenue/monthly", response_model=list[MonthlyRevenueItem])
async def get_monthly_revenue(
    months: int = Query(12, ge=1, le=24, description="조회 개월 수"),
    current_user: AdminUser = Depends(require_viewer),
    main_db: AsyncSession = Depends(get_main_db),
):
    """월별 매출 조회"""
    service = StatisticsService(main_db)
    revenue = await service.get_monthly_revenue(months)
    return [MonthlyRevenueItem(**item) for item in revenue]


@router.get("/game/statistics", response_model=GameStatisticsResponse)
async def get_game_statistics(
    current_user: AdminUser = Depends(require_viewer),
    main_db: AsyncSession = Depends(get_main_db),
):
    """게임 통계 요약 (오늘/전체)"""
    service = StatisticsService(main_db)
    stats = await service.get_game_statistics()
    return GameStatisticsResponse(**stats)


@router.get("/revenue/top-players")
async def get_top_players_by_rake(
    limit: int = Query(10, ge=1, le=100, description="조회 인원 수"),
    current_user: AdminUser = Depends(require_viewer),
    main_db: AsyncSession = Depends(get_main_db),
):
    """레이크 기여 상위 플레이어"""
    service = StatisticsService(main_db)
    players = await service.get_top_players_by_rake(limit)
    return {"players": players}


@router.get("/players/activity")
async def get_player_activity_summary(
    current_user: AdminUser = Depends(require_viewer),
    main_db: AsyncSession = Depends(get_main_db),
):
    """플레이어 활동 요약"""
    service = StatisticsService(main_db)
    activity = await service.get_player_activity_summary()
    return activity


@router.get("/players/hourly-activity")
async def get_hourly_player_activity(
    hours: int = Query(24, ge=1, le=168, description="조회 시간 범위"),
    current_user: AdminUser = Depends(require_viewer),
    main_db: AsyncSession = Depends(get_main_db),
):
    """시간별 플레이어 활동 조회"""
    service = StatisticsService(main_db)
    activity = await service.get_hourly_player_activity(hours)
    return {"activity": activity}


@router.get("/stake-levels")
async def get_stake_level_statistics(
    current_user: AdminUser = Depends(require_viewer),
    main_db: AsyncSession = Depends(get_main_db),
):
    """스테이크 레벨별 통계"""
    service = StatisticsService(main_db)
    stats = await service.get_stake_level_statistics()
    return {"stake_levels": stats}
