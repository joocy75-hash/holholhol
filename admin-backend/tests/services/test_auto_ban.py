"""
Auto Ban Service Tests - 자동 제재 서비스 테스트

Property-based tests for auto-ban logic and audit logging.

**Property 9: 탐지 점수 기반 자동 조치**
**Property 10: 자동 제재 감사 로그**
**Validates: Requirements 6.1, 6.2, 6.4**
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from hypothesis import given, settings, strategies as st

from app.services.auto_ban import AutoBanService, SEVERITY_ACTIONS


# ============================================================================
# Strategies for Property-Based Testing
# ============================================================================

user_id_strategy = st.uuids().map(str)

suspicion_score_strategy = st.integers(min_value=0, max_value=100)

severity_strategy = st.sampled_from(["low", "medium", "high"])


class TestEvaluateUser:
    """evaluate_user 메서드 테스트"""
    
    @pytest.fixture
    def mock_main_db(self):
        return AsyncMock()
    
    @pytest.fixture
    def mock_admin_db(self):
        return AsyncMock()
    
    @pytest.fixture
    def service(self, mock_main_db, mock_admin_db):
        return AutoBanService(mock_main_db, mock_admin_db)
    
    @pytest.mark.asyncio
    async def test_evaluates_user(self, service, mock_main_db, mock_admin_db):
        """사용자 평가 실행"""
        result = MagicMock()
        result.fetchall.return_value = []
        mock_main_db.execute.return_value = result
        
        evaluation = await service.evaluate_user("user-1")
        
        assert "user_id" in evaluation
        assert "should_flag" in evaluation
        assert "severity" in evaluation
        assert "bot_detection" in evaluation
        assert "anomaly_detection" in evaluation


class TestCreateFlag:
    """create_flag 메서드 테스트"""
    
    @pytest.fixture
    def mock_main_db(self):
        return AsyncMock()
    
    @pytest.fixture
    def mock_admin_db(self):
        return AsyncMock()
    
    @pytest.fixture
    def service(self, mock_main_db, mock_admin_db):
        return AutoBanService(mock_main_db, mock_admin_db)
    
    @pytest.mark.asyncio
    async def test_creates_flag(self, service, mock_admin_db):
        """플래그 생성"""
        flag_id = await service.create_flag(
            user_id="user-1",
            detection_type="auto_detection",
            reasons=["likely_bot"],
            severity="high",
            details={"suspicion_score": 80}
        )
        
        assert flag_id != ""
        assert mock_admin_db.commit.called
    
    @pytest.mark.asyncio
    async def test_handles_exception(self, service, mock_admin_db):
        """예외 발생 시 빈 문자열 반환"""
        mock_admin_db.execute.side_effect = Exception("Database error")
        
        flag_id = await service.create_flag(
            user_id="user-1",
            detection_type="auto_detection",
            reasons=[],
            severity="low",
            details={}
        )
        
        assert flag_id == ""


class TestNotifyAdmins:
    """notify_admins 메서드 테스트"""
    
    @pytest.fixture
    def mock_main_db(self):
        return AsyncMock()
    
    @pytest.fixture
    def mock_admin_db(self):
        return AsyncMock()
    
    @pytest.fixture
    def service(self, mock_main_db, mock_admin_db):
        return AutoBanService(mock_main_db, mock_admin_db)
    
    @pytest.mark.asyncio
    async def test_notifies_admins(self, service, mock_admin_db):
        """관리자 알림 전송"""
        success = await service.notify_admins(
            user_id="user-1",
            reasons=["likely_bot"],
            severity="high"
        )
        
        assert success is True
        assert mock_admin_db.commit.called
    
    @pytest.mark.asyncio
    async def test_handles_exception(self, service, mock_admin_db):
        """예외 발생 시 False 반환"""
        mock_admin_db.execute.side_effect = Exception("Database error")
        
        success = await service.notify_admins(
            user_id="user-1",
            reasons=[],
            severity="low"
        )
        
        assert success is False


class TestBatchEvaluateUsers:
    """batch_evaluate_users 메서드 테스트"""
    
    @pytest.fixture
    def mock_main_db(self):
        return AsyncMock()
    
    @pytest.fixture
    def mock_admin_db(self):
        return AsyncMock()
    
    @pytest.fixture
    def service(self, mock_main_db, mock_admin_db):
        return AutoBanService(mock_main_db, mock_admin_db)
    
    @pytest.mark.asyncio
    async def test_batch_evaluates_users(self, service, mock_main_db, mock_admin_db):
        """여러 사용자 일괄 평가"""
        result = MagicMock()
        result.fetchall.return_value = []
        mock_main_db.execute.return_value = result
        
        batch_result = await service.batch_evaluate_users(["user-1", "user-2"])
        
        assert batch_result["total_evaluated"] == 2
        assert "flagged_count" in batch_result
        assert len(batch_result["results"]) == 2


class TestGetActivePlayersForScan:
    """get_active_players_for_scan 메서드 테스트"""
    
    @pytest.fixture
    def mock_main_db(self):
        return AsyncMock()
    
    @pytest.fixture
    def mock_admin_db(self):
        return AsyncMock()
    
    @pytest.fixture
    def service(self, mock_main_db, mock_admin_db):
        return AutoBanService(mock_main_db, mock_admin_db)
    
    @pytest.mark.asyncio
    async def test_gets_active_players(self, service, mock_main_db):
        """활성 플레이어 목록 조회"""
        mock_rows = [
            MagicMock(user_id="user-1", hand_count=100),
            MagicMock(user_id="user-2", hand_count=75),
        ]
        
        result = MagicMock()
        result.fetchall.return_value = mock_rows
        mock_main_db.execute.return_value = result
        
        players = await service.get_active_players_for_scan()
        
        assert len(players) == 2
        assert "user-1" in players
        assert "user-2" in players
    
    @pytest.mark.asyncio
    async def test_handles_exception(self, service, mock_main_db):
        """예외 발생 시 빈 목록 반환"""
        mock_main_db.execute.side_effect = Exception("Database error")
        
        players = await service.get_active_players_for_scan()
        
        assert players == []


# ============================================================================
# Property-Based Tests
# ============================================================================

class TestSeverityBasedActionProperty:
    """Property 9: 탐지 점수 기반 자동 조치.
    
    **Validates: Requirements 6.1, 6.2**
    
    For any 부정 행위 탐지 결과에 대해, Auto_Ban_Service는 점수에 따라 
    적절한 조치를 취해야 한다: 임계값 미만(무시), low(모니터링), 
    medium(경고), high(임시 제재).
    """

    @pytest.fixture
    def mock_main_db(self):
        return AsyncMock()
    
    @pytest.fixture
    def mock_admin_db(self):
        return AsyncMock()
    
    @pytest.fixture
    def mock_audit_service(self):
        mock = AsyncMock()
        mock.log_action = AsyncMock(return_value={"id": "audit-log-id"})
        return mock

    @pytest.mark.asyncio
    async def test_high_severity_triggers_temp_ban(self, mock_main_db, mock_admin_db, mock_audit_service):
        """high 심각도는 임시 제재 조치."""
        service = AutoBanService(mock_main_db, mock_admin_db, mock_audit_service)
        
        # Mock bot detector to return high suspicion
        with patch.object(service.bot_detector, 'run_bot_detection', new_callable=AsyncMock) as mock_bot:
            with patch.object(service.anomaly_detector, 'run_full_anomaly_detection', new_callable=AsyncMock) as mock_anomaly:
                mock_bot.return_value = {
                    "is_likely_bot": True,
                    "suspicion_score": 85,
                }
                mock_anomaly.return_value = {
                    "is_suspicious": False,
                }
                
                result = await service.evaluate_user("user-123")
                
                assert result["severity"] == "high"
                assert result["action_taken"] == "temp_ban"
                assert result["should_flag"] is True

    @pytest.mark.asyncio
    async def test_medium_severity_triggers_warning(self, mock_main_db, mock_admin_db, mock_audit_service):
        """medium 심각도는 경고 조치."""
        service = AutoBanService(mock_main_db, mock_admin_db, mock_audit_service)
        
        with patch.object(service.bot_detector, 'run_bot_detection', new_callable=AsyncMock) as mock_bot:
            with patch.object(service.anomaly_detector, 'run_full_anomaly_detection', new_callable=AsyncMock) as mock_anomaly:
                mock_bot.return_value = {
                    "is_likely_bot": False,
                    "suspicion_score": 50,  # >= 40 triggers possible_bot
                }
                mock_anomaly.return_value = {
                    "is_suspicious": False,
                }
                
                result = await service.evaluate_user("user-123")
                
                assert result["severity"] == "medium"
                assert result["action_taken"] == "warning"
                assert result["should_flag"] is True

    @pytest.mark.asyncio
    async def test_low_severity_triggers_monitor(self, mock_main_db, mock_admin_db, mock_audit_service):
        """low 심각도는 모니터링 조치."""
        service = AutoBanService(mock_main_db, mock_admin_db, mock_audit_service)
        
        with patch.object(service.bot_detector, 'run_bot_detection', new_callable=AsyncMock) as mock_bot:
            with patch.object(service.anomaly_detector, 'run_full_anomaly_detection', new_callable=AsyncMock) as mock_anomaly:
                mock_bot.return_value = {
                    "is_likely_bot": False,
                    "suspicion_score": 20,  # Below threshold
                }
                mock_anomaly.return_value = {
                    "is_suspicious": False,
                }
                
                result = await service.evaluate_user("user-123")
                
                assert result["severity"] == "low"
                assert result["should_flag"] is False

    @given(severity=severity_strategy)
    @settings(max_examples=10)
    def test_severity_action_mapping(self, severity: str):
        """심각도별 조치 매핑 검증."""
        action = SEVERITY_ACTIONS.get(severity)
        
        assert action is not None
        
        if severity == "low":
            assert action == "monitor"
        elif severity == "medium":
            assert action == "warning"
        elif severity == "high":
            assert action == "temp_ban"


class TestAutoBanAuditLogProperty:
    """Property 10: 자동 제재 감사 로그.
    
    **Validates: Requirements 6.4**
    
    For any 자동 제재 결정에 대해, Auto_Ban_Service는 해당 결정을 
    감사 로그에 기록해야 한다.
    """

    @pytest.fixture
    def mock_main_db(self):
        return AsyncMock()
    
    @pytest.fixture
    def mock_admin_db(self):
        return AsyncMock()
    
    @pytest.fixture
    def mock_audit_service(self):
        mock = AsyncMock()
        mock.log_action = AsyncMock(return_value={"id": "audit-log-id"})
        return mock

    @pytest.mark.asyncio
    async def test_audit_log_created_on_flag(self, mock_main_db, mock_admin_db, mock_audit_service):
        """플래그 생성 시 감사 로그 기록."""
        service = AutoBanService(mock_main_db, mock_admin_db, mock_audit_service)
        
        with patch.object(service.bot_detector, 'run_bot_detection', new_callable=AsyncMock) as mock_bot:
            with patch.object(service.anomaly_detector, 'run_full_anomaly_detection', new_callable=AsyncMock) as mock_anomaly:
                mock_bot.return_value = {
                    "is_likely_bot": True,
                    "suspicion_score": 85,
                }
                mock_anomaly.return_value = {
                    "is_suspicious": False,
                }
                
                await service.evaluate_user("user-123")
                
                # Verify audit log was called
                mock_audit_service.log_action.assert_called_once()
                
                # Verify audit log parameters
                call_args = mock_audit_service.log_action.call_args
                assert call_args.kwargs["admin_user_id"] == "system"
                assert call_args.kwargs["admin_username"] == "auto_ban_system"
                assert call_args.kwargs["action"] == "auto_temp_ban"
                assert call_args.kwargs["target_type"] == "user"
                assert call_args.kwargs["target_id"] == "user-123"
                assert "severity" in call_args.kwargs["details"]
                assert "action_taken" in call_args.kwargs["details"]
                assert "flag_reasons" in call_args.kwargs["details"]

    @pytest.mark.asyncio
    async def test_audit_log_contains_detection_details(self, mock_main_db, mock_admin_db, mock_audit_service):
        """감사 로그에 탐지 상세 정보 포함."""
        service = AutoBanService(mock_main_db, mock_admin_db, mock_audit_service)
        
        with patch.object(service.bot_detector, 'run_bot_detection', new_callable=AsyncMock) as mock_bot:
            with patch.object(service.anomaly_detector, 'run_full_anomaly_detection', new_callable=AsyncMock) as mock_anomaly:
                mock_bot.return_value = {
                    "is_likely_bot": True,
                    "suspicion_score": 90,
                }
                mock_anomaly.return_value = {
                    "is_suspicious": True,
                }
                
                await service.evaluate_user("user-456")
                
                call_args = mock_audit_service.log_action.call_args
                details = call_args.kwargs["details"]
                
                assert details["bot_suspicion_score"] == 90
                assert details["is_likely_bot"] is True
                assert details["is_suspicious"] is True

    @pytest.mark.asyncio
    async def test_no_audit_log_when_no_flag(self, mock_main_db, mock_admin_db, mock_audit_service):
        """플래그가 생성되지 않으면 감사 로그 없음."""
        service = AutoBanService(mock_main_db, mock_admin_db, mock_audit_service)
        
        with patch.object(service.bot_detector, 'run_bot_detection', new_callable=AsyncMock) as mock_bot:
            with patch.object(service.anomaly_detector, 'run_full_anomaly_detection', new_callable=AsyncMock) as mock_anomaly:
                mock_bot.return_value = {
                    "is_likely_bot": False,
                    "suspicion_score": 10,  # Below threshold
                }
                mock_anomaly.return_value = {
                    "is_suspicious": False,
                }
                
                result = await service.evaluate_user("user-789")
                
                assert result["should_flag"] is False
                mock_audit_service.log_action.assert_not_called()

    @pytest.mark.asyncio
    async def test_audit_log_without_audit_service(self, mock_main_db, mock_admin_db):
        """AuditService 없이도 정상 동작."""
        service = AutoBanService(mock_main_db, mock_admin_db, audit_service=None)
        
        with patch.object(service.bot_detector, 'run_bot_detection', new_callable=AsyncMock) as mock_bot:
            with patch.object(service.anomaly_detector, 'run_full_anomaly_detection', new_callable=AsyncMock) as mock_anomaly:
                mock_bot.return_value = {
                    "is_likely_bot": True,
                    "suspicion_score": 85,
                }
                mock_anomaly.return_value = {
                    "is_suspicious": False,
                }
                
                # Should not raise exception
                result = await service.evaluate_user("user-123")
                
                assert result["should_flag"] is True
                assert result["severity"] == "high"

    @given(user_id=user_id_strategy)
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_audit_log_for_any_flagged_user(self, user_id: str):
        """플래그된 모든 사용자에 대해 감사 로그 기록."""
        mock_main_db = AsyncMock()
        mock_admin_db = AsyncMock()
        mock_audit_service = AsyncMock()
        mock_audit_service.log_action = AsyncMock(return_value={"id": "audit-log-id"})
        
        service = AutoBanService(mock_main_db, mock_admin_db, mock_audit_service)
        
        with patch.object(service.bot_detector, 'run_bot_detection', new_callable=AsyncMock) as mock_bot:
            with patch.object(service.anomaly_detector, 'run_full_anomaly_detection', new_callable=AsyncMock) as mock_anomaly:
                mock_bot.return_value = {
                    "is_likely_bot": True,
                    "suspicion_score": 85,
                }
                mock_anomaly.return_value = {
                    "is_suspicious": False,
                }
                
                result = await service.evaluate_user(user_id)
                
                # Property: If flagged, audit log must be created
                if result["should_flag"]:
                    mock_audit_service.log_action.assert_called_once()
                    call_args = mock_audit_service.log_action.call_args
                    assert call_args.kwargs["target_id"] == user_id



class TestAdminNotificationProperty:
    """Property 11: 자동 제재 시 관리자 알림.
    
    **Validates: Requirements 6.3**
    
    For any 자동 제재가 적용되면, Admin_Backend는 관리자에게 알림을 전송해야 한다.
    """

    @pytest.fixture
    def mock_main_db(self):
        return AsyncMock()
    
    @pytest.fixture
    def mock_admin_db(self):
        return AsyncMock()
    
    @pytest.fixture
    def mock_audit_service(self):
        mock = AsyncMock()
        mock.log_action = AsyncMock(return_value={"id": "audit-log-id"})
        return mock
    
    @pytest.fixture
    def mock_telegram_notifier(self):
        mock = MagicMock()
        mock.is_configured = True
        mock.admin_chat_id = "123456789"
        mock._send_message = AsyncMock(return_value=True)
        return mock

    @pytest.mark.asyncio
    async def test_telegram_notification_sent_on_flag(
        self,
        mock_main_db,
        mock_admin_db,
        mock_audit_service,
        mock_telegram_notifier,
    ):
        """플래그 생성 시 Telegram 알림 전송."""
        service = AutoBanService(
            mock_main_db,
            mock_admin_db,
            mock_audit_service,
            mock_telegram_notifier,
        )
        
        with patch.object(service.bot_detector, 'run_bot_detection', new_callable=AsyncMock) as mock_bot:
            with patch.object(service.anomaly_detector, 'run_full_anomaly_detection', new_callable=AsyncMock) as mock_anomaly:
                mock_bot.return_value = {
                    "is_likely_bot": True,
                    "suspicion_score": 85,
                }
                mock_anomaly.return_value = {
                    "is_suspicious": False,
                }
                
                await service.evaluate_user("user-123")
                
                # Verify Telegram notification was sent
                mock_telegram_notifier._send_message.assert_called_once()
                
                # Verify message content
                call_args = mock_telegram_notifier._send_message.call_args
                assert call_args[0][0] == 123456789  # chat_id
                message = call_args[0][1]
                assert "자동 제재 알림" in message
                assert "user-123" in message
                assert "HIGH" in message

    @pytest.mark.asyncio
    async def test_telegram_notification_contains_severity(
        self,
        mock_main_db,
        mock_admin_db,
        mock_audit_service,
        mock_telegram_notifier,
    ):
        """Telegram 알림에 심각도 정보 포함."""
        service = AutoBanService(
            mock_main_db,
            mock_admin_db,
            mock_audit_service,
            mock_telegram_notifier,
        )
        
        with patch.object(service.bot_detector, 'run_bot_detection', new_callable=AsyncMock) as mock_bot:
            with patch.object(service.anomaly_detector, 'run_full_anomaly_detection', new_callable=AsyncMock) as mock_anomaly:
                mock_bot.return_value = {
                    "is_likely_bot": False,
                    "suspicion_score": 50,
                }
                mock_anomaly.return_value = {
                    "is_suspicious": True,
                }
                
                await service.evaluate_user("user-456")
                
                call_args = mock_telegram_notifier._send_message.call_args
                message = call_args[0][1]
                assert "MEDIUM" in message
                assert "경고" in message

    @pytest.mark.asyncio
    async def test_db_notification_saved_on_flag(
        self,
        mock_main_db,
        mock_admin_db,
        mock_audit_service,
    ):
        """플래그 생성 시 DB에 알림 저장."""
        service = AutoBanService(
            mock_main_db,
            mock_admin_db,
            mock_audit_service,
            telegram_notifier=None,
        )
        
        with patch.object(service.bot_detector, 'run_bot_detection', new_callable=AsyncMock) as mock_bot:
            with patch.object(service.anomaly_detector, 'run_full_anomaly_detection', new_callable=AsyncMock) as mock_anomaly:
                mock_bot.return_value = {
                    "is_likely_bot": True,
                    "suspicion_score": 85,
                }
                mock_anomaly.return_value = {
                    "is_suspicious": False,
                }
                
                await service.evaluate_user("user-789")
                
                # Verify DB notification was saved (execute called for both flag and notification)
                assert mock_admin_db.execute.call_count >= 2
                assert mock_admin_db.commit.call_count >= 2

    @pytest.mark.asyncio
    async def test_notification_without_telegram(
        self,
        mock_main_db,
        mock_admin_db,
        mock_audit_service,
    ):
        """Telegram 없이도 DB 알림은 저장."""
        service = AutoBanService(
            mock_main_db,
            mock_admin_db,
            mock_audit_service,
            telegram_notifier=None,
        )
        
        with patch.object(service.bot_detector, 'run_bot_detection', new_callable=AsyncMock) as mock_bot:
            with patch.object(service.anomaly_detector, 'run_full_anomaly_detection', new_callable=AsyncMock) as mock_anomaly:
                mock_bot.return_value = {
                    "is_likely_bot": True,
                    "suspicion_score": 85,
                }
                mock_anomaly.return_value = {
                    "is_suspicious": False,
                }
                
                result = await service.evaluate_user("user-123")
                
                # Should still flag and save notification
                assert result["should_flag"] is True
                assert mock_admin_db.commit.called

    @pytest.mark.asyncio
    async def test_telegram_not_configured(
        self,
        mock_main_db,
        mock_admin_db,
        mock_audit_service,
    ):
        """Telegram이 설정되지 않은 경우."""
        mock_telegram = MagicMock()
        mock_telegram.is_configured = False
        mock_telegram._send_message = AsyncMock()
        
        service = AutoBanService(
            mock_main_db,
            mock_admin_db,
            mock_audit_service,
            mock_telegram,
        )
        
        with patch.object(service.bot_detector, 'run_bot_detection', new_callable=AsyncMock) as mock_bot:
            with patch.object(service.anomaly_detector, 'run_full_anomaly_detection', new_callable=AsyncMock) as mock_anomaly:
                mock_bot.return_value = {
                    "is_likely_bot": True,
                    "suspicion_score": 85,
                }
                mock_anomaly.return_value = {
                    "is_suspicious": False,
                }
                
                await service.evaluate_user("user-123")
                
                # Telegram should not be called when not configured
                mock_telegram._send_message.assert_not_called()

    @given(user_id=user_id_strategy, severity=severity_strategy)
    @settings(max_examples=15)
    @pytest.mark.asyncio
    async def test_notification_for_any_flagged_user(
        self,
        user_id: str,
        severity: str,
    ):
        """플래그된 모든 사용자에 대해 알림 전송."""
        mock_main_db = AsyncMock()
        mock_admin_db = AsyncMock()
        mock_audit_service = AsyncMock()
        mock_audit_service.log_action = AsyncMock(return_value={"id": "audit-log-id"})
        mock_telegram = MagicMock()
        mock_telegram.is_configured = True
        mock_telegram.admin_chat_id = "123456789"
        mock_telegram._send_message = AsyncMock(return_value=True)

        service = AutoBanService(
            mock_main_db,
            mock_admin_db,
            mock_audit_service,
            mock_telegram,
        )

        # Configure bot detector based on severity
        is_likely_bot = severity == "high"
        suspicion_score = {"low": 20, "medium": 50, "high": 85}[severity]

        with patch.object(service.bot_detector, 'run_bot_detection', new_callable=AsyncMock) as mock_bot:
            with patch.object(service.anomaly_detector, 'run_full_anomaly_detection', new_callable=AsyncMock) as mock_anomaly:
                mock_bot.return_value = {
                    "is_likely_bot": is_likely_bot,
                    "suspicion_score": suspicion_score,
                }
                mock_anomaly.return_value = {
                    "is_suspicious": severity == "medium",
                }

                result = await service.evaluate_user(user_id)

                # Property: If flagged, notification must be sent
                if result["should_flag"]:
                    # Either DB or Telegram notification should be attempted
                    assert mock_admin_db.execute.call_count >= 1 or mock_telegram._send_message.called


# ============================================================================
# Phase 2.4: 자동 밴 시스템 연동 테스트
# ============================================================================

class TestProcessDetection:
    """process_detection 메서드 테스트 (Phase 2.4)"""

    @pytest.fixture
    def mock_main_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_admin_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_audit_service(self):
        mock = AsyncMock()
        mock.log_action = AsyncMock(return_value={"id": "audit-log-id"})
        return mock

    @pytest.fixture
    def mock_telegram_notifier(self):
        mock = MagicMock()
        mock.is_configured = True
        mock.admin_chat_id = "123456789"
        mock._send_message = AsyncMock(return_value=True)
        return mock

    @pytest.mark.asyncio
    async def test_process_detection_creates_flag(
        self, mock_main_db, mock_admin_db, mock_audit_service, mock_telegram_notifier
    ):
        """process_detection이 플래그를 생성하는지 확인."""
        service = AutoBanService(
            mock_main_db, mock_admin_db, mock_audit_service, mock_telegram_notifier
        )

        result = await service.process_detection(
            user_id="user-123",
            detection_type="bot_detection",
            severity="medium",
            reasons=["consistent_timing"],
            details={"suspicion_score": 65},
        )

        assert result["flag_id"] is not None
        assert result["user_id"] == "user-123"
        assert result["detection_type"] == "bot_detection"

    @pytest.mark.asyncio
    async def test_process_detection_high_severity_immediate_ban(
        self, mock_main_db, mock_admin_db, mock_audit_service, mock_telegram_notifier
    ):
        """high 심각도 + 즉시 밴 설정 시 자동 밴 적용."""
        service = AutoBanService(
            mock_main_db, mock_admin_db, mock_audit_service, mock_telegram_notifier
        )

        # Mock user exists
        mock_user_result = MagicMock()
        mock_user_result.fetchone.return_value = MagicMock(username="test_user")
        mock_main_db.execute.return_value = mock_user_result

        with patch.object(service, "_settings") as mock_settings:
            mock_settings.auto_ban_enabled = True
            mock_settings.auto_ban_high_severity_immediate = True
            mock_settings.auto_ban_temp_duration_hours = 24

            result = await service.process_detection(
                user_id="user-123",
                detection_type="bot_detection",
                severity="high",
                reasons=["likely_bot"],
                details={"suspicion_score": 85},
            )

            assert result["was_banned"] is True
            assert result["ban_id"] is not None
            assert "high severity" in result["ban_reason"]

    @pytest.mark.asyncio
    async def test_process_detection_disabled_auto_ban(
        self, mock_main_db, mock_admin_db, mock_audit_service, mock_telegram_notifier
    ):
        """auto_ban_enabled=False 시 밴 미적용."""
        service = AutoBanService(
            mock_main_db, mock_admin_db, mock_audit_service, mock_telegram_notifier
        )

        with patch.object(service, "_settings") as mock_settings:
            mock_settings.auto_ban_enabled = False

            result = await service.process_detection(
                user_id="user-123",
                detection_type="bot_detection",
                severity="high",
                reasons=["likely_bot"],
                details={},
            )

            assert result["was_banned"] is False
            assert result["ban_id"] is None


class TestGetUserDetectionCount:
    """_get_user_detection_count 메서드 테스트 (Phase 2.4)"""

    @pytest.fixture
    def mock_main_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_admin_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_returns_detection_count(self, mock_main_db, mock_admin_db):
        """탐지 횟수를 올바르게 반환."""
        service = AutoBanService(mock_main_db, mock_admin_db)

        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(count=5)
        mock_admin_db.execute.return_value = mock_result

        count = await service._get_user_detection_count(
            user_id="user-123",
            detection_type="bot_detection",
        )

        assert count == 5

    @pytest.mark.asyncio
    async def test_returns_zero_on_error(self, mock_main_db, mock_admin_db):
        """에러 발생 시 0 반환."""
        service = AutoBanService(mock_main_db, mock_admin_db)
        mock_admin_db.execute.side_effect = Exception("Database error")

        count = await service._get_user_detection_count(
            user_id="user-123",
            detection_type="bot_detection",
        )

        assert count == 0


class TestGetThresholdForType:
    """_get_threshold_for_type 메서드 테스트 (Phase 2.4)"""

    @pytest.fixture
    def mock_main_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_admin_db(self):
        return AsyncMock()

    def test_chip_dumping_threshold(self, mock_main_db, mock_admin_db):
        """chip_dumping 임계값 반환."""
        service = AutoBanService(mock_main_db, mock_admin_db)
        threshold = service._get_threshold_for_type("chip_dumping")
        assert threshold == service._settings.auto_ban_threshold_chip_dumping

    def test_bot_detection_threshold(self, mock_main_db, mock_admin_db):
        """bot_detection 임계값 반환."""
        service = AutoBanService(mock_main_db, mock_admin_db)
        threshold = service._get_threshold_for_type("bot_detection")
        assert threshold == service._settings.auto_ban_threshold_bot

    def test_anomaly_detection_threshold(self, mock_main_db, mock_admin_db):
        """anomaly_detection 임계값 반환."""
        service = AutoBanService(mock_main_db, mock_admin_db)
        threshold = service._get_threshold_for_type("anomaly_detection")
        assert threshold == service._settings.auto_ban_threshold_anomaly

    def test_unknown_type_default_threshold(self, mock_main_db, mock_admin_db):
        """알 수 없는 유형은 기본값 5 반환."""
        service = AutoBanService(mock_main_db, mock_admin_db)
        threshold = service._get_threshold_for_type("unknown_type")
        assert threshold == 5


class TestApplyAutoBan:
    """_apply_auto_ban 메서드 테스트 (Phase 2.4)"""

    @pytest.fixture
    def mock_main_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_admin_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_audit_service(self):
        mock = AsyncMock()
        mock.log_action = AsyncMock(return_value={"id": "audit-log-id"})
        return mock

    @pytest.fixture
    def mock_telegram_notifier(self):
        mock = MagicMock()
        mock.is_configured = True
        mock.admin_chat_id = "123456789"
        mock._send_message = AsyncMock(return_value=True)
        return mock

    @pytest.mark.asyncio
    async def test_applies_ban_successfully(
        self, mock_main_db, mock_admin_db, mock_audit_service, mock_telegram_notifier
    ):
        """밴을 성공적으로 적용."""
        service = AutoBanService(
            mock_main_db, mock_admin_db, mock_audit_service, mock_telegram_notifier
        )

        # Mock BanService
        with patch("app.services.ban_service.BanService") as MockBanService:
            mock_ban_service = AsyncMock()
            mock_ban_service.create_ban.return_value = {
                "id": "ban-123",
                "user_id": "user-123",
                "expires_at": "2026-01-18T12:00:00Z",
            }
            MockBanService.return_value = mock_ban_service

            result = await service._apply_auto_ban(
                user_id="user-123",
                detection_type="bot_detection",
                severity="high",
                reasons=["likely_bot"],
                flag_id="flag-123",
            )

            assert result is not None
            assert result["id"] == "ban-123"
            mock_ban_service.create_ban.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_on_error(
        self, mock_main_db, mock_admin_db, mock_audit_service, mock_telegram_notifier
    ):
        """에러 발생 시 None 반환."""
        service = AutoBanService(
            mock_main_db, mock_admin_db, mock_audit_service, mock_telegram_notifier
        )

        with patch("app.services.ban_service.BanService") as MockBanService:
            mock_ban_service = AsyncMock()
            mock_ban_service.create_ban.side_effect = Exception("Ban failed")
            MockBanService.return_value = mock_ban_service

            result = await service._apply_auto_ban(
                user_id="user-123",
                detection_type="bot_detection",
                severity="high",
                reasons=["likely_bot"],
                flag_id="flag-123",
            )

            assert result is None


class TestCheckAndLiftExpiredBans:
    """check_and_lift_expired_bans 메서드 테스트 (Phase 2.4)"""

    @pytest.fixture
    def mock_main_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_admin_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_lifts_expired_bans(self, mock_main_db, mock_admin_db):
        """만료된 밴을 해제."""
        service = AutoBanService(mock_main_db, mock_admin_db)

        # Mock expired bans
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            MagicMock(id="ban-1", user_id="user-1", username="user1"),
            MagicMock(id="ban-2", user_id="user-2", username="user2"),
        ]
        mock_admin_db.execute.return_value = mock_result

        with patch("app.services.ban_service.BanService") as MockBanService:
            mock_ban_service = AsyncMock()
            mock_ban_service.lift_ban.return_value = True
            MockBanService.return_value = mock_ban_service

            lifted_count = await service.check_and_lift_expired_bans()

            assert lifted_count == 2
            assert mock_ban_service.lift_ban.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_zero_on_error(self, mock_main_db, mock_admin_db):
        """에러 발생 시 0 반환."""
        service = AutoBanService(mock_main_db, mock_admin_db)
        mock_admin_db.execute.side_effect = Exception("Database error")

        lifted_count = await service.check_and_lift_expired_bans()

        assert lifted_count == 0


class TestAutoBanThresholdBasedProperty:
    """Property 12: 누적 탐지 횟수 기반 자동 밴 (Phase 2.4).

    **Validates: Requirements 6.1, 6.5**

    For any 누적 탐지 횟수가 임계값을 초과하면, Auto_Ban_Service는
    자동으로 임시 밴을 적용해야 한다.
    """

    @pytest.fixture
    def mock_main_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_admin_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_audit_service(self):
        mock = AsyncMock()
        mock.log_action = AsyncMock(return_value={"id": "audit-log-id"})
        return mock

    @pytest.fixture
    def mock_telegram_notifier(self):
        mock = MagicMock()
        mock.is_configured = True
        mock.admin_chat_id = "123456789"
        mock._send_message = AsyncMock(return_value=True)
        return mock

    @pytest.mark.asyncio
    async def test_threshold_exceeded_triggers_ban(
        self, mock_main_db, mock_admin_db, mock_audit_service, mock_telegram_notifier
    ):
        """임계값 초과 시 자동 밴 적용."""
        service = AutoBanService(
            mock_main_db, mock_admin_db, mock_audit_service, mock_telegram_notifier
        )

        # Mock detection count exceeds threshold
        mock_count_result = MagicMock()
        mock_count_result.fetchone.return_value = MagicMock(count=6)  # > 5 (bot threshold)

        # Mock user exists
        mock_user_result = MagicMock()
        mock_user_result.fetchone.return_value = MagicMock(username="test_user")

        mock_admin_db.execute.return_value = mock_count_result
        mock_main_db.execute.return_value = mock_user_result

        with patch.object(service, "_settings") as mock_settings:
            mock_settings.auto_ban_enabled = True
            mock_settings.auto_ban_high_severity_immediate = False
            mock_settings.auto_ban_threshold_bot = 5
            mock_settings.auto_ban_temp_duration_hours = 24

            with patch("app.services.ban_service.BanService") as MockBanService:
                mock_ban_service = AsyncMock()
                mock_ban_service.create_ban.return_value = {
                    "id": "ban-123",
                    "user_id": "user-123",
                    "expires_at": "2026-01-18T12:00:00Z",
                }
                MockBanService.return_value = mock_ban_service

                result = await service.process_detection(
                    user_id="user-123",
                    detection_type="bot_detection",
                    severity="medium",
                    reasons=["consistent_timing"],
                    details={},
                )

                assert result["was_banned"] is True
                assert "threshold exceeded" in result["ban_reason"]

    @pytest.mark.asyncio
    async def test_below_threshold_no_ban(
        self, mock_main_db, mock_admin_db, mock_audit_service, mock_telegram_notifier
    ):
        """임계값 미만 시 밴 미적용."""
        service = AutoBanService(
            mock_main_db, mock_admin_db, mock_audit_service, mock_telegram_notifier
        )

        # Mock detection count below threshold
        mock_count_result = MagicMock()
        mock_count_result.fetchone.return_value = MagicMock(count=2)  # < 5 (bot threshold)
        mock_admin_db.execute.return_value = mock_count_result

        with patch.object(service, "_settings") as mock_settings:
            mock_settings.auto_ban_enabled = True
            mock_settings.auto_ban_high_severity_immediate = False
            mock_settings.auto_ban_threshold_bot = 5

            result = await service.process_detection(
                user_id="user-123",
                detection_type="bot_detection",
                severity="medium",
                reasons=["consistent_timing"],
                details={},
            )

            assert result["was_banned"] is False

    @given(detection_count=st.integers(min_value=0, max_value=10))
    @settings(max_examples=15)
    @pytest.mark.asyncio
    async def test_ban_only_when_threshold_exceeded(self, detection_count: int):
        """임계값 초과 여부에 따른 밴 적용 property 테스트."""
        mock_main_db = AsyncMock()
        mock_admin_db = AsyncMock()
        mock_audit_service = AsyncMock()
        mock_audit_service.log_action = AsyncMock()
        mock_telegram = MagicMock()
        mock_telegram.is_configured = True
        mock_telegram.admin_chat_id = "123456789"
        mock_telegram._send_message = AsyncMock(return_value=True)

        threshold = 5
        service = AutoBanService(
            mock_main_db, mock_admin_db, mock_audit_service, mock_telegram
        )

        # Mock detection count
        mock_count_result = MagicMock()
        mock_count_result.fetchone.return_value = MagicMock(count=detection_count)

        # Mock user exists
        mock_user_result = MagicMock()
        mock_user_result.fetchone.return_value = MagicMock(username="test_user")

        mock_admin_db.execute.return_value = mock_count_result
        mock_main_db.execute.return_value = mock_user_result

        with patch.object(service, "_settings") as mock_settings:
            mock_settings.auto_ban_enabled = True
            mock_settings.auto_ban_high_severity_immediate = False
            mock_settings.auto_ban_threshold_bot = threshold
            mock_settings.auto_ban_temp_duration_hours = 24

            with patch("app.services.ban_service.BanService") as MockBanService:
                mock_ban_service = AsyncMock()
                mock_ban_service.create_ban.return_value = {
                    "id": "ban-123",
                    "user_id": "user-123",
                    "expires_at": "2026-01-18T12:00:00Z",
                }
                MockBanService.return_value = mock_ban_service

                result = await service.process_detection(
                    user_id="user-123",
                    detection_type="bot_detection",
                    severity="medium",
                    reasons=["test"],
                    details={},
                )

                # Property: Ban only when detection_count >= threshold
                if detection_count >= threshold:
                    assert result["was_banned"] is True
                else:
                    assert result["was_banned"] is False
