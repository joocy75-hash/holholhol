"""
User Service - 메인 시스템 사용자 조회 서비스
메인 DB에서 사용자 정보를 읽기 전용으로 조회합니다.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import get_settings


class UserService:
    """사용자 조회 서비스 (메인 DB 읽기 전용)"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
    
    async def search_users(
        self,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        is_banned: Optional[bool] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> dict:
        """사용자 검색 및 목록 조회"""
        offset = (page - 1) * page_size
        
        # 기본 쿼리
        where_clauses = []
        params = {"limit": page_size, "offset": offset}

        if search:
            where_clauses.append("""
                (username ILIKE :search 
                OR email ILIKE :search 
                OR id::text ILIKE :search)
            """)
            params["search"] = f"%{search}%"
        
        if is_banned is not None:
            where_clauses.append("is_banned = :is_banned")
            params["is_banned"] = is_banned
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # 정렬 검증
        valid_sort_fields = ["created_at", "username", "email", "balance", "last_login"]
        if sort_by not in valid_sort_fields:
            sort_by = "created_at"
        sort_order = "DESC" if sort_order.lower() == "desc" else "ASC"
        
        try:
            # 총 개수 조회
            count_query = text(f"""
                SELECT COUNT(*) as total
                FROM users
                WHERE {where_sql}
            """)
            count_result = await self.db.execute(count_query, params)
            total = count_result.scalar() or 0
            
            # 사용자 목록 조회
            list_query = text(f"""
                SELECT 
                    id, username, email, balance, 
                    created_at, last_login, is_banned
                FROM users
                WHERE {where_sql}
                ORDER BY {sort_by} {sort_order}
                LIMIT :limit OFFSET :offset
            """)
            result = await self.db.execute(list_query, params)
            rows = result.fetchall()
            
            users = [
                {
                    "id": str(row.id),
                    "username": row.username,
                    "email": row.email,
                    "balance": float(row.balance) if row.balance else 0,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "last_login": row.last_login.isoformat() if row.last_login else None,
                    "is_banned": row.is_banned or False
                }
                for row in rows
            ]
            
            return {
                "items": users,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }
        except Exception as e:
            return {
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0
            }

    async def get_user_detail(self, user_id: str) -> Optional[dict]:
        """사용자 상세 정보 조회"""
        try:
            query = text("""
                SELECT 
                    id, username, email, balance,
                    created_at, last_login, is_banned,
                    ban_reason, ban_expires_at
                FROM users
                WHERE id = :user_id
            """)
            result = await self.db.execute(query, {"user_id": user_id})
            row = result.fetchone()
            
            if not row:
                return None
            
            return {
                "id": str(row.id),
                "username": row.username,
                "email": row.email,
                "balance": float(row.balance) if row.balance else 0,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "last_login": row.last_login.isoformat() if row.last_login else None,
                "is_banned": row.is_banned or False,
                "ban_reason": row.ban_reason if hasattr(row, 'ban_reason') else None,
                "ban_expires_at": row.ban_expires_at.isoformat() if hasattr(row, 'ban_expires_at') and row.ban_expires_at else None
            }
        except Exception:
            return None
    
    async def get_user_transactions(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        tx_type: Optional[str] = None
    ) -> dict:
        """사용자 거래 내역 조회"""
        offset = (page - 1) * page_size
        params = {"user_id": user_id, "limit": page_size, "offset": offset}
        
        where_clauses = ["user_id = :user_id"]
        if tx_type:
            where_clauses.append("type = :tx_type")
            params["tx_type"] = tx_type
        
        where_sql = " AND ".join(where_clauses)
        
        try:
            count_query = text(f"""
                SELECT COUNT(*) FROM transactions WHERE {where_sql}
            """)
            count_result = await self.db.execute(count_query, params)
            total = count_result.scalar() or 0
            
            list_query = text(f"""
                SELECT id, type, amount, balance_before, balance_after, 
                       description, created_at
                FROM transactions
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """)
            result = await self.db.execute(list_query, params)
            rows = result.fetchall()
            
            items = [
                {
                    "id": str(row.id),
                    "type": row.type,
                    "amount": float(row.amount),
                    "balance_before": float(row.balance_before) if row.balance_before else 0,
                    "balance_after": float(row.balance_after) if row.balance_after else 0,
                    "description": row.description,
                    "created_at": row.created_at.isoformat() if row.created_at else None
                }
                for row in rows
            ]
            
            return {"items": items, "total": total, "page": page, "page_size": page_size}
        except Exception:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}

    async def get_user_login_history(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> dict:
        """사용자 로그인 기록 조회"""
        offset = (page - 1) * page_size
        params = {"user_id": user_id, "limit": page_size, "offset": offset}
        
        try:
            count_query = text("""
                SELECT COUNT(*) FROM login_history WHERE user_id = :user_id
            """)
            count_result = await self.db.execute(count_query, params)
            total = count_result.scalar() or 0
            
            list_query = text("""
                SELECT id, ip_address, user_agent, success, created_at
                FROM login_history
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """)
            result = await self.db.execute(list_query, params)
            rows = result.fetchall()
            
            items = [
                {
                    "id": str(row.id),
                    "ip_address": row.ip_address,
                    "user_agent": row.user_agent,
                    "success": row.success,
                    "created_at": row.created_at.isoformat() if row.created_at else None
                }
                for row in rows
            ]
            
            return {"items": items, "total": total, "page": page, "page_size": page_size}
        except Exception:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
    
    async def get_user_hands(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> dict:
        """사용자 핸드 기록 조회"""
        offset = (page - 1) * page_size
        params = {"user_id": user_id, "limit": page_size, "offset": offset}
        
        try:
            count_query = text("""
                SELECT COUNT(*) FROM hand_participants WHERE user_id = :user_id
            """)
            count_result = await self.db.execute(count_query, params)
            total = count_result.scalar() or 0
            
            list_query = text("""
                SELECT hp.id, hp.hand_id, hp.position, hp.cards, 
                       hp.bet_amount, hp.won_amount, hp.created_at,
                       h.room_id, h.pot_size
                FROM hand_participants hp
                JOIN hand_history h ON hp.hand_id = h.id
                WHERE hp.user_id = :user_id
                ORDER BY hp.created_at DESC
                LIMIT :limit OFFSET :offset
            """)
            result = await self.db.execute(list_query, params)
            rows = result.fetchall()
            
            items = [
                {
                    "id": str(row.id),
                    "hand_id": str(row.hand_id),
                    "room_id": str(row.room_id) if row.room_id else None,
                    "position": row.position,
                    "cards": row.cards,
                    "bet_amount": float(row.bet_amount) if row.bet_amount else 0,
                    "won_amount": float(row.won_amount) if row.won_amount else 0,
                    "pot_size": float(row.pot_size) if row.pot_size else 0,
                    "created_at": row.created_at.isoformat() if row.created_at else None
                }
                for row in rows
            ]
            
            return {"items": items, "total": total, "page": page, "page_size": page_size}
        except Exception:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
