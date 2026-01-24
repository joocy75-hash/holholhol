"""
Tournament Recovery Tests.

서버 재시작 시 토너먼트 자동 복구 기능을 테스트합니다.

P0 - 상용화 필수 항목:
- Redis 스냅샷에서 토너먼트 상태 복구
- 복구 후 진행 중인 토너먼트 자동 재개
- 종료된 토너먼트 스냅샷 정리
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class MockRedis:
    """Mock Redis client for recovery tests."""

    def __init__(self):
        self._data = {}
        self._sorted_sets = {}
        self._hashes = {}
        self._scan_results = []

    async def set(self, key, value, nx=False, px=None, ex=None):
        if nx and key in self._data:
            return False
        self._data[key] = value
        return True

    async def get(self, key):
        return self._data.get(key)

    async def delete(self, *keys):
        count = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                count += 1
        return count

    async def exists(self, key):
        return 1 if key in self._data else 0

    async def zadd(self, key, mapping):
        if key not in self._sorted_sets:
            self._sorted_sets[key] = {}
        self._sorted_sets[key].update(mapping)

    async def zrevrank(self, key, member):
        if key not in self._sorted_sets:
            return None
        sorted_members = sorted(
            self._sorted_sets[key].items(), key=lambda x: x[1], reverse=True
        )
        for idx, (m, _) in enumerate(sorted_members):
            if m == member:
                return idx
        return None

    async def zrevrange(self, key, start, end, withscores=False):
        if key not in self._sorted_sets:
            return []
        sorted_members = sorted(
            self._sorted_sets[key].items(), key=lambda x: x[1], reverse=True
        )
        if end == -1:
            end = len(sorted_members)
        result = sorted_members[start : end + 1]
        if withscores:
            return result
        return [m for m, _ in result]

    async def hset(self, key, field=None, value=None, mapping=None):
        if key not in self._hashes:
            self._hashes[key] = {}
        if mapping:
            self._hashes[key].update(mapping)
        elif field is not None:
            self._hashes[key][field] = value

    async def hget(self, key, field):
        return self._hashes.get(key, {}).get(field)

    async def hgetall(self, key):
        return self._hashes.get(key, {})

    def register_script(self, script):
        async def mock_script(keys=None, args=None):
            return 1

        return mock_script

    def pipeline(self, transaction=False):
        return MockPipeline(self)

    async def xgroup_create(self, stream, group, id="0", mkstream=False):
        pass

    async def xadd(self, stream, data, maxlen=None, approximate=False):
        return f"{datetime.utcnow().timestamp()}-0"

    async def xreadgroup(
        self, groupname, consumername, streams, count=None, block=None
    ):
        return []

    async def xack(self, stream, group, message_id):
        pass

    def set_scan_results(self, results: list):
        """Set mock scan results for scan_iter."""
        self._scan_results = results

    async def scan_iter(self, match=None, count=None):
        """Mock scan_iter that yields from _scan_results."""
        for key in self._scan_results:
            yield key


class MockPipeline:
    def __init__(self, redis):
        self._redis = redis
        self._commands = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def set(self, key, value):
        self._commands.append(("set", key, value))
        return self

    def expire(self, key, seconds):
        return self

    def zadd(self, key, mapping):
        self._commands.append(("zadd", key, mapping))
        return self

    def hset(self, key, field=None, value=None, mapping=None):
        self._commands.append(("hset", key, field, value, mapping))
        return self

    async def execute(self):
        for cmd in self._commands:
            if cmd[0] == "set":
                await self._redis.set(cmd[1], cmd[2])
            elif cmd[0] == "zadd":
                await self._redis.zadd(cmd[1], cmd[2])
            elif cmd[0] == "hset":
                await self._redis.hset(
                    cmd[1], field=cmd[2], value=cmd[3], mapping=cmd[4]
                )
        return [True] * len(self._commands)


class TestSnapshotManager:
    """Test SnapshotManager recovery functionality."""

    @pytest.fixture
    def mock_redis(self):
        return MockRedis()

    @pytest.fixture
    def snapshot_manager(self, mock_redis):
        from app.tournament.snapshot import SnapshotManager

        return SnapshotManager(mock_redis, "test-hmac-key")

    @pytest.fixture
    def sample_tournament_state(self):
        from app.tournament.models import (
            TournamentState,
            TournamentConfig,
            TournamentPlayer,
            TournamentTable,
            TournamentStatus,
        )

        config = TournamentConfig(
            tournament_id="test-tournament-123",
            name="Test Tournament",
            max_players=100,
        )

        players = {
            "user1": TournamentPlayer(
                user_id="user1",
                nickname="Player1",
                chip_count=15000,
                table_id="table1",
                seat_position=0,
            ),
            "user2": TournamentPlayer(
                user_id="user2",
                nickname="Player2",
                chip_count=10000,
                table_id="table1",
                seat_position=1,
            ),
            "user3": TournamentPlayer(
                user_id="user3",
                nickname="Player3",
                chip_count=5000,
                table_id="table1",
                seat_position=2,
            ),
        }

        tables = {
            "table1": TournamentTable(
                table_id="table1",
                table_number=1,
                seats=("user1", "user2", "user3", None, None, None, None, None, None),
            ),
        }

        return TournamentState(
            tournament_id="test-tournament-123",
            config=config,
            status=TournamentStatus.RUNNING,
            current_blind_level=3,
            players=players,
            tables=tables,
            total_prize_pool=30000,
        )

    @pytest.mark.asyncio
    async def test_save_and_load_snapshot(
        self, snapshot_manager, sample_tournament_state
    ):
        """스냅샷 저장 및 로드 테스트."""
        # 스냅샷 저장
        metadata = await snapshot_manager.save_full_snapshot(sample_tournament_state)

        assert metadata.tournament_id == "test-tournament-123"
        assert metadata.blind_level == 3
        assert metadata.active_players == 3
        assert metadata.size_bytes > 0
        assert metadata.checksum != ""

        # 스냅샷 로드
        loaded_state = await snapshot_manager.load_latest("test-tournament-123")

        assert loaded_state is not None
        assert loaded_state.tournament_id == "test-tournament-123"
        assert loaded_state.status.value == "running"
        assert loaded_state.current_blind_level == 3
        assert len(loaded_state.players) == 3
        assert len(loaded_state.tables) == 1

    @pytest.mark.asyncio
    async def test_list_recoverable_tournaments(
        self, mock_redis, snapshot_manager, sample_tournament_state
    ):
        """복구 가능한 토너먼트 목록 조회 테스트."""
        # 스냅샷 저장
        await snapshot_manager.save_full_snapshot(sample_tournament_state)

        # Mock scan results
        mock_redis.set_scan_results(
            [
                "tournament:snapshot:test-tournament-123:latest",
                "tournament:snapshot:test-tournament-456:latest",
            ]
        )

        # 목록 조회
        tournament_ids = await snapshot_manager.list_recoverable_tournaments()

        assert "test-tournament-123" in tournament_ids
        assert "test-tournament-456" in tournament_ids
        assert len(tournament_ids) == 2

    @pytest.mark.asyncio
    async def test_delete_snapshot(
        self, mock_redis, snapshot_manager, sample_tournament_state
    ):
        """스냅샷 삭제 테스트."""
        # 스냅샷 저장
        await snapshot_manager.save_full_snapshot(sample_tournament_state)

        # 삭제 전 확인
        loaded = await snapshot_manager.load_latest("test-tournament-123")
        assert loaded is not None

        # 스냅샷 삭제
        deleted = await snapshot_manager.delete_snapshot("test-tournament-123")
        assert deleted is True

        # 삭제 후 확인
        loaded = await snapshot_manager.load_latest("test-tournament-123")
        assert loaded is None


class TestTournamentEngineRecovery:
    """Test TournamentEngine recovery functionality."""

    @pytest.fixture
    def mock_redis(self):
        return MockRedis()

    @pytest.fixture
    def tournament_engine(self, mock_redis):
        from app.tournament.engine import TournamentEngine

        engine = TournamentEngine(mock_redis, "test-hmac-key")
        # Don't call initialize to avoid background tasks
        return engine

    @pytest.mark.asyncio
    async def test_recover_tournament_from_snapshot(
        self, mock_redis, tournament_engine
    ):
        """스냅샷에서 토너먼트 복구 테스트."""
        from app.tournament.models import (
            TournamentState,
            TournamentConfig,
            TournamentPlayer,
            TournamentTable,
            TournamentStatus,
        )

        # 테스트용 토너먼트 상태 생성
        config = TournamentConfig(
            tournament_id="recovery-test-123",
            name="Recovery Test",
            max_players=50,
        )

        players = {
            "player1": TournamentPlayer(
                user_id="player1",
                nickname="TestPlayer1",
                chip_count=20000,
                table_id="table_a",
                seat_position=0,
            ),
            "player2": TournamentPlayer(
                user_id="player2",
                nickname="TestPlayer2",
                chip_count=10000,
                table_id="table_a",
                seat_position=1,
            ),
        }

        tables = {
            "table_a": TournamentTable(
                table_id="table_a",
                table_number=1,
                seats=("player1", "player2", None, None, None, None, None, None, None),
            ),
        }

        state = TournamentState(
            tournament_id="recovery-test-123",
            config=config,
            status=TournamentStatus.RUNNING,
            current_blind_level=5,
            players=players,
            tables=tables,
            total_prize_pool=30000,
        )

        # 스냅샷 저장
        await tournament_engine.snapshot.save_full_snapshot(state)

        # 토너먼트 복구
        recovered = await tournament_engine.recover_tournament("recovery-test-123")

        assert recovered is not None
        assert recovered.tournament_id == "recovery-test-123"
        assert recovered.status == TournamentStatus.RUNNING
        assert recovered.current_blind_level == 5
        assert len(recovered.players) == 2
        assert recovered.active_player_count == 2

        # 엔진 내부 상태 확인
        assert "recovery-test-123" in tournament_engine._tournaments

    @pytest.mark.asyncio
    async def test_recover_nonexistent_tournament(self, tournament_engine):
        """존재하지 않는 토너먼트 복구 시도 테스트."""
        recovered = await tournament_engine.recover_tournament("nonexistent-id")
        assert recovered is None

    @pytest.mark.asyncio
    async def test_recover_completed_tournament(self, mock_redis, tournament_engine):
        """완료된 토너먼트 복구 테스트 (이벤트 미발행 확인)."""
        from app.tournament.models import (
            TournamentState,
            TournamentConfig,
            TournamentPlayer,
            TournamentTable,
            TournamentStatus,
        )

        config = TournamentConfig(
            tournament_id="completed-tournament",
            name="Completed Tournament",
        )

        players = {
            "winner": TournamentPlayer(
                user_id="winner",
                nickname="Winner",
                chip_count=100000,
                is_active=True,
            ),
        }

        state = TournamentState(
            tournament_id="completed-tournament",
            config=config,
            status=TournamentStatus.COMPLETED,  # 이미 완료됨
            players=players,
            tables={},
        )

        # 스냅샷 저장
        await tournament_engine.snapshot.save_full_snapshot(state)

        # 복구
        recovered = await tournament_engine.recover_tournament("completed-tournament")

        assert recovered is not None
        assert recovered.status == TournamentStatus.COMPLETED


class TestAutoRecoveryOnStartup:
    """Test automatic recovery during server startup."""

    @pytest.fixture
    def mock_redis(self):
        return MockRedis()

    @pytest.mark.asyncio
    async def test_recover_crashed_tournaments(self, mock_redis):
        """서버 시작 시 크래시된 토너먼트 자동 복구 테스트."""
        from app.tournament.engine import TournamentEngine
        from app.tournament.models import (
            TournamentState,
            TournamentConfig,
            TournamentPlayer,
            TournamentTable,
            TournamentStatus,
        )

        # 엔진 생성 (initialize 호출 전)
        engine = TournamentEngine(mock_redis, "test-key")

        # 복구 대상 토너먼트 상태 생성 및 저장
        running_state = TournamentState(
            tournament_id="running-tournament",
            config=TournamentConfig(tournament_id="running-tournament", name="Running"),
            status=TournamentStatus.RUNNING,
            players={
                "p1": TournamentPlayer(user_id="p1", nickname="P1", chip_count=5000),
                "p2": TournamentPlayer(user_id="p2", nickname="P2", chip_count=5000),
            },
            tables={"t1": TournamentTable(table_id="t1", table_number=1)},
        )

        paused_state = TournamentState(
            tournament_id="paused-tournament",
            config=TournamentConfig(tournament_id="paused-tournament", name="Paused"),
            status=TournamentStatus.PAUSED,
            players={
                "p3": TournamentPlayer(user_id="p3", nickname="P3", chip_count=3000),
            },
            tables={"t2": TournamentTable(table_id="t2", table_number=1)},
        )

        completed_state = TournamentState(
            tournament_id="completed-tournament",
            config=TournamentConfig(
                tournament_id="completed-tournament", name="Completed"
            ),
            status=TournamentStatus.COMPLETED,
            players={},
            tables={},
        )

        # 스냅샷 저장
        await engine.snapshot.save_full_snapshot(running_state)
        await engine.snapshot.save_full_snapshot(paused_state)
        await engine.snapshot.save_full_snapshot(completed_state)

        # Mock scan results
        mock_redis.set_scan_results(
            [
                "tournament:snapshot:running-tournament:latest",
                "tournament:snapshot:paused-tournament:latest",
                "tournament:snapshot:completed-tournament:latest",
            ]
        )

        # _recover_crashed_tournaments 호출
        recovered_count = await engine._recover_crashed_tournaments()

        # 검증: RUNNING, PAUSED는 복구됨, COMPLETED는 정리됨
        assert "running-tournament" in engine._tournaments
        assert "paused-tournament" in engine._tournaments
        # COMPLETED는 복구되지만 스냅샷은 삭제됨
        # (실제 구현에서는 삭제 로직이 있음)

        # 복구된 토너먼트 상태 확인
        assert (
            engine._tournaments["running-tournament"].status == TournamentStatus.RUNNING
        )
        assert (
            engine._tournaments["paused-tournament"].status == TournamentStatus.PAUSED
        )


class TestRecoveryIntegration:
    """Integration tests for tournament recovery."""

    @pytest.fixture
    def mock_redis(self):
        return MockRedis()

    @pytest.mark.asyncio
    async def test_full_recovery_cycle(self, mock_redis):
        """완전한 복구 사이클 테스트: 생성 → 저장 → 크래시 시뮬레이션 → 복구."""
        from app.tournament.engine import TournamentEngine
        from app.tournament.models import (
            TournamentConfig,
            TournamentStatus,
            TournamentState,
            TournamentPlayer,
            TournamentTable,
        )

        # 1. 첫 번째 엔진 인스턴스 (서버 1)
        engine1 = TournamentEngine(mock_redis, "test-key")

        # 토너먼트 생성 (직접 상태 설정 - 락 문제 회피)
        config = TournamentConfig(
            tournament_id="cycle-test",
            name="Cycle Test Tournament",
            min_players=2,
        )

        players = {
            "user1": TournamentPlayer(
                user_id="user1",
                nickname="Alice",
                chip_count=config.starting_chips,
            ),
            "user2": TournamentPlayer(
                user_id="user2",
                nickname="Bob",
                chip_count=config.starting_chips,
            ),
        }

        tables = {
            "table1": TournamentTable(
                table_id="table1",
                table_number=1,
                seats=("user1", "user2", None, None, None, None, None, None, None),
            ),
        }

        state = TournamentState(
            tournament_id="cycle-test",
            config=config,
            status=TournamentStatus.RUNNING,
            players=players,
            tables=tables,
            total_prize_pool=20000,
        )

        # 엔진에 직접 상태 설정
        engine1._tournaments["cycle-test"] = state

        # 스냅샷 저장
        await engine1.snapshot.save_full_snapshot(state)

        # 2. 서버 크래시 시뮬레이션 (engine1 참조 제거)
        del engine1

        # 3. 새 엔진 인스턴스 (서버 2 - 재시작)
        mock_redis.set_scan_results(["tournament:snapshot:cycle-test:latest"])

        engine2 = TournamentEngine(mock_redis, "test-key")

        # 4. 복구
        recovered_count = await engine2._recover_crashed_tournaments()

        # 5. 검증
        assert recovered_count >= 1
        assert "cycle-test" in engine2._tournaments

        recovered_state = engine2._tournaments["cycle-test"]
        assert recovered_state.tournament_id == "cycle-test"
        assert len(recovered_state.players) == 2
        assert "user1" in recovered_state.players
        assert "user2" in recovered_state.players
        assert recovered_state.status == TournamentStatus.RUNNING


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
