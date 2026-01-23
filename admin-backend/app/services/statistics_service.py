"""
Statistics Service - 매출 및 통계 집계
메인 DB에서 레이크 수익, 거래 내역 등을 조회합니다.
"""
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import get_settings

logger = logging.getLogger(__name__)


class StatisticsError(Exception):
    """Exception raised for statistics service errors."""
    pass


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
            end_date = datetime.now(timezone.utc)
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
        except Exception as e:
            logger.error(f"Failed to get revenue summary: {e}", exc_info=True)
            raise StatisticsError(f"Failed to get revenue summary: {e}") from e
    
    async def get_daily_revenue(self, days: int = 30) -> list[dict]:
        """일별 매출 조회"""
        end_date = datetime.now(timezone.utc)
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
        except Exception as e:
            logger.error(f"Failed to get daily revenue: {e}", exc_info=True)
            raise StatisticsError(f"Failed to get daily revenue: {e}") from e
    
    async def get_weekly_revenue(self, weeks: int = 12) -> list[dict]:
        """주별 매출 조회"""
        end_date = datetime.now(timezone.utc)
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
        except Exception as e:
            logger.error(f"Failed to get weekly revenue: {e}", exc_info=True)
            raise StatisticsError(f"Failed to get weekly revenue: {e}") from e
    
    async def get_monthly_revenue(self, months: int = 12) -> list[dict]:
        """월별 매출 조회"""
        end_date = datetime.now(timezone.utc)
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
        except Exception as e:
            logger.error(f"Failed to get monthly revenue: {e}", exc_info=True)
            raise StatisticsError(f"Failed to get monthly revenue: {e}") from e
    
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
        except Exception as e:
            logger.error(f"Failed to get top players by rake: {e}", exc_info=True)
            raise StatisticsError(f"Failed to get top players by rake: {e}") from e
    
    async def get_game_statistics(self) -> dict:
        """게임 통계 요약"""
        default_stats = {
            "today": {"hands": 0, "rake": 0.0, "rooms": 0},
            "total": {"hands": 0, "rake": 0.0}
        }

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
        except Exception as e:
            # 테이블이 없는 경우 기본값 반환 (hand_history 테이블 미생성 시)
            if "UndefinedTableError" in str(type(e).__name__) or "does not exist" in str(e):
                logger.warning("hand_history 테이블이 없습니다. 기본값 반환.")
                return default_stats
            logger.error(f"Failed to get game statistics: {e}", exc_info=True)
            raise StatisticsError(f"Failed to get game statistics: {e}") from e
    
    async def get_room_statistics(self) -> dict:
        """방 통계 조회 (DB 기반)"""
        try:
            # 활성 방 통계
            active_rooms_query = text("""
                SELECT 
                    COUNT(*) as total_rooms,
                    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_rooms,
                    COUNT(CASE WHEN status = 'waiting' THEN 1 END) as waiting_rooms,
                    COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_rooms
                FROM rooms
            """)
            
            result = await self.db.execute(active_rooms_query)
            row = result.fetchone()
            
            return {
                "total_rooms": row.total_rooms if row else 0,
                "active_rooms": row.active_rooms if row else 0,
                "waiting_rooms": row.waiting_rooms if row else 0,
                "closed_rooms": row.closed_rooms if row else 0
            }
        except Exception as e:
            logger.error(f"Failed to get room statistics: {e}", exc_info=True)
            raise StatisticsError(f"Failed to get room statistics: {e}") from e
    
    async def get_player_distribution(self) -> list[dict]:
        """플레이어 분포 조회 (스테이크별)"""
        try:
            query = text("""
                SELECT 
                    r.stake_level,
                    COUNT(DISTINCT rp.user_id) as player_count,
                    COUNT(DISTINCT r.id) as room_count
                FROM rooms r
                LEFT JOIN room_players rp ON r.id = rp.room_id
                WHERE r.status = 'active'
                GROUP BY r.stake_level
                ORDER BY r.stake_level
            """)
            
            result = await self.db.execute(query)
            rows = result.fetchall()
            
            return [
                {
                    "stake_level": row.stake_level or "unknown",
                    "player_count": row.player_count or 0,
                    "room_count": row.room_count or 0
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get player distribution: {e}", exc_info=True)
            raise StatisticsError(f"Failed to get player distribution: {e}") from e
    
    async def get_player_activity_summary(self) -> dict:
        """플레이어 활동 요약"""
        try:
            # 오늘 활성 플레이어
            today_query = text("""
                SELECT 
                    COUNT(DISTINCT user_id) as active_players,
                    COUNT(*) as total_actions
                FROM hand_participants
                WHERE DATE(created_at) = CURRENT_DATE
            """)
            
            today_result = await self.db.execute(today_query)
            today = today_result.fetchone()
            
            # 이번 주 활성 플레이어
            week_query = text("""
                SELECT 
                    COUNT(DISTINCT user_id) as active_players
                FROM hand_participants
                WHERE created_at > NOW() - INTERVAL '7 days'
            """)
            
            week_result = await self.db.execute(week_query)
            week = week_result.fetchone()
            
            # 이번 달 활성 플레이어
            month_query = text("""
                SELECT 
                    COUNT(DISTINCT user_id) as active_players
                FROM hand_participants
                WHERE created_at > NOW() - INTERVAL '30 days'
            """)
            
            month_result = await self.db.execute(month_query)
            month = month_result.fetchone()
            
            return {
                "today": {
                    "active_players": today.active_players if today else 0,
                    "total_actions": today.total_actions if today else 0
                },
                "week": {
                    "active_players": week.active_players if week else 0
                },
                "month": {
                    "active_players": month.active_players if month else 0
                }
            }
        except Exception as e:
            logger.error(f"Failed to get player activity summary: {e}", exc_info=True)
            raise StatisticsError(f"Failed to get player activity summary: {e}") from e
    
    async def get_hourly_player_activity(self, hours: int = 24) -> list[dict]:
        """시간별 플레이어 활동 조회"""
        try:
            # 입력값 검증 - SQL Injection 방지
            if not isinstance(hours, int) or hours < 1 or hours > 168:
                hours = 24  # 기본값으로 폴백 (최대 7일)
            
            query = text("""
                SELECT 
                    DATE_TRUNC('hour', created_at) as hour,
                    COUNT(DISTINCT user_id) as unique_players,
                    COUNT(*) as total_hands
                FROM hand_participants
                WHERE created_at > NOW() - :hours * INTERVAL '1 hour'
                GROUP BY DATE_TRUNC('hour', created_at)
                ORDER BY hour DESC
            """)
            
            result = await self.db.execute(query, {"hours": hours})
            rows = result.fetchall()
            
            return [
                {
                    "hour": row.hour.isoformat() if row.hour else "",
                    "unique_players": row.unique_players or 0,
                    "total_hands": row.total_hands or 0
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get hourly player activity: {e}", exc_info=True)
            raise StatisticsError(f"Failed to get hourly player activity: {e}") from e
    
    async def get_stake_level_statistics(self) -> list[dict]:
        """스테이크 레벨별 통계"""
        try:
            query = text("""
                SELECT 
                    r.stake_level,
                    COUNT(DISTINCT h.id) as total_hands,
                    COALESCE(SUM(h.rake_amount), 0) as total_rake,
                    COALESCE(AVG(h.pot_size), 0) as avg_pot_size
                FROM rooms r
                JOIN hand_history h ON r.id = h.room_id
                WHERE h.created_at > NOW() - INTERVAL '30 days'
                GROUP BY r.stake_level
                ORDER BY r.stake_level
            """)
            
            result = await self.db.execute(query)
            rows = result.fetchall()
            
            return [
                {
                    "stake_level": row.stake_level or "unknown",
                    "total_hands": row.total_hands or 0,
                    "total_rake": float(row.total_rake or 0),
                    "avg_pot_size": float(row.avg_pot_size or 0)
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get stake level statistics: {e}", exc_info=True)
            raise StatisticsError(f"Failed to get stake level statistics: {e}") from e
