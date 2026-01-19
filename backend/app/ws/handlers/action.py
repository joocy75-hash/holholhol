"""Action event handlers for game actions.

Simplified implementation using in-memory GameManager (poker project style).

Phase 4 Enhancement:
- Structured logging for all game actions
- Security event logging (rate limits, invalid actions)
- Performance timing for action processing

Phase 5 Enhancement:
- Safe async task management with error handling
- Resource tracking with automatic cleanup
- Memory leak prevention
"""

from __future__ import annotations

import asyncio
import random
import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from app.utils.json_utils import json_dumps, json_loads

from pydantic import ValidationError
from redis.asyncio import Redis

from app.game import game_manager, Player
from app.game.hand_evaluator import evaluate_hand_for_bot
from app.game.poker_table import PokerTable
from app.game.types import ActionResult, AvailableActions, HandResult
from app.utils.async_utils import ResourceTracker, create_safe_task, cancel_task_safe
from app.utils.redis_client import RedisService
from app.ws.connection import WebSocketConnection
from app.ws.events import EventType
from app.ws.handlers.base import BaseHandler
from app.ws.messages import MessageEnvelope
from app.ws.schemas import ActionRequestPayload
from app.logging_config import get_logger
from app.services.fraud_event_publisher import FraudEventPublisher, get_fraud_publisher
from app.services.hand_history import HandHistoryService
from app.services.player_session_tracker import get_session_tracker
from app.utils.db import get_db_session

if TYPE_CHECKING:
    from app.ws.manager import ConnectionManager

logger = get_logger(__name__)

# Constants for resource management
LOCK_MAX_AGE_SECONDS = 3600  # 1 hour
CLEANUP_INTERVAL_SECONDS = 300  # 5 minutes
TURN_TIMEOUT_MAX_AGE_SECONDS = 120  # 2 minutes


def is_bot_player(player) -> bool:
    """Check if player is a bot.

    user_id 접두사를 우선 확인 (bot_ 또는 test_player_로 시작하면 봇).
    is_bot 필드가 명시적으로 True인 경우도 봇으로 처리.
    """
    if player is None:
        return False
    # 우선 user_id 접두사 확인 (가장 신뢰할 수 있는 방법)
    user_id = getattr(player, 'user_id', str(player))
    if user_id.startswith("bot_") or user_id.startswith("test_player_"):
        return True
    # 폴백: is_bot 필드 확인
    if hasattr(player, 'is_bot') and player.is_bot:
        return True
    return False


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
    
    Resource Management:
    - Uses ResourceTracker for automatic cleanup of locks and timeout tasks
    - Prevents memory leaks from orphaned resources
    """

    def __init__(
        self,
        manager: "ConnectionManager",
        redis: Redis | None = None,
    ):
        super().__init__(manager)
        self.redis = redis
        self.redis_service = RedisService(redis) if redis else None
        # FraudEventPublisher for fraud detection events
        self._fraud_publisher = FraudEventPublisher(redis)
        
        # Resource tracking with automatic cleanup (prevents memory leaks)
        self._lock_tracker: ResourceTracker[asyncio.Lock] = ResourceTracker(
            max_age_seconds=LOCK_MAX_AGE_SECONDS,
            cleanup_interval_seconds=CLEANUP_INTERVAL_SECONDS,
        )
        
        # 테이블별 타임아웃 태스크 관리 (with tracking)
        self._timeout_tasks: dict[str, asyncio.Task] = {}
        
        # 테이블별 턴 시작 시간 추적 (응답 시간 측정용)
        self._turn_start_times: dict[str, datetime] = {}
        
        # Cleanup task reference
        self._cleanup_task: asyncio.Task | None = None
        
        # Load settings
        from app.config import get_settings
        self._settings = get_settings()
        
        # Start auto-cleanup for resources
        self._start_resource_cleanup()

    def _start_resource_cleanup(self) -> None:
        """Start background cleanup for resources."""
        def get_active_tables() -> set[str]:
            """Get set of currently active table IDs."""
            return set(game_manager.list_tables())
        
        # Start lock tracker auto-cleanup
        self._lock_tracker.start_auto_cleanup(get_active_keys=get_active_tables)
        
        # Start turn start times cleanup
        async def cleanup_turn_times():
            while True:
                await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
                await self._cleanup_stale_turn_times()
        
        self._cleanup_task = create_safe_task(
            cleanup_turn_times(),
            name="turn_times_cleanup",
        )

    async def _cleanup_stale_turn_times(self) -> None:
        """Clean up stale turn start times."""
        cutoff = datetime.utcnow() - timedelta(seconds=TURN_TIMEOUT_MAX_AGE_SECONDS)
        stale_keys = [
            k for k, v in self._turn_start_times.items()
            if v < cutoff
        ]
        for key in stale_keys:
            del self._turn_start_times[key]
        
        if stale_keys:
            logger.debug(f"Cleaned up {len(stale_keys)} stale turn start times")

    def _get_table_lock(self, room_id: str) -> asyncio.Lock:
        """Get or create lock for a table (with automatic cleanup)."""
        return self._lock_tracker.get_or_create(room_id, asyncio.Lock)

    @property
    def handled_events(self) -> tuple[EventType, ...]:
        return (EventType.ACTION_REQUEST, EventType.START_GAME, EventType.REVEAL_CARDS)

    async def handle(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope | None:
        if event.type == EventType.ACTION_REQUEST:
            return await self._handle_action(conn, event)
        elif event.type == EventType.START_GAME:
            return await self._handle_start_game(conn, event)
        elif event.type == EventType.REBUY:
            return await self._handle_rebuy(conn, event)
        elif event.type == EventType.REVEAL_CARDS:
            return await self._handle_reveal_cards(conn, event)
        return None

    async def _handle_action(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope:
        """Handle ACTION_REQUEST event."""
        start_time = time.time()

        # Validate payload with Pydantic
        try:
            validated = ActionRequestPayload(**event.payload)
        except ValidationError as e:
            error_details = e.errors()[0] if e.errors() else {}
            error_msg = error_details.get("msg", "잘못된 요청 형식입니다")
            logger.warning(
                "action_validation_failed",
                user_id=conn.user_id,
                table_id=event.payload.get("tableId", ""),
                error=error_msg,
                trace_id=event.trace_id,
            )
            return self._create_error_result(
                event.payload.get("tableId", ""),
                "INVALID_PAYLOAD",
                f"요청 검증 실패: {error_msg}",
                event.request_id,
                event.trace_id
            )

        room_id = validated.tableId
        action_type = validated.actionType
        amount = validated.amount
        request_id = event.request_id

        # Structured logging for action request
        logger.info(
            "action_received",
            user_id=conn.user_id,
            table_id=room_id,
            action=action_type,
            amount=amount,
            request_id=request_id,
            trace_id=event.trace_id,
        )

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
                        cached_payload = json_loads(cached)
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
            
            # Structured logging for action result
            processing_time = (time.time() - start_time) * 1000  # ms
            logger.info(
                "action_processed",
                user_id=conn.user_id,
                table_id=room_id,
                action=action_type,
                amount=amount,
                success=result.get("success", False),
                pot=result.get("pot", 0),
                phase=result.get("phase"),
                hand_complete=result.get("hand_complete", False),
                processing_time_ms=round(processing_time, 2),
                trace_id=event.trace_id,
            )

            if not result.get("success"):
                return self._create_error_result(
                    room_id, "INVALID_ACTION", result.get("error", "액션 처리 실패"),
                    request_id, event.trace_id,
                    should_refresh=result.get("should_refresh", False)
                )

            # 5.5. Publish fraud detection event (player action)
            # 봇이 아닌 인간 플레이어의 액션만 발행
            player = table.players.get(player_seat)
            is_bot = is_bot_player(player) if player else False
            await self._publish_player_action_event(
                user_id=conn.user_id,
                room_id=room_id,
                action_type=action_type,
                amount=result.get("amount", amount),
                is_bot=is_bot,
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
                    room_id, conn.user_id, request_id, json_dumps(action_result)
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
                create_safe_task(
                    self._auto_start_next_hand(room_id, table),
                    name=f"auto_start_{room_id}",
                )
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
        """Handle START_GAME event.
        
        동시에 여러 START_GAME 요청이 들어올 때 첫 번째만 처리하고 나머지는 거부합니다.
        레이스 컨디션 방지를 위해 락 내부에서 phase 체크를 수행합니다.
        """
        payload = event.payload
        room_id = payload.get("tableId")

        logger.info(f"[GAME] START_GAME request from {conn.user_id} for room {room_id}")

        # Lock per table to prevent concurrent starts (레이스 컨디션 방지)
        table_lock = self._get_table_lock(room_id)
        async with table_lock:
            table = game_manager.get_table(room_id)
            if not table:
                logger.warning(f"[GAME] START_GAME rejected: table {room_id} not found")
                return self._create_error_result(
                    room_id, "TABLE_NOT_FOUND", "테이블을 찾을 수 없습니다",
                    event.request_id, event.trace_id
                )

            # 락 내부에서 phase 체크 - 이미 게임이 진행 중인지 확인
            from app.game.poker_table import GamePhase
            if table.phase != GamePhase.WAITING:
                logger.warning(
                    f"[GAME] START_GAME rejected: game already in progress "
                    f"(room={room_id}, phase={table.phase.value}, requester={conn.user_id})"
                )
                return self._create_error_result(
                    room_id, "GAME_ALREADY_IN_PROGRESS", 
                    f"게임이 이미 진행 중입니다 (현재 단계: {table.phase.value})",
                    event.request_id, event.trace_id
                )

            # 플레이어 수 체크
            active_players = table.get_active_players()
            if len(active_players) < 2:
                logger.warning(
                    f"[GAME] START_GAME rejected: not enough players "
                    f"(room={room_id}, players={len(active_players)}, requester={conn.user_id})"
                )
                return self._create_error_result(
                    room_id, "NOT_ENOUGH_PLAYERS", 
                    f"게임을 시작할 수 없습니다 (최소 2명 필요, 현재 {len(active_players)}명)",
                    event.request_id, event.trace_id
                )

            # 이제 게임 시작 (start_new_hand 내부에서도 phase를 즉시 변경하여 이중 보호)
            result = table.start_new_hand()
            logger.info(f"[GAME] start_new_hand result: {result}, requester={conn.user_id}")

            if not result.get("success"):
                error_msg = result.get("error", "핸드 시작 실패")
                logger.error(
                    f"[GAME] START_GAME failed: {error_msg} "
                    f"(room={room_id}, requester={conn.user_id})"
                )
                return self._create_error_result(
                    room_id, "START_FAILED", error_msg,
                    event.request_id, event.trace_id
                )

            logger.info(
                f"[GAME] Game started successfully: hand #{result.get('hand_number')} "
                f"(room={room_id}, dealer={result.get('dealer')}, requester={conn.user_id})"
            )

            # Broadcast hand started (with seats/blinds data)
            await self._broadcast_hand_started(room_id, result, table)

            # Send personalized states (with hole cards)
            await self._broadcast_personalized_states(room_id, table)

            # 카드 딜링 애니메이션 대기 (플레이어 수 × 2장 × 0.15초 + 여유)
            # 프론트엔드: 150ms 시작지연 + (카드수 × 150ms) + 400ms 완료지연 + 네트워크/렌더링 여유
            active_player_count = len([p for p in table.players.values() if p and p.status == "active"])
            dealing_delay = (active_player_count * 2 * 0.15) + 2.5  # 딜링 + 블라인드 표시(0.5s) + 딜링 시작 전(0.5s) + 여유(1.5s)
            logger.info(f"[GAME] Waiting {dealing_delay:.1f}s for dealing animation ({active_player_count} players)")
            await asyncio.sleep(dealing_delay)

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

    def _get_player_seat(self, table: PokerTable, user_id: str) -> int | None:
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
        """Create an error ACTION_RESULT message with structured logging."""
        # Structured error logging
        logger.warning(
            "action_error",
            table_id=table_id,
            error_code=error_code,
            error_message=error_message,
            recoverable=not should_refresh,
            request_id=request_id,
            trace_id=trace_id,
        )

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

    async def _process_next_turn(self, room_id: str, table: PokerTable) -> None:
        """Process next turn - with bot loop (poker style).

        Uses iteration instead of recursion to prevent stack overflow.
        Includes retry logic for phase transitions where actor may be temporarily None.
        
        Safety features:
        - MAX_ITERATIONS: Prevents infinite loops
        - Table existence check: Handles table deletion during loop
        - Hand completion check: Exits when hand is complete (phase=waiting or hand_in_progress=False)
        - Current player re-validation: Ensures bot is still the current player before action
        - Retry logic: Handles temporary None states during phase transitions
        """
        MAX_ITERATIONS = 50  # Safety limit
        MAX_RETRY_FOR_NONE_SEAT = 5  # current_player_seat가 None일 때 재시도 횟수
        RETRY_DELAY = 0.3  # 재시도 대기 시간 (초)

        none_seat_retry_count = 0
        no_actions_retry_count = 0

        try:
            for iteration in range(MAX_ITERATIONS):
                # ========================================
                # Safety Check 1: 테이블 존재 여부 확인
                # ========================================
                current_table = game_manager.get_table(room_id)
                if current_table is None:
                    logger.warning(f"[TURN] Table {room_id} no longer exists, exiting bot loop")
                    return
                
                # 테이블 참조 갱신 (삭제 후 재생성된 경우 대비)
                if current_table is not table:
                    logger.warning(f"[TURN] Table reference changed for {room_id}, updating reference")
                    table = current_table

                logger.info(f"[TURN] iter={iteration}, current_seat={table.current_player_seat}, phase={table.phase}")

                # ========================================
                # Safety Check 2: 핸드 완료 상태 체크 강화
                # ========================================
                if table.phase.value == "waiting":
                    logger.info("[TURN] Hand complete, phase is waiting")
                    return
                
                # hand_in_progress 속성이 있으면 추가 체크
                if hasattr(table, 'hand_in_progress') and not table.hand_in_progress:
                    logger.info("[TURN] Hand complete, hand_in_progress is False")
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

                # 봇 액션 처리 전 현재 플레이어 좌석 저장 (재확인용)
                expected_seat = table.current_player_seat

                # Bot auto-play with human-like thinking delay
                delay = random.triangular(
                    self._settings.bot_think_time_min,
                    self._settings.bot_think_time_max,
                    self._settings.bot_think_time_mode
                )
                if random.random() < 0.2:  # 20% 확률로 추가 시간
                    delay += random.uniform(1.0, 2.0)
                logger.debug(f"[BOT] {current_player.username} thinking for {delay:.1f}s...")
                await asyncio.sleep(delay)

                # ========================================
                # Safety Check 3: 봇 액션 처리 전 재확인
                # ========================================
                # 딜레이 후 테이블 상태가 변경되었을 수 있음
                current_table = game_manager.get_table(room_id)
                if current_table is None:
                    logger.warning(f"[BOT] Table {room_id} deleted during bot thinking, exiting")
                    return
                
                if current_table is not table:
                    logger.warning(f"[BOT] Table reference changed during bot thinking, updating")
                    table = current_table
                
                # 핸드 완료 상태 재확인
                if table.phase.value == "waiting":
                    logger.info("[BOT] Hand completed during bot thinking, exiting")
                    return
                
                if hasattr(table, 'hand_in_progress') and not table.hand_in_progress:
                    logger.info("[BOT] Hand completed during bot thinking (hand_in_progress=False), exiting")
                    return
                
                # 현재 플레이어가 변경되었는지 확인
                if table.current_player_seat != expected_seat:
                    logger.warning(
                        f"[BOT] Current player changed during thinking: "
                        f"expected={expected_seat}, actual={table.current_player_seat}, refreshing..."
                    )
                    continue
                
                # 현재 플레이어가 여전히 봇인지 확인
                current_player = table.players.get(table.current_player_seat)
                if not current_player:
                    logger.warning(f"[BOT] Player at seat {table.current_player_seat} no longer exists")
                    return
                
                if not is_bot_player(current_player):
                    logger.warning(f"[BOT] Player at seat {table.current_player_seat} is no longer a bot")
                    await self._send_turn_prompt(room_id, table)
                    return

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

                # ========================================
                # Safety Check 4: 액션 처리 후 핸드 완료 상태 체크
                # ========================================
                # Hand complete - 결과 먼저 전송
                if result.get("hand_complete"):
                    logger.info("[BOT] Hand complete after action, broadcasting results")
                    await self._broadcast_hand_result(room_id, result.get("hand_result"))
                    await self._broadcast_action(room_id, result)
                    await self._broadcast_personalized_states(room_id, table)
                    # Auto-start next hand
                    create_safe_task(
                        self._auto_start_next_hand(room_id, table),
                        name=f"auto_start_bot_{room_id}",
                    )
                    return

                # Broadcast action
                await self._broadcast_action(room_id, result)

                # Phase changed - broadcast community cards (핸드 완료 시에는 전송 안 함)
                if result.get("phase_changed"):
                    await self._broadcast_community_cards(room_id, table)
                    # 페이즈 전환 후 커뮤니티 카드 애니메이션 대기
                    # 프론트엔드 애니메이션: 칩 수집(700ms) + 대기(400ms) + 카드 공개(3장×300ms) + 마무리(300ms) ≈ 2.3초
                    await asyncio.sleep(self._settings.phase_transition_delay_seconds + 2.5)
                    table._update_current_player()

                    # 페이즈 전환 후 핸드 완료 상태 재확인
                    if table.phase.value == "waiting":
                        logger.info("[BOT] Hand completed after phase change, exiting")
                        return

                    # 페이즈 전환 후 현재 플레이어가 휴먼이면 즉시 TURN_PROMPT 전송
                    current_player = table.players.get(table.current_player_seat)
                    if current_player and not is_bot_player(current_player):
                        logger.info(f"[BOT] Phase changed, human player at seat {table.current_player_seat}, sending TURN_PROMPT")
                        await self._broadcast_turn_changed(room_id, table)
                        await self._send_turn_prompt(room_id, table)
                        return

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
        actions: list[str],
        call_amount: int,
        stack: int,
        available: AvailableActions,
        hole_cards: list[str] | None = None,
        community_cards: list[str] | None = None,
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

    async def _start_turn_timeout(self, room_id: str, table: PokerTable, position: int, turn_time: int = 15) -> None:
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

        self._timeout_tasks[room_id] = create_safe_task(
            timeout_handler(),
            name=f"turn_timeout_{room_id}",
        )
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

    async def _execute_timeout_fold(self, room_id: str, table: PokerTable, position: int) -> None:
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
                    create_safe_task(
                        self._auto_start_next_hand(room_id, table),
                        name=f"auto_start_timeout_{room_id}",
                    )
                else:
                    await self._broadcast_action(room_id, result)
                    await self._process_next_turn(room_id, table)
            else:
                # 둘 다 실패하면 로그 (일반적으로 발생하지 않아야 함)
                logger.error(f"[TIMEOUT] Failed to execute {action_type}: {result.get('error')}")

    async def _send_turn_prompt(self, room_id: str, table: PokerTable) -> None:
        """Send TURN_PROMPT to current player. UTG gets 20s, others get 15s."""
        if table.current_player_seat is None:
            return

        current_player = table.players.get(table.current_player_seat)
        if not current_player:
            return

        available = table.get_available_actions(current_player.user_id)
        logger.info(f"[TURN_PROMPT] available_actions for {current_player.user_id}: {available}")

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

        # Fraud detection: 턴 시작 시간 기록 (응답 시간 측정용)
        self._record_turn_start(room_id, current_player.user_id)

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

    async def _broadcast_action(self, room_id: str, result: ActionResult) -> None:
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

        channel = f"table:{room_id}"
        await self.manager.broadcast_to_channel(channel, message.to_dict())

    async def _broadcast_hand_result(self, room_id: str, hand_result: HandResult | None) -> None:
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

        # 환불 (Uncalled Bet) 이벤트 발송
        refund_info = hand_result.get("refund")
        if refund_info:
            refund_message = MessageEnvelope.create(
                event_type=EventType.REFUND,
                payload={
                    "tableId": room_id,
                    "seat": refund_info.get("seat"),
                    "userId": refund_info.get("userId"),
                    "amount": refund_info.get("amount"),
                },
            )
            await self.manager.broadcast_to_channel(channel, refund_message.to_dict())
            logger.info(f"[REFUND] Broadcast: seat={refund_info.get('seat')}, amount={refund_info.get('amount')}")

        # Publish fraud detection event (hand completed)
        await self._publish_hand_completed_event(room_id, hand_result)

        # 스택이 0인 플레이어에게 STACK_ZERO 이벤트 전송 (리바이 모달용)
        zero_stack_players = hand_result.get("zeroStackPlayers", [])
        if zero_stack_players:
            await self._send_stack_zero_prompts(room_id, zero_stack_players)

    async def _send_stack_zero_prompts(self, room_id: str, zero_stack_players: list[dict[str, Any]]) -> None:
        """Send STACK_ZERO event to players with zero stack (for rebuy modal)."""
        for player_info in zero_stack_players:
            user_id = player_info.get("userId")
            seat = player_info.get("seat")
            if user_id:
                message = MessageEnvelope.create(
                    event_type=EventType.STACK_ZERO,
                    payload={
                        "tableId": room_id,
                        "seat": seat,
                        "options": ["rebuy", "leave", "spectate"],
                    },
                )
                await self.manager.send_to_user(user_id, message.to_dict())
                logger.info(f"[STACK_ZERO] Sent to user {user_id} at seat {seat}")

    async def _handle_rebuy(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope | None:
        """Handle REBUY event - player rebuy request."""
        room_id = event.payload.get("tableId")
        amount = event.payload.get("amount", 0)
        user_id = conn.user_id

        if not room_id:
            logger.warning(f"[REBUY] Missing tableId from user {user_id}")
            return None

        # Get table from game manager
        table = game_manager.get_table(room_id)
        if not table:
            logger.warning(f"[REBUY] Table not found: {room_id}")
            return None

        # Find player's seat
        player_seat = None
        for seat, player in table.players.items():
            if player and player.user_id == user_id:
                player_seat = seat
                break

        if player_seat is None:
            logger.warning(f"[REBUY] Player {user_id} not found at table {room_id}")
            return None

        player = table.players.get(player_seat)
        if not player:
            return None

        # Validate rebuy amount
        min_buy_in = table.min_buy_in
        max_buy_in = table.max_buy_in

        if amount < min_buy_in or amount > max_buy_in:
            logger.warning(f"[REBUY] Invalid amount {amount} (min: {min_buy_in}, max: {max_buy_in})")
            return None

        # Update player stack
        player.stack = amount
        player.status = "active"  # sitting_out → active

        logger.info(f"[REBUY] Player {user_id} rebuyed {amount} at seat {player_seat}")

        # Broadcast table state update
        await self._broadcast_table_state(room_id, table)

        return None

    async def _broadcast_hand_started(self, room_id: str, result: dict[str, Any], table: PokerTable) -> None:
        """Broadcast hand started with seats data (including blinds)."""
        # seats 데이터 구성 (블라인드 칩 포함)
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
                    "betAmount": player.current_bet,  # 블라인드 칩
                })
            else:
                seats_data.append(None)

        # SB/BB 좌석 계산
        sb_seat, bb_seat = table.get_blind_seats()

        message = MessageEnvelope.create(
            event_type=EventType.HAND_STARTED,
            payload={
                "tableId": room_id,
                "handNumber": result.get("hand_number"),
                "dealer": result.get("dealer"),
                "smallBlindSeat": sb_seat,
                "bigBlindSeat": bb_seat,
                "seats": seats_data,  # 블라인드 칩 포함된 seats
                "phase": "preflop",
                "pot": table.pot,
            },
        )

        channel = f"table:{room_id}"
        await self.manager.broadcast_to_channel(channel, message.to_dict())

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

        channel = f"table:{room_id}"
        await self.manager.broadcast_to_channel(channel, message.to_dict())

    async def _broadcast_personalized_states(self, room_id: str, table: PokerTable) -> None:
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

    async def _auto_start_next_hand(self, room_id: str, table: PokerTable) -> None:
        """Auto-start next hand after delay."""
        # WIN 표시가 충분히 보이도록 대기
        await asyncio.sleep(self._settings.hand_result_display_seconds + 2.0)

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

            await self._broadcast_hand_started(room_id, result, table)
            await self._broadcast_personalized_states(room_id, table)

            # 카드 딜링 애니메이션 대기 (플레이어 수 × 2장 × 0.15초 + 여유)
            # 프론트엔드: 150ms 시작지연 + (카드수 × 150ms) + 400ms 완료지연 + 네트워크/렌더링 여유
            active_player_count = len([p for p in table.players.values() if p and p.status == "active"])
            dealing_delay = (active_player_count * 2 * 0.15) + 2.5  # 딜링 + 블라인드 표시(0.5s) + 딜링 시작 전(0.5s) + 여유(1.5s)
            logger.info(f"[GAME] Waiting {dealing_delay:.1f}s for dealing animation ({active_player_count} players)")
            await asyncio.sleep(dealing_delay)

            await self._process_next_turn(room_id, table)

    # ========================================
    # Resource Cleanup Methods
    # ========================================

    async def cleanup_table_resources(self, room_id: str) -> None:
        """Clean up all resources associated with a table.

        Called when a table is removed or reset.
        Prevents memory leaks by removing locks and cancelling timeout tasks.

        Args:
            room_id: The table/room identifier to clean up
        """
        # Cancel and remove timeout task
        await self._cancel_turn_timeout(room_id)

        # Remove table lock from tracker
        removed = self._lock_tracker.remove(room_id)
        if removed:
            logger.info(f"[CLEANUP] Removed lock for room {room_id}")

        # Clean up turn start times for this room
        stale_keys = [k for k in self._turn_start_times if k.startswith(f"{room_id}:")]
        for key in stale_keys:
            del self._turn_start_times[key]

        logger.info(f"[CLEANUP] Table resources cleaned up for room {room_id}")

    async def cleanup_all_resources(self) -> None:
        """Clean up all resources. Called on shutdown.

        Cancels all pending timeout tasks, clears all table locks,
        and stops background cleanup tasks.
        Should be called during graceful server shutdown.
        """
        # Stop auto-cleanup tasks
        await self._lock_tracker.stop_auto_cleanup()
        await cancel_task_safe(self._cleanup_task)
        self._cleanup_task = None

        # Cancel all timeout tasks
        for room_id in list(self._timeout_tasks.keys()):
            await self._cancel_turn_timeout(room_id)

        # Clear timeout tasks dict (should already be empty after cancellation)
        self._timeout_tasks.clear()

        # Clear turn start times
        self._turn_start_times.clear()

        logger.info(
            f"[CLEANUP] All resources cleaned up: "
            f"locks={len(self._lock_tracker)}, "
            f"timeouts={len(self._timeout_tasks)}"
        )

    async def _handle_reveal_cards(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope | None:
        """Handle REVEAL_CARDS event - 플레이어가 카드를 오픈했음을 서버에 알림."""
        room_id = event.payload.get("tableId")
        if not room_id:
            return None

        game_table = game_manager.get_table(room_id)
        if not game_table:
            return None

        # 해당 유저의 플레이어 찾기
        player = None
        player_seat = None
        for seat, p in game_table.players.items():
            if p.user_id == conn.user_id:
                player = p
                player_seat = seat
                break

        if not player:
            return None

        # 이미 카드가 오픈된 상태면 무시
        if player.is_cards_revealed:
            return None

        # 카드 오픈 상태 설정
        player.is_cards_revealed = True

        logger.info(
            "cards_revealed",
            user_id=conn.user_id,
            table_id=room_id,
            seat=player_seat,
            trace_id=event.trace_id,
        )

        # 같은 테이블의 다른 플레이어들에게 브로드캐스트
        broadcast_payload = {
            "tableId": room_id,
            "position": player_seat,
            "userId": conn.user_id,
        }
        message = MessageEnvelope.create(
            event_type=EventType.CARDS_REVEALED,
            payload=broadcast_payload,
        )
        await self.manager.broadcast_to_room(room_id, message)

        return None  # 요청자에게는 별도 응답 없음 (브로드캐스트로 처리)

    # =========================================================================
    # Fraud Detection Event Publishing
    # =========================================================================

    async def _publish_hand_completed_event(
        self,
        room_id: str,
        hand_result: HandResult,
    ) -> None:
        """Publish hand completed event for fraud detection.
        
        핸드 완료 시 fraud:hand_completed 채널로 이벤트를 발행합니다.
        칩 밀어주기 탐지에 사용됩니다.
        """
        if not self._fraud_publisher.enabled:
            return

        try:
            table = game_manager.get_table(room_id)
            if not table:
                return

            # 참가자 정보 수집
            participants = []
            showdown_data = hand_result.get("showdown", [])
            winners = hand_result.get("winners", [])
            winner_ids = {w.get("userId") for w in winners}

            for seat, player in table.players.items():
                if player is None:
                    continue
                
                # 핸드에 참여한 플레이어만 (folded 포함)
                if player.status in ("active", "folded", "all_in"):
                    # showdown 데이터에서 홀카드 찾기
                    hole_cards = None
                    for sd in showdown_data:
                        if sd.get("userId") == player.user_id:
                            hole_cards = sd.get("cards")
                            break
                    
                    # 승리 금액 계산
                    won_amount = 0
                    for w in winners:
                        if w.get("userId") == player.user_id:
                            won_amount = w.get("amount", 0)
                            break

                    participants.append({
                        "user_id": player.user_id,
                        "seat": seat,
                        "hole_cards": hole_cards or player.hole_cards,
                        "bet_amount": player.total_bet_this_hand,
                        "won_amount": won_amount,
                        "final_action": player.status,
                    })

            # 핸드 ID 생성 (room_id + hand_number)
            hand_id = f"{room_id}_{table.hand_number}"

            await self._fraud_publisher.publish_hand_completed(
                hand_id=hand_id,
                room_id=room_id,
                hand_number=table.hand_number,
                pot_size=hand_result.get("pot", 0),
                community_cards=table.community_cards or [],
                participants=participants,
            )

            # Phase 2.3: 플레이어 세션 통계 업데이트
            session_tracker = get_session_tracker()
            if session_tracker:
                for p in participants:
                    user_id = p.get("user_id", "")
                    # 봇 플레이어는 세션 통계에서 제외
                    if user_id.startswith("bot_") or user_id.startswith("test_player_"):
                        continue
                    session_tracker.update_hand_stats(
                        user_id=user_id,
                        room_id=room_id,
                        bet_amount=p.get("bet_amount", 0),
                        won_amount=p.get("won_amount", 0),
                    )

            # Phase 2.5: 핸드 히스토리 DB 저장
            try:
                async with get_db_session() as db:
                    hand_history_service = HandHistoryService(db)
                    await hand_history_service.save_hand_result({
                        "hand_id": hand_id,
                        "table_id": room_id,
                        "hand_number": table.hand_number,
                        "pot_size": hand_result.get("pot", 0),
                        "community_cards": table.community_cards or [],
                        "participants": participants,
                    })
                    logger.info(f"핸드 히스토리 저장 완료: hand_id={hand_id}")
            except Exception as db_error:
                # DB 저장 실패는 게임 진행에 영향을 주지 않음
                logger.error(f"핸드 히스토리 DB 저장 실패: {db_error}")

        except Exception as e:
            logger.error(f"Failed to publish hand_completed event: {e}")

    async def _publish_player_action_event(
        self,
        user_id: str,
        room_id: str,
        action_type: str,
        amount: int,
        is_bot: bool,
    ) -> None:
        """Publish player action event for fraud detection.

        플레이어 액션 시 fraud:player_action 채널로 이벤트를 발행합니다.
        봇 탐지에 사용됩니다.

        Phase 2.2 개선:
        - 응답 시간을 Redis SORTED SET에 저장 (7일간 보관)
        - 액션 패턴을 Redis HASH에 저장 (24시간 집계)

        봇 플레이어의 액션은 발행하지 않습니다 (Requirements 2.4).
        """
        if not self._fraud_publisher.enabled:
            return

        # 봇 플레이어 액션은 발행하지 않음
        if is_bot:
            logger.debug(f"Skipping fraud event for bot player: {user_id}")
            return

        try:
            table = game_manager.get_table(room_id)
            if not table:
                return

            # 응답 시간 계산
            turn_key = f"{room_id}:{user_id}"
            turn_start_time = self._turn_start_times.get(turn_key)

            if turn_start_time:
                response_time_ms = int((datetime.now() - turn_start_time).total_seconds() * 1000)
                turn_start_iso = turn_start_time.isoformat()
            else:
                response_time_ms = 0
                turn_start_iso = datetime.now().isoformat()

            # 핸드 ID 생성
            hand_id = f"{room_id}_{table.hand_number}"

            await self._fraud_publisher.publish_player_action(
                user_id=user_id,
                room_id=room_id,
                hand_id=hand_id,
                action_type=action_type,
                amount=amount,
                response_time_ms=response_time_ms,
                turn_start_time=turn_start_iso,
            )

            # Phase 2.2: Redis에 응답 시간 및 액션 패턴 저장
            if self.redis_service and response_time_ms > 0:
                # 응답 시간 저장 (SORTED SET)
                await self.redis_service.save_response_time(user_id, response_time_ms)
                # 액션 패턴 저장 (HASH)
                await self.redis_service.save_action_pattern(user_id, action_type)
                logger.debug(
                    f"Saved timing data to Redis: user={user_id}, "
                    f"response_time={response_time_ms}ms, action={action_type}"
                )

            # 턴 시작 시간 정리 (인메모리)
            if turn_key in self._turn_start_times:
                del self._turn_start_times[turn_key]

            # Redis 턴 시작 시간 정리
            if self.redis_service:
                await self.redis_service.delete_turn_start(room_id, user_id)

        except Exception as e:
            logger.error(f"Failed to publish player_action event: {e}")

    def _record_turn_start(self, room_id: str, user_id: str) -> None:
        """Record turn start time for response time measurement.

        인메모리와 Redis 모두에 저장하여 즉시 응답 시간 계산과
        다중 인스턴스 간 공유를 모두 지원합니다.
        """
        turn_key = f"{room_id}:{user_id}"
        self._turn_start_times[turn_key] = datetime.now()

        # Redis에도 저장 (비동기 태스크로 처리하여 블로킹 방지)
        if self.redis_service:
            create_safe_task(
                self.redis_service.record_turn_start(room_id, user_id),
                name=f"record_turn_start_{room_id}_{user_id[:8]}",
            )
