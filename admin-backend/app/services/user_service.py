"""
User Service - 메인 시스템 사용자 조회 및 자산 관리 서비스
메인 DB에서 사용자 정보를 조회하고 자산을 관리합니다.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from passlib.context import CryptContext

from app.config import get_settings
from app.models.main_db import User

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserServiceError(Exception):
    """User Service 에러"""
    pass


class InsufficientBalanceError(UserServiceError):
    """잔액 부족 에러"""
    pass


class UserNotFoundError(UserServiceError):
    """사용자를 찾을 수 없음"""
    pass


class DuplicateEmailError(UserServiceError):
    """이메일 중복"""
    pass


class DuplicateNicknameError(UserServiceError):
    """닉네임 중복"""
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
                (nickname ILIKE :search
                OR email ILIKE :search
                OR id::text ILIKE :search)
            """)
            params["search"] = f"%{search}%"

        if is_banned is not None:
            if is_banned:
                where_clauses.append("status = 'banned'")
            else:
                where_clauses.append("status != 'banned'")

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # 정렬 검증 (nickname으로 변경)
        valid_sort_fields = ["created_at", "nickname", "email", "balance", "updated_at"]
        # sort_by가 username이면 nickname으로 변환
        if sort_by == "username":
            sort_by = "nickname"
        if sort_by == "last_login":
            sort_by = "updated_at"
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
                    id, nickname, email, balance,
                    created_at, updated_at, status
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
                    "username": row.nickname,  # nickname을 username으로 매핑
                    "email": row.email,
                    "balance": float(row.balance) if row.balance else 0,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "last_login": row.updated_at.isoformat() if row.updated_at else None,  # updated_at을 last_login으로 사용
                    "is_banned": row.status == 'banned'
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
            logger.error(f"사용자 검색 실패: search={search}, error={e}", exc_info=True)
            raise UserServiceError(f"사용자 검색 실패: {e}") from e

    async def get_user_detail(self, user_id: str) -> Optional[dict]:
        """사용자 상세 정보 조회"""
        try:
            query = text("""
                SELECT
                    id, nickname, email, balance,
                    created_at, updated_at, status
                FROM users
                WHERE id = :user_id
            """)
            result = await self.db.execute(query, {"user_id": user_id})
            row = result.fetchone()

            if not row:
                return None

            return {
                "id": str(row.id),
                "username": row.nickname,  # nickname을 username으로 매핑
                "email": row.email,
                "balance": float(row.balance) if row.balance else 0,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "last_login": row.updated_at.isoformat() if row.updated_at else None,  # updated_at을 last_login으로 사용
                "is_banned": row.status == 'banned',
                "ban_reason": None,  # 현재 테이블에 없음
                "ban_expires_at": None  # 현재 테이블에 없음
            }
        except Exception as e:
            logger.error(f"사용자 상세 조회 실패: user_id={user_id}, error={e}", exc_info=True)
            raise UserServiceError(f"사용자 상세 조회 실패: {e}") from e
    
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
        except Exception as e:
            logger.error(f"거래 내역 조회 실패: user_id={user_id}, error={e}", exc_info=True)
            raise UserServiceError(f"거래 내역 조회 실패: {e}") from e

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
        except Exception as e:
            logger.error(f"로그인 기록 조회 실패: user_id={user_id}, error={e}", exc_info=True)
            raise UserServiceError(f"로그인 기록 조회 실패: {e}") from e
    
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
        except Exception as e:
            logger.error(f"핸드 기록 조회 실패: user_id={user_id}, error={e}", exc_info=True)
            raise UserServiceError(f"핸드 기록 조회 실패: {e}") from e

    async def get_user_activity(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        activity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        use_cache: bool = True
    ) -> dict:
        """
        사용자 통합 활동 로그 조회 (최적화 버전)

        최적화 전략:
        1. Redis 캐싱 (날짜 필터 없을 때만)
        2. 개별 테이블 COUNT 후 합산 (UNION ALL COUNT 회피)
        3. 각 테이블에서 필요한 만큼만 조회 후 병합

        Args:
            user_id: 사용자 ID
            page: 페이지 번호
            page_size: 페이지 크기
            activity_type: 활동 타입 필터 (login, transaction, hand)
            start_date: 시작 날짜
            end_date: 종료 날짜
            use_cache: 캐시 사용 여부 (날짜 필터 시 False 권장)

        Returns:
            통합 활동 로그 (페이지네이션 포함)
        """
        # 날짜 필터가 있으면 캐시 사용 안함
        if start_date or end_date:
            use_cache = False
        
        # 캐시 체크 (날짜 필터 없을 때만)
        if use_cache:
            try:
                from app.services.cache_service import get_cache_service
                cache = await get_cache_service()
                cached = await cache.get_user_activity(user_id, page, page_size, activity_type)
                if cached:
                    logger.debug(f"캐시 히트: user_activity:{user_id}:{page}")
                    return cached
            except Exception as e:
                logger.warning(f"캐시 조회 중 오류: {e}")
        
        offset = (page - 1) * page_size
        
        try:
            # 최적화: 개별 테이블 카운트 조회 (병렬로 실행하면 더 빠름)
            total = 0
            counts = {}
            
            if activity_type is None or activity_type == "login":
                count_query = text("""
                    SELECT COUNT(*) FROM login_history WHERE user_id = :user_id
                """)
                result = await self.db.execute(count_query, {"user_id": user_id})
                counts["login"] = result.scalar() or 0
                total += counts["login"]
            
            if activity_type is None or activity_type == "transaction":
                count_query = text("""
                    SELECT COUNT(*) FROM transactions WHERE user_id = :user_id
                """)
                result = await self.db.execute(count_query, {"user_id": user_id})
                counts["transaction"] = result.scalar() or 0
                total += counts["transaction"]
            
            if activity_type is None or activity_type == "hand":
                count_query = text("""
                    SELECT COUNT(*) FROM hand_participants WHERE user_id = :user_id
                """)
                result = await self.db.execute(count_query, {"user_id": user_id})
                counts["hand"] = result.scalar() or 0
                total += counts["hand"]
            
            if total == 0:
                result_data = {
                    "items": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": 0
                }
                return result_data
            
            # 최적화된 UNION ALL 쿼리 (LIMIT 적용)
            params = {"user_id": user_id, "limit": page_size, "offset": offset}
            
            # 날짜 필터 조건
            date_filter_login = ""
            date_filter_tx = ""
            date_filter_hand = ""
            
            if start_date:
                date_filter_login = " AND created_at >= :start_date"
                date_filter_tx = " AND created_at >= :start_date"
                date_filter_hand = " AND hp.created_at >= :start_date"
                params["start_date"] = start_date
            
            if end_date:
                date_filter_login += " AND created_at <= :end_date"
                date_filter_tx += " AND created_at <= :end_date"
                date_filter_hand += " AND hp.created_at <= :end_date"
                params["end_date"] = end_date
            
            union_parts = []
            
            if activity_type is None or activity_type == "login":
                union_parts.append(f"""
                    SELECT
                        id::text as id,
                        'login' as activity_type,
                        CASE WHEN success THEN '로그인 성공' ELSE '로그인 실패' END as description,
                        NULL::numeric as amount,
                        ip_address,
                        user_agent as device_info,
                        NULL::text as room_id,
                        NULL::text as hand_id,
                        created_at
                    FROM login_history
                    WHERE user_id = :user_id{date_filter_login}
                """)
            
            if activity_type is None or activity_type == "transaction":
                union_parts.append(f"""
                    SELECT
                        id::text as id,
                        'transaction' as activity_type,
                        description,
                        amount,
                        NULL::text as ip_address,
                        type as device_info,
                        NULL::text as room_id,
                        NULL::text as hand_id,
                        created_at
                    FROM transactions
                    WHERE user_id = :user_id{date_filter_tx}
                """)
            
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
                        hp.created_at
                    FROM hand_participants hp
                    JOIN hand_history h ON hp.hand_id = h.id
                    WHERE hp.user_id = :user_id{date_filter_hand}
                """)
            
            if not union_parts:
                return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}
            
            union_query = " UNION ALL ".join(union_parts)
            
            # 정렬 및 페이지네이션 적용
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
            
            result_data = {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if total > 0 else 0
            }
            
            # 캐시 저장 (날짜 필터 없을 때만)
            if use_cache and not start_date and not end_date:
                try:
                    from app.services.cache_service import get_cache_service
                    cache = await get_cache_service()
                    await cache.set_user_activity(user_id, page, page_size, activity_type, result_data)
                except Exception as e:
                    logger.warning(f"캐시 저장 중 오류: {e}")
            
            return result_data
            
        except Exception as e:
            logger.error(f"활동 로그 조회 실패: user_id={user_id}, error={e}", exc_info=True)
            raise UserServiceError(f"활동 로그 조회 실패: {e}") from e

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
                SELECT id, nickname, balance FROM users WHERE id = :user_id FOR UPDATE
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
                "username": user.nickname,  # nickname을 username으로 매핑
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
                SELECT id, nickname, balance FROM users WHERE id = :user_id FOR UPDATE
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
                "username": user.nickname,  # nickname을 username으로 매핑
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

    async def create_user(
        self,
        nickname: str,
        email: str,
        password: str,
        balance: int = 10000
    ) -> dict:
        """
        사용자 생성

        Args:
            nickname: 닉네임
            email: 이메일
            password: 평문 비밀번호
            balance: 초기 잔액

        Returns:
            생성된 사용자 정보

        Raises:
            DuplicateEmailError: 이메일 중복
            DuplicateNicknameError: 닉네임 중복
        """
        try:
            # 이메일 중복 확인
            result = await self.db.execute(
                select(User).where(User.email == email)
            )
            if result.scalar_one_or_none():
                raise DuplicateEmailError(f"이미 사용 중인 이메일입니다: {email}")

            # 닉네임 중복 확인
            result = await self.db.execute(
                select(User).where(User.nickname == nickname)
            )
            if result.scalar_one_or_none():
                raise DuplicateNicknameError(f"이미 사용 중인 닉네임입니다: {nickname}")

            # 비밀번호 해시
            password_hash = pwd_context.hash(password)

            # 사용자 생성 (ORM 사용)
            user = User(
                id=str(uuid.uuid4()),
                nickname=nickname,
                email=email,
                password_hash=password_hash,
                balance=balance,
                status="active",
            )
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)

            logger.info(f"사용자 생성 완료: user_id={user.id}, nickname={nickname}, email={email}")

            return {
                "id": user.id,
                "username": user.nickname,
                "email": user.email,
                "balance": user.balance,
                "status": user.status,
                "created_at": user.created_at.isoformat() if user.created_at else datetime.now(timezone.utc).isoformat()
            }

        except (DuplicateEmailError, DuplicateNicknameError):
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"사용자 생성 실패: nickname={nickname}, error={e}", exc_info=True)
            raise UserServiceError(f"사용자 생성 실패: {e}") from e

    async def delete_user(self, user_id: str) -> dict:
        """
        사용자 삭제 (soft-delete: status='deleted')

        Args:
            user_id: 사용자 ID

        Returns:
            삭제된 사용자 정보

        Raises:
            UserNotFoundError: 사용자를 찾을 수 없음
        """
        try:
            # 사용자 존재 확인
            user_query = text("SELECT id, nickname, email, status FROM users WHERE id = :user_id")
            result = await self.db.execute(user_query, {"user_id": user_id})
            user = result.fetchone()

            if not user:
                raise UserNotFoundError(f"사용자를 찾을 수 없습니다: {user_id}")

            if user.status == "deleted":
                raise UserServiceError("이미 삭제된 사용자입니다")

            # Soft delete
            now = datetime.now(timezone.utc)
            update_query = text("""
                UPDATE users SET status = 'deleted', updated_at = :updated_at WHERE id = :user_id
            """)
            await self.db.execute(update_query, {"user_id": user_id, "updated_at": now})

            await self.db.commit()

            logger.info(f"사용자 삭제 완료: user_id={user_id}, nickname={user.nickname}")

            return {
                "id": str(user.id),
                "username": user.nickname,
                "email": user.email,
                "status": "deleted"
            }

        except UserNotFoundError:
            await self.db.rollback()
            raise
        except UserServiceError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"사용자 삭제 실패: user_id={user_id}, error={e}", exc_info=True)
            raise UserServiceError(f"사용자 삭제 실패: {e}") from e

    async def update_status(
        self,
        user_id: str,
        status: Literal["active", "suspended"]
    ) -> dict:
        """
        사용자 상태 변경

        Args:
            user_id: 사용자 ID
            status: 새로운 상태 (active/suspended)

        Returns:
            업데이트된 사용자 정보

        Raises:
            UserNotFoundError: 사용자를 찾을 수 없음
        """
        try:
            # 사용자 존재 확인
            user_query = text("SELECT id, nickname, email, status FROM users WHERE id = :user_id")
            result = await self.db.execute(user_query, {"user_id": user_id})
            user = result.fetchone()

            if not user:
                raise UserNotFoundError(f"사용자를 찾을 수 없습니다: {user_id}")

            if user.status == "deleted":
                raise UserServiceError("삭제된 사용자의 상태를 변경할 수 없습니다")

            # 상태 업데이트
            now = datetime.now(timezone.utc)
            update_query = text("""
                UPDATE users SET status = :status, updated_at = :updated_at WHERE id = :user_id
            """)
            await self.db.execute(update_query, {
                "user_id": user_id,
                "status": status,
                "updated_at": now
            })

            await self.db.commit()

            logger.info(f"사용자 상태 변경: user_id={user_id}, old_status={user.status}, new_status={status}")

            return {
                "id": str(user.id),
                "username": user.nickname,
                "email": user.email,
                "status": status
            }

        except UserNotFoundError:
            await self.db.rollback()
            raise
        except UserServiceError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"사용자 상태 변경 실패: user_id={user_id}, error={e}", exc_info=True)
            raise UserServiceError(f"사용자 상태 변경 실패: {e}") from e

    async def reset_password(self, user_id: str, new_password: str) -> dict:
        """
        비밀번호 초기화

        Args:
            user_id: 사용자 ID
            new_password: 새 비밀번호

        Returns:
            사용자 정보

        Raises:
            UserNotFoundError: 사용자를 찾을 수 없음
        """
        try:
            # 사용자 존재 확인
            user_query = text("SELECT id, nickname, email FROM users WHERE id = :user_id")
            result = await self.db.execute(user_query, {"user_id": user_id})
            user = result.fetchone()

            if not user:
                raise UserNotFoundError(f"사용자를 찾을 수 없습니다: {user_id}")

            # 비밀번호 해시 업데이트
            password_hash = pwd_context.hash(new_password)
            now = datetime.now(timezone.utc)

            update_query = text("""
                UPDATE users SET password_hash = :password_hash, updated_at = :updated_at WHERE id = :user_id
            """)
            await self.db.execute(update_query, {
                "user_id": user_id,
                "password_hash": password_hash,
                "updated_at": now
            })

            await self.db.commit()

            logger.info(f"비밀번호 초기화 완료: user_id={user_id}, nickname={user.nickname}")

            return {
                "id": str(user.id),
                "username": user.nickname,
                "email": user.email
            }

        except UserNotFoundError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"비밀번호 초기화 실패: user_id={user_id}, error={e}", exc_info=True)
            raise UserServiceError(f"비밀번호 초기화 실패: {e}") from e

    async def update_user(
        self,
        user_id: str,
        nickname: Optional[str] = None,
        email: Optional[str] = None
    ) -> dict:
        """
        사용자 프로필 수정

        Args:
            user_id: 사용자 ID
            nickname: 새 닉네임 (선택)
            email: 새 이메일 (선택)

        Returns:
            업데이트된 사용자 정보

        Raises:
            UserNotFoundError: 사용자를 찾을 수 없음
            DuplicateEmailError: 이메일 중복
            DuplicateNicknameError: 닉네임 중복
        """
        if not nickname and not email:
            raise ValueError("수정할 필드가 없습니다")

        try:
            # 사용자 존재 확인
            user_query = text("SELECT id, nickname, email, balance, status, created_at FROM users WHERE id = :user_id")
            result = await self.db.execute(user_query, {"user_id": user_id})
            user = result.fetchone()

            if not user:
                raise UserNotFoundError(f"사용자를 찾을 수 없습니다: {user_id}")

            # 중복 확인
            if email and email != user.email:
                check_email = text("SELECT id FROM users WHERE email = :email AND id != :user_id")
                result = await self.db.execute(check_email, {"email": email, "user_id": user_id})
                if result.fetchone():
                    raise DuplicateEmailError(f"이미 사용 중인 이메일입니다: {email}")

            if nickname and nickname != user.nickname:
                check_nickname = text("SELECT id FROM users WHERE nickname = :nickname AND id != :user_id")
                result = await self.db.execute(check_nickname, {"nickname": nickname, "user_id": user_id})
                if result.fetchone():
                    raise DuplicateNicknameError(f"이미 사용 중인 닉네임입니다: {nickname}")

            # 업데이트
            now = datetime.now(timezone.utc)
            update_fields = ["updated_at = :updated_at"]
            params = {"user_id": user_id, "updated_at": now}

            if nickname:
                update_fields.append("nickname = :nickname")
                params["nickname"] = nickname
            if email:
                update_fields.append("email = :email")
                params["email"] = email

            update_query = text(f"UPDATE users SET {', '.join(update_fields)} WHERE id = :user_id")
            await self.db.execute(update_query, params)

            await self.db.commit()

            logger.info(f"사용자 프로필 수정 완료: user_id={user_id}, nickname={nickname}, email={email}")

            return {
                "id": str(user.id),
                "username": nickname or user.nickname,
                "email": email or user.email,
                "balance": float(user.balance) if user.balance else 0,
                "status": user.status,
                "created_at": user.created_at.isoformat() if user.created_at else None
            }

        except (UserNotFoundError, DuplicateEmailError, DuplicateNicknameError, ValueError):
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"사용자 프로필 수정 실패: user_id={user_id}, error={e}", exc_info=True)
            raise UserServiceError(f"사용자 프로필 수정 실패: {e}") from e
