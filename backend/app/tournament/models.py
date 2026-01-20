"""
Tournament Data Models.

Immutable state representations for tournament entities.
All mutations go through the TournamentEngine.
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from uuid import uuid4
import json


class TournamentStatus(Enum):
    """Tournament lifecycle states."""

    REGISTERING = "registering"  # 접수 중
    STARTING = "starting"  # 시작 대기 (샷건 스타트 동기화)
    RUNNING = "running"  # 진행 중
    PAUSED = "paused"  # 일시정지 (관리자)
    FINAL_TABLE = "final_table"  # 파이널 테이블
    HEADS_UP = "heads_up"  # 헤즈업
    COMPLETED = "completed"  # 완료
    CANCELLED = "cancelled"  # 취소


class TournamentEventType(Enum):
    """Event types for tournament event bus."""

    # Lifecycle
    TOURNAMENT_CREATED = auto()
    TOURNAMENT_STARTED = auto()
    TOURNAMENT_PAUSED = auto()
    TOURNAMENT_RESUMED = auto()
    TOURNAMENT_COMPLETED = auto()
    TOURNAMENT_CANCELLED = auto()

    # Player
    PLAYER_REGISTERED = auto()
    PLAYER_UNREGISTERED = auto()
    PLAYER_SEATED = auto()
    PLAYER_ELIMINATED = auto()
    PLAYER_MOVED = auto()  # 테이블 밸런싱
    PLAYER_REBUY = auto()
    PLAYER_ADDON = auto()
    PLAYER_DISCONNECTED = auto()
    PLAYER_RECONNECTED = auto()
    PLAYER_KICKED = auto()  # 관리자 강제 퇴장

    # Table
    TABLE_CREATED = auto()
    TABLE_CLOSED = auto()
    TABLE_HAND_STARTED = auto()
    TABLE_HAND_COMPLETED = auto()
    TABLE_BALANCING_SCHEDULED = auto()
    TABLE_BALANCING_EXECUTED = auto()

    # Blind
    BLIND_LEVEL_CHANGED = auto()
    BLIND_INCREASE_WARNING = auto()  # 30초 전 경고

    # Ranking
    RANKING_UPDATED = auto()
    IN_THE_MONEY = auto()  # ITM 진입


@dataclass(frozen=True)
class BlindLevel:
    """Blind level configuration."""

    level: int
    small_blind: int
    big_blind: int
    ante: int = 0
    duration_minutes: int = 15

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "small_blind": self.small_blind,
            "big_blind": self.big_blind,
            "ante": self.ante,
            "duration_minutes": self.duration_minutes,
        }


@dataclass(frozen=True)
class TournamentConfig:
    """
    Tournament configuration - immutable after creation.

    Supports various tournament formats:
    - Freezeout (no rebuy/addon)
    - Rebuy tournaments
    - Multi-table tournaments (MTT)
    - Sit & Go (SNG)
    """

    tournament_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = "Tournament"

    # 규모 설정
    min_players: int = 2
    max_players: int = 300
    players_per_table: int = 9  # 테이블당 인원 (6 or 9)

    # 바이인 설정
    buy_in: int = 10000  # 바이인 비용
    starting_chips: int = 10000  # 초기 칩

    # 리바이/애드온
    allow_rebuy: bool = False
    rebuy_period_levels: int = 6  # 리바이 가능 레벨 수
    rebuy_chips: int = 10000
    max_rebuys: int = 3
    allow_addon: bool = False
    addon_chips: int = 15000

    # 블라인드 구조
    blind_levels: Tuple[BlindLevel, ...] = field(
        default_factory=lambda: (
            BlindLevel(1, 25, 50, 0, 15),
            BlindLevel(2, 50, 100, 0, 15),
            BlindLevel(3, 75, 150, 0, 15),
            BlindLevel(4, 100, 200, 25, 15),
            BlindLevel(5, 150, 300, 25, 15),
            BlindLevel(6, 200, 400, 50, 15),
            BlindLevel(7, 300, 600, 75, 12),
            BlindLevel(8, 400, 800, 100, 12),
            BlindLevel(9, 600, 1200, 150, 12),
            BlindLevel(10, 800, 1600, 200, 10),
            BlindLevel(11, 1000, 2000, 300, 10),
            BlindLevel(12, 1500, 3000, 400, 10),
            BlindLevel(13, 2000, 4000, 500, 8),
            BlindLevel(14, 3000, 6000, 750, 8),
            BlindLevel(15, 4000, 8000, 1000, 8),
        )
    )

    # 페이아웃 구조 (상위 %별 분배 비율)
    payout_structure: Tuple[float, ...] = field(
        default_factory=lambda: (
            0.25,
            0.15,
            0.10,
            0.08,
            0.07,
            0.06,
            0.05,
            0.04,
            0.04,
            0.03,
            0.03,
            0.03,
            0.02,
            0.02,
            0.02,
            0.01,
        )
    )
    itm_percentage: float = 15.0  # 입상 비율 (상위 15%)

    # 시작 설정
    scheduled_start_time: Optional[datetime] = None
    late_registration_levels: int = 6  # 레이트 레지 가능 레벨

    # 샷건 스타트 동기화 설정
    shotgun_start_enabled: bool = True
    shotgun_countdown_seconds: int = 10

    def get_blind_level(self, level: int) -> Optional[BlindLevel]:
        """Get blind level by number."""
        for bl in self.blind_levels:
            if bl.level == level:
                return bl
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tournament_id": self.tournament_id,
            "name": self.name,
            "min_players": self.min_players,
            "max_players": self.max_players,
            "players_per_table": self.players_per_table,
            "buy_in": self.buy_in,
            "starting_chips": self.starting_chips,
            "allow_rebuy": self.allow_rebuy,
            "blind_levels": [bl.to_dict() for bl in self.blind_levels],
            "itm_percentage": self.itm_percentage,
        }


@dataclass(frozen=True)
class TournamentPlayer:
    """
    Tournament player state - immutable.

    Tracks player throughout tournament lifecycle.
    """

    user_id: str
    nickname: str
    registration_time: datetime = field(default_factory=datetime.utcnow)

    # 현재 상태
    chip_count: int = 0
    table_id: Optional[str] = None
    seat_position: Optional[int] = None

    # 기록
    is_active: bool = True
    is_sitting_out: bool = False
    elimination_rank: Optional[int] = None
    elimination_time: Optional[datetime] = None
    eliminated_by: Optional[str] = None  # user_id of eliminator

    # 리바이/애드온
    rebuy_count: int = 0
    addon_used: bool = False

    # 연결 상태
    is_connected: bool = True
    last_seen: datetime = field(default_factory=datetime.utcnow)
    disconnected_at: Optional[datetime] = None

    def with_chips(self, chip_count: int) -> "TournamentPlayer":
        """Return new instance with updated chip count."""
        return TournamentPlayer(
            user_id=self.user_id,
            nickname=self.nickname,
            registration_time=self.registration_time,
            chip_count=chip_count,
            table_id=self.table_id,
            seat_position=self.seat_position,
            is_active=self.is_active,
            is_sitting_out=self.is_sitting_out,
            elimination_rank=self.elimination_rank,
            elimination_time=self.elimination_time,
            eliminated_by=self.eliminated_by,
            rebuy_count=self.rebuy_count,
            addon_used=self.addon_used,
            is_connected=self.is_connected,
            last_seen=self.last_seen,
            disconnected_at=self.disconnected_at,
        )

    def at_table(self, table_id: str, seat: int) -> "TournamentPlayer":
        """Return new instance seated at table."""
        return TournamentPlayer(
            user_id=self.user_id,
            nickname=self.nickname,
            registration_time=self.registration_time,
            chip_count=self.chip_count,
            table_id=table_id,
            seat_position=seat,
            is_active=self.is_active,
            is_sitting_out=self.is_sitting_out,
            elimination_rank=self.elimination_rank,
            elimination_time=self.elimination_time,
            eliminated_by=self.eliminated_by,
            rebuy_count=self.rebuy_count,
            addon_used=self.addon_used,
            is_connected=self.is_connected,
            last_seen=self.last_seen,
            disconnected_at=self.disconnected_at,
        )

    def eliminated(
        self, rank: int, by_user: Optional[str] = None
    ) -> "TournamentPlayer":
        """Return new instance marked as eliminated."""
        return TournamentPlayer(
            user_id=self.user_id,
            nickname=self.nickname,
            registration_time=self.registration_time,
            chip_count=0,
            table_id=None,
            seat_position=None,
            is_active=False,
            is_sitting_out=self.is_sitting_out,
            elimination_rank=rank,
            elimination_time=datetime.utcnow(),
            eliminated_by=by_user,
            rebuy_count=self.rebuy_count,
            addon_used=self.addon_used,
            is_connected=self.is_connected,
            last_seen=self.last_seen,
            disconnected_at=self.disconnected_at,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "nickname": self.nickname,
            "chip_count": self.chip_count,
            "table_id": self.table_id,
            "seat_position": self.seat_position,
            "is_active": self.is_active,
            "elimination_rank": self.elimination_rank,
            "rebuy_count": self.rebuy_count,
        }


@dataclass(frozen=True)
class TournamentTable:
    """
    Tournament table state - immutable.

    Each table runs independent hands but syncs blinds/breaks
    with the tournament level.
    """

    table_id: str = field(default_factory=lambda: str(uuid4()))
    table_number: int = 1

    # 좌석 (position -> user_id)
    seats: Tuple[Optional[str], ...] = field(default_factory=lambda: tuple([None] * 9))
    max_seats: int = 9

    # 현재 핸드 상태
    hand_in_progress: bool = False
    current_hand_id: Optional[str] = None
    hand_snapshot: Optional[bytes] = None  # PokerKit state snapshot

    # 밸런싱 관련
    is_breaking: bool = False  # 해체 예정 테이블
    pending_move_in: List[str] = field(default_factory=list)  # 입장 대기 유저
    pending_move_out: List[str] = field(default_factory=list)  # 퇴장 대기 유저

    @property
    def player_count(self) -> int:
        """Current player count."""
        return sum(1 for s in self.seats if s is not None)

    @property
    def empty_seats(self) -> List[int]:
        """List of empty seat positions."""
        return [i for i, s in enumerate(self.seats) if s is None]

    def with_player_seated(self, user_id: str, position: int) -> "TournamentTable":
        """Return new table with player seated."""
        new_seats = list(self.seats)
        new_seats[position] = user_id
        return TournamentTable(
            table_id=self.table_id,
            table_number=self.table_number,
            seats=tuple(new_seats),
            max_seats=self.max_seats,
            hand_in_progress=self.hand_in_progress,
            current_hand_id=self.current_hand_id,
            hand_snapshot=self.hand_snapshot,
            is_breaking=self.is_breaking,
            pending_move_in=self.pending_move_in,
            pending_move_out=self.pending_move_out,
        )

    def with_player_removed(self, user_id: str) -> "TournamentTable":
        """Return new table with player removed."""
        new_seats = list(self.seats)
        for i, s in enumerate(new_seats):
            if s == user_id:
                new_seats[i] = None
                break
        return TournamentTable(
            table_id=self.table_id,
            table_number=self.table_number,
            seats=tuple(new_seats),
            max_seats=self.max_seats,
            hand_in_progress=self.hand_in_progress,
            current_hand_id=self.current_hand_id,
            hand_snapshot=self.hand_snapshot,
            is_breaking=self.is_breaking,
            pending_move_in=self.pending_move_in,
            pending_move_out=self.pending_move_out,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_id": self.table_id,
            "table_number": self.table_number,
            "player_count": self.player_count,
            "max_seats": self.max_seats,
            "hand_in_progress": self.hand_in_progress,
            "is_breaking": self.is_breaking,
        }


@dataclass(frozen=True)
class TournamentEvent:
    """
    Tournament event for event bus.

    All tournament state changes emit events for:
    - Real-time client notifications (WebSocket)
    - Audit logging
    - Analytics
    """

    event_id: str = field(default_factory=lambda: str(uuid4()))
    event_type: TournamentEventType = TournamentEventType.TOURNAMENT_CREATED
    tournament_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Event-specific data
    data: Dict[str, Any] = field(default_factory=dict)

    # Optional references
    table_id: Optional[str] = None
    user_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.name,
            "tournament_id": self.tournament_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "table_id": self.table_id,
            "user_id": self.user_id,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass(frozen=True)
class TournamentState:
    """
    Complete tournament state - immutable.

    This is the single source of truth for tournament status.
    All mutations return new state instances.
    """

    tournament_id: str
    config: TournamentConfig
    status: TournamentStatus = TournamentStatus.REGISTERING

    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None

    # Blind progression
    current_blind_level: int = 1
    level_started_at: Optional[datetime] = None
    next_level_at: Optional[datetime] = None

    # Players (user_id -> TournamentPlayer)
    players: Dict[str, TournamentPlayer] = field(default_factory=dict)

    # Tables (table_id -> TournamentTable)
    tables: Dict[str, TournamentTable] = field(default_factory=dict)

    # Ranking cache (updated periodically)
    ranking: List[str] = field(default_factory=list)  # user_ids sorted by chips

    # Prize pool
    total_prize_pool: int = 0
    itm_threshold: int = 0  # ITM 진입 등수

    # Pause reason (admin)
    pause_reason: Optional[str] = None

    @property
    def active_player_count(self) -> int:
        """Count of players still in tournament."""
        return sum(1 for p in self.players.values() if p.is_active)

    @property
    def eliminated_player_count(self) -> int:
        """Count of eliminated players."""
        return sum(1 for p in self.players.values() if not p.is_active)

    @property
    def current_blind(self) -> Optional[BlindLevel]:
        """Get current blind level config."""
        return self.config.get_blind_level(self.current_blind_level)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tournament_id": self.tournament_id,
            "name": self.config.name,
            "status": self.status.value,
            "current_blind_level": self.current_blind_level,
            "current_blind": self.current_blind.to_dict()
            if self.current_blind
            else None,
            "active_players": self.active_player_count,
            "total_players": len(self.players),
            "table_count": len(self.tables),
            "total_prize_pool": self.total_prize_pool,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "next_level_at": self.next_level_at.isoformat()
            if self.next_level_at
            else None,
        }
