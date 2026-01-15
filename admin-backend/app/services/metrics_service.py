"""
Metrics Service - CCU/DAU 및 서버 상태 집계
메인 시스템의 Redis와 DB에서 실시간 데이터를 조회합니다.
"""
from datetime import datetime, timedelta
from typing import Optional
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import get_settings


class MetricsService:
    """실시간 메트릭 수집 서비스"""
    
    def __init__(self, redis_client: redis.Redis, main_db: Optional[AsyncSession] = None):
        self.redis = redis_client
        self.main_db = main_db
        self.settings = get_settings()
    
    async def get_ccu(self) -> int:
        """현재 동시 접속자 수 (CCU) 조회"""
        try:
            # Redis에서 활성 세션 수 조회
            # 메인 시스템이 "active_sessions" 또는 "online_users" 키에 저장한다고 가정
            ccu = await self.redis.scard("online_users")
            if ccu is None:
                # 대안: 활성 WebSocket 연결 수
                ccu = await self.redis.get("ws_connections_count")
                return int(ccu) if ccu else 0
            return ccu
        except Exception:
            return 0
    
    async def get_dau(self, date: Optional[datetime] = None) -> int:
        """일일 활성 사용자 수 (DAU) 조회"""
        if date is None:
            date = datetime.utcnow()
        
        date_key = date.strftime("%Y-%m-%d")
        
        try:
            # Redis에서 DAU 조회 (메인 시스템이 HyperLogLog로 저장)
            dau = await self.redis.pfcount(f"dau:{date_key}")
            return dau if dau else 0
        except Exception:
            return 0
    
    async def get_ccu_history(self, hours: int = 24) -> list[dict]:
        """CCU 히스토리 조회 (시간별)"""
        history = []
        now = datetime.utcnow()
        
        try:
            for i in range(hours):
                timestamp = now - timedelta(hours=i)
                hour_key = timestamp.strftime("%Y-%m-%d:%H")
                
                # Redis에서 시간별 CCU 조회
                ccu = await self.redis.get(f"ccu_hourly:{hour_key}")
                history.append({
                    "timestamp": timestamp.isoformat(),
                    "hour": timestamp.strftime("%H:00"),
                    "ccu": int(ccu) if ccu else 0
                })
            
            return list(reversed(history))
        except Exception:
            return []
    
    async def get_dau_history(self, days: int = 30) -> list[dict]:
        """DAU 히스토리 조회 (일별)"""
        history = []
        now = datetime.utcnow()
        
        try:
            for i in range(days):
                date = now - timedelta(days=i)
                date_key = date.strftime("%Y-%m-%d")
                
                dau = await self.redis.pfcount(f"dau:{date_key}")
                history.append({
                    "date": date_key,
                    "dau": dau if dau else 0
                })
            
            return list(reversed(history))
        except Exception:
            return []
    
    async def get_active_rooms(self) -> dict:
        """활성 방 통계 조회"""
        try:
            # Redis에서 활성 방 정보 조회
            active_rooms = await self.redis.scard("active_rooms")
            
            # 방별 플레이어 수 집계
            total_players = 0
            room_ids = await self.redis.smembers("active_rooms")
            
            for room_id in room_ids:
                if isinstance(room_id, bytes):
                    room_id = room_id.decode()
                players = await self.redis.scard(f"room:{room_id}:players")
                total_players += players if players else 0
            
            return {
                "active_rooms": active_rooms if active_rooms else 0,
                "total_players": total_players,
                "avg_players_per_room": round(total_players / max(active_rooms, 1), 1)
            }
        except Exception:
            return {
                "active_rooms": 0,
                "total_players": 0,
                "avg_players_per_room": 0
            }
    
    async def get_room_distribution(self) -> list[dict]:
        """방 유형별 분포 조회"""
        try:
            distribution = []
            room_types = ["cash", "tournament", "sit_n_go"]
            
            for room_type in room_types:
                count = await self.redis.scard(f"rooms:{room_type}")
                distribution.append({
                    "type": room_type,
                    "count": count if count else 0
                })
            
            return distribution
        except Exception:
            return []
    
    async def get_server_health(self) -> dict:
        """서버 상태 조회"""
        try:
            # Redis에서 서버 메트릭 조회
            cpu = await self.redis.get("server:cpu_usage")
            memory = await self.redis.get("server:memory_usage")
            latency = await self.redis.get("server:avg_latency")
            
            cpu_val = float(cpu) if cpu else 0
            memory_val = float(memory) if memory else 0
            latency_val = float(latency) if latency else 0
            
            # 상태 판단
            if cpu_val > 90 or memory_val > 90 or latency_val > 500:
                status = "critical"
            elif cpu_val > 70 or memory_val > 70 or latency_val > 200:
                status = "warning"
            else:
                status = "healthy"
            
            return {
                "cpu": cpu_val,
                "memory": memory_val,
                "latency": latency_val,
                "status": status
            }
        except Exception:
            return {
                "cpu": 0,
                "memory": 0,
                "latency": 0,
                "status": "unknown"
            }
    
    async def get_dashboard_summary(self) -> dict:
        """대시보드 요약 데이터"""
        ccu = await self.get_ccu()
        dau = await self.get_dau()
        rooms = await self.get_active_rooms()
        health = await self.get_server_health()
        
        return {
            "ccu": ccu,
            "dau": dau,
            "active_rooms": rooms["active_rooms"],
            "total_players": rooms["total_players"],
            "server_health": health
        }


# Redis 클라이언트 싱글톤
_redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> redis.Redis:
    """Redis 클라이언트 가져오기"""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def get_metrics_service() -> MetricsService:
    """MetricsService 인스턴스 가져오기"""
    redis_client = await get_redis_client()
    return MetricsService(redis_client)
