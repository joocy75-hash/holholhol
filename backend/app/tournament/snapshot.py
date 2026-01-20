"""
Snapshot Manager for Fault Tolerance.

서버 다운 시에도 진행 중인 핸드 상태와 칩 정보를 즉시 복구.
"""

import asyncio
import gzip
import hashlib
import hmac
import json
import pickle
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

import redis.asyncio as redis

from .models import (
    TournamentState,
    TournamentConfig,
    TournamentStatus,
    TournamentPlayer,
    TournamentTable,
    BlindLevel,
)


class SnapshotType(Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    HAND = "hand"
    CHECKPOINT = "checkpoint"


@dataclass
class SnapshotMetadata:
    snapshot_id: str = field(default_factory=lambda: str(uuid4()))
    tournament_id: str = ""
    snapshot_type: SnapshotType = SnapshotType.FULL
    created_at: datetime = field(default_factory=datetime.utcnow)
    blind_level: int = 1
    active_players: int = 0
    size_bytes: int = 0
    checksum: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "tournament_id": self.tournament_id,
            "snapshot_type": self.snapshot_type.value,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class HandSnapshot:
    snapshot_id: str = field(default_factory=lambda: str(uuid4()))
    table_id: str = ""
    hand_id: str = ""
    pk_state_bytes: bytes = b""
    starting_stacks: Dict[str, int] = field(default_factory=dict)
    action_log: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class SnapshotManager:
    """Tournament Snapshot Manager for fault tolerance."""

    KEY_PREFIX = "tournament:snapshot"
    MAX_HISTORY = 100

    def __init__(self, redis_client: redis.Redis, hmac_key: str = "key"):
        self.redis = redis_client
        self._hmac_key = hmac_key.encode()
        self._active: set[str] = set()

    def _latest_key(self, tid: str) -> str:
        return f"{self.KEY_PREFIX}:{tid}:latest"

    def _hand_key(self, tid: str, table_id: str) -> str:
        return f"{self.KEY_PREFIX}:{tid}:hand:{table_id}"

    def _compute_checksum(self, data: bytes) -> str:
        return hmac.new(self._hmac_key, data, hashlib.sha256).hexdigest()

    async def save_full_snapshot(self, state: TournamentState) -> SnapshotMetadata:
        """Save complete tournament state."""
        state_dict = self._serialize_state(state)
        compressed = gzip.compress(pickle.dumps(state_dict))
        checksum = self._compute_checksum(compressed)

        metadata = SnapshotMetadata(
            tournament_id=state.tournament_id,
            blind_level=state.current_blind_level,
            active_players=state.active_player_count,
            size_bytes=len(compressed),
            checksum=checksum,
        )

        await self.redis.set(self._latest_key(state.tournament_id), compressed)
        return metadata

    async def save_hand_snapshot(
        self,
        tid: str,
        table_id: str,
        hand_id: str,
        pk_state: bytes,
        stacks: Dict[str, int],
    ) -> HandSnapshot:
        """Save hand-in-progress state."""
        snapshot = HandSnapshot(
            table_id=table_id,
            hand_id=hand_id,
            pk_state_bytes=pk_state,
            starting_stacks=stacks,
        )
        data = pickle.dumps(
            {
                "table_id": table_id,
                "hand_id": hand_id,
                "pk_state": pk_state,
                "stacks": stacks,
            }
        )
        await self.redis.set(self._hand_key(tid, table_id), gzip.compress(data))
        return snapshot

    async def complete_hand(self, tid: str, table_id: str) -> None:
        await self.redis.delete(self._hand_key(tid, table_id))

    async def load_latest(self, tid: str) -> Optional[TournamentState]:
        """Load latest tournament snapshot."""
        compressed = await self.redis.get(self._latest_key(tid))
        if not compressed:
            return None
        state_dict = pickle.loads(gzip.decompress(compressed))
        return self._deserialize_state(state_dict)

    async def load_hand(self, tid: str, table_id: str) -> Optional[HandSnapshot]:
        compressed = await self.redis.get(self._hand_key(tid, table_id))
        if not compressed:
            return None
        data = pickle.loads(gzip.decompress(compressed))
        return HandSnapshot(
            table_id=data["table_id"],
            hand_id=data["hand_id"],
            pk_state_bytes=data["pk_state"],
            starting_stacks=data["stacks"],
        )

    def _serialize_state(self, state: TournamentState) -> Dict[str, Any]:
        return {
            "tournament_id": state.tournament_id,
            "config": self._ser_config(state.config),
            "status": state.status.value,
            "current_blind_level": state.current_blind_level,
            "players": {u: self._ser_player(p) for u, p in state.players.items()},
            "tables": {t: self._ser_table(tb) for t, tb in state.tables.items()},
            "ranking": state.ranking,
            "total_prize_pool": state.total_prize_pool,
        }

    def _ser_config(self, c: TournamentConfig) -> Dict:
        return {
            "tournament_id": c.tournament_id,
            "name": c.name,
            "max_players": c.max_players,
            "buy_in": c.buy_in,
            "starting_chips": c.starting_chips,
            "blind_levels": [
                {
                    "level": b.level,
                    "sb": b.small_blind,
                    "bb": b.big_blind,
                    "ante": b.ante,
                }
                for b in c.blind_levels
            ],
        }

    def _ser_player(self, p: TournamentPlayer) -> Dict:
        return {
            "user_id": p.user_id,
            "nickname": p.nickname,
            "chip_count": p.chip_count,
            "table_id": p.table_id,
            "seat_position": p.seat_position,
            "is_active": p.is_active,
        }

    def _ser_table(self, t: TournamentTable) -> Dict:
        return {
            "table_id": t.table_id,
            "table_number": t.table_number,
            "seats": list(t.seats),
            "hand_in_progress": t.hand_in_progress,
        }

    def _deserialize_state(self, d: Dict) -> TournamentState:
        config = self._deser_config(d["config"])
        players = {u: self._deser_player(p) for u, p in d["players"].items()}
        tables = {t: self._deser_table(tb) for t, tb in d["tables"].items()}
        return TournamentState(
            tournament_id=d["tournament_id"],
            config=config,
            status=TournamentStatus(d["status"]),
            current_blind_level=d["current_blind_level"],
            players=players,
            tables=tables,
            ranking=d.get("ranking", []),
            total_prize_pool=d.get("total_prize_pool", 0),
        )

    def _deser_config(self, d: Dict) -> TournamentConfig:
        levels = tuple(
            BlindLevel(b["level"], b["sb"], b["bb"], b.get("ante", 0))
            for b in d.get("blind_levels", [])
        )
        return TournamentConfig(
            tournament_id=d["tournament_id"],
            name=d["name"],
            max_players=d["max_players"],
            buy_in=d["buy_in"],
            starting_chips=d["starting_chips"],
            blind_levels=levels,
        )

    def _deser_player(self, d: Dict) -> TournamentPlayer:
        return TournamentPlayer(
            user_id=d["user_id"],
            nickname=d["nickname"],
            chip_count=d["chip_count"],
            table_id=d.get("table_id"),
            seat_position=d.get("seat_position"),
            is_active=d["is_active"],
        )

    def _deser_table(self, d: Dict) -> TournamentTable:
        return TournamentTable(
            table_id=d["table_id"],
            table_number=d["table_number"],
            seats=tuple(d["seats"]),
            hand_in_progress=d["hand_in_progress"],
        )
