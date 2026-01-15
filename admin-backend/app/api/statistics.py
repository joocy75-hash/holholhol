"""
Statistics API - 매출 및 게임 통계 엔드포인트
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_main_db
from app.utils.dependencies import require_viewer
from app.models.admin_user import AdminUser
from app.services.statistics_service import StatisticsService


router = APIRouter()


# Response Models
class PeriodInfo(BaseModel):
    start: str
    end: str


class RevenueSummaryResponse(BaseModel):
    total_rake: float
    total_hands: int
    unique_rooms: int
    period: PeriodInfo


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


class TopPlayerItem(BaseModel):
    user_id: str
    total_rake: float
    hands_played: int


class TodayStats(BaseModel):
    hands: int
    rake: float
    rooms: int


class TotalStats(BaseModel):
    hands: int
    rake: float


class GameStatisticsResponse(BaseModel):
    today: TodayStats
    total: TotalStats


# Endpoints
@router.get("/revenue/summary", response_model=RevenueSummaryResponse)
async def get_revenue_summary(
    start_date: Optional[str] = Query(None, description="시작 날짜 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="종료 날짜 (YYYY-MM-DD)"),
    current_user: AdminUser = Depends(require_viewer),
    db: AsyncSession = Depends(get_main_db),
):
    """매출 요약 조회"""
    service = StatisticsService(db)
    
    start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else None
    end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else None
    
    data = await service.get_revenue_summary(start, end)
    return RevenueSummaryResponse(
        total_rake=data["total_rake"],
        total_hands=data["total_hands"],
        unique_rooms=data["unique_rooms"],
        period=PeriodInfo(**data["period"])
    )


@router.get("/revenue/daily", response_model=list[DailyRevenueItem])
async def get_daily_revenue(
    days: int = Query(30, ge=1, le=365, description="조회 일수"),
    current_user: AdminUser = Depends(require_viewer),
    db: AsyncSession = Depends(get_main_db),
):
    """일별 매출 조회"""
    service = StatisticsService(db)
    data = await service.get_daily_revenue(days)
    return [DailyRevenueItem(**item) for item in data]


@router.get("/revenue/weekly", response_model=list[WeeklyRevenueItem])
async def get_weekly_revenue(
    weeks: int = Query(12, ge=1, le=52, description="조회 주수"),
    current_user: AdminUser = Depends(require_viewer),
    db: AsyncSession = Depends(get_main_db),
):
    """주별 매출 조회"""
    service = StatisticsService(db)
    data = await service.get_weekly_revenue(weeks)
    return [WeeklyRevenueItem(**item) for item in data]


@router.get("/revenue/monthly", response_model=list[MonthlyRevenueItem])
async def get_monthly_revenue(
    months: int = Query(12, ge=1, le=24, description="조회 월수"),
    current_user: AdminUser = Depends(require_viewer),
    db: AsyncSession = Depends(get_main_db),
):
    """월별 매출 조회"""
    service = StatisticsService(db)
    data = await service.get_monthly_revenue(months)
    return [MonthlyRevenueItem(**item) for item in data]


@router.get("/top-players", response_model=list[TopPlayerItem])
async def get_top_players(
    limit: int = Query(10, ge=1, le=100, description="조회 수"),
    current_user: AdminUser = Depends(require_viewer),
    db: AsyncSession = Depends(get_main_db),
):
    """레이크 기여 상위 플레이어 조회"""
    service = StatisticsService(db)
    data = await service.get_top_players_by_rake(limit)
    return [TopPlayerItem(**item) for item in data]


@router.get("/game", response_model=GameStatisticsResponse)
async def get_game_statistics(
    current_user: AdminUser = Depends(require_viewer),
    db: AsyncSession = Depends(get_main_db),
):
    """게임 통계 요약 조회"""
    service = StatisticsService(db)
    data = await service.get_game_statistics()
    return GameStatisticsResponse(
        today=TodayStats(**data["today"]),
        total=TotalStats(**data["total"])
    )
