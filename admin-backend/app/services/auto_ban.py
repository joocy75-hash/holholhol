"""
Auto Ban Service - 자동 제재 서비스

Phase 2.4에서 업그레이드:
- BanService 연동으로 실제 제재 적용
- 누적 탐지 횟수 기반 자동 밴
- 심각도별 자동 제재 정책 적용

탐지 결과 → 플래그 생성 → 누적 횟수 확인 → 임계값 초과 시 자동 밴
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import uuid

from app.services.bot_detector import BotDetector
from app.services.anomaly_detector import AnomalyDetector
from app.services.audit_service import AuditService
from app.services.telegram_notifier import TelegramNotifier
from app.config import get_settings

logger = logging.getLogger(__name__)


# 심각도별 자동 조치 정의
SEVERITY_ACTIONS = {
    "low": "monitor",      # 모니터링만
    "medium": "warning",   # 경고
    "high": "temp_ban",    # 임시 제재
}


class AutoBanService:
    """자동 제재 서비스

    Phase 2.4에서 업그레이드:
    - BanService 연동으로 실제 제재 적용
    - 누적 탐지 횟수 기반 자동 밴
    - 심각도별 자동 제재 정책 적용
    """

    def __init__(
        self,
        main_db: AsyncSession,
        admin_db: AsyncSession,
        audit_service: Optional[AuditService] = None,
        telegram_notifier: Optional[TelegramNotifier] = None,
    ):
        self.main_db = main_db
        self.admin_db = admin_db
        self.bot_detector = BotDetector(main_db, admin_db)
        self.anomaly_detector = AnomalyDetector(main_db, admin_db)
        self._audit_service = audit_service
        self._telegram_notifier = telegram_notifier
        self._settings = get_settings()

        # BanService는 필요할 때 lazy import (순환 참조 방지)
        self._ban_service = None

    def _get_ban_service(self):
        """BanService 인스턴스를 lazy하게 가져옴"""
        if self._ban_service is None:
            from app.services.ban_service import BanService
            self._ban_service = BanService(self.admin_db, self.main_db)
        return self._ban_service
    
    async def evaluate_user(self, user_id: str) -> dict:
        """
        사용자 평가 및 자동 플래깅
        
        Args:
            user_id: 대상 사용자 ID
        
        Returns:
            평가 결과
        """
        bot_result = await self.bot_detector.run_bot_detection(user_id)
        anomaly_result = await self.anomaly_detector.run_full_anomaly_detection(user_id)
        
        should_flag = False
        flag_reasons = []
        severity = "low"
        
        # 봇 탐지 결과 평가
        if bot_result.get("is_likely_bot"):
            should_flag = True
            flag_reasons.append("likely_bot")
            severity = "high"
        elif bot_result.get("suspicion_score", 0) >= 40:
            should_flag = True
            flag_reasons.append("possible_bot")
            severity = "medium"
        
        # 이상 탐지 결과 평가
        if anomaly_result.get("is_suspicious"):
            should_flag = True
            flag_reasons.append("statistical_anomaly")
            if severity != "high":
                severity = "medium"
        
        # 심각도에 따른 자동 조치 결정
        action_taken = SEVERITY_ACTIONS.get(severity, "monitor")
        
        result = {
            "user_id": user_id,
            "should_flag": should_flag,
            "flag_reasons": flag_reasons,
            "severity": severity,
            "action_taken": action_taken,
            "bot_detection": bot_result,
            "anomaly_detection": anomaly_result
        }
        
        # 자동 플래깅
        if should_flag:
            flag_id = await self.create_flag(
                user_id=user_id,
                detection_type="auto_detection",
                reasons=flag_reasons,
                severity=severity,
                details=result
            )
            result["flag_id"] = flag_id
            
            # 감사 로그 기록
            await self._log_auto_ban_decision(
                user_id=user_id,
                severity=severity,
                action_taken=action_taken,
                flag_reasons=flag_reasons,
                flag_id=flag_id,
                details=result,
            )
            
            # 관리자 알림
            await self.notify_admins(user_id, flag_reasons, severity)
        
        return result
    
    async def _log_auto_ban_decision(
        self,
        user_id: str,
        severity: str,
        action_taken: str,
        flag_reasons: list[str],
        flag_id: str,
        details: dict,
    ) -> None:
        """
        자동 제재 결정을 감사 로그에 기록
        
        Args:
            user_id: 대상 사용자 ID
            severity: 심각도
            action_taken: 취해진 조치
            flag_reasons: 플래그 사유 목록
            flag_id: 생성된 플래그 ID
            details: 상세 정보
        """
        if not self._audit_service:
            logger.warning("AuditService not configured, skipping audit log")
            return
        
        try:
            await self._audit_service.log_action(
                admin_user_id="system",
                admin_username="auto_ban_system",
                action=f"auto_{action_taken}",
                target_type="user",
                target_id=user_id,
                details={
                    "severity": severity,
                    "action_taken": action_taken,
                    "flag_reasons": flag_reasons,
                    "flag_id": flag_id,
                    "bot_suspicion_score": details.get("bot_detection", {}).get("suspicion_score"),
                    "is_likely_bot": details.get("bot_detection", {}).get("is_likely_bot"),
                    "is_suspicious": details.get("anomaly_detection", {}).get("is_suspicious"),
                },
                ip_address=None,
            )
            logger.info(
                f"Auto-ban decision logged: user={user_id}, "
                f"severity={severity}, action={action_taken}"
            )
        except Exception as e:
            logger.error(f"Failed to log auto-ban decision: {e}")
    
    async def create_flag(
        self,
        user_id: str,
        detection_type: str,
        reasons: list[str],
        severity: str,
        details: dict
    ) -> str:
        """
        의심 활동 플래그 생성
        
        Args:
            user_id: 사용자 ID
            detection_type: 탐지 유형
            reasons: 플래그 사유 목록
            severity: 심각도
            details: 상세 정보
        
        Returns:
            생성된 플래그 ID
        """
        flag_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        try:
            query = text("""
                INSERT INTO suspicious_activities 
                (id, detection_type, user_ids, details, severity, status, created_at)
                VALUES (:id, :detection_type, :user_ids, :details, :severity, 'pending', :created_at)
            """)
            await self.admin_db.execute(query, {
                "id": flag_id,
                "detection_type": detection_type,
                "user_ids": [user_id],
                "details": str({"reasons": reasons, **details}),
                "severity": severity,
                "created_at": now
            })
            await self.admin_db.commit()
            
            return flag_id
        except Exception:
            return ""
    
    async def notify_admins(
        self,
        user_id: str,
        reasons: list[str],
        severity: str
    ) -> bool:
        """
        관리자에게 알림 전송
        
        Args:
            user_id: 의심 사용자 ID
            reasons: 플래그 사유 목록
            severity: 심각도
        
        Returns:
            알림 전송 성공 여부
        """
        db_success = False
        telegram_success = False
        
        try:
            # 알림 기록 저장
            notification_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            
            query = text("""
                INSERT INTO admin_notifications 
                (id, type, title, message, severity, is_read, created_at)
                VALUES (:id, :type, :title, :message, :severity, false, :created_at)
            """)
            await self.admin_db.execute(query, {
                "id": notification_id,
                "type": "suspicious_activity",
                "title": f"의심 활동 감지: {user_id[:8]}...",
                "message": f"사유: {', '.join(reasons)}",
                "severity": severity,
                "created_at": now
            })
            await self.admin_db.commit()
            db_success = True
        except Exception as e:
            logger.error(f"Failed to save admin notification: {e}")
        
        # Telegram 알림 전송
        if self._telegram_notifier:
            telegram_success = await self._send_telegram_alert(
                user_id=user_id,
                reasons=reasons,
                severity=severity,
            )
        
        return db_success or telegram_success
    
    async def _send_telegram_alert(
        self,
        user_id: str,
        reasons: list[str],
        severity: str,
    ) -> bool:
        """
        Telegram으로 자동 제재 알림 전송
        
        Args:
            user_id: 의심 사용자 ID
            reasons: 플래그 사유 목록
            severity: 심각도
        
        Returns:
            알림 전송 성공 여부
        """
        if not self._telegram_notifier or not self._telegram_notifier.is_configured:
            logger.debug("Telegram notifier not configured, skipping alert")
            return False
        
        try:
            # 심각도별 이모지
            severity_emoji = {
                "low": "ℹ️",
                "medium": "⚠️",
                "high": "🚨",
            }
            
            action = SEVERITY_ACTIONS.get(severity, "monitor")
            action_text = {
                "monitor": "모니터링",
                "warning": "경고",
                "temp_ban": "임시 제재",
            }
            
            message = (
                f"{severity_emoji.get(severity, '⚠️')} <b>[자동 제재 알림]</b>\n\n"
                f"👤 User: <code>{user_id}</code>\n"
                f"📊 심각도: <b>{severity.upper()}</b>\n"
                f"🔧 조치: <b>{action_text.get(action, action)}</b>\n"
                f"📋 사유: {', '.join(reasons)}\n\n"
                "관리자 대시보드에서 확인해주세요."
            )
            
            if self._telegram_notifier.admin_chat_id:
                return await self._telegram_notifier._send_message(
                    int(self._telegram_notifier.admin_chat_id),
                    message,
                )
            return False
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False
    
    async def batch_evaluate_users(
        self,
        user_ids: list[str]
    ) -> dict:
        """
        여러 사용자 일괄 평가
        
        Args:
            user_ids: 평가할 사용자 ID 목록
        
        Returns:
            일괄 평가 결과
        """
        results = []
        flagged_count = 0
        
        for user_id in user_ids:
            result = await self.evaluate_user(user_id)
            results.append(result)
            if result.get("should_flag"):
                flagged_count += 1
        
        return {
            "total_evaluated": len(user_ids),
            "flagged_count": flagged_count,
            "results": results
        }
    
    async def get_active_players_for_scan(
        self,
        min_hands: int = 50,
        time_window_hours: int = 24
    ) -> list[str]:
        """
        스캔 대상 활성 플레이어 목록 조회

        Args:
            min_hands: 최소 핸드 수
            time_window_hours: 시간 범위 (시간)

        Returns:
            사용자 ID 목록
        """
        since = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)

        try:
            query = text("""
                SELECT hp.user_id, COUNT(*) as hand_count
                FROM hand_participants hp
                JOIN hand_history h ON hp.hand_id = h.id
                WHERE h.created_at >= :since
                GROUP BY hp.user_id
                HAVING COUNT(*) >= :min_hands
            """)
            result = await self.main_db.execute(query, {
                "since": since,
                "min_hands": min_hands
            })
            rows = result.fetchall()

            return [row.user_id for row in rows]
        except Exception:
            return []

    # ========== Phase 2.4: 자동 밴 시스템 연동 ==========

    async def process_detection(
        self,
        user_id: str,
        detection_type: str,
        severity: str,
        reasons: list[str],
        details: dict,
    ) -> dict:
        """
        탐지 결과 처리 - 플래그 생성 및 자동 밴 판단

        Phase 2.4의 메인 엔트리 포인트입니다.

        Args:
            user_id: 사용자 ID
            detection_type: 탐지 유형 (chip_dumping, bot_detection, anomaly_detection)
            severity: 심각도 (low, medium, high)
            reasons: 탐지 사유 목록
            details: 상세 정보

        Returns:
            처리 결과 (flag_id, was_banned, ban_id 등)
        """
        result = {
            "user_id": user_id,
            "detection_type": detection_type,
            "severity": severity,
            "flag_id": None,
            "was_banned": False,
            "ban_id": None,
            "ban_reason": None,
        }

        # 1. 플래그 생성
        flag_id = await self.create_flag(
            user_id=user_id,
            detection_type=detection_type,
            reasons=reasons,
            severity=severity,
            details=details,
        )
        result["flag_id"] = flag_id

        if not flag_id:
            logger.error(f"Failed to create flag for user {user_id}")
            return result

        # 2. 자동 밴 활성화 여부 확인
        if not self._settings.auto_ban_enabled:
            logger.debug("Auto ban is disabled, skipping ban check")
            return result

        # 3. 심각도 high이고 즉시 밴 설정이 활성화된 경우 즉시 밴
        if severity == "high" and self._settings.auto_ban_high_severity_immediate:
            ban_result = await self._apply_auto_ban(
                user_id=user_id,
                detection_type=detection_type,
                severity=severity,
                reasons=reasons,
                flag_id=flag_id,
            )
            if ban_result:
                result["was_banned"] = True
                result["ban_id"] = ban_result.get("id")
                result["ban_reason"] = f"high severity {detection_type}"
            return result

        # 4. 누적 탐지 횟수 확인 및 임계값 기반 자동 밴
        detection_count = await self._get_user_detection_count(user_id, detection_type)
        threshold = self._get_threshold_for_type(detection_type)

        logger.info(
            f"User {user_id} detection count for {detection_type}: "
            f"{detection_count}/{threshold}"
        )

        if detection_count >= threshold:
            ban_result = await self._apply_auto_ban(
                user_id=user_id,
                detection_type=detection_type,
                severity=severity,
                reasons=reasons,
                flag_id=flag_id,
            )
            if ban_result:
                result["was_banned"] = True
                result["ban_id"] = ban_result.get("id")
                result["ban_reason"] = f"threshold exceeded ({detection_count}/{threshold})"

        return result

    def _get_threshold_for_type(self, detection_type: str) -> int:
        """탐지 유형별 임계값 반환"""
        thresholds = {
            "chip_dumping": self._settings.auto_ban_threshold_chip_dumping,
            "bot_detection": self._settings.auto_ban_threshold_bot,
            "anomaly_detection": self._settings.auto_ban_threshold_anomaly,
            "auto_detection": self._settings.auto_ban_threshold_anomaly,  # 종합 탐지
        }
        return thresholds.get(detection_type, 5)

    async def _get_user_detection_count(
        self,
        user_id: str,
        detection_type: str,
        time_window_days: int = 30,
    ) -> int:
        """
        사용자의 특정 탐지 유형 누적 횟수 조회

        Args:
            user_id: 사용자 ID
            detection_type: 탐지 유형
            time_window_days: 조회 기간 (일)

        Returns:
            탐지 횟수
        """
        since = datetime.now(timezone.utc) - timedelta(days=time_window_days)

        try:
            query = text("""
                SELECT COUNT(*) as count
                FROM suspicious_activities
                WHERE :user_id = ANY(user_ids)
                  AND detection_type = :detection_type
                  AND created_at >= :since
                  AND status != 'dismissed'
            """)
            result = await self.admin_db.execute(query, {
                "user_id": user_id,
                "detection_type": detection_type,
                "since": since,
            })
            row = result.fetchone()
            return row.count if row else 0
        except Exception as e:
            logger.error(f"Failed to get detection count: {e}")
            return 0

    async def _apply_auto_ban(
        self,
        user_id: str,
        detection_type: str,
        severity: str,
        reasons: list[str],
        flag_id: str,
    ) -> Optional[dict]:
        """
        자동 밴 적용

        Args:
            user_id: 사용자 ID
            detection_type: 탐지 유형
            severity: 심각도
            reasons: 탐지 사유
            flag_id: 관련 플래그 ID

        Returns:
            생성된 밴 정보 또는 None
        """
        try:
            ban_service = self._get_ban_service()

            # 밴 사유 구성
            reason = (
                f"[자동 제재] {detection_type.replace('_', ' ').title()}\n"
                f"사유: {', '.join(reasons)}\n"
                f"심각도: {severity}\n"
                f"관련 플래그: {flag_id}"
            )

            # 임시 밴 적용
            ban_result = await ban_service.create_ban(
                user_id=user_id,
                ban_type="temporary",
                reason=reason,
                created_by="auto_ban_system",
                duration_hours=self._settings.auto_ban_temp_duration_hours,
            )

            logger.warning(
                f"Auto ban applied: user={user_id}, ban_id={ban_result.get('id')}, "
                f"type={detection_type}, severity={severity}"
            )

            # 감사 로그 기록
            await self._log_auto_ban_action(
                user_id=user_id,
                ban_id=ban_result.get("id"),
                detection_type=detection_type,
                severity=severity,
                reasons=reasons,
                flag_id=flag_id,
            )

            # 관리자 알림 (밴 적용 알림)
            await self._notify_auto_ban_applied(
                user_id=user_id,
                ban_result=ban_result,
                detection_type=detection_type,
                severity=severity,
                reasons=reasons,
            )

            return ban_result

        except Exception as e:
            logger.error(f"Failed to apply auto ban for user {user_id}: {e}")
            return None

    async def _log_auto_ban_action(
        self,
        user_id: str,
        ban_id: str,
        detection_type: str,
        severity: str,
        reasons: list[str],
        flag_id: str,
    ) -> None:
        """자동 밴 실행을 감사 로그에 기록"""
        if not self._audit_service:
            return

        try:
            await self._audit_service.log_action(
                admin_user_id="system",
                admin_username="auto_ban_system",
                action="auto_ban_applied",
                target_type="user",
                target_id=user_id,
                details={
                    "ban_id": ban_id,
                    "detection_type": detection_type,
                    "severity": severity,
                    "reasons": reasons,
                    "flag_id": flag_id,
                    "duration_hours": self._settings.auto_ban_temp_duration_hours,
                },
                ip_address=None,
            )
        except Exception as e:
            logger.error(f"Failed to log auto ban action: {e}")

    async def _notify_auto_ban_applied(
        self,
        user_id: str,
        ban_result: dict,
        detection_type: str,
        severity: str,
        reasons: list[str],
    ) -> None:
        """자동 밴 적용 알림 전송"""
        if not self._telegram_notifier or not self._telegram_notifier.is_configured:
            return

        try:
            expires_at = ban_result.get("expires_at", "N/A")
            ban_id = ban_result.get("id", "N/A")

            message = (
                f"🚫 <b>[자동 밴 적용]</b>\n\n"
                f"👤 User: <code>{user_id}</code>\n"
                f"🆔 Ban ID: <code>{ban_id[:8]}...</code>\n"
                f"📊 탐지 유형: <b>{detection_type.replace('_', ' ').title()}</b>\n"
                f"⚠️ 심각도: <b>{severity.upper()}</b>\n"
                f"📋 사유: {', '.join(reasons)}\n"
                f"⏰ 만료: {expires_at}\n\n"
                f"관리자 대시보드에서 확인 및 해제할 수 있습니다."
            )

            if self._telegram_notifier.admin_chat_id:
                await self._telegram_notifier._send_message(
                    int(self._telegram_notifier.admin_chat_id),
                    message,
                )
        except Exception as e:
            logger.error(f"Failed to send auto ban notification: {e}")

    async def check_and_lift_expired_bans(self) -> int:
        """
        만료된 임시 밴 자동 해제 (스케줄러용)

        Returns:
            해제된 밴 수
        """
        try:
            now = datetime.now(timezone.utc)

            # 만료된 밴 조회
            query = text("""
                SELECT id, user_id, username
                FROM bans
                WHERE ban_type = 'temporary'
                  AND expires_at IS NOT NULL
                  AND expires_at <= :now
                  AND lifted_at IS NULL
            """)
            result = await self.admin_db.execute(query, {"now": now})
            expired_bans = result.fetchall()

            lifted_count = 0
            ban_service = self._get_ban_service()

            for ban in expired_bans:
                try:
                    success = await ban_service.lift_ban(ban.id, "auto_ban_system")
                    if success:
                        lifted_count += 1
                        logger.info(f"Automatically lifted expired ban: {ban.id} for user {ban.user_id}")
                except Exception as e:
                    logger.error(f"Failed to lift expired ban {ban.id}: {e}")

            return lifted_count

        except Exception as e:
            logger.error(f"Failed to check expired bans: {e}")
            return 0


# SEVERITY_ACTIONS 상수는 파일 상단에 정의됨
