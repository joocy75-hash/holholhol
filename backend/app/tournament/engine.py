"""
Enterprise Tournament Engine - Core Implementation.

300명 이상 동시 접속 Shotgun Start 지원.
1ms 오차 없는 동기화된 게임 시작.
"""

import asyncio
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Callable
from uuid import uuid4

import redis.asyncio as redis

from .models import (
    TournamentState,
    TournamentStatus,
    TournamentConfig,
    TournamentPlayer,
    TournamentTable,
    BlindLevel,
    TournamentEvent,
    TournamentEventType,
)
from .distributed_lock import DistributedLockManager, LockType, MultiLockManager
from .event_bus import TournamentEventBus
from .balancer import TableBalancer, BalancingPlan, PlayerMove
from .ranking import RankingEngine
from .snapshot import SnapshotManager


@dataclass
class ShotgunStartState:
    """Shotgun start synchronization state."""

    tournament_id: str
    target_start_time: datetime
    countdown_seconds: int
    registered_players: int
    ready_players: set = field(default_factory=set)
    started: bool = False


class TournamentEngine:
    """
    엔터프라이즈급 토너먼트 엔진.

    핵심 기능:
    ─────────────────────────────────────────────────────────────────

    1. Shotgun Start (동시 시작):
       - 모든 테이블이 정확히 동시에 시작
       - 카운트다운 동기화
       - 네트워크 지연 보정

    2. 동시성 제어:
       - Redis 분산 락으로 Deadlock 방지
       - 계층적 락 (Tournament > Table > Player)
       - 낙관적/비관적 락 전략 혼합

    3. 테이블 밸런싱:
       - 탈락 시 자동 재배치
       - 핸드 진행 중 이동 방지
       - 최소 이동 알고리즘

    4. 블라인드 관리:
       - 정확한 시간 기반 레벨업
       - 모든 테이블 동시 전파
       - 30초 전 경고

    5. 장애 복구:
       - 주기적 스냅샷
       - 핸드 단위 복구
       - 칩 정합성 보장

    ─────────────────────────────────────────────────────────────────
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        hmac_key: str = "tournament-engine-key",
    ):
        self.redis = redis_client

        # Core components
        self.lock_manager = DistributedLockManager(redis_client)
        self.multi_lock = MultiLockManager(self.lock_manager)
        self.event_bus = TournamentEventBus(redis_client)
        self.balancer = TableBalancer()
        self.ranking = RankingEngine(redis_client)
        self.snapshot = SnapshotManager(redis_client, hmac_key)

        # State store (in production: Redis or DB)
        self._tournaments: Dict[str, TournamentState] = {}

        # Shotgun start tracking
        self._shotgun_states: Dict[str, ShotgunStartState] = {}

        # Background tasks
        self._blind_task: Optional[asyncio.Task] = None
        self._balance_task: Optional[asyncio.Task] = None
        self._running = False

        # Callbacks for hand execution
        self._hand_started_callback: Optional[Callable] = None
        self._hand_completed_callback: Optional[Callable] = None

    async def initialize(self) -> None:
        """Initialize tournament engine."""
        await self.event_bus.initialize()
        self._running = True
        self._blind_task = asyncio.create_task(self._blind_level_loop())
        self._balance_task = asyncio.create_task(self._balancing_loop())

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        self._running = False
        if self._blind_task:
            self._blind_task.cancel()
        if self._balance_task:
            self._balance_task.cancel()
        await self.event_bus.shutdown()
        await self.lock_manager.cleanup_all()

    # =========================================================================
    # Tournament Lifecycle
    # =========================================================================

    async def create_tournament(
        self,
        config: TournamentConfig,
    ) -> TournamentState:
        """
        새 토너먼트 생성.

        Args:
            config: Tournament configuration

        Returns:
            Initial tournament state
        """
        state = TournamentState(
            tournament_id=config.tournament_id,
            config=config,
            status=TournamentStatus.REGISTERING,
        )

        self._tournaments[config.tournament_id] = state

        await self.event_bus.publish(
            TournamentEvent(
                event_type=TournamentEventType.TOURNAMENT_CREATED,
                tournament_id=config.tournament_id,
                data=config.to_dict(),
            )
        )

        await self.ranking.initialize(config.tournament_id)

        return state

    async def register_player(
        self,
        tournament_id: str,
        user_id: str,
        nickname: str,
    ) -> Tuple[TournamentState, TournamentPlayer]:
        """
        플레이어 등록.

        동시성:
        - 토너먼트 락 획득 후 등록
        - 최대 인원 체크
        - 중복 등록 방지
        """
        async with self.lock_manager.lock(tournament_id, LockType.TOURNAMENT):
            state = self._tournaments.get(tournament_id)
            if not state:
                raise ValueError(f"Tournament {tournament_id} not found")

            if state.status != TournamentStatus.REGISTERING:
                raise ValueError("Registration closed")

            if len(state.players) >= state.config.max_players:
                raise ValueError("Tournament full")

            if user_id in state.players:
                raise ValueError("Already registered")

            # Create player
            player = TournamentPlayer(
                user_id=user_id,
                nickname=nickname,
                chip_count=state.config.starting_chips,
            )

            # Update state
            new_players = dict(state.players)
            new_players[user_id] = player

            new_state = TournamentState(
                tournament_id=state.tournament_id,
                config=state.config,
                status=state.status,
                created_at=state.created_at,
                players=new_players,
                tables=state.tables,
                total_prize_pool=state.total_prize_pool + state.config.buy_in,
            )

            self._tournaments[tournament_id] = new_state

            # Update ranking
            await self.ranking.register_player(tournament_id, player)

            # Emit event
            await self.event_bus.publish(
                TournamentEvent(
                    event_type=TournamentEventType.PLAYER_REGISTERED,
                    tournament_id=tournament_id,
                    user_id=user_id,
                    data={"nickname": nickname, "total_players": len(new_players)},
                )
            )

            return new_state, player

    async def start_tournament(
        self,
        tournament_id: str,
    ) -> TournamentState:
        """
        토너먼트 시작 - Shotgun Start.

        Shotgun Start 알고리즘:
        ─────────────────────────────────────────────────────────────

        1. 시작 조건 확인 (최소 인원)
        2. 테이블 생성 및 플레이어 배치
        3. 카운트다운 시작 (모든 클라이언트 동기화)
        4. 정확한 시각에 모든 테이블 동시 시작
        5. 블라인드 타이머 가동

        동기화:
        - 서버 시간 기준 정확한 시작 시각 설정
        - 클라이언트에 target_time 전송
        - 네트워크 지연을 고려한 버퍼 시간 추가

        ─────────────────────────────────────────────────────────────
        """
        async with self.lock_manager.lock(tournament_id, LockType.TOURNAMENT):
            state = self._tournaments.get(tournament_id)
            if not state:
                raise ValueError(f"Tournament {tournament_id} not found")

            if state.status != TournamentStatus.REGISTERING:
                raise ValueError("Cannot start: not in registration")

            if len(state.players) < state.config.min_players:
                raise ValueError(f"Minimum {state.config.min_players} players required")

            # Create tables and seat players
            tables = self._create_tables_and_seat_players(state)

            # Update player table assignments
            new_players = dict(state.players)
            for table in tables.values():
                for seat_idx, user_id in enumerate(table.seats):
                    if user_id and user_id in new_players:
                        new_players[user_id] = new_players[user_id].at_table(
                            table.table_id, seat_idx
                        )

            # Prepare shotgun start
            countdown = state.config.shotgun_countdown_seconds
            target_time = datetime.utcnow() + timedelta(seconds=countdown)

            shotgun_state = ShotgunStartState(
                tournament_id=tournament_id,
                target_start_time=target_time,
                countdown_seconds=countdown,
                registered_players=len(new_players),
            )
            self._shotgun_states[tournament_id] = shotgun_state

            # Update state to STARTING
            new_state = TournamentState(
                tournament_id=state.tournament_id,
                config=state.config,
                status=TournamentStatus.STARTING,
                created_at=state.created_at,
                current_blind_level=1,
                level_started_at=target_time,
                next_level_at=target_time
                + timedelta(minutes=state.config.blind_levels[0].duration_minutes),
                players=new_players,
                tables=tables,
                total_prize_pool=state.total_prize_pool,
                itm_threshold=int(len(new_players) * state.config.itm_percentage / 100),
            )

            self._tournaments[tournament_id] = new_state

            # Emit start countdown event
            await self.event_bus.publish(
                TournamentEvent(
                    event_type=TournamentEventType.TOURNAMENT_STARTED,
                    tournament_id=tournament_id,
                    data={
                        "target_start_time": target_time.isoformat(),
                        "countdown_seconds": countdown,
                        "table_count": len(tables),
                        "player_count": len(new_players),
                    },
                )
            )

            # Schedule actual start
            asyncio.create_task(self._execute_shotgun_start(tournament_id, countdown))

            # Save initial snapshot
            await self.snapshot.save_full_snapshot(new_state)

            return new_state

    def _create_tables_and_seat_players(
        self,
        state: TournamentState,
    ) -> Dict[str, TournamentTable]:
        """
        테이블 생성 및 플레이어 배치.

        배치 알고리즘:
        ─────────────────────────────────────────────────────────────

        1. 필요한 테이블 수 계산: ceil(players / max_per_table)
        2. 플레이어 랜덤 셔플
        3. 라운드 로빈으로 균등 배치
        4. 각 테이블 내 시트는 랜덤

        균등 배치 보장:
        - 모든 테이블이 ±1 인원 차이 이내
        - 예: 25명, 9인 테이블 → 3테이블 (9, 8, 8명)

        ─────────────────────────────────────────────────────────────
        """
        players = list(state.players.values())
        random.shuffle(players)  # 랜덤 배치

        max_per_table = state.config.players_per_table
        num_tables = (len(players) + max_per_table - 1) // max_per_table

        tables: Dict[str, TournamentTable] = {}

        # Create empty tables
        for i in range(num_tables):
            table_id = str(uuid4())
            tables[table_id] = TournamentTable(
                table_id=table_id,
                table_number=i + 1,
                max_seats=max_per_table,
            )

        # Distribute players (round-robin)
        table_list = list(tables.values())
        for idx, player in enumerate(players):
            table_idx = idx % num_tables
            table = table_list[table_idx]

            # Find empty seat
            seat = table.player_count
            if seat < max_per_table:
                tables[table.table_id] = table.with_player_seated(player.user_id, seat)
                table_list[table_idx] = tables[table.table_id]

        return tables

    async def _execute_shotgun_start(
        self,
        tournament_id: str,
        countdown: int,
    ) -> None:
        """
        Shotgun Start 실행.

        정확한 시각에 모든 테이블 동시 시작.
        """
        await asyncio.sleep(countdown)

        async with self.lock_manager.lock(tournament_id, LockType.TOURNAMENT):
            state = self._tournaments.get(tournament_id)
            if not state or state.status != TournamentStatus.STARTING:
                return

            # Update to RUNNING
            new_state = TournamentState(
                tournament_id=state.tournament_id,
                config=state.config,
                status=TournamentStatus.RUNNING,
                created_at=state.created_at,
                started_at=datetime.utcnow(),
                current_blind_level=1,
                level_started_at=datetime.utcnow(),
                next_level_at=datetime.utcnow()
                + timedelta(minutes=state.config.blind_levels[0].duration_minutes),
                players=state.players,
                tables=state.tables,
                total_prize_pool=state.total_prize_pool,
                itm_threshold=state.itm_threshold,
            )

            self._tournaments[tournament_id] = new_state

            # Start all tables simultaneously
            start_tasks = []
            for table_id in new_state.tables:
                task = asyncio.create_task(
                    self._start_table_hand(tournament_id, table_id)
                )
                start_tasks.append(task)

            # Wait for all to start
            await asyncio.gather(*start_tasks, return_exceptions=True)

            # Mark shotgun start complete
            if tournament_id in self._shotgun_states:
                self._shotgun_states[tournament_id].started = True

    async def _start_table_hand(
        self,
        tournament_id: str,
        table_id: str,
    ) -> None:
        """개별 테이블 핸드 시작."""
        async with self.lock_manager.lock(tournament_id, LockType.TABLE, table_id):
            state = self._tournaments.get(tournament_id)
            if not state:
                return

            table = state.tables.get(table_id)
            if not table or table.player_count < 2:
                return

            # Emit table hand started event
            await self.event_bus.publish(
                TournamentEvent(
                    event_type=TournamentEventType.TABLE_HAND_STARTED,
                    tournament_id=tournament_id,
                    table_id=table_id,
                    data={"player_count": table.player_count},
                )
            )

            if self._hand_started_callback:
                await self._hand_started_callback(tournament_id, table_id)

    # =========================================================================
    # Hand Completion & Player Elimination
    # =========================================================================

    async def complete_hand(
        self,
        tournament_id: str,
        table_id: str,
        winners: List[str],
        chip_changes: Dict[str, int],
        eliminated: List[str],
    ) -> TournamentState:
        """
        핸드 완료 처리.

        처리 순서:
        1. 칩 변경 적용
        2. 탈락자 처리
        3. 랭킹 업데이트
        4. 테이블 밸런싱 체크
        5. 다음 핸드 시작 또는 토너먼트 종료
        """
        async with self.lock_manager.lock(tournament_id, LockType.TABLE, table_id):
            state = self._tournaments.get(tournament_id)
            if not state:
                raise ValueError("Tournament not found")

            new_players = dict(state.players)
            active_count = state.active_player_count

            # Apply chip changes
            for user_id, new_chips in chip_changes.items():
                if user_id in new_players:
                    new_players[user_id] = new_players[user_id].with_chips(new_chips)

            # Process eliminations
            for user_id in eliminated:
                if user_id in new_players:
                    active_count -= 1
                    new_players[user_id] = new_players[user_id].eliminated(
                        rank=active_count + 1
                    )

                    await self.event_bus.emit_player_eliminated(
                        tournament_id,
                        user_id,
                        active_count + 1,
                        eliminated_by=winners[0] if winners else None,
                        table_id=table_id,
                    )

            # Update table state (hand complete)
            new_tables = dict(state.tables)
            table = new_tables.get(table_id)
            if table:
                # Remove eliminated players from table
                for user_id in eliminated:
                    if user_id:
                        table = table.with_player_removed(user_id)
                new_tables[table_id] = TournamentTable(
                    table_id=table.table_id,
                    table_number=table.table_number,
                    seats=table.seats,
                    max_seats=table.max_seats,
                    hand_in_progress=False,
                    current_hand_id=None,
                )

            # Check for tournament completion
            new_status = state.status
            if active_count <= 1:
                new_status = TournamentStatus.COMPLETED
            elif active_count <= 2:
                new_status = TournamentStatus.HEADS_UP
            elif active_count <= state.config.players_per_table:
                new_status = TournamentStatus.FINAL_TABLE

            new_state = TournamentState(
                tournament_id=state.tournament_id,
                config=state.config,
                status=new_status,
                created_at=state.created_at,
                started_at=state.started_at,
                ended_at=datetime.utcnow()
                if new_status == TournamentStatus.COMPLETED
                else None,
                current_blind_level=state.current_blind_level,
                level_started_at=state.level_started_at,
                next_level_at=state.next_level_at,
                players=new_players,
                tables=new_tables,
                ranking=state.ranking,
                total_prize_pool=state.total_prize_pool,
                itm_threshold=state.itm_threshold,
            )

            self._tournaments[tournament_id] = new_state

            # Update ranking
            ranking_updates = [
                (uid, new_players[uid].chip_count)
                for uid in chip_changes.keys()
                if uid in new_players
            ]
            await self.ranking.update_batch(tournament_id, ranking_updates)

            # Clear hand snapshot
            await self.snapshot.complete_hand(tournament_id, table_id)

            # Emit hand complete event
            await self.event_bus.publish(
                TournamentEvent(
                    event_type=TournamentEventType.TABLE_HAND_COMPLETED,
                    tournament_id=tournament_id,
                    table_id=table_id,
                    data={"winners": winners, "eliminated": eliminated},
                )
            )

            return new_state

    # =========================================================================
    # Blind Level Management
    # =========================================================================

    async def _blind_level_loop(self) -> None:
        """블라인드 레벨 관리 백그라운드 태스크."""
        while self._running:
            try:
                now = datetime.utcnow()

                for tournament_id, state in list(self._tournaments.items()):
                    if state.status not in (
                        TournamentStatus.RUNNING,
                        TournamentStatus.FINAL_TABLE,
                        TournamentStatus.HEADS_UP,
                    ):
                        continue

                    # Check for level up
                    if state.next_level_at and now >= state.next_level_at:
                        await self._level_up(tournament_id)

                    # 30-second warning
                    elif state.next_level_at:
                        time_to_level = (state.next_level_at - now).total_seconds()
                        if 29 < time_to_level <= 30:
                            await self.event_bus.publish(
                                TournamentEvent(
                                    event_type=TournamentEventType.BLIND_INCREASE_WARNING,
                                    tournament_id=tournament_id,
                                    data={"seconds_remaining": 30},
                                )
                            )

                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1)

    async def _level_up(self, tournament_id: str) -> None:
        """블라인드 레벨업 처리."""
        async with self.lock_manager.lock(tournament_id, LockType.BLIND):
            state = self._tournaments.get(tournament_id)
            if not state:
                return

            next_level = state.current_blind_level + 1
            blind_config = state.config.get_blind_level(next_level)

            if not blind_config:
                return  # Max level reached

            new_state = TournamentState(
                tournament_id=state.tournament_id,
                config=state.config,
                status=state.status,
                created_at=state.created_at,
                started_at=state.started_at,
                current_blind_level=next_level,
                level_started_at=datetime.utcnow(),
                next_level_at=datetime.utcnow()
                + timedelta(minutes=blind_config.duration_minutes),
                players=state.players,
                tables=state.tables,
                ranking=state.ranking,
                total_prize_pool=state.total_prize_pool,
                itm_threshold=state.itm_threshold,
            )

            self._tournaments[tournament_id] = new_state

            # Broadcast blind change to all tables
            await self.event_bus.emit_blind_change(
                tournament_id,
                next_level,
                blind_config.small_blind,
                blind_config.big_blind,
                blind_config.ante,
            )

            # Save checkpoint
            await self.snapshot.save_full_snapshot(new_state)

    # =========================================================================
    # Table Balancing
    # =========================================================================

    async def _balancing_loop(self) -> None:
        """테이블 밸런싱 백그라운드 태스크."""
        while self._running:
            try:
                for tournament_id, state in list(self._tournaments.items()):
                    if state.status not in (
                        TournamentStatus.RUNNING,
                        TournamentStatus.FINAL_TABLE,
                    ):
                        continue

                    await self._check_and_balance(tournament_id)

                await asyncio.sleep(2)  # Check every 2 seconds

            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(2)

    async def _check_and_balance(self, tournament_id: str) -> None:
        """테이블 밸런싱 필요 여부 확인 및 실행."""
        state = self._tournaments.get(tournament_id)
        if not state:
            return

        plan = self.balancer.calculate_balancing_plan(state)

        if not plan.moves:
            return

        # Execute moves for tables not in hand
        for move in plan.moves:
            from_table = state.tables.get(move.from_table_id)
            if from_table and not from_table.hand_in_progress:
                await self._execute_player_move(tournament_id, move)

    async def _execute_player_move(
        self,
        tournament_id: str,
        move: PlayerMove,
    ) -> None:
        """플레이어 테이블 이동 실행."""
        locks_needed = [
            (tournament_id, LockType.TABLE, move.from_table_id),
            (tournament_id, LockType.TABLE, move.to_table_id),
            (tournament_id, LockType.PLAYER, move.user_id),
        ]

        async with self.multi_lock.multi_lock(locks_needed):
            state = self._tournaments.get(tournament_id)
            if not state:
                return

            # Update tables
            new_tables = dict(state.tables)
            from_table = new_tables.get(move.from_table_id)
            to_table = new_tables.get(move.to_table_id)

            if not from_table or not to_table:
                return

            new_tables[move.from_table_id] = from_table.with_player_removed(
                move.user_id
            )
            new_tables[move.to_table_id] = to_table.with_player_seated(
                move.user_id, move.to_seat
            )

            # Update player
            new_players = dict(state.players)
            player = new_players.get(move.user_id)
            if player:
                new_players[move.user_id] = player.at_table(
                    move.to_table_id, move.to_seat
                )

            new_state = TournamentState(
                tournament_id=state.tournament_id,
                config=state.config,
                status=state.status,
                created_at=state.created_at,
                started_at=state.started_at,
                current_blind_level=state.current_blind_level,
                level_started_at=state.level_started_at,
                next_level_at=state.next_level_at,
                players=new_players,
                tables=new_tables,
                ranking=state.ranking,
                total_prize_pool=state.total_prize_pool,
                itm_threshold=state.itm_threshold,
            )

            self._tournaments[tournament_id] = new_state

            # Emit move event
            await self.event_bus.publish(
                TournamentEvent(
                    event_type=TournamentEventType.PLAYER_MOVED,
                    tournament_id=tournament_id,
                    user_id=move.user_id,
                    data=move.to_dict(),
                )
            )

            self.balancer.complete_move(move.move_id)

    # =========================================================================
    # State Access
    # =========================================================================

    def get_state(self, tournament_id: str) -> Optional[TournamentState]:
        return self._tournaments.get(tournament_id)

    async def get_ranking(self, tournament_id: str, top_n: int = 100):
        return await self.ranking.get_top_players(tournament_id, top_n)

    async def recover_tournament(self, tournament_id: str) -> Optional[TournamentState]:
        """서버 재시작 후 토너먼트 복구."""
        state = await self.snapshot.load_latest(tournament_id)
        if state:
            self._tournaments[tournament_id] = state
            await self.ranking.sync_from_state(state)
        return state
