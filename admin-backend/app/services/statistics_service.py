"""
Statistics Service - 매출 및 통계 집계
메인 DB에서 레이크 수익, 거래 내역 등을 조회합니다.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import get_settings


class StatisticsService:
    """매출 및 통계 서비스"""
    
    def __init__(self, main_db: AsyncSession):
        self.db = main_db
        self.settings = get_settings()
    
    async def get_revenue_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> dict:
        """매출 요약 조회"""
        if end_date is None:
            end_date = datetime.utcnow()
        if start_date is None:
            start_date = end_date - timedelta(days=30)
        
        try:
            # 레이크 수익 집계 쿼리
            query = text("""
                SELECT 
                    COALESCE(SUM(rake_amount), 0) as total_rake,
                    COUNT(DISTINCT hand_id) as total_hands,
                    COUNT(DISTINCT room_id) as unique_rooms
                FROM hand_history
                WHERE created_at BETWEEN :start_date AND :end_date
            """)
            
            result = await self.db.execute(
                query,
                {"start_date": start_date, "end_date": end_date}
            )
            row = result.fetchone()
            
            if row:
                return {
                    "total_rake": float(row.total_rake or 0),
                    "total_hands": row.total_hands or 0,
                    "unique_rooms": row.unique_rooms or 0,
                    "period": {
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat()
                    }
                }
            
            return {
                "total_rake": 0,
                "total_hands": 0,
                "unique_rooms": 0,
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }
            }
        except Exception:
            return {
                "total_rake": 0,
                "total_hands": 0,
                "unique_rooms": 0,
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }
            }
    
    async def get_daily_revenue(self, days: int = 30) -> list[dict]:
        """일별 매출 조회"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        try:
            query = text("""
                SELECT 
                    DATE(created_at) as date,
                    COALESCE(SUM(rake_amount), 0) as rake,
                    COUNT(*) as hands
                FROM hand_history
                WHERE created_at BETWEEN :start_date AND :end_date
                GROUP BY DATE(created_at)
                ORDER BY date DESC
            """)
            
            result = await self.db.execute(
                query,
                {"start_date": start_date, "end_date": end_date}
            )
            rows = result.fetchall()
            
            return [
                {
                    "date": str(row.date),
                    "rake": float(row.rake),
                    "hands": row.hands
                }
                for row in rows
            ]
        except Exception:
            return []
    
    async def get_weekly_revenue(self, weeks: int = 12) -> list[dict]:
        """주별 매출 조회"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(weeks=weeks)
        
        try:
            query = text("""
                SELECT 
                    DATE_TRUNC('week', created_at) as week_start,
                    COALESCE(SUM(rake_amount), 0) as rake,
                    COUNT(*) as hands
                FROM hand_history
                WHERE created_at BETWEEN :start_date AND :end_date
                GROUP BY DATE_TRUNC('week', created_at)
                ORDER BY week_start DESC
            """)
            
            result = await self.db.execute(
                query,
                {"start_date": start_date, "end_date": end_date}
            )
            rows = result.fetchall()
            
            return [
                {
                    "week_start": str(row.week_start.date()) if row.week_start else "",
                    "rake": float(row.rake),
                    "hands": row.hands
                }
                for row in rows
            ]
        except Exception:
            return []
    
    async def get_monthly_revenue(self, months: int = 12) -> list[dict]:
        """월별 매출 조회"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=months * 30)
        
        try:
            query = text("""
                SELECT 
                    DATE_TRUNC('month', created_at) as month_start,
                    COALESCE(SUM(rake_amount), 0) as rake,
                    COUNT(*) as hands
                FROM hand_history
                WHERE created_at BETWEEN :start_date AND :end_date
                GROUP BY DATE_TRUNC('month', created_at)
                ORDER BY month_start DESC
            """)
            
            result = await self.db.execute(
                query,
                {"start_date": start_date, "end_date": end_date}
            )
            rows = result.fetchall()
            
            return [
                {
                    "month": row.month_start.strftime("%Y-%m") if row.month_start else "",
                    "rake": float(row.rake),
                    "hands": row.hands
                }
                for row in rows
            ]
        except Exception:
            return []
    
    async def get_top_players_by_rake(self, limit: int = 10) -> list[dict]:
        """레이크 기여 상위 플레이어"""
        try:
            query = text("""
                SELECT 
                    user_id,
                    COALESCE(SUM(rake_contribution), 0) as total_rake,
                    COUNT(*) as hands_played
                FROM hand_participants
                WHERE created_at > NOW() - INTERVAL '30 days'
                GROUP BY user_id
                ORDER BY total_rake DESC
                LIMIT :limit
            """)
            
            result = await self.db.execute(query, {"limit": limit})
            rows = result.fetchall()
            
            return [
                {
                    "user_id": row.user_id,
                    "total_rake": float(row.total_rake),
                    "hands_played": row.hands_played
                }
                for row in rows
            ]
        except Exception:
            return []
    
    async def get_game_statistics(self) -> dict:
        """게임 통계 요약"""
        try:
            # 오늘 통계
            today_query = text("""
                SELECT 
                    COUNT(*) as hands_today,
                    COALESCE(SUM(rake_amount), 0) as rake_today,
                    COUNT(DISTINCT room_id) as rooms_today
                FROM hand_history
                WHERE DATE(created_at) = CURRENT_DATE
            """)
            
            today_result = await self.db.execute(today_query)
            today = today_result.fetchone()
            
            # 전체 통계
            total_query = text("""
                SELECT 
                    COUNT(*) as total_hands,
                    COALESCE(SUM(rake_amount), 0) as total_rake
                FROM hand_history
            """)
            
            total_result = await self.db.execute(total_query)
            total = total_result.fetchone()
            
            return {
                "today": {
                    "hands": today.hands_today if today else 0,
                    "rake": float(today.rake_today) if today else 0,
                    "rooms": today.rooms_today if today else 0
                },
                "total": {
                    "hands": total.total_hands if total else 0,
                    "rake": float(total.total_rake) if total else 0
                }
            }
        except Exception:
            return {
                "today": {"hands": 0, "rake": 0, "rooms": 0},
                "total": {"hands": 0, "rake": 0}
            }
