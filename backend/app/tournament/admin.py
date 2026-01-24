"""
Tournament Admin Controller.

토너먼트 강제 일시정지, 특정 테이블 모니터링, 비정상 유저 강제 퇴장 기능.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .models import (
    TournamentState,
    TournamentStatus,
    TournamentPlayer,
    TournamentEvent,
    TournamentEventType,
)
from .event_bus import TournamentEventBus
from .distributed_lock import DistributedLockManager, LockType


class AdminActionType(Enum):
    PAUSE = "pause"
    RESUME = "resume"
    KICK_PLAYER = "kick_player"
    ADD_CHIPS = "add_chips"
    REMOVE_CHIPS = "remove_chips"
    FORCE_END = "force_end"
    ADJUST_BLIND = "adjust_blind"
    MOVE_PLAYER = "move_player"


@dataclass
class AdminAction:
    """Record of admin action for audit."""

    action_id: str = field(default_factory=lambda: str(uuid4()))
    action_type: AdminActionType = AdminActionType.PAUSE
    admin_id: str = ""
    tournament_id: str = ""
    target_user_id: Optional[str] = None
    target_table_id: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    success: bool = True
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "admin_id": self.admin_id,
            "tournament_id": self.tournament_id,
            "target_user_id": self.target_user_id,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "success": self.success,
        }


@dataclass
class TableMonitorData:
    """Real-time table monitoring data."""

    table_id: str
    table_number: int
    player_count: int
    players: List[Dict[str, Any]]
    hand_in_progress: bool
    current_hand_id: Optional[str]
    pot_size: int = 0
    current_bet: int = 0
    acting_player: Optional[str] = None


class TournamentAdminController:
    """
    관리자 제어 컨트롤러.

    기능:
    1. 토너먼트 일시정지/재개
    2. 특정 테이블 실시간 모니터링
    3. 비정상 유저 강제 퇴장
    4. 칩 조정 (분쟁 해결용)
    5. 블라인드 레벨 조정
    """

    def __init__(
        self,
        lock_manager: DistributedLockManager,
        event_bus: TournamentEventBus,
    ):
        self.lock_manager = lock_manager
        self.event_bus = event_bus
        self._action_log: List[AdminAction] = []

    async def pause_tournament(
        self,
        state: TournamentState,
        admin_id: str,
        reason: str = "Admin pause",
    ) -> TournamentState:
        """
        토너먼트 강제 일시정지.

        일시정지 시:
        - 모든 테이블에 PAUSE 이벤트 전파
        - 현재 핸드는 완료 허용
        - 새 핸드 시작 금지
        - 블라인드 타이머 정지
        """
        action = AdminAction(
            action_type=AdminActionType.PAUSE,
            admin_id=admin_id,
            tournament_id=state.tournament_id,
            reason=reason,
        )

        async with self.lock_manager.lock(state.tournament_id, LockType.TOURNAMENT):
            if state.status == TournamentStatus.PAUSED:
                action.success = False
                action.error_message = "Already paused"
                self._action_log.append(action)
                return state

            # Update state to paused
            new_state = TournamentState(
                tournament_id=state.tournament_id,
                config=state.config,
                status=TournamentStatus.PAUSED,
                created_at=state.created_at,
                started_at=state.started_at,
                paused_at=datetime.now(timezone.utc),
                current_blind_level=state.current_blind_level,
                level_started_at=state.level_started_at,
                players=state.players,
                tables=state.tables,
                ranking=state.ranking,
                total_prize_pool=state.total_prize_pool,
                pause_reason=reason,
            )

            # Emit pause event
            await self.event_bus.publish(
                TournamentEvent(
                    event_type=TournamentEventType.TOURNAMENT_PAUSED,
                    tournament_id=state.tournament_id,
                    data={"reason": reason, "admin_id": admin_id},
                )
            )

            self._action_log.append(action)
            return new_state

    async def resume_tournament(
        self,
        state: TournamentState,
        admin_id: str,
    ) -> TournamentState:
        """토너먼트 재개."""
        action = AdminAction(
            action_type=AdminActionType.RESUME,
            admin_id=admin_id,
            tournament_id=state.tournament_id,
        )

        async with self.lock_manager.lock(state.tournament_id, LockType.TOURNAMENT):
            if state.status != TournamentStatus.PAUSED:
                action.success = False
                action.error_message = "Not paused"
                self._action_log.append(action)
                return state

            new_state = TournamentState(
                tournament_id=state.tournament_id,
                config=state.config,
                status=TournamentStatus.RUNNING,
                created_at=state.created_at,
                started_at=state.started_at,
                current_blind_level=state.current_blind_level,
                level_started_at=datetime.now(timezone.utc),
                players=state.players,
                tables=state.tables,
                ranking=state.ranking,
                total_prize_pool=state.total_prize_pool,
            )

            await self.event_bus.publish(
                TournamentEvent(
                    event_type=TournamentEventType.TOURNAMENT_RESUMED,
                    tournament_id=state.tournament_id,
                    data={"admin_id": admin_id},
                )
            )

            self._action_log.append(action)
            return new_state

    async def kick_player(
        self,
        state: TournamentState,
        admin_id: str,
        user_id: str,
        reason: str,
    ) -> TournamentState:
        """
        비정상 유저 강제 퇴장.

        처리:
        - 즉시 탈락 처리
        - 현재 핸드에서 폴드 처리
        - 칩 몰수 (상금 지급 없음)
        """
        action = AdminAction(
            action_type=AdminActionType.KICK_PLAYER,
            admin_id=admin_id,
            tournament_id=state.tournament_id,
            target_user_id=user_id,
            reason=reason,
        )

        player = state.players.get(user_id)
        if not player:
            action.success = False
            action.error_message = "Player not found"
            self._action_log.append(action)
            return state

        async with self.lock_manager.lock(
            state.tournament_id, LockType.PLAYER, user_id
        ):
            # Mark player as eliminated
            eliminated_player = player.eliminated(rank=state.active_player_count)

            # Update players dict
            new_players = dict(state.players)
            new_players[user_id] = eliminated_player

            # Remove from table
            new_tables = dict(state.tables)
            if player.table_id and player.table_id in new_tables:
                table = new_tables[player.table_id]
                new_tables[player.table_id] = table.with_player_removed(user_id)

            new_state = TournamentState(
                tournament_id=state.tournament_id,
                config=state.config,
                status=state.status,
                created_at=state.created_at,
                started_at=state.started_at,
                current_blind_level=state.current_blind_level,
                players=new_players,
                tables=new_tables,
                ranking=state.ranking,
                total_prize_pool=state.total_prize_pool,
            )

            # Emit kick event
            await self.event_bus.publish(
                TournamentEvent(
                    event_type=TournamentEventType.PLAYER_KICKED,
                    tournament_id=state.tournament_id,
                    user_id=user_id,
                    data={"reason": reason, "admin_id": admin_id},
                )
            )

            self._action_log.append(action)
            return new_state

    async def add_chips(
        self,
        state: TournamentState,
        admin_id: str,
        user_id: str,
        amount: int,
        reason: str,
    ) -> TournamentState:
        """칩 추가 (분쟁 해결용)."""
        action = AdminAction(
            action_type=AdminActionType.ADD_CHIPS,
            admin_id=admin_id,
            tournament_id=state.tournament_id,
            target_user_id=user_id,
            parameters={"amount": amount},
            reason=reason,
        )

        player = state.players.get(user_id)
        if not player or not player.is_active:
            action.success = False
            action.error_message = "Player not found or eliminated"
            self._action_log.append(action)
            return state

        async with self.lock_manager.lock(
            state.tournament_id, LockType.PLAYER, user_id
        ):
            updated_player = player.with_chips(player.chip_count + amount)

            new_players = dict(state.players)
            new_players[user_id] = updated_player

            new_state = TournamentState(
                tournament_id=state.tournament_id,
                config=state.config,
                status=state.status,
                created_at=state.created_at,
                started_at=state.started_at,
                current_blind_level=state.current_blind_level,
                players=new_players,
                tables=state.tables,
                ranking=state.ranking,
                total_prize_pool=state.total_prize_pool,
            )

            self._action_log.append(action)
            return new_state

    async def get_table_monitor(
        self,
        state: TournamentState,
        table_id: str,
    ) -> Optional[TableMonitorData]:
        """특정 테이블 실시간 모니터링 데이터."""
        table = state.tables.get(table_id)
        if not table:
            return None

        players = []
        for user_id in table.seats:
            if user_id:
                player = state.players.get(user_id)
                if player:
                    players.append(
                        {
                            "user_id": user_id,
                            "nickname": player.nickname,
                            "chip_count": player.chip_count,
                            "seat": player.seat_position,
                            "is_connected": player.is_connected,
                        }
                    )

        return TableMonitorData(
            table_id=table_id,
            table_number=table.table_number,
            player_count=table.player_count,
            players=players,
            hand_in_progress=table.hand_in_progress,
            current_hand_id=table.current_hand_id,
        )

    async def get_all_tables_monitor(
        self,
        state: TournamentState,
    ) -> List[TableMonitorData]:
        """모든 테이블 모니터링 데이터."""
        monitors = []
        for table_id in state.tables:
            monitor = await self.get_table_monitor(state, table_id)
            if monitor:
                monitors.append(monitor)
        return monitors

    async def force_blind_level(
        self,
        state: TournamentState,
        admin_id: str,
        level: int,
        reason: str,
    ) -> TournamentState:
        """블라인드 레벨 강제 조정."""
        action = AdminAction(
            action_type=AdminActionType.ADJUST_BLIND,
            admin_id=admin_id,
            tournament_id=state.tournament_id,
            parameters={"level": level},
            reason=reason,
        )

        blind_config = state.config.get_blind_level(level)
        if not blind_config:
            action.success = False
            action.error_message = f"Invalid blind level: {level}"
            self._action_log.append(action)
            return state

        async with self.lock_manager.lock(state.tournament_id, LockType.BLIND):
            new_state = TournamentState(
                tournament_id=state.tournament_id,
                config=state.config,
                status=state.status,
                created_at=state.created_at,
                started_at=state.started_at,
                current_blind_level=level,
                level_started_at=datetime.now(timezone.utc),
                players=state.players,
                tables=state.tables,
                ranking=state.ranking,
                total_prize_pool=state.total_prize_pool,
            )

            await self.event_bus.emit_blind_change(
                state.tournament_id,
                level,
                blind_config.small_blind,
                blind_config.big_blind,
                blind_config.ante,
            )

            self._action_log.append(action)
            return new_state

    def get_action_log(
        self,
        tournament_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AdminAction]:
        """관리자 액션 로그 조회."""
        logs = self._action_log
        if tournament_id:
            logs = [a for a in logs if a.tournament_id == tournament_id]
        return logs[-limit:]
