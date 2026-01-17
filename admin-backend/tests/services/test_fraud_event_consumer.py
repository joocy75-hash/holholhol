"""Tests for FraudEventConsumer service.

Property 6: 이벤트 유형별 탐지기 호출
Property 7: 의심 활동 탐지 시 자동 제재 평가

**Validates: Requirements 4.2, 4.3, 4.4, 4.5**
"""

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.fraud_event_consumer import (
    CHANNEL_HAND_COMPLETED,
    CHANNEL_PLAYER_ACTION,
    CHANNEL_PLAYER_STATS,
    FraudEventConsumer,
    get_fraud_consumer,
    init_fraud_consumer,
)


class TestFraudEventConsumerInit:
    """FraudEventConsumer 초기화 테스트."""

    def test_init(self):
        """초기화 테스트."""
        mock_redis = MagicMock()
        mock_main_db_factory = MagicMock()
        mock_admin_db_factory = MagicMock()
        
        consumer = FraudEventConsumer(
            mock_redis,
            mock_main_db_factory,
            mock_admin_db_factory,
        )
        
        assert consumer.redis is mock_redis
        assert consumer._running is False
        assert consumer._task is None

    def test_global_instance(self):
        """글로벌 인스턴스 초기화 테스트."""
        mock_redis = MagicMock()
        mock_main_db_factory = MagicMock()
        mock_admin_db_factory = MagicMock()
        
        consumer = init_fraud_consumer(
            mock_redis,
            mock_main_db_factory,
            mock_admin_db_factory,
        )
        
        assert get_fraud_consumer() is consumer


class TestStartStop:
    """시작/중지 테스트."""

    @pytest.mark.asyncio
    async def test_start(self):
        """시작 테스트."""
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        mock_pubsub.get_message = AsyncMock(return_value=None)
        
        mock_redis = MagicMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
        
        consumer = FraudEventConsumer(
            mock_redis,
            MagicMock(),
            MagicMock(),
        )
        
        await consumer.start()
        
        assert consumer._running is True
        assert consumer._pubsub is mock_pubsub
        
        mock_pubsub.subscribe.assert_called_once_with(
            CHANNEL_HAND_COMPLETED,
            CHANNEL_PLAYER_ACTION,
            CHANNEL_PLAYER_STATS,
        )
        
        await consumer.stop()

    @pytest.mark.asyncio
    async def test_stop(self):
        """중지 테스트."""
        mock_pubsub = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        mock_pubsub.get_message = AsyncMock(return_value=None)
        
        mock_redis = MagicMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
        
        consumer = FraudEventConsumer(
            mock_redis,
            MagicMock(),
            MagicMock(),
        )
        
        await consumer.start()
        await consumer.stop()
        
        assert consumer._running is False
        assert consumer._pubsub is None
        assert consumer._task is None


class TestHandleHandCompleted:
    """Property 6: 이벤트 유형별 탐지기 호출 - hand_completed."""

    @pytest.fixture
    def consumer(self):
        mock_redis = MagicMock()
        mock_main_db = AsyncMock()
        mock_main_db.close = AsyncMock()
        mock_admin_db = AsyncMock()
        mock_admin_db.close = AsyncMock()
        
        return FraudEventConsumer(
            mock_redis,
            lambda: mock_main_db,
            lambda: mock_admin_db,
        )

    @pytest.mark.asyncio
    async def test_handle_hand_completed_calls_detector(self, consumer):
        """핸드 완료 이벤트 시 ChipDumpingDetector 호출."""
        event = {
            "event_type": "hand_completed",
            "hand_id": "hand-123",
            "room_id": "room-456",
            "hand_number": 42,
            "pot_size": 1500,
            "community_cards": ["Ah", "Kd", "Qc", "Js", "Th"],
            "participants": [
                {"user_id": "user-1", "seat": 0, "bet_amount": 500, "won_amount": 1500},
                {"user_id": "user-2", "seat": 1, "bet_amount": 500, "won_amount": 0},
            ],
        }
        
        mock_detector = MagicMock()
        mock_detector.detect_one_way_chip_flow = AsyncMock(return_value=[])
        
        import app.services.chip_dumping_detector as cdd_module
        original_class = cdd_module.ChipDumpingDetector
        cdd_module.ChipDumpingDetector = MagicMock(return_value=mock_detector)
        
        try:
            await consumer.handle_hand_completed(event)
            mock_detector.detect_one_way_chip_flow.assert_called_once()
        finally:
            cdd_module.ChipDumpingDetector = original_class

    @pytest.mark.asyncio
    async def test_handle_hand_completed_skips_single_participant(self, consumer):
        """참가자가 1명이면 분석 스킵."""
        event = {
            "event_type": "hand_completed",
            "hand_id": "hand-123",
            "room_id": "room-456",
            "participants": [
                {"user_id": "user-1", "seat": 0, "bet_amount": 500, "won_amount": 1500},
            ],
        }
        
        await consumer.handle_hand_completed(event)


class TestHandlePlayerAction:
    """Property 6: 이벤트 유형별 탐지기 호출 - player_action."""

    @pytest.fixture
    def consumer(self):
        mock_redis = MagicMock()
        mock_main_db = AsyncMock()
        mock_admin_db = AsyncMock()
        
        return FraudEventConsumer(
            mock_redis,
            lambda: mock_main_db,
            lambda: mock_admin_db,
        )

    @pytest.mark.asyncio
    async def test_handle_player_action_buffers_data(self, consumer):
        """플레이어 액션 이벤트 버퍼링."""
        event = {
            "event_type": "player_action",
            "user_id": "user-123",
            "room_id": "room-456",
            "action_type": "call",
            "amount": 100,
            "response_time_ms": 2500,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        await consumer.handle_player_action(event)
        
        assert "user-123" in consumer._action_buffer
        assert len(consumer._action_buffer["user-123"]) == 1

    @pytest.mark.asyncio
    async def test_handle_player_action_analyzes_when_buffer_full(self, consumer):
        """버퍼가 가득 차면 분석 실행."""
        user_id = "user-123"
        
        for i in range(consumer._action_buffer_size):
            event = {
                "event_type": "player_action",
                "user_id": user_id,
                "room_id": "room-456",
                "action_type": "call",
                "amount": 100,
                "response_time_ms": 2500 + i,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await consumer.handle_player_action(event)
        
        assert len(consumer._action_buffer.get(user_id, [])) <= consumer._action_buffer_size


class TestHandlePlayerStats:
    """Property 6: 이벤트 유형별 탐지기 호출 - player_stats."""

    @pytest.fixture
    def consumer(self):
        mock_redis = MagicMock()
        mock_main_db = AsyncMock()
        mock_admin_db = AsyncMock()
        
        return FraudEventConsumer(
            mock_redis,
            lambda: mock_main_db,
            lambda: mock_admin_db,
        )

    @pytest.mark.asyncio
    async def test_handle_player_stats_normal(self, consumer):
        """정상 통계 이벤트 처리."""
        event = {
            "event_type": "player_stats",
            "user_id": "user-123",
            "room_id": "room-456",
            "session_duration_seconds": 3600,
            "hands_played": 45,
            "total_bet": 15000,
            "total_won": 16000,
            "join_time": "2026-01-16T11:00:00Z",
            "leave_time": "2026-01-16T12:00:00Z",
        }
        
        await consumer.handle_player_stats(event)

    @pytest.mark.asyncio
    async def test_handle_player_stats_skips_few_hands(self, consumer):
        """핸드 수가 적으면 분석 스킵."""
        event = {
            "event_type": "player_stats",
            "user_id": "user-123",
            "room_id": "room-456",
            "session_duration_seconds": 600,
            "hands_played": 3,
            "total_bet": 1000,
            "total_won": 5000,
            "join_time": "2026-01-16T11:00:00Z",
            "leave_time": "2026-01-16T11:10:00Z",
        }
        
        await consumer.handle_player_stats(event)


class TestFlagSuspiciousActivity:
    """Property 7: 의심 활동 탐지 시 자동 제재 평가."""

    @pytest.fixture
    def consumer(self):
        mock_redis = MagicMock()
        mock_main_db = AsyncMock()
        mock_main_db.close = AsyncMock()
        mock_admin_db = AsyncMock()
        mock_admin_db.close = AsyncMock()
        
        return FraudEventConsumer(
            mock_redis,
            lambda: mock_main_db,
            lambda: mock_admin_db,
        )

    @pytest.mark.asyncio
    async def test_flag_suspicious_activity_calls_auto_ban(self, consumer):
        """의심 활동 플래깅 시 AutoBanService.process_detection 호출 (Phase 2.4)."""
        mock_auto_ban = MagicMock()
        # Phase 2.4: process_detection 사용
        mock_auto_ban.process_detection = AsyncMock(return_value={
            "flag_id": "flag-123",
            "was_banned": True,
            "ban_id": "ban-123",
        })
        mock_auto_ban.notify_admins = AsyncMock(return_value=True)

        import app.services.auto_ban as auto_ban_module
        original_class = auto_ban_module.AutoBanService
        auto_ban_module.AutoBanService = MagicMock(return_value=mock_auto_ban)

        try:
            await consumer._flag_suspicious_activity(
                detection_type="bot_detection",
                user_ids=["user-123"],
                details={"reasons": ["superhuman_reaction"]},
                severity="high",
            )

            # Phase 2.4: process_detection 호출 확인
            mock_auto_ban.process_detection.assert_called_once()
            call_args = mock_auto_ban.process_detection.call_args
            assert call_args.kwargs["user_id"] == "user-123"
            assert call_args.kwargs["detection_type"] == "bot_detection"
            assert call_args.kwargs["severity"] == "high"
        finally:
            auto_ban_module.AutoBanService = original_class

    @pytest.mark.asyncio
    async def test_flag_suspicious_activity_notify_for_medium(self, consumer):
        """밴 미적용 + medium 심각도이면 관리자 알림 보냄 (Phase 2.4)."""
        mock_auto_ban = MagicMock()
        # Phase 2.4: process_detection 사용 (밴 미적용 케이스)
        mock_auto_ban.process_detection = AsyncMock(return_value={
            "flag_id": "flag-123",
            "was_banned": False,
            "ban_id": None,
        })
        mock_auto_ban.notify_admins = AsyncMock(return_value=True)

        import app.services.auto_ban as auto_ban_module
        original_class = auto_ban_module.AutoBanService
        auto_ban_module.AutoBanService = MagicMock(return_value=mock_auto_ban)

        try:
            await consumer._flag_suspicious_activity(
                detection_type="anomaly_detection",
                user_ids=["user-123"],
                details={"reasons": ["excessive_win_rate"]},
                severity="medium",
            )

            mock_auto_ban.process_detection.assert_called_once()
            # Phase 2.4: 밴 미적용 + medium이면 notify_admins 호출
            mock_auto_ban.notify_admins.assert_called_once()
        finally:
            auto_ban_module.AutoBanService = original_class

    @pytest.mark.asyncio
    async def test_flag_suspicious_activity_no_notify_for_low(self, consumer):
        """심각도가 low이면 관리자 알림 안 함."""
        mock_auto_ban = MagicMock()
        mock_auto_ban.process_detection = AsyncMock(return_value={
            "flag_id": "flag-123",
            "was_banned": False,
            "ban_id": None,
        })
        mock_auto_ban.notify_admins = AsyncMock(return_value=True)

        import app.services.auto_ban as auto_ban_module
        original_class = auto_ban_module.AutoBanService
        auto_ban_module.AutoBanService = MagicMock(return_value=mock_auto_ban)

        try:
            await consumer._flag_suspicious_activity(
                detection_type="anomaly_detection",
                user_ids=["user-123"],
                details={"reasons": ["minor_anomaly"]},
                severity="low",
            )

            mock_auto_ban.process_detection.assert_called_once()
            # low 심각도는 알림 안 보냄
            mock_auto_ban.notify_admins.assert_not_called()
        finally:
            auto_ban_module.AutoBanService = original_class


class TestMessageHandling:
    """메시지 처리 테스트."""

    @pytest.fixture
    def consumer(self):
        mock_redis = MagicMock()
        mock_main_db = AsyncMock()
        mock_admin_db = AsyncMock()
        
        return FraudEventConsumer(
            mock_redis,
            lambda: mock_main_db,
            lambda: mock_admin_db,
        )

    @pytest.mark.asyncio
    async def test_handle_message_routes_correctly(self, consumer):
        """메시지가 올바른 핸들러로 라우팅됨."""
        consumer.handle_hand_completed = AsyncMock()
        consumer.handle_player_action = AsyncMock()
        consumer.handle_player_stats = AsyncMock()
        
        await consumer._handle_message(
            CHANNEL_HAND_COMPLETED,
            json.dumps({"event_type": "hand_completed"}),
        )
        consumer.handle_hand_completed.assert_called_once()
        
        await consumer._handle_message(
            CHANNEL_PLAYER_ACTION,
            json.dumps({"event_type": "player_action"}),
        )
        consumer.handle_player_action.assert_called_once()
        
        await consumer._handle_message(
            CHANNEL_PLAYER_STATS,
            json.dumps({"event_type": "player_stats"}),
        )
        consumer.handle_player_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_message_invalid_json(self, consumer):
        """잘못된 JSON 처리."""
        await consumer._handle_message(CHANNEL_HAND_COMPLETED, "invalid json")

    @pytest.mark.asyncio
    async def test_handle_message_unknown_channel(self, consumer):
        """알 수 없는 채널 처리."""
        await consumer._handle_message("unknown:channel", json.dumps({}))
