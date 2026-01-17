"""
User Service - 메인 시스템 사용자 조회 및 자산 관리 서비스
메인 DB에서 사용자 정보를 조회하고 자산을 관리합니다.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import get_settings

logger = logging.getLogger(__name__)


class UserServiceError(Exception):
    """User Service 에러"""
    pass


class InsufficientBalanceError(UserServiceError):
    """잔액 부족 에러"""
    pass


class UserNotFoundError(UserServiceError):
    """사용자를 찾을 수 없음"""
    pass


class UserService:
    """사용자 조회 및 자산 관리 서비스"""
    
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

    async def get_user_activity(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        activity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> dict:
        """
        사용자 통합 활동 로그 조회

        로그인 기록, 거래 내역, 핸드 기록을 통합하여 시간순으로 조회합니다.

        Args:
            user_id: 사용자 ID
            page: 페이지 번호
            page_size: 페이지 크기
            activity_type: 활동 타입 필터 (login, transaction, hand)
            start_date: 시작 날짜
            end_date: 종료 날짜

        Returns:
            통합 활동 로그 (페이지네이션 포함)
        """
        offset = (page - 1) * page_size
        params = {"user_id": user_id, "limit": page_size, "offset": offset}

        # 날짜 필터 조건
        date_filter_login = ""
        date_filter_tx = ""
        date_filter_hand = ""

        if start_date:
            date_filter_login += " AND lh.created_at >= :start_date"
            date_filter_tx += " AND t.created_at >= :start_date"
            date_filter_hand += " AND hp.created_at >= :start_date"
            params["start_date"] = start_date

        if end_date:
            date_filter_login += " AND lh.created_at <= :end_date"
            date_filter_tx += " AND t.created_at <= :end_date"
            date_filter_hand += " AND hp.created_at <= :end_date"
            params["end_date"] = end_date

        # 활동 타입에 따라 쿼리 구성
        union_parts = []

        # 로그인 기록
        if activity_type is None or activity_type == "login":
            union_parts.append(f"""
                SELECT
                    lh.id::text as id,
                    'login' as activity_type,
                    CASE WHEN lh.success THEN '로그인 성공' ELSE '로그인 실패' END as description,
                    NULL::numeric as amount,
                    lh.ip_address as ip_address,
                    lh.user_agent as device_info,
                    NULL::text as room_id,
                    NULL::text as hand_id,
                    lh.created_at as created_at
                FROM login_history lh
                WHERE lh.user_id = :user_id{date_filter_login}
            """)

        # 거래 내역
        if activity_type is None or activity_type == "transaction":
            union_parts.append(f"""
                SELECT
                    t.id::text as id,
                    'transaction' as activity_type,
                    t.description as description,
                    t.amount as amount,
                    NULL::text as ip_address,
                    t.type as device_info,
                    NULL::text as room_id,
                    NULL::text as hand_id,
                    t.created_at as created_at
                FROM transactions t
                WHERE t.user_id = :user_id{date_filter_tx}
            """)

        # 핸드 기록
        if activity_type is None or activity_type == "hand":
            union_parts.append(f"""
                SELECT
                    hp.id::text as id,
                    'hand' as activity_type,
                    CASE
                        WHEN hp.won_amount > 0 THEN '핸드 승리'
                        WHEN hp.won_amount = 0 AND hp.bet_amount > 0 THEN '핸드 패배'
                        ELSE '핸드 참가'
                    END as description,
                    (hp.won_amount - hp.bet_amount) as amount,
                    NULL::text as ip_address,
                    hp.cards as device_info,
                    h.room_id::text as room_id,
                    hp.hand_id::text as hand_id,
                    hp.created_at as created_at
                FROM hand_participants hp
                JOIN hand_history h ON hp.hand_id = h.id
                WHERE hp.user_id = :user_id{date_filter_hand}
            """)

        if not union_parts:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}

        union_query = " UNION ALL ".join(union_parts)

        try:
            # 총 개수 조회
            count_query = text(f"""
                SELECT COUNT(*) FROM ({union_query}) as activity
            """)
            count_result = await self.db.execute(count_query, params)
            total = count_result.scalar() or 0

            # 활동 로그 조회 (시간순 정렬)
            list_query = text(f"""
                SELECT * FROM ({union_query}) as activity
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """)
            result = await self.db.execute(list_query, params)
            rows = result.fetchall()

            items = [
                {
                    "id": row.id,
                    "activity_type": row.activity_type,
                    "description": row.description,
                    "amount": float(row.amount) if row.amount else None,
                    "ip_address": row.ip_address,
                    "device_info": row.device_info,
                    "room_id": row.room_id,
                    "hand_id": row.hand_id,
                    "created_at": row.created_at.isoformat() if row.created_at else None
                }
                for row in rows
            ]

            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if total > 0 else 0
            }
        except Exception as e:
            logger.error(f"활동 로그 조회 실패: user_id={user_id}, error={e}", exc_info=True)
            return {
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0
            }

    async def credit_chips(
        self,
        user_id: str,
        amount: float,
        reason: str,
        admin_user_id: str,
        admin_username: str
    ) -> dict:
        """
        사용자에게 칩 지급

        Args:
            user_id: 대상 사용자 ID
            amount: 지급 금액 (양수)
            reason: 지급 사유
            admin_user_id: 관리자 ID
            admin_username: 관리자 사용자명

        Returns:
            트랜잭션 정보

        Raises:
            UserNotFoundError: 사용자를 찾을 수 없음
            ValueError: 금액이 유효하지 않음
        """
        if amount <= 0:
            raise ValueError("지급 금액은 양수여야 합니다")

        try:
            # 사용자 존재 확인 및 현재 잔액 조회
            user_query = text("""
                SELECT id, username, balance FROM users WHERE id = :user_id FOR UPDATE
            """)
            result = await self.db.execute(user_query, {"user_id": user_id})
            user = result.fetchone()

            if not user:
                raise UserNotFoundError(f"사용자를 찾을 수 없습니다: {user_id}")

            balance_before = float(user.balance) if user.balance else 0.0
            balance_after = balance_before + amount

            # 잔액 업데이트
            update_query = text("""
                UPDATE users SET balance = :new_balance WHERE id = :user_id
            """)
            await self.db.execute(update_query, {
                "user_id": user_id,
                "new_balance": balance_after
            })

            # 트랜잭션 기록
            tx_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            description = f"[관리자 지급] {reason} (by {admin_username})"

            tx_query = text("""
                INSERT INTO transactions
                (id, user_id, type, amount, balance_before, balance_after, description, created_at)
                VALUES (:id, :user_id, :type, :amount, :balance_before, :balance_after, :description, :created_at)
            """)
            await self.db.execute(tx_query, {
                "id": tx_id,
                "user_id": user_id,
                "type": "admin_credit",
                "amount": amount,
                "balance_before": balance_before,
                "balance_after": balance_after,
                "description": description,
                "created_at": now
            })

            await self.db.commit()

            logger.info(
                f"칩 지급 완료: user_id={user_id}, amount={amount}, "
                f"balance_before={balance_before}, balance_after={balance_after}, "
                f"admin={admin_username}, reason={reason}"
            )

            return {
                "transaction_id": tx_id,
                "user_id": user_id,
                "username": user.username,
                "type": "credit",
                "amount": amount,
                "balance_before": balance_before,
                "balance_after": balance_after,
                "reason": reason,
                "admin_user_id": admin_user_id,
                "admin_username": admin_username,
                "created_at": now.isoformat()
            }

        except UserNotFoundError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"칩 지급 실패: user_id={user_id}, amount={amount}, error={e}", exc_info=True)
            raise UserServiceError(f"칩 지급 실패: {e}") from e

    async def debit_chips(
        self,
        user_id: str,
        amount: float,
        reason: str,
        admin_user_id: str,
        admin_username: str
    ) -> dict:
        """
        사용자로부터 칩 회수

        Args:
            user_id: 대상 사용자 ID
            amount: 회수 금액 (양수)
            reason: 회수 사유
            admin_user_id: 관리자 ID
            admin_username: 관리자 사용자명

        Returns:
            트랜잭션 정보

        Raises:
            UserNotFoundError: 사용자를 찾을 수 없음
            InsufficientBalanceError: 잔액 부족
            ValueError: 금액이 유효하지 않음
        """
        if amount <= 0:
            raise ValueError("회수 금액은 양수여야 합니다")

        try:
            # 사용자 존재 확인 및 현재 잔액 조회 (FOR UPDATE로 락)
            user_query = text("""
                SELECT id, username, balance FROM users WHERE id = :user_id FOR UPDATE
            """)
            result = await self.db.execute(user_query, {"user_id": user_id})
            user = result.fetchone()

            if not user:
                raise UserNotFoundError(f"사용자를 찾을 수 없습니다: {user_id}")

            balance_before = float(user.balance) if user.balance else 0.0

            # 잔액 부족 확인
            if balance_before < amount:
                raise InsufficientBalanceError(
                    f"잔액 부족: 현재 잔액={balance_before}, 회수 요청={amount}"
                )

            balance_after = balance_before - amount

            # 잔액 업데이트
            update_query = text("""
                UPDATE users SET balance = :new_balance WHERE id = :user_id
            """)
            await self.db.execute(update_query, {
                "user_id": user_id,
                "new_balance": balance_after
            })

            # 트랜잭션 기록
            tx_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            description = f"[관리자 회수] {reason} (by {admin_username})"

            tx_query = text("""
                INSERT INTO transactions
                (id, user_id, type, amount, balance_before, balance_after, description, created_at)
                VALUES (:id, :user_id, :type, :amount, :balance_before, :balance_after, :description, :created_at)
            """)
            await self.db.execute(tx_query, {
                "id": tx_id,
                "user_id": user_id,
                "type": "admin_debit",
                "amount": -amount,  # 회수는 음수로 기록
                "balance_before": balance_before,
                "balance_after": balance_after,
                "description": description,
                "created_at": now
            })

            await self.db.commit()

            logger.info(
                f"칩 회수 완료: user_id={user_id}, amount={amount}, "
                f"balance_before={balance_before}, balance_after={balance_after}, "
                f"admin={admin_username}, reason={reason}"
            )

            return {
                "transaction_id": tx_id,
                "user_id": user_id,
                "username": user.username,
                "type": "debit",
                "amount": amount,
                "balance_before": balance_before,
                "balance_after": balance_after,
                "reason": reason,
                "admin_user_id": admin_user_id,
                "admin_username": admin_username,
                "created_at": now.isoformat()
            }

        except (UserNotFoundError, InsufficientBalanceError):
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"칩 회수 실패: user_id={user_id}, amount={amount}, error={e}", exc_info=True)
            raise UserServiceError(f"칩 회수 실패: {e}") from e
