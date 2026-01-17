"""
Suspicious User Service - 의심 사용자 통합 조회 서비스

Phase 3.7: 부정 사용자 의심 리스트
- 사용자별 의심 점수 계산
- 탐지 시스템 결과 통합 뷰 (ChipDumping, Bot, Anomaly)
- 관리자 검토 상태 관리
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


# 탐지 유형별 점수 가중치
DETECTION_TYPE_WEIGHTS = {
    "chip_dumping": 40,
    "bot_detection": 35,
    "anomaly_detection": 25,
    "auto_detection": 30,  # 종합 탐지
}

# 심각도별 점수 배수
SEVERITY_MULTIPLIERS = {
    "low": 1.0,
    "medium": 1.5,
    "high": 2.5,
}


class SuspiciousUserService:
    """의심 사용자 통합 조회 서비스"""

    def __init__(self, main_db: AsyncSession, admin_db: AsyncSession):
        self.main_db = main_db
        self.admin_db = admin_db

    async def get_suspicious_users(
        self,
        page: int = 1,
        page_size: int = 20,
        detection_type: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        min_score: Optional[float] = None,
        sort_by: str = "suspicion_score",
        sort_order: str = "desc",
    ) -> dict:
        """
        의심 사용자 목록 조회 (사용자 중심 통합 뷰)

        Args:
            page: 페이지 번호
            page_size: 페이지 크기
            detection_type: 탐지 유형 필터
            severity: 심각도 필터
            status: 검토 상태 필터
            min_score: 최소 의심 점수
            sort_by: 정렬 기준 (suspicion_score, detection_count, last_detected)
            sort_order: 정렬 순서 (asc, desc)

        Returns:
            의심 사용자 목록 (페이지네이션)
        """
        offset = (page - 1) * page_size

        # 필터 조건 구성
        where_clauses = []
        params = {"limit": page_size, "offset": offset}

        if detection_type:
            where_clauses.append("sa.detection_type = :detection_type")
            params["detection_type"] = detection_type

        if severity:
            where_clauses.append("sa.severity = :severity")
            params["severity"] = severity

        if status:
            where_clauses.append("sa.status = :status")
            params["status"] = status

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # 정렬 검증
        valid_sort_fields = ["suspicion_score", "detection_count", "last_detected"]
        if sort_by not in valid_sort_fields:
            sort_by = "suspicion_score"
        sort_order = "DESC" if sort_order.lower() == "desc" else "ASC"

        try:
            # 사용자별 집계 쿼리
            # PostgreSQL의 unnest를 사용하여 user_ids 배열을 풀어서 집계
            aggregate_query = text(f"""
                WITH user_activities AS (
                    SELECT
                        unnest(user_ids) as user_id,
                        id,
                        detection_type,
                        severity,
                        status,
                        created_at
                    FROM suspicious_activities
                    WHERE {where_sql}
                ),
                user_scores AS (
                    SELECT
                        user_id,
                        COUNT(*) as detection_count,
                        COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count,
                        COUNT(CASE WHEN status = 'confirmed' THEN 1 END) as confirmed_count,
                        MAX(created_at) as last_detected,
                        -- 의심 점수 계산: 탐지 유형 가중치 * 심각도 배수의 합
                        SUM(
                            CASE detection_type
                                WHEN 'chip_dumping' THEN 40
                                WHEN 'bot_detection' THEN 35
                                WHEN 'anomaly_detection' THEN 25
                                ELSE 30
                            END *
                            CASE severity
                                WHEN 'high' THEN 2.5
                                WHEN 'medium' THEN 1.5
                                ELSE 1.0
                            END
                        ) as suspicion_score,
                        -- 탐지 유형별 카운트
                        COUNT(CASE WHEN detection_type = 'chip_dumping' THEN 1 END) as chip_dumping_count,
                        COUNT(CASE WHEN detection_type = 'bot_detection' THEN 1 END) as bot_detection_count,
                        COUNT(CASE WHEN detection_type = 'anomaly_detection' THEN 1 END) as anomaly_count,
                        -- 최고 심각도
                        MAX(CASE severity
                            WHEN 'high' THEN 3
                            WHEN 'medium' THEN 2
                            ELSE 1
                        END) as max_severity_level
                    FROM user_activities
                    GROUP BY user_id
                )
                SELECT
                    user_id,
                    detection_count,
                    pending_count,
                    confirmed_count,
                    last_detected,
                    suspicion_score,
                    chip_dumping_count,
                    bot_detection_count,
                    anomaly_count,
                    CASE max_severity_level
                        WHEN 3 THEN 'high'
                        WHEN 2 THEN 'medium'
                        ELSE 'low'
                    END as max_severity
                FROM user_scores
                {"WHERE suspicion_score >= :min_score" if min_score else ""}
                ORDER BY {sort_by} {sort_order}
                LIMIT :limit OFFSET :offset
            """)

            if min_score:
                params["min_score"] = min_score

            result = await self.admin_db.execute(aggregate_query, params)
            rows = result.fetchall()

            # 총 개수 조회
            count_query = text(f"""
                WITH user_activities AS (
                    SELECT
                        unnest(user_ids) as user_id,
                        detection_type,
                        severity,
                        status
                    FROM suspicious_activities
                    WHERE {where_sql}
                ),
                user_scores AS (
                    SELECT
                        user_id,
                        SUM(
                            CASE detection_type
                                WHEN 'chip_dumping' THEN 40
                                WHEN 'bot_detection' THEN 35
                                WHEN 'anomaly_detection' THEN 25
                                ELSE 30
                            END *
                            CASE severity
                                WHEN 'high' THEN 2.5
                                WHEN 'medium' THEN 1.5
                                ELSE 1.0
                            END
                        ) as suspicion_score
                    FROM user_activities
                    GROUP BY user_id
                )
                SELECT COUNT(DISTINCT user_id)
                FROM user_scores
                {"WHERE suspicion_score >= :min_score" if min_score else ""}
            """)
            count_result = await self.admin_db.execute(count_query, params)
            total = count_result.scalar() or 0

            # 사용자 정보 조회 (메인 DB에서)
            user_ids = [row.user_id for row in rows]
            user_info = await self._get_user_info_batch(user_ids)

            items = []
            for row in rows:
                user = user_info.get(row.user_id, {})
                items.append({
                    "user_id": row.user_id,
                    "username": user.get("username", "Unknown"),
                    "email": user.get("email"),
                    "is_banned": user.get("is_banned", False),
                    "suspicion_score": float(row.suspicion_score) if row.suspicion_score else 0,
                    "detection_count": row.detection_count,
                    "pending_count": row.pending_count,
                    "confirmed_count": row.confirmed_count,
                    "max_severity": row.max_severity,
                    "detection_breakdown": {
                        "chip_dumping": row.chip_dumping_count,
                        "bot_detection": row.bot_detection_count,
                        "anomaly_detection": row.anomaly_count,
                    },
                    "last_detected": row.last_detected.isoformat() if row.last_detected else None,
                })

            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
            }

        except Exception as e:
            logger.error(f"의심 사용자 목록 조회 실패: {e}", exc_info=True)
            return {
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0,
            }

    async def get_suspicious_user_detail(self, user_id: str) -> Optional[dict]:
        """
        의심 사용자 상세 정보 조회

        Args:
            user_id: 사용자 ID

        Returns:
            사용자 상세 정보 (탐지 기록 포함)
        """
        try:
            # 사용자 기본 정보
            user_info = await self._get_user_info(user_id)
            if not user_info:
                return None

            # 탐지 기록 조회
            activities_query = text("""
                SELECT
                    id, detection_type, details, severity, status,
                    created_at, updated_at, reviewed_by
                FROM suspicious_activities
                WHERE :user_id = ANY(user_ids)
                ORDER BY created_at DESC
                LIMIT 50
            """)
            result = await self.admin_db.execute(activities_query, {"user_id": user_id})
            activities = result.fetchall()

            # 통계 계산
            stats = {
                "total_detections": 0,
                "pending": 0,
                "reviewing": 0,
                "confirmed": 0,
                "dismissed": 0,
                "by_type": {},
                "by_severity": {"low": 0, "medium": 0, "high": 0},
            }

            activity_list = []
            for act in activities:
                stats["total_detections"] += 1
                stats[act.status] = stats.get(act.status, 0) + 1
                stats["by_type"][act.detection_type] = stats["by_type"].get(act.detection_type, 0) + 1
                stats["by_severity"][act.severity] = stats["by_severity"].get(act.severity, 0) + 1

                # 상세 정보 파싱
                details = act.details
                if isinstance(details, str):
                    import json
                    try:
                        details = json.loads(details)
                    except:
                        details = {"raw": details}

                activity_list.append({
                    "id": act.id,
                    "detection_type": act.detection_type,
                    "severity": act.severity,
                    "status": act.status,
                    "details": details if isinstance(details, dict) else {"raw": str(details)},
                    "created_at": act.created_at.isoformat() if act.created_at else None,
                    "updated_at": act.updated_at.isoformat() if act.updated_at else None,
                    "reviewed_by": act.reviewed_by,
                })

            # 의심 점수 계산
            suspicion_score = self._calculate_suspicion_score(activity_list)

            return {
                "user_id": user_id,
                "username": user_info.get("username"),
                "email": user_info.get("email"),
                "balance": user_info.get("balance", 0),
                "is_banned": user_info.get("is_banned", False),
                "ban_reason": user_info.get("ban_reason"),
                "created_at": user_info.get("created_at"),
                "last_login": user_info.get("last_login"),
                "suspicion_score": suspicion_score,
                "statistics": stats,
                "activities": activity_list,
            }

        except Exception as e:
            logger.error(f"의심 사용자 상세 조회 실패: user_id={user_id}, error={e}", exc_info=True)
            return None

    def _calculate_suspicion_score(self, activities: list) -> float:
        """의심 점수 계산"""
        score = 0.0
        for act in activities:
            # dismissed 상태는 점수에서 제외
            if act.get("status") == "dismissed":
                continue

            base_score = DETECTION_TYPE_WEIGHTS.get(act.get("detection_type"), 30)
            multiplier = SEVERITY_MULTIPLIERS.get(act.get("severity"), 1.0)

            # confirmed 상태는 추가 가중치
            if act.get("status") == "confirmed":
                multiplier *= 1.5

            score += base_score * multiplier

        return round(score, 2)

    async def _get_user_info(self, user_id: str) -> Optional[dict]:
        """사용자 정보 조회"""
        try:
            query = text("""
                SELECT id, username, email, balance, is_banned, ban_reason,
                       created_at, last_login
                FROM users
                WHERE id = :user_id
            """)
            result = await self.main_db.execute(query, {"user_id": user_id})
            row = result.fetchone()

            if not row:
                return None

            return {
                "id": str(row.id),
                "username": row.username,
                "email": row.email,
                "balance": float(row.balance) if row.balance else 0,
                "is_banned": row.is_banned or False,
                "ban_reason": row.ban_reason if hasattr(row, "ban_reason") else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "last_login": row.last_login.isoformat() if row.last_login else None,
            }
        except Exception as e:
            logger.error(f"사용자 정보 조회 실패: {e}")
            return None

    async def _get_user_info_batch(self, user_ids: list[str]) -> dict:
        """사용자 정보 일괄 조회"""
        if not user_ids:
            return {}

        try:
            # PostgreSQL의 ANY를 사용하여 일괄 조회
            query = text("""
                SELECT id, username, email, is_banned
                FROM users
                WHERE id = ANY(:user_ids)
            """)
            result = await self.main_db.execute(query, {"user_ids": user_ids})
            rows = result.fetchall()

            return {
                str(row.id): {
                    "username": row.username,
                    "email": row.email,
                    "is_banned": row.is_banned or False,
                }
                for row in rows
            }
        except Exception as e:
            logger.error(f"사용자 정보 일괄 조회 실패: {e}")
            return {}

    async def get_suspicion_summary(self) -> dict:
        """
        의심 사용자 요약 통계

        Returns:
            요약 통계
        """
        try:
            # 전체 의심 사용자 수 및 상태별 통계
            summary_query = text("""
                WITH user_activities AS (
                    SELECT
                        unnest(user_ids) as user_id,
                        status,
                        severity
                    FROM suspicious_activities
                ),
                user_stats AS (
                    SELECT
                        user_id,
                        MAX(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as has_pending,
                        MAX(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as has_confirmed,
                        MAX(CASE severity
                            WHEN 'high' THEN 3
                            WHEN 'medium' THEN 2
                            ELSE 1
                        END) as max_severity_level
                    FROM user_activities
                    GROUP BY user_id
                )
                SELECT
                    COUNT(DISTINCT user_id) as total_suspicious_users,
                    SUM(has_pending) as users_with_pending,
                    SUM(has_confirmed) as users_with_confirmed,
                    SUM(CASE WHEN max_severity_level = 3 THEN 1 ELSE 0 END) as high_severity_users,
                    SUM(CASE WHEN max_severity_level = 2 THEN 1 ELSE 0 END) as medium_severity_users,
                    SUM(CASE WHEN max_severity_level = 1 THEN 1 ELSE 0 END) as low_severity_users
                FROM user_stats
            """)
            result = await self.admin_db.execute(summary_query)
            row = result.fetchone()

            if not row:
                return {
                    "total_suspicious_users": 0,
                    "users_with_pending": 0,
                    "users_with_confirmed": 0,
                    "by_severity": {"high": 0, "medium": 0, "low": 0},
                }

            return {
                "total_suspicious_users": row.total_suspicious_users or 0,
                "users_with_pending": row.users_with_pending or 0,
                "users_with_confirmed": row.users_with_confirmed or 0,
                "by_severity": {
                    "high": row.high_severity_users or 0,
                    "medium": row.medium_severity_users or 0,
                    "low": row.low_severity_users or 0,
                },
            }

        except Exception as e:
            logger.error(f"의심 사용자 요약 조회 실패: {e}", exc_info=True)
            return {
                "total_suspicious_users": 0,
                "users_with_pending": 0,
                "users_with_confirmed": 0,
                "by_severity": {"high": 0, "medium": 0, "low": 0},
            }

    async def update_review_status(
        self,
        activity_id: int,
        status: str,
        admin_user_id: str,
        notes: Optional[str] = None,
    ) -> Optional[dict]:
        """
        의심 활동 검토 상태 업데이트

        Args:
            activity_id: 활동 ID
            status: 새 상태 (pending, reviewing, confirmed, dismissed)
            admin_user_id: 관리자 ID
            notes: 검토 메모

        Returns:
            업데이트된 활동 정보
        """
        valid_statuses = ["pending", "reviewing", "confirmed", "dismissed"]
        if status not in valid_statuses:
            raise ValueError(f"유효하지 않은 상태: {status}")

        try:
            # 현재 활동 조회
            select_query = text("""
                SELECT id, detection_type, user_ids, severity, status, details
                FROM suspicious_activities
                WHERE id = :activity_id
            """)
            result = await self.admin_db.execute(select_query, {"activity_id": activity_id})
            activity = result.fetchone()

            if not activity:
                return None

            # 상태 업데이트
            now = datetime.now(timezone.utc)
            update_query = text("""
                UPDATE suspicious_activities
                SET status = :status,
                    reviewed_by = :reviewed_by,
                    reviewed_at = :reviewed_at,
                    review_notes = :notes,
                    updated_at = :updated_at
                WHERE id = :activity_id
                RETURNING id, detection_type, severity, status, created_at, updated_at
            """)
            result = await self.admin_db.execute(update_query, {
                "activity_id": activity_id,
                "status": status,
                "reviewed_by": admin_user_id,
                "reviewed_at": now,
                "notes": notes,
                "updated_at": now,
            })
            updated = result.fetchone()
            await self.admin_db.commit()

            if not updated:
                return None

            logger.info(
                f"검토 상태 업데이트: activity_id={activity_id}, "
                f"status={status}, admin={admin_user_id}"
            )

            return {
                "id": updated.id,
                "detection_type": updated.detection_type,
                "severity": updated.severity,
                "status": updated.status,
                "reviewed_by": admin_user_id,
                "reviewed_at": now.isoformat(),
                "notes": notes,
                "created_at": updated.created_at.isoformat() if updated.created_at else None,
                "updated_at": updated.updated_at.isoformat() if updated.updated_at else None,
            }

        except ValueError:
            raise
        except Exception as e:
            await self.admin_db.rollback()
            logger.error(f"검토 상태 업데이트 실패: activity_id={activity_id}, error={e}", exc_info=True)
            raise

    async def get_activity_detail(self, activity_id: int) -> Optional[dict]:
        """
        의심 활동 상세 조회

        Args:
            activity_id: 활동 ID

        Returns:
            활동 상세 정보
        """
        try:
            query = text("""
                SELECT
                    id, detection_type, user_ids, details, severity, status,
                    created_at, updated_at, reviewed_by, reviewed_at, review_notes
                FROM suspicious_activities
                WHERE id = :activity_id
            """)
            result = await self.admin_db.execute(query, {"activity_id": activity_id})
            row = result.fetchone()

            if not row:
                return None

            # 관련 사용자 정보 조회
            user_ids = row.user_ids or []
            user_info = await self._get_user_info_batch(user_ids)

            # 상세 정보 파싱
            details = row.details
            if isinstance(details, str):
                import json
                try:
                    details = json.loads(details)
                except:
                    details = {"raw": details}

            return {
                "id": row.id,
                "detection_type": row.detection_type,
                "user_ids": user_ids,
                "users": [
                    {
                        "user_id": uid,
                        "username": user_info.get(uid, {}).get("username", "Unknown"),
                        "is_banned": user_info.get(uid, {}).get("is_banned", False),
                    }
                    for uid in user_ids
                ],
                "details": details if isinstance(details, dict) else {"raw": str(details)},
                "severity": row.severity,
                "status": row.status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "reviewed_by": row.reviewed_by,
                "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
                "review_notes": row.review_notes,
            }

        except Exception as e:
            logger.error(f"활동 상세 조회 실패: activity_id={activity_id}, error={e}", exc_info=True)
            return None
