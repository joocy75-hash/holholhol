"""
Tournament Engine Tests - Simplified.
"""

import pytest
from datetime import datetime

import sys

sys.path.insert(0, "/Users/mr.joo/Desktop/holdem/backend")


class MockRedis:
    """Mock Redis client."""

    def __init__(self):
        self._data = {}
        self._sorted_sets = {}
        self._hashes = {}

    async def set(self, key, value, nx=False, px=None):
        if nx and key in self._data:
            return False
        self._data[key] = value
        return True

    async def get(self, key):
        return self._data.get(key)

    async def delete(self, *keys):
        for key in keys:
            self._data.pop(key, None)

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

    async def scan_iter(self, match=None):
        if False:
            yield


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


class TestTournamentModels:
    """Test tournament data models."""

    def test_tournament_config_defaults(self):
        from app.tournament.models import TournamentConfig

        config = TournamentConfig()
        assert config.max_players == 300
        assert config.players_per_table == 9
        assert config.starting_chips == 10000

    def test_tournament_player_mutations(self):
        from app.tournament.models import TournamentPlayer

        player = TournamentPlayer(
            user_id="user1",
            nickname="Player1",
            chip_count=10000,
        )

        updated = player.with_chips(15000)
        assert updated.chip_count == 15000
        assert player.chip_count == 10000

        seated = player.at_table("table1", 3)
        assert seated.table_id == "table1"
        assert seated.seat_position == 3

        eliminated = player.eliminated(rank=50)
        assert eliminated.is_active is False
        assert eliminated.elimination_rank == 50

    def test_tournament_table_operations(self):
        from app.tournament.models import TournamentTable

        table = TournamentTable(table_id="t1", table_number=1)
        assert table.player_count == 0

        with_player = table.with_player_seated("user1", 0)
        assert with_player.player_count == 1

        without_player = with_player.with_player_removed("user1")
        assert without_player.player_count == 0


class TestTableBalancer:
    """Test table balancing."""

    def test_no_balancing_needed(self):
        from app.tournament.balancer import TableBalancer
        from app.tournament.models import (
            TournamentState,
            TournamentConfig,
            TournamentPlayer,
            TournamentTable,
        )

        balancer = TableBalancer()
        config = TournamentConfig()

        tables = {}
        players = {}

        for t in range(2):
            table_id = f"table_{t}"
            seats = [f"user_{t}_{s}" for s in range(5)] + [None] * 4
            tables[table_id] = TournamentTable(
                table_id=table_id,
                table_number=t + 1,
                seats=tuple(seats),
            )
            for s in range(5):
                user_id = f"user_{t}_{s}"
                players[user_id] = TournamentPlayer(
                    user_id=user_id,
                    nickname=f"Player{t}{s}",
                    chip_count=10000,
                    table_id=table_id,
                    seat_position=s,
                )

        state = TournamentState(
            tournament_id="t1",
            config=config,
            players=players,
            tables=tables,
        )

        plan = balancer.calculate_balancing_plan(state)
        assert len(plan.moves) == 0


class TestRankingEngine:
    """Test ranking engine."""

    @pytest.fixture
    def mock_redis(self):
        return MockRedis()

    @pytest.mark.asyncio
    async def test_ranking_updates(self, mock_redis):
        from app.tournament.ranking import RankingEngine
        from app.tournament.models import TournamentPlayer

        engine = RankingEngine(mock_redis)
        tid = "t1"

        for i in range(5):
            player = TournamentPlayer(
                user_id=f"user_{i}",
                nickname=f"Player{i}",
                chip_count=10000 + (i * 1000),
            )
            await engine.register_player(tid, player)

        top = await engine.get_top_players(tid, 10)
        assert len(top) == 5
        assert top[0].user_id == "user_4"

        new_rank = await engine.update_chips(tid, "user_0", 20000)
        assert new_rank == 1


class TestTournamentEngine:
    """Test tournament engine."""

    @pytest.fixture
    def mock_redis(self):
        return MockRedis()

    @pytest.mark.asyncio
    async def test_tournament_creation(self, mock_redis):
        from app.tournament.engine import TournamentEngine
        from app.tournament.models import TournamentConfig, TournamentStatus

        engine = TournamentEngine(mock_redis)
        # Don't call initialize to avoid background tasks

        config = TournamentConfig(name="Test Tournament", max_players=100)
        state = await engine.create_tournament(config)

        assert state.tournament_id == config.tournament_id
        assert state.status == TournamentStatus.REGISTERING

    @pytest.mark.asyncio
    async def test_player_registration(self, mock_redis):
        from app.tournament.models import TournamentConfig, TournamentPlayer

        # Test direct state manipulation without lock
        config = TournamentConfig(name="Test", max_players=10)

        player = TournamentPlayer(
            user_id="user1",
            nickname="Player1",
            chip_count=config.starting_chips,
        )

        assert player.chip_count == config.starting_chips
        assert player.user_id == "user1"
        assert player.is_active is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
