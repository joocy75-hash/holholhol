"""
Real-time Ranking Engine.

수백 명의 칩 보유량을 실시간으로 집계하여 전체 순위를 리더보드에 즉시 반영.

핵심 설계:
1. Redis Sorted Set으로 O(log n) 순위 조회
2. 주기적 배치 업데이트로 부하 최소화
3. 캐싱된 랭킹 스냅샷으로 즉시 응답
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import redis.asyncio as redis

from .models import TournamentState, TournamentPlayer


@dataclass
class RankingEntry:
    """Single ranking entry."""

    rank: int
    user_id: str
    nickname: str
    chip_count: int
    table_id: Optional[str] = None
    is_active: bool = True
    last_update: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "user_id": self.user_id,
            "nickname": self.nickname,
            "chip_count": self.chip_count,
            "table_id": self.table_id,
            "is_active": self.is_active,
        }


@dataclass
class RankingSnapshot:
    """Complete ranking snapshot."""

    snapshot_id: str = field(default_factory=lambda: str(uuid4()))
    tournament_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    entries: List[RankingEntry] = field(default_factory=list)
    total_players: int = 0
    active_players: int = 0
    total_chips: int = 0
    average_stack: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "tournament_id": self.tournament_id,
            "timestamp": self.timestamp.isoformat(),
            "total_players": self.total_players,
            "active_players": self.active_players,
            "total_chips": self.total_chips,
            "average_stack": self.average_stack,
            "entries": [e.to_dict() for e in self.entries],
        }


class RankingEngine:
    """
    High-performance Real-time Ranking Engine.

    아키텍처:
    ─────────────────────────────────────────────────────────────────

    [칩 변경] -> [Redis Sorted Set] <- [실시간 조회]
                     |
                     v
    [주기적 스냅샷] -> [인메모리 캐시] <- [리더보드 API]

    Redis Sorted Set 활용:
    - ZADD: 플레이어 칩 업데이트 O(log n)
    - ZRANK: 특정 플레이어 순위 조회 O(log n)
    - ZREVRANGE: 상위 N명 조회 O(log n + N)
    - ZCARD: 전체 인원 O(1)

    순위 계산 최적화:
    - 칩 변경 발생 시 Redis 즉시 업데이트
    - 전체 스냅샷은 1초 주기로 배치 생성
    - 클라이언트는 캐싱된 스냅샷 수신 (WebSocket)

    ─────────────────────────────────────────────────────────────────
    """

    # Redis key prefix
    KEY_PREFIX = "tournament:ranking"

    # Update interval for full snapshot (ms)
    SNAPSHOT_INTERVAL_MS = 1000

    # Top players to include in broadcast
    TOP_PLAYERS_BROADCAST = 100

    def __init__(
        self,
        redis_client: redis.Redis,
    ):
        self.redis = redis_client

        # In-memory snapshot cache
        self._snapshots: Dict[str, RankingSnapshot] = {}

        # Background update task
        self._update_task: Optional[asyncio.Task] = None
        self._running = False

        # Active tournaments
        self._active_tournaments: set[str] = set()

        # Player info cache (user_id -> nickname, table_id)
        self._player_info: Dict[str, Dict[str, str]] = {}

    def _ranking_key(self, tournament_id: str) -> str:
        """Get Redis key for tournament ranking."""
        return f"{self.KEY_PREFIX}:{tournament_id}"

    def _player_info_key(self, tournament_id: str) -> str:
        """Get Redis key for player info hash."""
        return f"{self.KEY_PREFIX}:{tournament_id}:info"

    async def initialize(self, tournament_id: str) -> None:
        """
        Initialize ranking for tournament.

        - Create Redis keys
        - Start background update task
        """
        self._active_tournaments.add(tournament_id)

        if not self._running:
            self._running = True
            self._update_task = asyncio.create_task(self._snapshot_updater())

    async def shutdown(self) -> None:
        """Stop ranking engine."""
        self._running = False
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass

    async def register_player(
        self,
        tournament_id: str,
        player: TournamentPlayer,
    ) -> None:
        """
        Register player in ranking.

        Args:
            tournament_id: Tournament ID
            player: Player to register
        """
        ranking_key = self._ranking_key(tournament_id)
        info_key = self._player_info_key(tournament_id)

        # Add to sorted set with chip count as score
        await self.redis.zadd(
            ranking_key,
            {player.user_id: player.chip_count},
        )

        # Store player info
        await self.redis.hset(
            info_key,
            player.user_id,
            json.dumps(
                {
                    "nickname": player.nickname,
                    "table_id": player.table_id,
                    "is_active": player.is_active,
                }
            ),
        )

        # Update local cache
        self._player_info[player.user_id] = {
            "nickname": player.nickname,
            "table_id": player.table_id or "",
        }

    async def update_chips(
        self,
        tournament_id: str,
        user_id: str,
        chip_count: int,
        table_id: Optional[str] = None,
    ) -> int:
        """
        Update player chip count and get new rank.

        실시간 칩 업데이트:
        ─────────────────────────────────────────────────────────────

        Redis Sorted Set의 score를 chip_count로 사용.
        ZADD는 원자적으로 실행되어 동시성 안전.

        순위는 score 내림차순 (칩 많은 순).
        동일 칩 시 Redis 내부 사전순 (일관성 보장).

        ─────────────────────────────────────────────────────────────

        Args:
            tournament_id: Tournament ID
            user_id: Player user ID
            chip_count: New chip count
            table_id: Player's current table (optional)

        Returns:
            New rank (1-indexed), or -1 if player not found
        """
        ranking_key = self._ranking_key(tournament_id)

        # Update score (chip count)
        await self.redis.zadd(
            ranking_key,
            {user_id: chip_count},
        )

        # Update table info if provided
        if table_id is not None:
            info_key = self._player_info_key(tournament_id)
            existing = await self.redis.hget(info_key, user_id)
            if existing:
                info = json.loads(existing)
                info["table_id"] = table_id
                await self.redis.hset(info_key, user_id, json.dumps(info))

        # Get new rank (0-indexed, reversed for chip count)
        rank_0 = await self.redis.zrevrank(ranking_key, user_id)

        if rank_0 is None:
            return -1

        return rank_0 + 1  # 1-indexed rank

    async def update_batch(
        self,
        tournament_id: str,
        updates: List[Tuple[str, int]],  # (user_id, chip_count)
    ) -> None:
        """
        Batch update multiple player chip counts.

        핸드 종료 시 여러 플레이어 동시 업데이트에 최적.
        Pipeline으로 한 번의 RTT로 처리.

        Args:
            tournament_id: Tournament ID
            updates: List of (user_id, chip_count) tuples
        """
        if not updates:
            return

        ranking_key = self._ranking_key(tournament_id)

        # Prepare ZADD arguments
        mapping = {user_id: chips for user_id, chips in updates}

        await self.redis.zadd(ranking_key, mapping)

    async def eliminate_player(
        self,
        tournament_id: str,
        user_id: str,
        final_rank: int,
    ) -> None:
        """
        Mark player as eliminated.

        탈락 플레이어 처리:
        - chip_count를 0으로 설정 (순위 최하위)
        - is_active를 False로 설정
        - final_rank 기록

        Args:
            tournament_id: Tournament ID
            user_id: Eliminated player ID
            final_rank: Player's final rank
        """
        ranking_key = self._ranking_key(tournament_id)
        info_key = self._player_info_key(tournament_id)

        # Set chips to 0
        await self.redis.zadd(ranking_key, {user_id: 0})

        # Update info
        existing = await self.redis.hget(info_key, user_id)
        if existing:
            info = json.loads(existing)
            info["is_active"] = False
            info["final_rank"] = final_rank
            await self.redis.hset(info_key, user_id, json.dumps(info))

    async def get_rank(
        self,
        tournament_id: str,
        user_id: str,
    ) -> int:
        """
        Get player's current rank.

        O(log n) 시간복잡도.

        Returns:
            Rank (1-indexed), or -1 if not found
        """
        ranking_key = self._ranking_key(tournament_id)
        rank_0 = await self.redis.zrevrank(ranking_key, user_id)

        if rank_0 is None:
            return -1

        return rank_0 + 1

    async def get_top_players(
        self,
        tournament_id: str,
        count: int = 10,
    ) -> List[RankingEntry]:
        """
        Get top N players by chip count.

        O(log n + count) 시간복잡도.

        Args:
            tournament_id: Tournament ID
            count: Number of players to return

        Returns:
            List of RankingEntry in rank order
        """
        ranking_key = self._ranking_key(tournament_id)
        info_key = self._player_info_key(tournament_id)

        # Get top players with scores
        top = await self.redis.zrevrange(
            ranking_key,
            0,
            count - 1,
            withscores=True,
        )

        entries: List[RankingEntry] = []

        for rank, (user_id, chips) in enumerate(top, 1):
            # Get player info
            info_raw = await self.redis.hget(info_key, user_id)
            if info_raw:
                info = json.loads(info_raw)
                nickname = info.get("nickname", user_id[:8])
                table_id = info.get("table_id")
                is_active = info.get("is_active", True)
            else:
                nickname = user_id[:8]
                table_id = None
                is_active = True

            entry = RankingEntry(
                rank=rank,
                user_id=user_id,
                nickname=nickname,
                chip_count=int(chips),
                table_id=table_id,
                is_active=is_active,
            )
            entries.append(entry)

        return entries

    async def get_nearby_players(
        self,
        tournament_id: str,
        user_id: str,
        above: int = 2,
        below: int = 2,
    ) -> List[RankingEntry]:
        """
        Get players near a specific player's rank.

        현재 플레이어 주변 순위 조회:
        - 상위 above명
        - 본인
        - 하위 below명

        Args:
            tournament_id: Tournament ID
            user_id: Target player ID
            above: Number of higher-ranked players
            below: Number of lower-ranked players

        Returns:
            List of RankingEntry around the player
        """
        ranking_key = self._ranking_key(tournament_id)

        # Get player's rank first
        rank_0 = await self.redis.zrevrank(ranking_key, user_id)
        if rank_0 is None:
            return []

        # Calculate range
        start = max(0, rank_0 - above)
        end = rank_0 + below

        # Get range
        nearby = await self.redis.zrevrange(
            ranking_key,
            start,
            end,
            withscores=True,
        )

        info_key = self._player_info_key(tournament_id)
        entries: List[RankingEntry] = []

        for idx, (uid, chips) in enumerate(nearby):
            rank = start + idx + 1  # 1-indexed

            info_raw = await self.redis.hget(info_key, uid)
            if info_raw:
                info = json.loads(info_raw)
                nickname = info.get("nickname", uid[:8])
                table_id = info.get("table_id")
                is_active = info.get("is_active", True)
            else:
                nickname = uid[:8]
                table_id = None
                is_active = True

            entry = RankingEntry(
                rank=rank,
                user_id=uid,
                nickname=nickname,
                chip_count=int(chips),
                table_id=table_id,
                is_active=is_active,
            )
            entries.append(entry)

        return entries

    async def get_snapshot(
        self,
        tournament_id: str,
    ) -> RankingSnapshot:
        """
        Get cached ranking snapshot.

        캐시된 스냅샷 반환 (1초 이내 신선도).
        스냅샷 없으면 즉시 생성.

        Returns:
            Complete RankingSnapshot
        """
        # Check cache
        cached = self._snapshots.get(tournament_id)
        if cached:
            age_ms = (datetime.now(timezone.utc) - cached.timestamp).total_seconds() * 1000
            if age_ms < self.SNAPSHOT_INTERVAL_MS:
                return cached

        # Generate new snapshot
        return await self._generate_snapshot(tournament_id)

    async def _generate_snapshot(
        self,
        tournament_id: str,
    ) -> RankingSnapshot:
        """
        Generate complete ranking snapshot.

        전체 순위 스냅샷 생성:
        1. 전체 플레이어 조회
        2. 통계 계산 (총 칩, 평균 스택 등)
        3. 캐시 업데이트
        """
        ranking_key = self._ranking_key(tournament_id)
        info_key = self._player_info_key(tournament_id)

        # Get all players with scores
        all_players = await self.redis.zrevrange(
            ranking_key,
            0,
            -1,
            withscores=True,
        )

        entries: List[RankingEntry] = []
        total_chips = 0
        active_count = 0

        # Batch get all info
        all_info = await self.redis.hgetall(info_key)

        for rank, (user_id, chips) in enumerate(all_players, 1):
            chips_int = int(chips)
            total_chips += chips_int

            info_raw = all_info.get(user_id)
            if info_raw:
                info = json.loads(info_raw)
                nickname = info.get("nickname", user_id[:8])
                table_id = info.get("table_id")
                is_active = info.get("is_active", True)
            else:
                nickname = user_id[:8]
                table_id = None
                is_active = True

            if is_active:
                active_count += 1

            entry = RankingEntry(
                rank=rank,
                user_id=user_id,
                nickname=nickname,
                chip_count=chips_int,
                table_id=table_id,
                is_active=is_active,
            )
            entries.append(entry)

        total_players = len(entries)
        avg_stack = total_chips // active_count if active_count > 0 else 0

        snapshot = RankingSnapshot(
            tournament_id=tournament_id,
            entries=entries,
            total_players=total_players,
            active_players=active_count,
            total_chips=total_chips,
            average_stack=avg_stack,
        )

        # Cache it
        self._snapshots[tournament_id] = snapshot

        return snapshot

    async def _snapshot_updater(self) -> None:
        """
        Background task for periodic snapshot updates.

        모든 활성 토너먼트의 스냅샷을 주기적으로 갱신.
        """
        while self._running:
            try:
                for tournament_id in list(self._active_tournaments):
                    await self._generate_snapshot(tournament_id)

                await asyncio.sleep(self.SNAPSHOT_INTERVAL_MS / 1000)

            except asyncio.CancelledError:
                break
            except Exception as e:
                await asyncio.sleep(1)

    async def sync_from_state(
        self,
        state: TournamentState,
    ) -> None:
        """
        Sync ranking from tournament state.

        메모리 상태에서 Redis 동기화:
        - 서버 재시작 후 복구
        - State와 Redis 불일치 해결

        Args:
            state: Complete tournament state
        """
        tournament_id = state.tournament_id
        ranking_key = self._ranking_key(tournament_id)
        info_key = self._player_info_key(tournament_id)

        # Clear existing
        await self.redis.delete(ranking_key, info_key)

        # Rebuild from state
        async with self.redis.pipeline(transaction=False) as pipe:
            for player in state.players.values():
                pipe.zadd(ranking_key, {player.user_id: player.chip_count})
                pipe.hset(
                    info_key,
                    player.user_id,
                    json.dumps(
                        {
                            "nickname": player.nickname,
                            "table_id": player.table_id,
                            "is_active": player.is_active,
                        }
                    ),
                )
            await pipe.execute()

        # Initialize for updates
        await self.initialize(tournament_id)

    async def cleanup(self, tournament_id: str) -> None:
        """
        Cleanup ranking data for tournament.

        토너먼트 종료 후 정리.
        """
        ranking_key = self._ranking_key(tournament_id)
        info_key = self._player_info_key(tournament_id)

        await self.redis.delete(ranking_key, info_key)

        self._active_tournaments.discard(tournament_id)
        self._snapshots.pop(tournament_id, None)
