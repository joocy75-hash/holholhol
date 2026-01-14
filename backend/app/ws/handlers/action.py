"""Action event handlers for game actions.

Simplified implementation using in-memory GameManager (poker project style).
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from redis.asyncio import Redis

from app.game import game_manager, Player
from app.game.hand_evaluator import evaluate_hand_for_bot
from app.utils.redis_client import RedisService
from app.ws.connection import WebSocketConnection
from app.ws.events import EventType
from app.ws.handlers.base import BaseHandler
from app.ws.messages import MessageEnvelope

if TYPE_CHECKING:
    from app.ws.manager import ConnectionManager

logger = logging.getLogger(__name__)


def is_bot_player(player) -> bool:
    """Check if player is a bot.

    Uses player.is_bot field if available, otherwise falls back to user_id prefix check.
    """
    if player is None:
        return False
    # 우선 is_bot 필드 확인 (Player 객체)
    if hasattr(player, 'is_bot'):
        return player.is_bot
    # 폴백: user_id 접두사 확인
    user_id = getattr(player, 'user_id', str(player))
    return user_id.startswith("bot_") or user_id.startswith("test_player_")


class ActionHandler(BaseHandler):
    """Handles game action requests using in-memory game state.

    Events:
    - ACTION_REQUEST: Player action (fold, check, call, bet, raise, all-in)
    - START_GAME: Start a new hand

    Broadcasts:
    - ACTION_RESULT: Result of action
    - TABLE_STATE_UPDATE: State changes after action
    - TURN_PROMPT: Next player's turn
    - HAND_RESULT: Hand completion
    - COMMUNITY_CARDS: New community cards
    """

    def __init__(
        self,
        manager: "ConnectionManager",
        redis: Redis | None = None,
    ):
        super().__init__(manager)
        self.redis = redis
        self.redis_service = RedisService(redis) if redis else None
        # 테이블별 Lock - 동시 액션 처리 방지
        self._table_locks: dict[str, asyncio.Lock] = {}
        # 테이블별 타임아웃 태스크 관리
        self._timeout_tasks: dict[str, asyncio.Task] = {}

    def _get_table_lock(self, room_id: str) -> asyncio.Lock:
        """Get or create lock for a table."""
        if room_id not in self._table_locks:
            self._table_locks[room_id] = asyncio.Lock()
        return self._table_locks[room_id]

    @property
    def handled_events(self) -> tuple[EventType, ...]:
        return (EventType.ACTION_REQUEST, EventType.START_GAME)

    async def handle(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope | None:
        if event.type == EventType.ACTION_REQUEST:
            return await self._handle_action(conn, event)
        elif event.type == EventType.START_GAME:
            return await self._handle_start_game(conn, event)
        return None

    async def _handle_action(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope:
        """Handle ACTION_REQUEST event."""
        payload = event.payload
        room_id = payload.get("tableId")
        action_type = payload.get("actionType", "").lower()
        amount = payload.get("amount", 0)
        request_id = event.request_id

        logger.info(f"[ACTION] user={conn.user_id}, action={action_type}, amount={amount}, room={room_id}")

        # Lock per table to prevent concurrent action processing
        table_lock = self._get_table_lock(room_id)
        async with table_lock:
            # 1. Idempotency check (optional)
            if request_id and self.redis_service:
                is_new = await self.redis_service.check_and_set_idempotency(
                    table_id=room_id,
                    user_id=conn.user_id,
                    request_id=request_id,
                )
                if not is_new:
                    cached = await self.redis_service.get_idempotency_result(
                        room_id, conn.user_id, request_id
                    )
                    if cached:
                        cached_payload = json.loads(cached)
                        return MessageEnvelope.create(
                            event_type=EventType.ACTION_RESULT,
                            payload=cached_payload,
                            request_id=request_id,
                            trace_id=event.trace_id,
                        )

            # 2. Get table from memory
            table = game_manager.get_table(room_id)
            if not table:
                return self._create_error_result(
                    room_id, "TABLE_NOT_FOUND", "테이블을 찾을 수 없습니다",
                    request_id, event.trace_id
                )

            # 3. Check if game is in progress
            if table.phase.value == "waiting":
                return self._create_error_result(
                    room_id, "NO_ACTIVE_HAND", "진행 중인 핸드가 없습니다",
                    request_id, event.trace_id
                )

            # 4. Validate it's player's turn
            player_seat = self._get_player_seat(table, conn.user_id)
            if player_seat is None:
                return self._create_error_result(
                    room_id, "NOT_A_PLAYER", "테이블에 앉아있지 않습니다",
                    request_id, event.trace_id
                )

            if table.current_player_seat != player_seat:
                return self._create_error_result(
                    room_id, "NOT_YOUR_TURN", "당신의 차례가 아닙니다",
                    request_id, event.trace_id
                )

            # 4.5. Cancel timeout
            await self._cancel_turn_timeout(room_id)

            # 5. Process action
            result = table.process_action(conn.user_id, action_type, amount)
            logger.info(f"[ACTION] process_action result: {result}")

            if not result.get("success"):
                return self._create_error_result(
                    room_id, "INVALID_ACTION", result.get("error", "액션 처리 실패"),
                    request_id, event.trace_id,
                    should_refresh=result.get("should_refresh", False)
                )

            # 6. Build success response
            action_result = {
                "success": True,
                "tableId": room_id,
                "action": {
                    "type": result.get("action", action_type),
                    "amount": result.get("amount", 0),
                    "position": result.get("seat", player_seat),
                },
                "pot": result.get("pot", 0),
                "phase": result.get("phase"),
            }

            # Cache result for idempotency
            if request_id and self.redis_service:
                await self.redis_service.set_idempotency_result(
                    room_id, conn.user_id, request_id, json.dumps(action_result)
                )

            # 7. Handle hand completion first (브로드캐스트 순서 중요!)
            if result.get("hand_complete"):
                # 핸드 결과 먼저 전송 (리셋 전 상태)
                await self._broadcast_hand_result(room_id, result.get("hand_result"))
                # 그 다음 액션 브로드캐스트 (리셋 후 상태)
                await self._broadcast_action(room_id, result)
                # Send updated states to all players
                await self._broadcast_personalized_states(room_id, table)
                # Auto-start next hand after delay (락 밖에서 실행)
                asyncio.create_task(self._auto_start_next_hand(room_id, table))
            else:
                # 8. Broadcast state update
                await self._broadcast_action(room_id, result)

                # 9. Handle phase change (community cards) - 핸드 완료 시에는 전송 안 함
                if result.get("phase_changed"):
                    await self._broadcast_community_cards(room_id, table)

                # 10. Process next turn (with bot loop)
                await self._process_next_turn(room_id, table)

            return MessageEnvelope.create(
                event_type=EventType.ACTION_RESULT,
                payload=action_result,
                request_id=request_id,
                trace_id=event.trace_id,
            )

    async def _handle_start_game(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope:
        """Handle START_GAME event."""
        payload = event.payload
        room_id = payload.get("tableId")

        logger.info(f"[GAME] START_GAME from {conn.user_id} for room {room_id}")

        # Lock per table to prevent concurrent starts
        table_lock = self._get_table_lock(room_id)
        async with table_lock:
            table = game_manager.get_table(room_id)
            if not table:
                return self._create_error_result(
                    room_id, "TABLE_NOT_FOUND", "테이블을 찾을 수 없습니다",
                    event.request_id, event.trace_id
                )

            if not table.can_start_hand():
                return self._create_error_result(
                    room_id, "CANNOT_START", "게임을 시작할 수 없습니다 (최소 2명 필요)",
                    event.request_id, event.trace_id
                )

            result = table.start_new_hand()
            logger.info(f"[GAME] start_new_hand result: {result}")

            if not result.get("success"):
                return self._create_error_result(
                    room_id, "START_FAILED", result.get("error", "핸드 시작 실패"),
                    event.request_id, event.trace_id
                )

            # Broadcast hand started
            await self._broadcast_hand_started(room_id, result)

            # Send personalized states (with hole cards)
            await self._broadcast_personalized_states(room_id, table)

            # Start first turn (with bot loop)
            await self._process_next_turn(room_id, table)

            return MessageEnvelope.create(
                event_type=EventType.ACTION_RESULT,
                payload={
                    "success": True,
                    "tableId": room_id,
                    "handNumber": result.get("hand_number"),
                    "dealer": result.get("dealer"),
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

    def _get_player_seat(self, table, user_id: str) -> int | None:
        """Get player's seat at the table."""
        for seat, player in table.players.items():
            if player and player.user_id == user_id:
                if player.status in ("active", "all_in"):
                    return seat
        return None

    def _create_error_result(
        self,
        table_id: str,
        error_code: str,
        error_message: str,
        request_id: str | None,
        trace_id: str,
        should_refresh: bool = False,
    ) -> MessageEnvelope:
        """Create an error ACTION_RESULT message."""
        payload = {
            "success": False,
            "tableId": table_id,
            "errorCode": error_code,
            "errorMessage": error_message,
        }
        if should_refresh:
            payload["shouldRefresh"] = True
        return MessageEnvelope.create(
            event_type=EventType.ACTION_RESULT,
            payload=payload,
            request_id=request_id,
            trace_id=trace_id,
        )

    async def _process_next_turn(self, room_id: str, table) -> None:
        """Process next turn - with bot loop (poker style).

        Uses iteration instead of recursion to prevent stack overflow.
        Includes retry logic for phase transitions where actor may be temporarily None.
        """
        MAX_ITERATIONS = 50  # Safety limit
        MAX_RETRY_FOR_NONE_SEAT = 5  # current_player_seat가 None일 때 재시도 횟수
        RETRY_DELAY = 0.3  # 재시도 대기 시간 (초)

        none_seat_retry_count = 0
        no_actions_retry_count = 0

        try:
            for iteration in range(MAX_ITERATIONS):
                logger.info(f"[TURN] iter={iteration}, current_seat={table.current_player_seat}, phase={table.phase}")

                # 핸드가 완료된 상태면 종료
                if table.phase.value == "waiting":
                    logger.info("[TURN] Hand complete, phase is waiting")
                    return

                if table.current_player_seat is None:
                    none_seat_retry_count += 1
                    if none_seat_retry_count <= MAX_RETRY_FOR_NONE_SEAT:
                        logger.info(f"[TURN] No current player seat, retry {none_seat_retry_count}/{MAX_RETRY_FOR_NONE_SEAT}")
                        await asyncio.sleep(RETRY_DELAY)
                        # 테이블 상태 갱신 시도
                        table._update_current_player()
                        continue
                    else:
                        logger.warning("[TURN] No current player seat after max retries - hand may be complete")
                        return

                # 유효한 seat을 찾았으면 재시도 카운터 리셋
                none_seat_retry_count = 0

                current_player = table.players.get(table.current_player_seat)
                if not current_player:
                    logger.info(f"[TURN] No player at seat {table.current_player_seat}")
                    return

                # Check if current player is a bot
                is_bot = is_bot_player(current_player)
                logger.info(f"[TURN] Player {current_player.username} is_bot={is_bot}, user_id={current_player.user_id}")

                if not is_bot:
                    # Human player - send TURN_PROMPT and exit loop
                    logger.info(f"[TURN] Human player at seat {table.current_player_seat}, sending TURN_PROMPT")
                    await self._send_turn_prompt(room_id, table)
                    return

                # Bot auto-play with human-like thinking delay
                delay = random.triangular(2.0, 5.0, 3.0)  # 평균 3초, 2-5초 범위
                if random.random() < 0.2:  # 20% 확률로 추가 시간
                    delay += random.uniform(1.0, 2.0)
                logger.debug(f"[BOT] {current_player.username} thinking for {delay:.1f}s...")
                await asyncio.sleep(delay)

                available = table.get_available_actions(current_player.user_id)
                actions = available.get("actions", [])
                call_amount = available.get("call_amount", 0)

                logger.info(f"[BOT] {current_player.username} actions: {actions}, call={call_amount}")

                if not actions:
                    no_actions_retry_count += 1
                    if no_actions_retry_count <= 3:
                        logger.info(f"[BOT] No actions available, retry {no_actions_retry_count}/3")
                        await asyncio.sleep(RETRY_DELAY)
                        table._update_current_player()
                        continue
                    else:
                        logger.warning("[BOT] No actions available after retries")
                        return

                # 유효한 actions를 찾았으면 재시도 카운터 리셋
                no_actions_retry_count = 0

                # Bot decision logic with hand strength evaluation
                action, amount = self._decide_bot_action(
                    actions=actions,
                    call_amount=call_amount,
                    stack=current_player.stack,
                    available=available,
                    hole_cards=current_player.hole_cards or [],
                    community_cards=table.community_cards or [],
                    pot=table.pot,
                )

                logger.info(f"[BOT] {current_player.username} chose: {action} {amount}")

                # Process bot action
                result = table.process_action(current_player.user_id, action, amount)

                if not result.get("success"):
                    error_msg = result.get('error', 'Unknown error')
                    logger.error(f"[BOT] Action failed: {error_msg}")
                    # should_refresh가 있으면 상태 갱신 후 재시도
                    if result.get("should_refresh"):
                        logger.info("[BOT] Refreshing state and retrying...")
                        table._update_current_player()
                        continue
                    return

                # Hand complete - 결과 먼저 전송
                if result.get("hand_complete"):
                    await self._broadcast_hand_result(room_id, result.get("hand_result"))
                    await self._broadcast_action(room_id, result)
                    await self._broadcast_personalized_states(room_id, table)
                    # Auto-start next hand
                    asyncio.create_task(self._auto_start_next_hand(room_id, table))
                    return

                # Broadcast action
                await self._broadcast_action(room_id, result)

                # Phase changed - broadcast community cards (핸드 완료 시에는 전송 안 함)
                if result.get("phase_changed"):
                    await self._broadcast_community_cards(room_id, table)
                    # 페이즈 전환 후 커뮤니티 카드 애니메이션 대기 (1.5초)
                    await asyncio.sleep(1.5)
                    table._update_current_player()

                # Broadcast turn changed
                await self._broadcast_turn_changed(room_id, table)
                # Loop continues to handle next player

            logger.warning(f"[BOT] Max iterations ({MAX_ITERATIONS}) reached!")
        except Exception as e:
            logger.error(f"[BOT] Exception in _process_next_turn: {e}", exc_info=True)
            import traceback
            traceback.print_exc()

    def _decide_bot_action(
        self,
        actions: list,
        call_amount: int,
        stack: int,
        available: dict,
        hole_cards: list = None,
        community_cards: list = None,
        pot: int = 0,
    ) -> tuple[str, int]:
        """핸드 강도 기반 봇 결정 로직.

        실제 홀덤 플레이어처럼 행동:
        - 핸드 강도에 따라 베팅/레이즈/콜/폴드 결정
        - 팟 오즈 고려
        - 드로우 가능성 고려
        - 약간의 무작위성 추가 (예측 불가능하게)
        """
        hole_cards = hole_cards or []
        community_cards = community_cards or []

        # 핸드 강도 평가
        eval_result = evaluate_hand_for_bot(
            hole_cards=hole_cards,
            community_cards=community_cards,
            pot=pot,
            to_call=call_amount,
        )

        strength = eval_result["strength"]
        has_draw = eval_result["has_draw"]
        recommendation = eval_result["recommendation"]

        logger.info(
            f"[BOT] Hand eval: strength={strength:.2f}, "
            f"phase={eval_result['phase']}, draw={has_draw}, "
            f"rec={recommendation}, desc={eval_result['description']}"
        )

        # 무작위성 추가 (5% 확률로 예상 밖 행동)
        roll = random.random()

        # ========================================
        # 강한 핸드 (strength >= 0.70): 공격적
        # ========================================
        if strength >= 0.70:
            # 레이즈/베팅 우선
            if "raise" in actions and roll < 0.85:
                min_raise = available.get("min_raise", call_amount * 2)
                max_raise = available.get("max_raise", stack)
                # 강도에 따라 레이즈 크기 조절
                if strength >= 0.90:
                    # 매우 강함: 큰 레이즈 (50-100% pot)
                    raise_amount = min(max_raise, max(min_raise, int(pot * random.uniform(0.5, 1.0))))
                else:
                    # 강함: 중간 레이즈 (30-60% pot)
                    raise_amount = min(max_raise, max(min_raise, int(pot * random.uniform(0.3, 0.6))))
                return "raise", raise_amount

            if "bet" in actions:
                min_raise = available.get("min_raise", 0)
                max_raise = available.get("max_raise", stack)
                bet_amount = min(max_raise, max(min_raise, int(pot * random.uniform(0.4, 0.75))))
                return "bet", bet_amount

            # 레이즈/베팅 불가시 콜
            if "call" in actions:
                return "call", call_amount

            if "check" in actions:
                return "check", 0

        # ========================================
        # 중간 핸드 (0.45 <= strength < 0.70): 밸런스
        # ========================================
        elif strength >= 0.45:
            # 가끔 베팅/레이즈 (40% 확률)
            if roll < 0.40:
                if "bet" in actions:
                    min_raise = available.get("min_raise", 0)
                    max_raise = available.get("max_raise", stack)
                    bet_amount = min(max_raise, max(min_raise, int(pot * random.uniform(0.3, 0.5))))
                    return "bet", bet_amount

                if "raise" in actions and call_amount < stack * 0.15:
                    min_raise = available.get("min_raise", call_amount * 2)
                    return "raise", min_raise

            # 체크 가능하면 체크
            if "check" in actions:
                return "check", 0

            # 콜 금액이 적당하면 콜 (스택의 20% 이하)
            if "call" in actions:
                if call_amount <= stack * 0.20:
                    return "call", call_amount
                # 드로우가 있으면 좀 더 콜
                if has_draw and call_amount <= stack * 0.30:
                    return "call", call_amount
                # 아니면 폴드
                return "fold", 0

        # ========================================
        # 약한 핸드 + 드로우 (0.30 <= strength < 0.45)
        # ========================================
        elif strength >= 0.30 and has_draw:
            if "check" in actions:
                return "check", 0

            # 팟 오즈가 좋으면 콜 (콜 금액이 팟의 25% 이하)
            if "call" in actions:
                pot_odds_ok = call_amount <= pot * 0.25
                stack_ok = call_amount <= stack * 0.15
                if pot_odds_ok and stack_ok:
                    return "call", call_amount

            return "fold", 0

        # ========================================
        # 약한 핸드 (strength < 0.30): 수비적
        # ========================================
        else:
            if "check" in actions:
                # 가끔 블러프 (10% 확률, 프리플롭 제외)
                if roll < 0.10 and community_cards and "bet" in actions:
                    min_raise = available.get("min_raise", 0)
                    return "bet", min_raise
                return "check", 0

            # 매우 적은 금액만 콜 (스택의 5% 이하)
            if "call" in actions and call_amount <= stack * 0.05:
                # 그래도 30% 확률로만 콜
                if roll < 0.30:
                    return "call", call_amount

            return "fold", 0

        # ========================================
        # Fallback
        # ========================================
        if "check" in actions:
            return "check", 0
        if "fold" in actions:
            return "fold", 0
        if actions:
            return actions[0], call_amount if actions[0] == "call" else 0

        return "fold", 0

    async def _start_turn_timeout(self, room_id: str, table, position: int, turn_time: int = 15) -> None:
        """서버 측 턴 타임아웃 시작.

        지정된 시간(초) 후 자동 폴드.
        """
        # 기존 타임아웃 취소
        await self._cancel_turn_timeout(room_id)

        player = table.players.get(position)
        if not player:
            return

        # 봇은 타임아웃 처리 안 함 (봇 루프에서 별도 처리)
        if is_bot_player(player):
            return

        async def timeout_handler():
            try:
                await asyncio.sleep(turn_time)

                # 아직 이 플레이어 턴인지 확인 후 자동 폴드
                if table.current_player_seat == position:
                    await self._execute_timeout_fold(room_id, table, position)

            except asyncio.CancelledError:
                pass  # 정상적으로 취소됨 (액션 수행)

        self._timeout_tasks[room_id] = asyncio.create_task(timeout_handler())
        logger.info(f"[TIMEOUT] Started for room={room_id}, seat={position}, time={turn_time}s")

    async def _cancel_turn_timeout(self, room_id: str) -> None:
        """진행 중인 타임아웃 태스크 취소."""
        if room_id in self._timeout_tasks:
            self._timeout_tasks[room_id].cancel()
            try:
                await self._timeout_tasks[room_id]
            except asyncio.CancelledError:
                pass
            del self._timeout_tasks[room_id]
            logger.debug(f"[TIMEOUT] Cancelled for room={room_id}")

    async def _execute_timeout_fold(self, room_id: str, table, position: int) -> None:
        """타임아웃으로 인한 자동 액션 실행.

        - 체크 가능하면 자동 체크
        - 콜해야 하면 자동 폴드
        """
        table_lock = self._get_table_lock(room_id)
        async with table_lock:
            player = table.players.get(position)
            if not player or table.current_player_seat != position:
                return

            # 체크 가능한지 확인 (현재 베팅이 내 베팅과 같으면 체크 가능)
            can_check = player.current_bet >= table.current_bet

            # 체크 가능하면 자동 체크, 아니면 자동 폴드
            action_type = "check" if can_check else "fold"
            result = table.process_action(player.user_id, action_type, 0)

            if result.get("success"):
                result["timeout"] = True
                result["timed_out_position"] = position

                logger.warning(f"[TIMEOUT_{action_type.upper()}] room={room_id}, seat={position}")

                # TIMEOUT_FOLD 이벤트 브로드캐스트 (체크든 폴드든 타임아웃 이벤트 전송)
                timeout_message = MessageEnvelope.create(
                    event_type=EventType.TIMEOUT_FOLD,
                    payload={
                        "tableId": room_id,
                        "position": position,
                        "action": action_type,
                    },
                )
                channel = f"table:{room_id}"
                await self.manager.broadcast_to_channel(channel, timeout_message.to_dict())

                # 핸드 완료 여부에 따라 처리
                if result.get("hand_complete"):
                    await self._broadcast_hand_result(room_id, result.get("hand_result"))
                    await self._broadcast_action(room_id, result)
                    await self._broadcast_personalized_states(room_id, table)
                    asyncio.create_task(self._auto_start_next_hand(room_id, table))
                else:
                    await self._broadcast_action(room_id, result)
                    await self._process_next_turn(room_id, table)
            else:
                # 둘 다 실패하면 로그 (일반적으로 발생하지 않아야 함)
                logger.error(f"[TIMEOUT] Failed to execute {action_type}: {result.get('error')}")

    async def _send_turn_prompt(self, room_id: str, table) -> None:
        """Send TURN_PROMPT to current player. UTG gets 20s, others get 15s."""
        if table.current_player_seat is None:
            return

        current_player = table.players.get(table.current_player_seat)
        if not current_player:
            return

        available = table.get_available_actions(current_player.user_id)

        # Format allowed actions for frontend
        allowed = []
        for action in available.get("actions", []):
            action_dict = {"type": action}
            if action == "call":
                action_dict["amount"] = available.get("call_amount", 0)
            if action == "raise":
                action_dict["minAmount"] = available.get("min_raise", 0)
                action_dict["maxAmount"] = available.get("max_raise", 0)
            if action == "bet":
                # bet도 min_raise/max_raise 사용 (같은 값)
                action_dict["minAmount"] = available.get("min_raise", 0)
                action_dict["maxAmount"] = available.get("max_raise", 0)
            allowed.append(action_dict)

        # 타이머 설정: 프리플랍 UTG는 20초, 나머지는 15초
        from app.game.poker_table import GamePhase
        is_utg = table.phase == GamePhase.PREFLOP and getattr(table, '_is_preflop_first_turn', False)
        turn_time = 20 if is_utg else 15

        # UTG 턴이 시작되면 플래그 해제
        if is_utg:
            table._is_preflop_first_turn = False

        now = datetime.utcnow()
        deadline = now + timedelta(seconds=turn_time)
        turn_start_time = int(now.timestamp() * 1000)

        # 테이블에 턴 시작 시간 기록
        table._turn_started_at = now

        message = MessageEnvelope.create(
            event_type=EventType.TURN_PROMPT,
            payload={
                "tableId": room_id,
                "position": table.current_player_seat,
                "allowedActions": allowed,
                "deadlineAt": deadline.isoformat(),
                "turnStartTime": turn_start_time,
                "turnTime": turn_time,  # 이번 턴 시간 (초)
                "pot": table.pot,
                "currentBet": table.current_bet,
            },
        )

        channel = f"table:{room_id}"
        await self.manager.broadcast_to_channel(channel, message.to_dict())
        logger.info(f"[TURN_PROMPT] seat={table.current_player_seat}, time={turn_time}s, utg={is_utg}")

        # 서버 타임아웃 시작 (휴먼 플레이어만)
        if not is_bot_player(current_player):
            await self._start_turn_timeout(room_id, table, table.current_player_seat, turn_time)

    async def _broadcast_action(self, room_id: str, result: dict) -> None:
        """Broadcast action result to all players."""
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
                    "players": result.get("players", []),  # 실시간 플레이어 스택/베팅
                    "currentBet": result.get("currentBet", 0),  # 콜 금액
                    "currentPlayer": result.get("currentPlayer"),  # 현재 턴
                },
            },
        )

        channel = f"table:{room_id}"
        await self.manager.broadcast_to_channel(channel, message.to_dict())

    async def _broadcast_community_cards(self, room_id: str, table) -> None:
        """Broadcast community cards."""
        message = MessageEnvelope.create(
            event_type=EventType.COMMUNITY_CARDS,
            payload={
                "tableId": room_id,
                "phase": table.phase.value,
                "cards": table.community_cards,
            },
        )

        channel = f"table:{room_id}"
        await self.manager.broadcast_to_channel(channel, message.to_dict())

    async def _broadcast_hand_result(self, room_id: str, hand_result: dict | None) -> None:
        """Broadcast hand result."""
        if not hand_result:
            return

        message = MessageEnvelope.create(
            event_type=EventType.HAND_RESULT,
            payload={
                "tableId": room_id,
                "winners": hand_result.get("winners", []),
                "pot": hand_result.get("pot", 0),
                "showdown": hand_result.get("showdown", []),
            },
        )

        channel = f"table:{room_id}"
        await self.manager.broadcast_to_channel(channel, message.to_dict())

        # 탈락한 플레이어가 있으면 PLAYER_ELIMINATED 이벤트 전송
        eliminated_players = hand_result.get("eliminatedPlayers", [])
        if eliminated_players:
            await self._broadcast_player_eliminated(room_id, eliminated_players)

    async def _broadcast_player_eliminated(self, room_id: str, eliminated_players: list) -> None:
        """Broadcast player eliminated event."""
        message = MessageEnvelope.create(
            event_type=EventType.PLAYER_ELIMINATED,
            payload={
                "tableId": room_id,
                "eliminatedPlayers": eliminated_players,
            },
        )

        channel = f"table:{room_id}"
        await self.manager.broadcast_to_channel(channel, message.to_dict())
        logger.info(f"[ELIMINATED] {len(eliminated_players)} player(s) eliminated: {[p['nickname'] for p in eliminated_players]}")

    async def _broadcast_hand_started(self, room_id: str, result: dict) -> None:
        """Broadcast hand started."""
        message = MessageEnvelope.create(
            event_type=EventType.HAND_STARTED,
            payload={
                "tableId": room_id,
                "handNumber": result.get("hand_number"),
                "dealer": result.get("dealer"),
            },
        )

        channel = f"table:{room_id}"
        await self.manager.broadcast_to_channel(channel, message.to_dict())

    async def _broadcast_turn_changed(self, room_id: str, table) -> None:
        """Broadcast turn changed."""
        message = MessageEnvelope.create(
            event_type=EventType.TURN_CHANGED,
            payload={
                "tableId": room_id,
                "currentPlayer": table.current_player_seat,
                "currentBet": table.current_bet,
            },
        )

        channel = f"table:{room_id}"
        await self.manager.broadcast_to_channel(channel, message.to_dict())

    async def _broadcast_personalized_states(self, room_id: str, table) -> None:
        """Send personalized game state to each player."""
        for seat, player in table.players.items():
            if player:
                state = table.get_state_for_player(player.user_id)
                message = MessageEnvelope.create(
                    event_type=EventType.TABLE_SNAPSHOT,
                    payload={
                        "tableId": room_id,
                        "state": state,
                    },
                )
                # Send to specific user
                await self.manager.send_to_user(player.user_id, message.to_dict())

    async def _auto_start_next_hand(self, room_id: str, table) -> None:
        """Auto-start next hand after delay."""
        # WIN 표시가 충분히 보이도록 5초 대기
        await asyncio.sleep(5.0)

        # Lock per table to prevent concurrent operations
        table_lock = self._get_table_lock(room_id)
        async with table_lock:
            if not table.can_start_hand():
                logger.info(f"[GAME] Cannot auto-start next hand (not enough players)")
                return

            result = table.start_new_hand()
            if not result.get("success"):
                logger.error(f"[GAME] Auto-start failed: {result.get('error')}")
                return

            logger.info(f"[GAME] Auto-started hand #{result.get('hand_number')}")

            await self._broadcast_hand_started(room_id, result)
            await self._broadcast_personalized_states(room_id, table)
            await self._process_next_turn(room_id, table)
