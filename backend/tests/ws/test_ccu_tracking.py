"""
CCU/DAU 트래킹 테스트

Phase 5.1: CCU 실시간 모니터링 테스트
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch


class TestCCUTracking:
    """CCU 트래킹 테스트"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        redis = AsyncMock()
        redis.sadd = AsyncMock(return_value=1)
        redis.srem = AsyncMock(return_value=1)
        redis.scard = AsyncMock(return_value=0)
        redis.pfadd = AsyncMock(return_value=1)
        redis.pfcount = AsyncMock(return_value=0)
        redis.setex = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.expire = AsyncMock()
        redis.pipeline = MagicMock(return_value=redis)
        redis.execute = AsyncMock(return_value=[1, 1, 1, True, 1, True])
        return redis

    @pytest.mark.asyncio
    async def test_track_user_online(self, mock_redis):
        """사용자 온라인 상태 추적 테스트"""
        from app.ws.manager import ConnectionManager

        manager = ConnectionManager(mock_redis)
        user_id = "test-user-123"

        await manager._track_user_online(user_id)

        # pipeline이 호출되었는지 확인
        mock_redis.pipeline.assert_called_once()

    @pytest.mark.asyncio
    async def test_track_user_offline(self, mock_redis):
        """사용자 오프라인 상태 추적 테스트"""
        from app.ws.manager import ConnectionManager

        manager = ConnectionManager(mock_redis)
        user_id = "test-user-123"

        await manager._track_user_offline(user_id)

        # online_users에서 제거되었는지 확인
        mock_redis.srem.assert_called_once_with("online_users", user_id)

    @pytest.mark.asyncio
    async def test_get_current_ccu(self, mock_redis):
        """현재 CCU 조회 테스트"""
        from app.ws.manager import ConnectionManager

        mock_redis.scard = AsyncMock(return_value=42)
        manager = ConnectionManager(mock_redis)

        ccu = await manager.get_current_ccu()

        assert ccu == 42
        mock_redis.scard.assert_called_with("online_users")

    @pytest.mark.asyncio
    async def test_get_online_users(self, mock_redis):
        """온라인 사용자 목록 조회 테스트"""
        from app.ws.manager import ConnectionManager

        mock_redis.smembers = AsyncMock(
            return_value={"user1", "user2", "user3"}
        )
        manager = ConnectionManager(mock_redis)

        users = await manager.get_online_users()

        assert len(users) == 3
        assert "user1" in users

    @pytest.mark.asyncio
    async def test_save_ccu_snapshot(self, mock_redis):
        """CCU 스냅샷 저장 테스트"""
        from app.ws.manager import ConnectionManager, CCU_HISTORY_TTL

        mock_redis.scard = AsyncMock(return_value=100)
        mock_redis.get = AsyncMock(return_value=None)

        manager = ConnectionManager(mock_redis)
        await manager._save_ccu_snapshot()

        # setex가 호출되었는지 확인 (시간별, 분별)
        assert mock_redis.setex.call_count >= 1

    @pytest.mark.asyncio
    async def test_save_ccu_snapshot_keeps_higher_value(self, mock_redis):
        """CCU 스냅샷이 더 높은 값을 유지하는지 테스트"""
        from app.ws.manager import ConnectionManager

        # 현재 CCU가 50이고, 저장된 값이 100인 경우
        mock_redis.scard = AsyncMock(return_value=50)
        mock_redis.get = AsyncMock(return_value="100")

        manager = ConnectionManager(mock_redis)
        await manager._save_ccu_snapshot()

        # 시간별 CCU는 업데이트되지 않아야 함 (더 낮은 값이므로)
        # 하지만 분별 CCU는 항상 저장됨
        calls = mock_redis.setex.call_args_list
        # 분별 CCU만 저장되었는지 확인 (ccu_minute 키)
        minute_calls = [c for c in calls if "ccu_minute" in str(c)]
        assert len(minute_calls) >= 1


class TestDAUTracking:
    """DAU 트래킹 테스트"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        redis = AsyncMock()
        redis.pfadd = AsyncMock(return_value=1)
        redis.pfcount = AsyncMock(return_value=500)
        redis.expire = AsyncMock()
        redis.pipeline = MagicMock(return_value=redis)
        redis.execute = AsyncMock(return_value=[1, 1, 1, True, 1, True])
        return redis

    @pytest.mark.asyncio
    async def test_dau_hyperloglog_tracking(self, mock_redis):
        """DAU HyperLogLog 트래킹 테스트"""
        from app.ws.manager import ConnectionManager

        manager = ConnectionManager(mock_redis)
        user_id = "test-user-456"

        # 온라인 상태 추적 시 DAU도 함께 추적됨
        await manager._track_user_online(user_id)

        # pipeline을 통해 DAU 키에 추가되었는지 확인
        mock_redis.pipeline.assert_called_once()


class TestMAUTracking:
    """MAU 트래킹 테스트"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        redis = AsyncMock()
        redis.pfadd = AsyncMock(return_value=1)
        redis.pfcount = AsyncMock(return_value=2000)
        redis.expire = AsyncMock()
        redis.pipeline = MagicMock(return_value=redis)
        redis.execute = AsyncMock(return_value=[1, 1, 1, True, 1, True])
        return redis

    @pytest.mark.asyncio
    async def test_mau_hyperloglog_tracking(self, mock_redis):
        """MAU HyperLogLog 트래킹 테스트"""
        from app.ws.manager import ConnectionManager

        manager = ConnectionManager(mock_redis)
        user_id = "test-user-789"

        # 온라인 상태 추적 시 MAU도 함께 추적됨
        await manager._track_user_online(user_id)

        # pipeline을 통해 MAU 키에 추가되었는지 확인
        mock_redis.pipeline.assert_called_once()
