"""
Bot Detector - 봇 탐지 서비스
행동 패턴 분석을 통해 봇 플레이어를 탐지합니다.

Phase 2.2 Enhancement:
- Redis 기반 실시간 분석 메서드 추가
- 실시간 버퍼 데이터 분석 지원
"""
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import statistics

from app.config import get_settings

if TYPE_CHECKING:
    from redis.asyncio import Redis

settings = get_settings()


class BotDetector:
    """봇 탐지 서비스

    Phase 2.2: Redis 기반 실시간 분석 지원 추가
    """

    def __init__(
        self,
        main_db: AsyncSession,
        admin_db: AsyncSession,
        redis_client: "Redis | None" = None,
    ):
        self.main_db = main_db
        self.admin_db = admin_db
        self.redis = redis_client
    
    async def analyze_response_times(
        self,
        user_id: str,
        time_window_hours: int = 24
    ) -> dict:
        """
        응답 시간 분석
        봇은 일정한 응답 시간을 보이는 경향이 있음
        
        Args:
            user_id: 대상 사용자 ID
            time_window_hours: 분석 시간 범위 (시간)
        
        Returns:
            응답 시간 분석 결과
        """
        since = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)
        
        try:
            query = text("""
                SELECT response_time_ms
                FROM player_actions
                WHERE user_id = :user_id
                  AND created_at >= :since
                  AND response_time_ms IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 100
            """)
            result = await self.main_db.execute(query, {
                "user_id": user_id,
                "since": since
            })
            rows = result.fetchall()
            
            if len(rows) < settings.bot_min_sample_size:
                return {
                    "user_id": user_id,
                    "sample_size": len(rows),
                    "is_suspicious": False,
                    "reason": "insufficient_data"
                }
            
            response_times = [row.response_time_ms for row in rows]
            
            avg_time = statistics.mean(response_times)
            std_dev = statistics.stdev(response_times) if len(response_times) > 1 else 0
            min_time = min(response_times)
            max_time = max(response_times)
            
            # 봇 의심 조건:
            # 1. 표준편차가 매우 낮음 (일정한 응답 시간)
            # 2. 최소 응답 시간이 비정상적으로 빠름 (< 100ms)
            # 3. 응답 시간 범위가 매우 좁음
            
            is_suspicious = False
            reasons = []
            
            if std_dev < settings.bot_std_dev_threshold and len(response_times) >= 20:
                is_suspicious = True
                reasons.append("very_consistent_timing")
            
            if min_time < settings.bot_min_response_time_ms:
                is_suspicious = True
                reasons.append("superhuman_reaction")
            
            if (max_time - min_time) < settings.bot_time_range_threshold and len(response_times) >= 20:
                is_suspicious = True
                reasons.append("narrow_time_range")
            
            return {
                "user_id": user_id,
                "sample_size": len(response_times),
                "avg_response_time_ms": round(avg_time, 2),
                "std_dev_ms": round(std_dev, 2),
                "min_time_ms": min_time,
                "max_time_ms": max_time,
                "is_suspicious": is_suspicious,
                "reasons": reasons
            }
        except Exception:
            return {
                "user_id": user_id,
                "sample_size": 0,
                "is_suspicious": False,
                "reason": "error"
            }
    
    async def analyze_action_patterns(
        self,
        user_id: str,
        time_window_hours: int = 24
    ) -> dict:
        """
        액션 패턴 분석
        봇은 특정 패턴의 액션을 반복하는 경향이 있음
        
        Args:
            user_id: 대상 사용자 ID
            time_window_hours: 분석 시간 범위 (시간)
        
        Returns:
            액션 패턴 분석 결과
        """
        since = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)
        
        try:
            query = text("""
                SELECT action_type, COUNT(*) as count
                FROM player_actions
                WHERE user_id = :user_id
                  AND created_at >= :since
                GROUP BY action_type
            """)
            result = await self.main_db.execute(query, {
                "user_id": user_id,
                "since": since
            })
            rows = result.fetchall()
            
            if not rows:
                return {
                    "user_id": user_id,
                    "is_suspicious": False,
                    "reason": "no_actions"
                }
            
            action_counts = {row.action_type: row.count for row in rows}
            total_actions = sum(action_counts.values())
            
            # 액션 비율 계산
            action_ratios = {
                action: count / total_actions
                for action, count in action_counts.items()
            }
            
            is_suspicious = False
            reasons = []
            
            # 봇 의심 조건:
            # 1. 폴드 비율이 비정상적으로 높거나 낮음
            # 2. 레이즈 비율이 매우 일정함
            # 3. 체크/콜 비율이 비정상적
            
            fold_ratio = action_ratios.get("fold", 0)
            if fold_ratio > settings.bot_excessive_fold_ratio:
                is_suspicious = True
                reasons.append("excessive_folding")
            elif fold_ratio < settings.bot_never_fold_ratio and total_actions > 50:
                is_suspicious = True
                reasons.append("never_folds")
            
            raise_ratio = action_ratios.get("raise", 0)
            if raise_ratio > settings.bot_excessive_raise_ratio and total_actions > 30:
                is_suspicious = True
                reasons.append("excessive_raising")
            
            return {
                "user_id": user_id,
                "total_actions": total_actions,
                "action_ratios": action_ratios,
                "is_suspicious": is_suspicious,
                "reasons": reasons
            }
        except Exception:
            return {
                "user_id": user_id,
                "is_suspicious": False,
                "reason": "error"
            }
    
    async def analyze_session_patterns(
        self,
        user_id: str,
        time_window_days: int = 7
    ) -> dict:
        """
        세션 패턴 분석
        봇은 비정상적으로 긴 세션이나 규칙적인 플레이 시간을 보임
        
        Args:
            user_id: 대상 사용자 ID
            time_window_days: 분석 시간 범위 (일)
        
        Returns:
            세션 패턴 분석 결과
        """
        since = datetime.now(timezone.utc) - timedelta(days=time_window_days)
        
        try:
            query = text("""
                SELECT 
                    DATE(joined_at) as play_date,
                    COUNT(*) as session_count,
                    SUM(EXTRACT(EPOCH FROM (left_at - joined_at))) / 3600 as total_hours
                FROM room_sessions
                WHERE user_id = :user_id
                  AND joined_at >= :since
                  AND left_at IS NOT NULL
                GROUP BY DATE(joined_at)
                ORDER BY play_date
            """)
            result = await self.main_db.execute(query, {
                "user_id": user_id,
                "since": since
            })
            rows = result.fetchall()
            
            if len(rows) < 3:
                return {
                    "user_id": user_id,
                    "is_suspicious": False,
                    "reason": "insufficient_data"
                }
            
            daily_hours = [float(row.total_hours) if row.total_hours else 0 for row in rows]
            
            avg_daily_hours = statistics.mean(daily_hours)
            max_daily_hours = max(daily_hours)
            
            is_suspicious = False
            reasons = []
            
            # 봇 의심 조건:
            # 1. 하루 평균 플레이 시간이 12시간 이상
            # 2. 하루 최대 플레이 시간이 20시간 이상
            # 3. 매일 비슷한 시간 플레이 (표준편차 낮음)
            
            if avg_daily_hours > settings.bot_excessive_daily_hours:
                is_suspicious = True
                reasons.append("excessive_daily_play")
            
            if max_daily_hours > settings.bot_superhuman_session_hours:
                is_suspicious = True
                reasons.append("superhuman_session")
            
            if len(daily_hours) >= 5:
                std_dev = statistics.stdev(daily_hours)
                if std_dev < settings.bot_schedule_std_dev and avg_daily_hours > 4:
                    is_suspicious = True
                    reasons.append("robotic_schedule")
            
            return {
                "user_id": user_id,
                "days_analyzed": len(rows),
                "avg_daily_hours": round(avg_daily_hours, 2),
                "max_daily_hours": round(max_daily_hours, 2),
                "is_suspicious": is_suspicious,
                "reasons": reasons
            }
        except Exception:
            return {
                "user_id": user_id,
                "is_suspicious": False,
                "reason": "error"
            }
    
    async def run_bot_detection(self, user_id: str) -> dict:
        """
        특정 사용자에 대한 전체 봇 탐지 실행

        Args:
            user_id: 대상 사용자 ID

        Returns:
            종합 탐지 결과
        """
        response_analysis = await self.analyze_response_times(user_id)
        action_analysis = await self.analyze_action_patterns(user_id)
        session_analysis = await self.analyze_session_patterns(user_id)

        # 종합 점수 계산
        suspicion_score = 0
        all_reasons = []

        if response_analysis.get("is_suspicious"):
            suspicion_score += 40
            all_reasons.extend(response_analysis.get("reasons", []))

        if action_analysis.get("is_suspicious"):
            suspicion_score += 30
            all_reasons.extend(action_analysis.get("reasons", []))

        if session_analysis.get("is_suspicious"):
            suspicion_score += 30
            all_reasons.extend(session_analysis.get("reasons", []))

        return {
            "user_id": user_id,
            "suspicion_score": suspicion_score,
            "is_likely_bot": suspicion_score >= settings.bot_suspicion_threshold,
            "reasons": all_reasons,
            "response_analysis": response_analysis,
            "action_analysis": action_analysis,
            "session_analysis": session_analysis
        }

    # ========================================
    # Phase 2.2: Redis 기반 실시간 분석 메서드
    # ========================================

    async def analyze_realtime_response_times(
        self,
        response_times: list[int],
    ) -> dict:
        """
        실시간 응답 시간 분석 (Redis 버퍼 데이터 기반)

        FraudEventConsumer에서 수집한 버퍼 데이터를 분석합니다.
        DB 쿼리 없이 메모리 데이터만 분석하여 빠른 응답을 제공합니다.

        Args:
            response_times: 응답 시간 목록 (밀리초)

        Returns:
            분석 결과 딕셔너리
        """
        if len(response_times) < settings.bot_min_sample_size:
            return {
                "sample_size": len(response_times),
                "is_suspicious": False,
                "reason": "insufficient_data"
            }

        try:
            avg_time = statistics.mean(response_times)
            std_dev = statistics.stdev(response_times) if len(response_times) > 1 else 0
            min_time = min(response_times)
            max_time = max(response_times)

            is_suspicious = False
            reasons = []

            # 봇 의심 조건 (settings 기반)
            if std_dev < settings.bot_std_dev_threshold and len(response_times) >= 15:
                is_suspicious = True
                reasons.append("very_consistent_timing")

            if min_time < settings.bot_min_response_time_ms:
                is_suspicious = True
                reasons.append("superhuman_reaction")

            if (max_time - min_time) < settings.bot_time_range_threshold and len(response_times) >= 15:
                is_suspicious = True
                reasons.append("narrow_time_range")

            return {
                "sample_size": len(response_times),
                "avg_response_time_ms": round(avg_time, 2),
                "std_dev_ms": round(std_dev, 2),
                "min_time_ms": min_time,
                "max_time_ms": max_time,
                "is_suspicious": is_suspicious,
                "reasons": reasons
            }

        except Exception:
            return {
                "sample_size": len(response_times),
                "is_suspicious": False,
                "reason": "error"
            }

    async def analyze_realtime_action_patterns(
        self,
        action_counts: dict[str, int],
    ) -> dict:
        """
        실시간 액션 패턴 분석 (Redis 버퍼 데이터 기반)

        Args:
            action_counts: 액션별 카운트 딕셔너리
                예: {"fold": 10, "call": 5, "raise": 2, "total": 17}

        Returns:
            분석 결과 딕셔너리
        """
        total = action_counts.get("total", 0)
        if total < 10:
            return {
                "total_actions": total,
                "is_suspicious": False,
                "reason": "insufficient_data"
            }

        try:
            # 액션 비율 계산
            action_ratios = {
                action: count / total
                for action, count in action_counts.items()
                if action != "total" and isinstance(count, int)
            }

            is_suspicious = False
            reasons = []

            fold_ratio = action_ratios.get("fold", 0)
            if fold_ratio > settings.bot_excessive_fold_ratio:
                is_suspicious = True
                reasons.append("excessive_folding")
            elif fold_ratio < settings.bot_never_fold_ratio and total > 30:
                is_suspicious = True
                reasons.append("never_folds")

            raise_ratio = action_ratios.get("raise", 0)
            if raise_ratio > settings.bot_excessive_raise_ratio and total > 20:
                is_suspicious = True
                reasons.append("excessive_raising")

            return {
                "total_actions": total,
                "action_ratios": action_ratios,
                "is_suspicious": is_suspicious,
                "reasons": reasons
            }

        except Exception:
            return {
                "total_actions": total,
                "is_suspicious": False,
                "reason": "error"
            }

    async def run_realtime_bot_detection(
        self,
        user_id: str,
        response_times: list[int],
        action_counts: dict[str, int] | None = None,
    ) -> dict:
        """
        실시간 봇 탐지 실행 (Redis 버퍼 데이터 기반)

        FraudEventConsumer에서 수집한 데이터를 기반으로 빠른 봇 탐지를 수행합니다.
        DB 쿼리 없이 인메모리 분석만 수행하여 응답 시간을 최소화합니다.

        Args:
            user_id: 대상 사용자 ID
            response_times: 응답 시간 목록 (밀리초)
            action_counts: 액션별 카운트 딕셔너리 (선택)

        Returns:
            종합 탐지 결과
        """
        response_analysis = await self.analyze_realtime_response_times(response_times)

        action_analysis = {}
        if action_counts:
            action_analysis = await self.analyze_realtime_action_patterns(action_counts)

        # 종합 점수 계산
        suspicion_score = 0
        all_reasons = []

        if response_analysis.get("is_suspicious"):
            # 응답 시간 분석 가중치: 50점 (실시간에서는 더 중요)
            suspicion_score += 50
            all_reasons.extend(response_analysis.get("reasons", []))

        if action_analysis.get("is_suspicious"):
            # 액션 패턴 분석 가중치: 30점
            suspicion_score += 30
            all_reasons.extend(action_analysis.get("reasons", []))

        # 심각도 계산
        severity = "low"
        if suspicion_score >= 60:
            severity = "high"
        elif suspicion_score >= 40:
            severity = "medium"

        return {
            "user_id": user_id,
            "suspicion_score": suspicion_score,
            "is_likely_bot": suspicion_score >= settings.bot_suspicion_threshold,
            "severity": severity,
            "reasons": all_reasons,
            "response_analysis": response_analysis,
            "action_analysis": action_analysis,
        }

    async def analyze_from_redis(
        self,
        user_id: str,
        time_window_hours: int = 24,
    ) -> dict:
        """
        Redis에 저장된 데이터를 기반으로 봇 탐지 실행

        게임 서버에서 저장한 Redis 데이터를 조회하여 분석합니다.
        DB 대신 Redis를 사용하여 빠른 분석이 가능합니다.

        Args:
            user_id: 대상 사용자 ID
            time_window_hours: 분석 시간 범위 (시간)

        Returns:
            종합 탐지 결과
        """
        if not self.redis:
            return {
                "user_id": user_id,
                "is_suspicious": False,
                "reason": "redis_not_available"
            }

        try:
            # Redis에서 응답 시간 조회
            response_times_key = f"stats:response_times:{user_id}"
            import time
            now_ms = int(time.time() * 1000)
            since_ms = now_ms - (time_window_hours * 3600 * 1000)

            members = await self.redis.zrangebyscore(
                response_times_key, since_ms, now_ms
            )

            response_times = []
            for member in members:
                try:
                    response_time = int(member.split(":")[0])
                    response_times.append(response_time)
                except (ValueError, IndexError):
                    continue

            # Redis에서 액션 패턴 조회
            action_pattern_key = f"stats:action_pattern:{user_id}"
            action_data = await self.redis.hgetall(action_pattern_key)
            action_counts = {k: int(v) for k, v in action_data.items()}

            # 실시간 분석 실행
            return await self.run_realtime_bot_detection(
                user_id=user_id,
                response_times=response_times,
                action_counts=action_counts if action_counts else None,
            )

        except Exception as e:
            return {
                "user_id": user_id,
                "is_suspicious": False,
                "reason": f"error: {str(e)}"
            }
