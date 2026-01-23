"""
Ban Service - 사용자 제재 관리 서비스
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import uuid

from app.config import get_settings

logger = logging.getLogger(__name__)


class BanServiceError(Exception):
    """Exception raised for ban service errors."""
    pass


class BanService:
    """사용자 제재 관리 서비스"""
    
    def __init__(self, admin_db: AsyncSession, main_db: AsyncSession):
        self.admin_db = admin_db
        self.main_db = main_db
        self.settings = get_settings()
    
    async def create_ban(
        self,
        user_id: str,
        ban_type: str,
        reason: str,
        created_by: str,
        duration_hours: Optional[int] = None
    ) -> dict:
        """
        사용자 제재 생성
        
        Args:
            user_id: 제재할 사용자 ID
            ban_type: 제재 유형 (temporary, permanent, chat_only)
            reason: 제재 사유
            created_by: 제재를 생성한 관리자 ID
            duration_hours: 임시 제재 기간 (시간)
        
        Returns:
            생성된 제재 정보
        """
        ban_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        expires_at = None
        
        if ban_type == "temporary" and duration_hours:
            expires_at = now + timedelta(hours=duration_hours)
        
        # 사용자 정보 조회
        user_query = text("SELECT username FROM users WHERE id = :user_id")
        user_result = await self.main_db.execute(user_query, {"user_id": user_id})
        user_row = user_result.fetchone()
        username = user_row.username if user_row else "Unknown"
        
        # 메인 DB에 제재 적용
        if ban_type != "chat_only":
            update_query = text("""
                UPDATE users 
                SET is_banned = true, 
                    ban_reason = :reason,
                    ban_expires_at = :expires_at
                WHERE id = :user_id
            """)
            await self.main_db.execute(update_query, {
                "user_id": user_id,
                "reason": reason,
                "expires_at": expires_at
            })
            await self.main_db.commit()
        
        # Admin DB에 제재 기록 저장
        insert_query = text("""
            INSERT INTO bans (id, user_id, username, ban_type, reason, expires_at, created_by, created_at)
            VALUES (:id, :user_id, :username, :ban_type, :reason, :expires_at, :created_by, :created_at)
        """)
        await self.admin_db.execute(insert_query, {
            "id": ban_id,
            "user_id": user_id,
            "username": username,
            "ban_type": ban_type,
            "reason": reason,
            "expires_at": expires_at,
            "created_by": created_by,
            "created_at": now
        })
        await self.admin_db.commit()
        
        return {
            "id": ban_id,
            "user_id": user_id,
            "username": username,
            "ban_type": ban_type,
            "reason": reason,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "created_by": created_by,
            "created_at": now.isoformat()
        }
    
    async def lift_ban(self, ban_id: str, lifted_by: str) -> bool:
        """
        제재 해제
        
        Args:
            ban_id: 해제할 제재 ID
            lifted_by: 해제를 수행한 관리자 ID
        
        Returns:
            성공 여부
        """
        # 제재 정보 조회
        ban_query = text("SELECT user_id, ban_type FROM bans WHERE id = :ban_id")
        ban_result = await self.admin_db.execute(ban_query, {"ban_id": ban_id})
        ban_row = ban_result.fetchone()
        
        if not ban_row:
            return False
        
        user_id = ban_row.user_id
        ban_type = ban_row.ban_type
        
        # 메인 DB에서 제재 해제
        if ban_type != "chat_only":
            update_query = text("""
                UPDATE users 
                SET is_banned = false, 
                    ban_reason = NULL,
                    ban_expires_at = NULL
                WHERE id = :user_id
            """)
            await self.main_db.execute(update_query, {"user_id": user_id})
            await self.main_db.commit()
        
        # Admin DB에서 제재 기록 업데이트
        now = datetime.now(timezone.utc)
        update_ban_query = text("""
            UPDATE bans 
            SET lifted_at = :lifted_at, lifted_by = :lifted_by
            WHERE id = :ban_id
        """)
        await self.admin_db.execute(update_ban_query, {
            "ban_id": ban_id,
            "lifted_at": now,
            "lifted_by": lifted_by
        })
        await self.admin_db.commit()
        
        return True
    
    async def list_bans(
        self,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> dict:
        """
        제재 목록 조회
        
        Args:
            status: 상태 필터 (active, expired, lifted)
            page: 페이지 번호
            page_size: 페이지 크기
        
        Returns:
            페이지네이션된 제재 목록
        """
        offset = (page - 1) * page_size
        params = {"limit": page_size, "offset": offset}
        
        where_clauses = []
        now = datetime.now(timezone.utc)
        
        if status == "active":
            where_clauses.append("""
                lifted_at IS NULL 
                AND (expires_at IS NULL OR expires_at > :now)
            """)
            params["now"] = now
        elif status == "expired":
            where_clauses.append("expires_at IS NOT NULL AND expires_at <= :now")
            params["now"] = now
        elif status == "lifted":
            where_clauses.append("lifted_at IS NOT NULL")
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        try:
            # 총 개수 조회
            count_query = text(f"SELECT COUNT(*) FROM bans WHERE {where_sql}")
            count_result = await self.admin_db.execute(count_query, params)
            total = count_result.scalar() or 0
            
            # 제재 목록 조회
            list_query = text(f"""
                SELECT id, user_id, username, ban_type, reason, 
                       expires_at, created_by, created_at, lifted_at, lifted_by
                FROM bans
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """)
            result = await self.admin_db.execute(list_query, params)
            rows = result.fetchall()
            
            items = [
                {
                    "id": row.id,
                    "user_id": row.user_id,
                    "username": row.username,
                    "ban_type": row.ban_type,
                    "reason": row.reason,
                    "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                    "created_by": row.created_by,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "lifted_at": row.lifted_at.isoformat() if hasattr(row, 'lifted_at') and row.lifted_at else None,
                    "lifted_by": row.lifted_by if hasattr(row, 'lifted_by') else None
                }
                for row in rows
            ]
            
            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }
        except Exception as e:
            # bans 테이블이 없는 경우 빈 목록 반환
            error_str = str(e).lower()
            if "does not exist" in error_str or "undefined" in error_str or "relation" in error_str:
                logger.warning("bans 테이블이 없습니다. 빈 목록 반환.")
                return {
                    "items": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": 0
                }
            logger.error(f"Failed to list bans: {e}", exc_info=True)
            raise BanServiceError(f"Failed to list bans: {e}") from e
    
    async def get_user_bans(self, user_id: str) -> list:
        """특정 사용자의 제재 기록 조회"""
        try:
            query = text("""
                SELECT id, ban_type, reason, expires_at, created_by, created_at, lifted_at
                FROM bans
                WHERE user_id = :user_id
                ORDER BY created_at DESC
            """)
            result = await self.admin_db.execute(query, {"user_id": user_id})
            rows = result.fetchall()
            
            return [
                {
                    "id": row.id,
                    "ban_type": row.ban_type,
                    "reason": row.reason,
                    "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                    "created_by": row.created_by,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "lifted_at": row.lifted_at.isoformat() if hasattr(row, 'lifted_at') and row.lifted_at else None
                }
                for row in rows
            ]
        except Exception as e:
            # bans 테이블이 없는 경우 빈 목록 반환
            error_str = str(e).lower()
            if "does not exist" in error_str or "undefined" in error_str or "relation" in error_str:
                logger.warning(f"bans 테이블이 없습니다. 사용자 {user_id}의 빈 목록 반환.")
                return []
            logger.error(f"Failed to get user bans for user {user_id}: {e}", exc_info=True)
            raise BanServiceError(f"Failed to get user bans: {e}") from e
