"""
Tournament Engine Integration with PokerKit.

기존 PokerKitWrapper와 토너먼트 엔진을 연동하여
토너먼트 핸드를 처리하는 브릿지 모듈.
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ..engine.core import PokerKitWrapper
from ..schemas.game import ActionRequest, ActionType
from .models import TournamentState, BlindLevel
from .snapshot import SnapshotManager
from .event_bus import TournamentEventBus

logger = logging.getLogger(__name__)


class TournamentHandBridge:
    """
    토너먼트 핸드 처리 브릿지.

    기존 PokerKitWrapper를 활용하여 토너먼트 핸드를 처리.
    """

    def __init__(
        self,
        snapshot_manager: SnapshotManager,
        event_bus: TournamentEventBus,
    ):
        self.poker_engine = PokerKitWrapper()
        self.snapshot = snapshot_manager
        self.event_bus = event_bus
        self._active_hands: dict[str, Any] = {}

    async def start_hand(
        self,
        tournament_state: TournamentState,
        table_id: str,
    ) -> tuple[Any, str]:
        """토너먼트 테이블에서 새 핸드 시작."""
        table = tournament_state.tables.get(table_id)
        if not table:
            raise ValueError(f"Table {table_id} not found")

        blind = tournament_state.current_blind or BlindLevel(1, 25, 50, 0, 15)

        from ..schemas.game import TableConfig, TableState, SeatState

        seated_players = []
        starting_stacks: dict[str, int] = {}

        for seat_idx, user_id in enumerate(table.seats):
            if user_id:
                player = tournament_state.players.get(user_id)
                if player and player.is_active and player.chip_count > 0:
                    seated_players.append((seat_idx, user_id, player.chip_count))
                    starting_stacks[user_id] = player.chip_count

        if len(seated_players) < 2:
            raise ValueError("Not enough players to start hand")

        config = TableConfig(
            table_id=table_id,
            max_seats=table.max_seats,
            small_blind=blind.small_blind,
            big_blind=blind.big_blind,
            ante=blind.ante,
            min_buy_in=0,
            max_buy_in=999999999,
        )

        seats = []
        for i in range(table.max_seats):
            seat_data = None
            for seat_idx, user_id, chips in seated_players:
                if seat_idx == i:
                    seat_data = SeatState(
                        position=i,
                        user_id=user_id,
                        nickname=tournament_state.players[user_id].nickname,
                        stack=chips,
                        is_sitting_out=False,
                    )
                    break
            seats.append(seat_data if seat_data else SeatState(position=i))

        table_state = TableState(
            table_id=table_id,
            config=config,
            seats=tuple(seats),
        )

        hand_id = str(uuid4())
        table_state = self.poker_engine.create_initial_hand(
            table_state, hand_id=hand_id
        )

        self._active_hands[table_id] = table_state

        await self.snapshot.save_hand_snapshot(
            tournament_state.tournament_id,
            table_id,
            hand_id,
            b"",
            starting_stacks,
        )

        logger.info(
            f"Tournament hand started: table={table_id}, hand={hand_id}, "
            f"players={len(seated_players)}"
        )

        return table_state, hand_id

    async def apply_action(
        self,
        tournament_id: str,
        table_id: str,
        user_id: str,
        action: ActionRequest,
    ) -> tuple[Any, dict[str, Any] | None]:
        """플레이어 액션 처리."""
        table_state = self._active_hands.get(table_id)
        if not table_state:
            raise ValueError(f"No active hand on table {table_id}")

        position = None
        for seat in table_state.seats:
            if seat.user_id == user_id:
                position = seat.position
                break

        if position is None:
            raise ValueError(f"Player {user_id} not at table {table_id}")

        new_state, executed_action = self.poker_engine.apply_action(
            table_state, position, action
        )

        self._active_hands[table_id] = new_state

        await self.snapshot.update_hand_action(
            tournament_id,
            table_id,
            {
                "user_id": user_id,
                "action": action.action.value,
                "amount": action.amount,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        if self.poker_engine.is_hand_finished(new_state):
            return new_state, {
                "action": executed_action.action.value if executed_action else None,
                "amount": executed_action.amount if executed_action else 0,
                "hand_complete": True,
            }

        return new_state, {
            "action": executed_action.action.value if executed_action else None,
            "amount": executed_action.amount if executed_action else 0,
            "hand_complete": False,
        }

    async def complete_hand(
        self,
        tournament_id: str,
        table_id: str,
    ) -> dict[str, Any]:
        """핸드 완료 처리."""
        table_state = self._active_hands.get(table_id)
        if not table_state:
            raise ValueError(f"No active hand on table {table_id}")

        if not self.poker_engine.is_hand_finished(table_state):
            raise ValueError("Hand is not finished")

        result = self.poker_engine.evaluate_hand(table_state)

        chip_changes: dict[str, int] = {}
        winners: list[str] = []
        eliminated: list[str] = []

        for seat in table_state.seats:
            if seat.user_id:
                chip_changes[seat.user_id] = seat.stack
                if seat.stack <= 0:
                    eliminated.append(seat.user_id)

        if result.winners:
            for winner in result.winners:
                if winner.user_id:
                    winners.append(winner.user_id)

        del self._active_hands[table_id]
        await self.snapshot.complete_hand(tournament_id, table_id)

        logger.info(
            f"Tournament hand completed: table={table_id}, "
            f"winners={winners}, eliminated={eliminated}"
        )

        return {
            "winners": winners,
            "chip_changes": chip_changes,
            "eliminated": eliminated,
        }

    def get_valid_actions(
        self,
        table_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """Get valid actions for player."""
        table_state = self._active_hands.get(table_id)
        if not table_state:
            return []

        position = None
        for seat in table_state.seats:
            if seat.user_id == user_id:
                position = seat.position
                break

        if position is None:
            return []

        valid_actions = self.poker_engine.get_valid_actions(table_state, position)

        return [
            {
                "action": va.action.value,
                "min_amount": va.min_amount,
                "max_amount": va.max_amount,
            }
            for va in valid_actions
        ]

    def get_table_state(self, table_id: str) -> Any | None:
        """Get current table state for active hand."""
        return self._active_hands.get(table_id)

    def is_hand_active(self, table_id: str) -> bool:
        """Check if hand is active on table."""
        return table_id in self._active_hands

    async def force_fold_player(
        self,
        tournament_id: str,
        table_id: str,
        user_id: str,
    ) -> Any | None:
        """Force fold a player (for kicks, disconnects)."""
        table_state = self._active_hands.get(table_id)
        if not table_state:
            return None

        position = None
        for seat in table_state.seats:
            if seat.user_id == user_id:
                position = seat.position
                break

        if position is None:
            return None

        try:
            fold_action = ActionRequest(action=ActionType.FOLD)
            new_state, _ = self.poker_engine.apply_action(
                table_state, position, fold_action
            )
            self._active_hands[table_id] = new_state
            return new_state
        except Exception as e:
            logger.warning(f"Could not force fold player {user_id}: {e}")
            return None
