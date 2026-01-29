"""Bot Game Loop - Autonomous game management for live bots.

This service handles game start and turn processing when bots are involved,
independent of WebSocket connections.
"""

import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Optional, Any

from app.bot.strategy import get_strategy
from app.bot.strategy.base import GameContext
from app.config import get_settings
from app.game.manager import game_manager
from app.game.poker_table import PokerTable, GamePhase
from app.game.types import ActionResult, HandResult
from app.ws.events import EventType
from app.ws.messages import MessageEnvelope

logger = logging.getLogger(__name__)

# Singleton instance
_game_loop: Optional["BotGameLoop"] = None


def is_bot_player(player) -> bool:
    """Check if player is a bot."""
    if not player:
        return False
    user_id = getattr(player, "user_id", "") or ""
    if user_id.startswith("livebot_") or user_id.startswith("bot_") or user_id.startswith("test_player_"):
        return True
    if hasattr(player, "is_bot") and player.is_bot:
        return True
    return False


def is_livebot_player(player) -> bool:
    """Check if player is a live bot (uses strategy system)."""
    if not player:
        return False
    user_id = getattr(player, "user_id", "") or ""
    return user_id.startswith("livebot_")


class BotGameLoop:
    """Manages game start and bot turn processing.

    Features:
    - Checks game start conditions after bot seating
    - Processes bot turns without WebSocket dependency
    - Auto-starts next hand after completion
    - Broadcasts game events via ConnectionManager
    """

    def __init__(self):
        self._settings = get_settings()
        self._running = False
        self._table_locks: dict[str, asyncio.Lock] = {}
        self._processing_tables: set[str] = set()  # 현재 처리 중인 테이블

    def _get_table_lock(self, room_id: str) -> asyncio.Lock:
        """Get or create a lock for a specific table."""
        if room_id not in self._table_locks:
            self._table_locks[room_id] = asyncio.Lock()
        return self._table_locks[room_id]

    async def start(self) -> None:
        """Start the game loop service."""
        if self._running:
            return
        self._running = True
        logger.info("[BOT_GAME_LOOP] Service started")

    async def stop(self) -> None:
        """Stop the game loop service."""
        self._running = False
        logger.info("[BOT_GAME_LOOP] Service stopped")

    async def try_start_game(self, room_id: str) -> bool:
        """Try to start a game if conditions are met.

        Called after a bot is seated. Checks if there are enough
        active players to start a hand.

        Args:
            room_id: The room/table ID

        Returns:
            True if game was started, False otherwise
        """
        if not self._running:
            logger.warning(f"[BOT_GAME_LOOP] Service not running, skipping start for {room_id}")
            return False

        # 이미 처리 중인 테이블이면 스킵
        if room_id in self._processing_tables:
            logger.debug(f"[BOT_GAME_LOOP] Table {room_id} already being processed")
            return False

        table_lock = self._get_table_lock(room_id)

        async with table_lock:
            table = game_manager.get_table(room_id)
            if not table:
                logger.warning(f"[BOT_GAME_LOOP] Table not found: {room_id}")
                return False

            # BB 대기자 활성화 시도
            pre_activated = table.try_activate_bb_waiter_for_next_hand()
            if pre_activated:
                logger.info(f"[BOT_GAME_LOOP] Activated BB waiters: {pre_activated}")
                await self._broadcast_sit_in_events(room_id, table, pre_activated)

            # 게임 시작 조건 확인
            if not table.can_start_hand():
                active_players = table.get_active_players()
                all_players = table.get_all_seated_players()
                logger.info(
                    f"[BOT_GAME_LOOP] Cannot start game for {room_id}: "
                    f"active={len(active_players)}, seated={len(all_players)}, "
                    f"phase={table.phase.value}"
                )
                return False

            logger.info(f"[BOT_GAME_LOOP] Starting game for room {room_id}")

            # 게임 시작
            result = table.start_new_hand()
            if not result.get("success"):
                logger.error(f"[BOT_GAME_LOOP] Failed to start: {result.get('error')}")
                return False

            # HAND_STARTED 브로드캐스트
            await self._broadcast_hand_started(room_id, table, result)

            # 개인화된 상태 전송
            await self._broadcast_personalized_states(room_id, table)

            # 딜링 애니메이션 대기
            await asyncio.sleep(self._settings.phase_transition_delay_seconds)

            # 봇 턴 처리 시작 (락 밖에서)
            self._processing_tables.add(room_id)

        # 락 밖에서 봇 턴 처리 (다른 이벤트 처리 가능하도록)
        try:
            await self.process_bot_turns(room_id)
        finally:
            self._processing_tables.discard(room_id)

        return True

    async def process_bot_turns(self, room_id: str) -> None:
        """Process turns while current player is a bot.

        This is the main bot action loop, processing turns sequentially
        until a human player's turn or hand completion.

        Args:
            room_id: The room/table ID
        """
        MAX_ITERATIONS = 50
        MAX_RETRY_FOR_NONE_SEAT = 5
        MAX_RETRY_FOR_NO_ACTIONS = 3
        RETRY_DELAY = 0.3

        none_seat_retry_count = 0
        no_actions_retry_count = 0

        logger.info(f"[BOT_GAME_LOOP] Starting process_bot_turns for {room_id}")

        try:
            for iteration in range(MAX_ITERATIONS):
                table = game_manager.get_table(room_id)
                if not table:
                    logger.warning(f"[BOT_GAME_LOOP] Table {room_id} not found during turn processing")
                    return

                # 핸드 완료 상태 확인
                if table.phase == GamePhase.WAITING:
                    logger.info(f"[BOT_GAME_LOOP] Hand complete for {room_id}")
                    return

                # 현재 플레이어 확인 (재시도 로직 포함)
                if table.current_player_seat is None:
                    none_seat_retry_count += 1
                    if none_seat_retry_count <= MAX_RETRY_FOR_NONE_SEAT:
                        logger.info(f"[BOT_GAME_LOOP] No current player for {room_id}, retry {none_seat_retry_count}/{MAX_RETRY_FOR_NONE_SEAT}, phase={table.phase.value}")
                        await asyncio.sleep(RETRY_DELAY)
                        table._update_current_player()
                        continue
                    logger.warning(f"[BOT_GAME_LOOP] No current player for {room_id} after {MAX_RETRY_FOR_NONE_SEAT} retries, phase={table.phase.value}, state={table._state}")
                    return

                # 성공적으로 현재 플레이어 찾음 - 카운터 리셋
                none_seat_retry_count = 0

                current_player = table.players.get(table.current_player_seat)
                if not current_player:
                    logger.warning(f"[BOT_GAME_LOOP] Current player not found at seat {table.current_player_seat}")
                    return

                # 인간 플레이어면 TURN_PROMPT 전송 후 종료
                if not is_bot_player(current_player):
                    logger.info(f"[BOT_GAME_LOOP] Human player {current_player.username} turn, sending prompt")
                    await self._broadcast_turn_changed(room_id, table)
                    await self._send_turn_prompt(room_id, table)
                    return

                # 봇 생각 시간 (자연스러운 플레이)
                delay = random.triangular(1.0, 3.0, 2.0)
                if random.random() < 0.2:
                    delay += random.uniform(1.0, 2.0)
                await asyncio.sleep(delay)

                # 상태 재확인 (생각 중 상태 변화)
                table = game_manager.get_table(room_id)
                if not table or table.phase == GamePhase.WAITING:
                    return

                current_player = table.players.get(table.current_player_seat)
                if not current_player or not is_bot_player(current_player):
                    if current_player:
                        await self._broadcast_turn_changed(room_id, table)
                        await self._send_turn_prompt(room_id, table)
                    return

                # 가능한 액션 가져오기 (재시도 로직 포함)
                available = table.get_available_actions(current_player.user_id)
                actions = available.get("actions", []) if available else []
                call_amount = available.get("call_amount", 0) if available else 0

                if not actions:
                    no_actions_retry_count += 1
                    if no_actions_retry_count <= MAX_RETRY_FOR_NO_ACTIONS:
                        logger.debug(f"[BOT_GAME_LOOP] No actions for {current_player.username}, retry {no_actions_retry_count}/{MAX_RETRY_FOR_NO_ACTIONS}")
                        await asyncio.sleep(RETRY_DELAY)
                        table._update_current_player()
                        continue
                    logger.warning(f"[BOT_GAME_LOOP] No actions for {current_player.username} after {MAX_RETRY_FOR_NO_ACTIONS} retries")
                    return

                # 성공적으로 액션 찾음 - 카운터 리셋
                no_actions_retry_count = 0

                # 봇 액션 결정
                if is_livebot_player(current_player):
                    action, amount = self._decide_livebot_action(
                        user_id=current_player.user_id,
                        actions=actions,
                        call_amount=call_amount,
                        stack=current_player.stack,
                        available=available,
                        hole_cards=current_player.hole_cards or [],
                        community_cards=table.community_cards or [],
                        pot=table.pot,
                        big_blind=table.big_blind,
                        phase=table.phase.value,
                        position=table.current_player_seat,
                        num_players=table.max_players,
                        num_active=len([p for p in table.players.values() if p and p.status == "active"]),
                    )
                else:
                    # Dev bot - simple fold/call/raise logic
                    action, amount = self._decide_simple_bot_action(actions, call_amount)

                logger.info(f"[BOT_GAME_LOOP] {current_player.username} chose: {action} {amount}")

                # 액션 처리
                result = table.process_action(current_player.user_id, action, amount)

                if not result.get("success"):
                    logger.error(f"[BOT_GAME_LOOP] Action failed: {result.get('error')}")
                    if result.get("should_refresh"):
                        table._update_current_player()
                        continue
                    return

                # 핸드 완료 처리
                if result.get("hand_complete"):
                    logger.info(f"[BOT_GAME_LOOP] Hand complete after {current_player.username} action")
                    await self._broadcast_hand_result(room_id, result.get("hand_result"))
                    await self._broadcast_action(room_id, result)
                    await self._broadcast_personalized_states(room_id, table)

                    # 봇 통계 업데이트
                    await self._notify_bots_hand_complete(room_id, table, result.get("hand_result"))

                    # 다음 핸드 자동 시작
                    asyncio.create_task(self._auto_start_next_hand(room_id))
                    return

                # 액션 브로드캐스트
                await self._broadcast_action(room_id, result)

                # 페이즈 변경 처리
                if result.get("phase_changed"):
                    await self._broadcast_community_cards(room_id, table)
                    await asyncio.sleep(self._settings.phase_transition_delay_seconds)  # 페이즈 전환 애니메이션
                    table._update_current_player()

                    if table.phase == GamePhase.WAITING:
                        return

                    # 페이즈 전환 후 인간 플레이어면 TURN_PROMPT
                    current_player = table.players.get(table.current_player_seat)
                    if current_player and not is_bot_player(current_player):
                        await self._broadcast_turn_changed(room_id, table)
                        await self._send_turn_prompt(room_id, table)
                        return

                # 턴 변경 브로드캐스트
                await self._broadcast_turn_changed(room_id, table)

            logger.warning(f"[BOT_GAME_LOOP] Max iterations ({MAX_ITERATIONS}) reached for {room_id}")

        except Exception as e:
            logger.error(f"[BOT_GAME_LOOP] Exception in process_bot_turns: {e}", exc_info=True)

    async def _auto_start_next_hand(self, room_id: str) -> None:
        """Auto-start next hand after delay."""
        await asyncio.sleep(self._settings.hand_result_display_seconds + 2.0)
        await self.try_start_game(room_id)

    def _decide_livebot_action(
        self,
        user_id: str,
        actions: list[str],
        call_amount: int,
        stack: int,
        available: dict,
        hole_cards: list[str],
        community_cards: list[str],
        pot: int,
        big_blind: int,
        phase: str,
        position: int,
        num_players: int,
        num_active: int,
    ) -> tuple[str, int]:
        """Live bot decision using strategy system."""
        from app.bot.orchestrator import get_bot_orchestrator

        orchestrator = get_bot_orchestrator()
        strategy_name = orchestrator.get_bot_strategy(user_id)

        if not strategy_name:
            strategy_name = "balanced"
            logger.warning(f"[BOT_GAME_LOOP] Strategy not found for {user_id}, using balanced")

        strategy = get_strategy(strategy_name)

        context = GameContext(
            actions=actions,
            call_amount=call_amount,
            min_raise=available.get("min_raise", call_amount * 2),
            max_raise=available.get("max_raise", stack),
            stack=stack,
            current_bet=available.get("current_bet", 0),
            position=position,
            hole_cards=hole_cards,
            community_cards=community_cards,
            pot=pot,
            phase=phase,
            big_blind=big_blind,
            num_players=num_players,
            num_active=num_active,
        )

        decision = strategy.decide(context)

        logger.info(
            f"[BOT_GAME_LOOP] {user_id} strategy={strategy_name}, "
            f"decision={decision.action} {decision.amount}"
        )

        return decision.to_tuple()

    def _decide_simple_bot_action(
        self,
        actions: list[str],
        call_amount: int,
    ) -> tuple[str, int]:
        """Simple bot decision for dev bots."""
        if "check" in actions:
            return "check", 0
        if "call" in actions and random.random() < 0.7:
            return "call", call_amount
        if "fold" in actions:
            return "fold", 0
        return actions[0], 0

    # =========================================================================
    # Broadcast methods
    # =========================================================================

    async def _get_connection_manager(self):
        """Get ConnectionManager instance."""
        from app.ws.gateway import get_manager
        return await get_manager()

    async def _broadcast_to_table(self, room_id: str, message: dict) -> None:
        """Broadcast message to all table subscribers."""
        manager = await self._get_connection_manager()
        if manager:
            channel = f"table:{room_id}"
            await manager.broadcast_to_channel(channel, message)

    async def _broadcast_sit_in_events(self, room_id: str, table: PokerTable, seats: list[int]) -> None:
        """Broadcast sit-in events for activated players."""
        for seat in seats:
            player = table.players.get(seat)
            if player:
                message = MessageEnvelope.create(
                    event_type=EventType.PLAYER_SIT_IN,
                    payload={
                        "tableId": room_id,
                        "position": seat,
                        "userId": player.user_id,
                        "auto": True,
                        "reason": "bb_reached",
                    },
                )
                await self._broadcast_to_table(room_id, message.to_dict())

    async def _broadcast_hand_started(self, room_id: str, table: PokerTable, result: dict) -> None:
        """Broadcast hand started event."""
        seats_data = []
        for seat in range(table.max_players):
            player = table.players.get(seat)
            if player:
                seats_data.append({
                    "position": seat,
                    "userId": player.user_id,
                    "nickname": player.username,
                    "stack": player.stack,
                    "status": player.status,
                    "betAmount": player.current_bet,
                })
            else:
                seats_data.append(None)

        sb_seat, bb_seat = table.get_blind_seats()

        message = MessageEnvelope.create(
            event_type=EventType.HAND_STARTED,
            payload={
                "tableId": room_id,
                "handNumber": result.get("hand_number"),
                "dealer": result.get("dealer"),
                "smallBlindSeat": sb_seat,
                "bigBlindSeat": bb_seat,
                "seats": seats_data,
                "phase": "preflop",
                "pot": table.pot,
            },
        )
        await self._broadcast_to_table(room_id, message.to_dict())

    async def _broadcast_personalized_states(self, room_id: str, table: PokerTable) -> None:
        """Send personalized game state to each player."""
        manager = await self._get_connection_manager()
        if not manager:
            return

        for seat, player in table.players.items():
            if player:
                state = table.get_state_for_player(player.user_id)
                message = MessageEnvelope.create(
                    event_type=EventType.TABLE_SNAPSHOT,
                    payload={"tableId": room_id, "state": state},
                )
                await manager.send_to_user(player.user_id, message.to_dict())

    async def _broadcast_action(self, room_id: str, result: ActionResult) -> None:
        """Broadcast action result."""
        message = MessageEnvelope.create(
            event_type=EventType.TABLE_STATE_UPDATE,
            payload={
                "tableId": room_id,
                "changes": {
                    "lastAction": {
                        "type": result.get("action"),
                        "amount": result.get("amount", 0),
                        "position": result.get("seat"),
                    },
                    "pot": result.get("pot", 0),
                    "phase": result.get("phase"),
                    "players": result.get("players", []),
                    "currentBet": result.get("currentBet", 0),
                    "currentPlayer": result.get("currentPlayer"),
                },
            },
        )
        await self._broadcast_to_table(room_id, message.to_dict())

    async def _broadcast_community_cards(self, room_id: str, table: PokerTable) -> None:
        """Broadcast community cards."""
        message = MessageEnvelope.create(
            event_type=EventType.COMMUNITY_CARDS,
            payload={
                "tableId": room_id,
                "phase": table.phase.value,
                "cards": table.community_cards,
            },
        )
        await self._broadcast_to_table(room_id, message.to_dict())

    async def _broadcast_turn_changed(self, room_id: str, table: PokerTable) -> None:
        """Broadcast turn changed."""
        message = MessageEnvelope.create(
            event_type=EventType.TURN_CHANGED,
            payload={
                "tableId": room_id,
                "currentPlayer": table.current_player_seat,
                "currentBet": table.current_bet,
            },
        )
        await self._broadcast_to_table(room_id, message.to_dict())

    async def _send_turn_prompt(self, room_id: str, table: PokerTable) -> None:
        """Send turn prompt to current player."""
        manager = await self._get_connection_manager()
        if not manager:
            return

        current_player = table.players.get(table.current_player_seat)
        if not current_player:
            return

        available = table.get_available_actions(current_player.user_id)
        if not available:
            return

        message = MessageEnvelope.create(
            event_type=EventType.TURN_PROMPT,
            payload={
                "tableId": room_id,
                "seat": table.current_player_seat,
                "actions": available.get("actions", []),
                "callAmount": available.get("call_amount", 0),
                "minRaise": available.get("min_raise", 0),
                "maxRaise": available.get("max_raise", 0),
                "timeoutSeconds": self._settings.turn_timeout_seconds,
            },
        )
        await manager.send_to_user(current_player.user_id, message.to_dict())

    async def _broadcast_hand_result(self, room_id: str, hand_result: HandResult | None) -> None:
        """Broadcast hand result."""
        if not hand_result:
            return

        # 간단한 버전: PersonalizedBroadcaster 없이 직접 브로드캐스트
        message = MessageEnvelope.create(
            event_type=EventType.HAND_RESULT,
            payload={
                "tableId": room_id,
                "winners": hand_result.get("winners", []),
                "pot": hand_result.get("pot", 0),
                "showdown": hand_result.get("showdown", []),
            },
        )
        await self._broadcast_to_table(room_id, message.to_dict())

    async def _notify_bots_hand_complete(
        self,
        room_id: str,
        table: PokerTable,
        hand_result: HandResult | None,
    ) -> None:
        """Notify bot orchestrator about hand completion for statistics."""
        if not hand_result:
            return

        from app.bot.orchestrator import get_bot_orchestrator

        orchestrator = get_bot_orchestrator()

        # Build winner map for quick lookup
        winners_map: dict[str, int] = {}
        for winner in hand_result.get("winners", []):
            user_id = winner.get("userId", "")
            amount = winner.get("amount", 0)
            if user_id:
                winners_map[user_id] = winners_map.get(user_id, 0) + amount

        # Notify each bot player
        for seat, player in table.players.items():
            if not player:
                continue
            if not is_bot_player(player):
                continue

            won_amount = winners_map.get(player.user_id, 0)
            # Note: we don't track lost amount accurately here, just won
            await orchestrator.notify_hand_complete(
                room_id=room_id,
                user_id=player.user_id,
                new_stack=player.stack,
                won_amount=won_amount,
            )


def get_bot_game_loop() -> BotGameLoop:
    """Get the singleton BotGameLoop instance."""
    global _game_loop
    if _game_loop is None:
        _game_loop = BotGameLoop()
    return _game_loop
