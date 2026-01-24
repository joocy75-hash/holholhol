"""
GameManager - Memory-based poker table management.

Manages all active poker tables in memory. This is a singleton that
provides thread-safe access to game tables.

Memory cleanup features:
- 빈 테이블 자동 정리 (30분 후)
- 완료된 핸드 데이터 정리 (최근 10핸드만 유지)
- 메모리 사용량 모니터링 로그
"""

from typing import Awaitable, Callable, Dict, List, Optional
import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone

from app.game.poker_table import PokerTable, GamePhase
from app.config import get_settings

logger = logging.getLogger(__name__)

# 메모리 정리 설정
EMPTY_TABLE_CLEANUP_MINUTES = 30  # 빈 테이블 정리 기준 시간 (분)
CLEANUP_CHECK_INTERVAL_SECONDS = 60  # 정리 체크 주기 (초)
MAX_HAND_HISTORY_PER_TABLE = 10  # 테이블당 최대 핸드 히스토리 개수
MEMORY_WARNING_THRESHOLD_MB = 500  # 메모리 경고 임계값 (MB)


class GameManager:
    """Manages all active poker tables in memory.

    메모리 정리 기능:
    - 빈 테이블 자동 정리 (30분 후)
    - 완료된 핸드 데이터 정리
    - 메모리 사용량 모니터링
    """

    def __init__(self):
        self._tables: Dict[str, PokerTable] = {}
        self._lock = asyncio.Lock()
        self._cleanup_callbacks: List[Callable[[str], Awaitable[None]]] = []

        # 메모리 정리 관련
        self._table_last_activity: Dict[str, datetime] = {}  # 테이블별 마지막 활동 시간
        self._table_hand_history: Dict[str, List[Dict]] = {}  # 테이블별 핸드 히스토리
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_running = False

    def create_table_sync(
        self,
        room_id: str,
        name: str,
        small_blind: int,
        big_blind: int,
        min_buy_in: int,
        max_buy_in: int,
        max_players: int = 9,
    ) -> PokerTable:
        """Create a new table (synchronous)."""
        table = PokerTable(
            room_id=room_id,
            name=name,
            small_blind=small_blind,
            big_blind=big_blind,
            min_buy_in=min_buy_in,
            max_buy_in=max_buy_in,
            max_players=max_players,
        )
        self._tables[room_id] = table
        return table

    async def create_table(
        self,
        room_id: str,
        name: str,
        small_blind: int,
        big_blind: int,
        min_buy_in: int,
        max_buy_in: int,
        max_players: int = 9,
    ) -> PokerTable:
        """Create a new table (async)."""
        async with self._lock:
            return self.create_table_sync(
                room_id, name, small_blind, big_blind,
                min_buy_in, max_buy_in, max_players
            )

    def get_table(self, room_id: str) -> Optional[PokerTable]:
        """Get a table by room ID."""
        return self._tables.get(room_id)

    def get_or_create_table(
        self,
        room_id: str,
        name: str,
        small_blind: int,
        big_blind: int,
        min_buy_in: int,
        max_buy_in: int,
        max_players: int = 9,
    ) -> PokerTable:
        """Get existing table or create new one."""
        if room_id in self._tables:
            return self._tables[room_id]

        return self.create_table_sync(
            room_id, name, small_blind, big_blind,
            min_buy_in, max_buy_in, max_players
        )

    def register_cleanup_callback(
        self,
        callback: Callable[[str], Awaitable[None]]
    ) -> None:
        """Register a callback to be called when a table is removed.
        
        Args:
            callback: Async function that takes room_id as parameter.
                     Will be called before the table is deleted.
        """
        self._cleanup_callbacks.append(callback)
        logger.debug(f"Registered cleanup callback: {callback.__name__ if hasattr(callback, '__name__') else callback}")

    async def remove_table(self, room_id: str) -> bool:
        """Remove a table and trigger cleanup callbacks."""
        async with self._lock:
            if room_id not in self._tables:
                return False
            
            # Trigger cleanup callbacks
            for callback in self._cleanup_callbacks:
                try:
                    await callback(room_id)
                except Exception as e:
                    logger.error(f"Cleanup callback failed for room {room_id}: {e}")
            
            del self._tables[room_id]
            logger.info(f"[CLEANUP] Table {room_id} removed")
            return True

    def get_all_tables(self) -> List[PokerTable]:
        """Get all active tables."""
        return list(self._tables.values())

    def get_table_count(self) -> int:
        """Get number of active tables."""
        return len(self._tables)

    def has_table(self, room_id: str) -> bool:
        """Check if table exists."""
        return room_id in self._tables

    def clear_all(self) -> None:
        """Clear all tables (for testing)."""
        self._tables.clear()

    def reset_table(self, room_id: str) -> Optional[PokerTable]:
        """Reset a table - remove all players/bots and reset game state."""
        table = self._tables.get(room_id)
        if not table:
            return None

        # 모든 플레이어 제거
        for seat in range(table.max_players):
            table.players[seat] = None

        # 게임 상태 초기화
        table.dealer_seat = -1
        table.hand_number = 0
        table.phase = table.phase.__class__.WAITING
        table.pot = 0
        table.community_cards = []
        table.current_player_seat = None
        table.current_bet = 0
        table._state = None
        table._seat_to_index = {}
        table._index_to_seat = {}
        table._hand_actions = []
        table._hand_starting_stacks = {}
        table._hand_start_time = None

        return table

    def remove_bots_from_table(self, room_id: str) -> int:
        """Remove all bots from a table. Returns count of removed bots."""
        table = self._tables.get(room_id)
        if not table:
            return 0

        removed = 0
        for seat in range(table.max_players):
            player = table.players.get(seat)
            if player and player.is_bot:
                table.players[seat] = None
                removed += 1

        return removed

    def force_phase_change(
        self,
        room_id: str,
        target_phase: str,
        community_cards: list[str] | None = None,
    ) -> dict:
        """Force phase change for a table.

        ⚠️ DEV API: 프로덕션에서 비활성화됨

        Args:
            room_id: Table ID
            target_phase: Target phase (preflop, flop, turn, river, showdown)
            community_cards: Optional community cards to set

        Returns:
            Result dict with success status and data
        """
        # 프로덕션 환경에서 차단
        if get_settings().app_env == "production":
            logger.warning(f"[DEV_API] force_phase_change blocked in production (room: {room_id})")
            return {"success": False, "error": "Not available in production environment"}

        from app.game.poker_table import GamePhase
        import random

        table = self._tables.get(room_id)
        if not table:
            return {"success": False, "error": "Table not found"}
        
        # Map string to GamePhase enum
        phase_map = {
            "waiting": GamePhase.WAITING,
            "preflop": GamePhase.PREFLOP,
            "flop": GamePhase.FLOP,
            "turn": GamePhase.TURN,
            "river": GamePhase.RIVER,
            "showdown": GamePhase.SHOWDOWN,
        }
        
        if target_phase not in phase_map:
            return {"success": False, "error": f"Invalid phase: {target_phase}"}
        
        new_phase = phase_map[target_phase]
        old_phase = table.phase
        
        # Generate community cards if needed
        if community_cards:
            table.community_cards = community_cards
        else:
            # Auto-generate cards based on phase
            existing_cards = set(table.community_cards)
            
            # Add player hole cards to used cards
            for seat, player in table.players.items():
                if player and player.hole_cards:
                    existing_cards.update(player.hole_cards)
            
            all_cards = [
                f"{r}{s}" for r in "23456789TJQKA" for s in "hdcs"
            ]
            available_cards = [c for c in all_cards if c not in existing_cards]
            
            if target_phase == "flop" and len(table.community_cards) < 3:
                needed = 3 - len(table.community_cards)
                new_cards = random.sample(available_cards, needed)
                table.community_cards.extend(new_cards)
            elif target_phase == "turn" and len(table.community_cards) < 4:
                needed = 4 - len(table.community_cards)
                new_cards = random.sample(available_cards, needed)
                table.community_cards.extend(new_cards)
            elif target_phase == "river" and len(table.community_cards) < 5:
                needed = 5 - len(table.community_cards)
                new_cards = random.sample(available_cards, needed)
                table.community_cards.extend(new_cards)
            elif target_phase == "showdown" and len(table.community_cards) < 5:
                needed = 5 - len(table.community_cards)
                new_cards = random.sample(available_cards, needed)
                table.community_cards.extend(new_cards)
        
        # Update phase
        table.phase = new_phase
        
        # Reset current bets for new betting round (except preflop)
        if target_phase in ("flop", "turn", "river"):
            for seat, player in table.players.items():
                if player:
                    player.current_bet = 0
            table.current_bet = 0
        
        return {
            "success": True,
            "old_phase": old_phase.value,
            "new_phase": new_phase.value,
            "community_cards": table.community_cards,
        }

    def inject_cards(
        self,
        room_id: str,
        hole_cards: dict[int, list[str]] | None = None,
        community_cards: list[str] | None = None,
    ) -> dict:
        """Inject specific cards for testing.

        ⚠️ DEV API: 프로덕션에서 비활성화됨

        Args:
            room_id: Table ID
            hole_cards: Dict of seat -> [card1, card2]
            community_cards: List of community cards

        Returns:
            Result dict with success status
        """
        # 프로덕션 환경에서 차단
        if get_settings().app_env == "production":
            logger.warning(f"[DEV_API] inject_cards blocked in production (room: {room_id})")
            return {"success": False, "error": "Not available in production environment"}

        table = self._tables.get(room_id)
        if not table:
            return {"success": False, "error": "Table not found"}
        
        # Store injected cards for next hand
        if not hasattr(table, '_injected_cards'):
            table._injected_cards = {"hole_cards": {}, "community_cards": []}
        
        if hole_cards:
            table._injected_cards["hole_cards"] = hole_cards
        
        if community_cards:
            table._injected_cards["community_cards"] = community_cards
        
        # If game is in progress, apply immediately to players
        if table.phase != table.phase.__class__.WAITING and hole_cards:
            for seat, cards in hole_cards.items():
                player = table.players.get(seat)
                if player:
                    player.hole_cards = cards
        
        if table.phase != table.phase.__class__.WAITING and community_cards:
            table.community_cards = community_cards
        
        return {
            "success": True,
            "injected": table._injected_cards,
            "applied_immediately": table.phase != table.phase.__class__.WAITING,
        }

    def force_pot(
        self,
        room_id: str,
        main_pot: int,
        side_pots: list[dict] | None = None,
    ) -> dict:
        """Force pot amount for testing.

        ⚠️ DEV API: 프로덕션에서 비활성화됨

        Args:
            room_id: Table ID
            main_pot: Main pot amount
            side_pots: Optional list of side pots

        Returns:
            Result dict with success status
        """
        # 프로덕션 환경에서 차단
        if get_settings().app_env == "production":
            logger.warning(f"[DEV_API] force_pot blocked in production (room: {room_id})")
            return {"success": False, "error": "Not available in production environment"}

        table = self._tables.get(room_id)
        if not table:
            return {"success": False, "error": "Table not found"}
        
        table.pot = main_pot
        
        # Store side pots if provided
        if side_pots:
            if not hasattr(table, '_side_pots'):
                table._side_pots = []
            table._side_pots = side_pots
        
        return {
            "success": True,
            "pot": table.pot,
            "side_pots": getattr(table, '_side_pots', []),
        }

    def start_hand_immediately(self, room_id: str) -> dict:
        """Start a new hand immediately.

        ⚠️ DEV API: 프로덕션에서 비활성화됨

        Args:
            room_id: Table ID

        Returns:
            Result dict with hand info
        """
        # 프로덕션 환경에서 차단
        if get_settings().app_env == "production":
            logger.warning(f"[DEV_API] start_hand_immediately blocked in production (room: {room_id})")
            return {"success": False, "error": "Not available in production environment"}

        table = self._tables.get(room_id)
        if not table:
            return {"success": False, "error": "Table not found"}
        
        # Check if we have enough players
        active_players = table.get_active_players()
        if len(active_players) < 2:
            return {"success": False, "error": "Need at least 2 players to start"}
        
        # Force waiting state if needed
        if table.phase != table.phase.__class__.WAITING:
            table.phase = table.phase.__class__.WAITING
            table._state = None
            table.current_player_seat = None
            table.current_bet = 0
            table.pot = 0
            table.community_cards = []
        
        # Start the hand
        result = table.start_new_hand()
        
        # Apply injected cards if any
        if hasattr(table, '_injected_cards') and table._injected_cards:
            injected = table._injected_cards
            
            # Apply hole cards
            if injected.get("hole_cards"):
                for seat, cards in injected["hole_cards"].items():
                    player = table.players.get(int(seat))
                    if player:
                        player.hole_cards = cards
            
            # Apply community cards (store for later phases)
            if injected.get("community_cards"):
                table._pending_community_cards = injected["community_cards"]
            
            # Clear injected cards after use
            table._injected_cards = {"hole_cards": {}, "community_cards": []}
        
        return result

    def add_bot_player(
        self,
        room_id: str,
        position: int | None = None,
        stack: int = 1000,
        strategy: str = "random",
        username: str | None = None,
    ) -> dict:
        """Add a bot player to the table.

        ⚠️ DEV API: 프로덕션에서 비활성화됨

        Args:
            room_id: Table ID
            position: Seat position (None for auto)
            stack: Initial stack
            strategy: Bot strategy (random, tight, loose)
            username: Bot username (auto-generated if None)

        Returns:
            Result dict with bot info
        """
        # 프로덕션 환경에서 차단
        if get_settings().app_env == "production":
            logger.warning(f"[DEV_API] add_bot_player blocked in production (room: {room_id})")
            return {"success": False, "error": "Not available in production environment"}

        from app.game.poker_table import Player
        import uuid

        table = self._tables.get(room_id)
        if not table:
            return {"success": False, "error": "Table not found"}
        
        # Find available seat
        if position is None:
            for seat in range(table.max_players):
                if table.players.get(seat) is None:
                    position = seat
                    break
            if position is None:
                return {"success": False, "error": "No available seats"}
        else:
            if table.players.get(position) is not None:
                return {"success": False, "error": f"Seat {position} is occupied"}
        
        # Validate stack
        if stack < table.min_buy_in:
            stack = table.min_buy_in
        if stack > table.max_buy_in:
            stack = table.max_buy_in
        
        # Create bot player
        bot_id = f"bot_{uuid.uuid4().hex[:8]}"
        bot_username = username or f"Bot_{position}"
        
        bot_player = Player(
            user_id=bot_id,
            username=bot_username,
            seat=position,
            stack=stack,
            is_bot=True,
        )
        
        # Store bot strategy
        if not hasattr(table, '_bot_strategies'):
            table._bot_strategies = {}
        table._bot_strategies[bot_id] = strategy
        
        # Seat the bot
        success = table.seat_player(position, bot_player)
        if not success:
            return {"success": False, "error": "Failed to seat bot"}

        # 봇은 즉시 참여 (sitting_out 기본값 해제)
        table.sit_in(position)

        return {
            "success": True,
            "bot_id": bot_id,
            "username": bot_username,
            "position": position,
            "stack": stack,
            "strategy": strategy,
        }

    def force_action(
        self,
        room_id: str,
        position: int,
        action: str,
        amount: int | None = None,
    ) -> dict:
        """Force a player action.
        
        Args:
            room_id: Table ID
            position: Player seat position
            action: Action to perform (fold, check, call, raise, all_in)
            amount: Amount for raise/bet
            
        Returns:
            Result dict with action result
        """
        table = self._tables.get(room_id)
        if not table:
            return {"success": False, "error": "Table not found"}
        
        player = table.players.get(position)
        if not player:
            return {"success": False, "error": f"No player at position {position}"}
        
        # Process the action
        result = table.process_action(player.user_id, action, amount or 0)
        
        return result

    def get_table_full_state(self, room_id: str) -> dict | None:
        """Get full table state for debugging.
        
        Args:
            room_id: Table ID
            
        Returns:
            Full table state dict or None
        """
        table = self._tables.get(room_id)
        if not table:
            return None
        
        players_data = []
        for seat in range(table.max_players):
            player = table.players.get(seat)
            if player:
                players_data.append({
                    "seat": seat,
                    "user_id": player.user_id,
                    "username": player.username,
                    "stack": player.stack,
                    "status": player.status,
                    "current_bet": player.current_bet,
                    "hole_cards": player.hole_cards,
                    "is_bot": player.is_bot,
                })
            else:
                players_data.append(None)
        
        return {
            "room_id": table.room_id,
            "name": table.name,
            "small_blind": table.small_blind,
            "big_blind": table.big_blind,
            "min_buy_in": table.min_buy_in,
            "max_buy_in": table.max_buy_in,
            "max_players": table.max_players,
            "phase": table.phase.value,
            "pot": table.pot,
            "community_cards": table.community_cards,
            "current_player_seat": table.current_player_seat,
            "current_bet": table.current_bet,
            "dealer_seat": table.dealer_seat,
            "hand_number": table.hand_number,
            "players": players_data,
        }

    def force_timeout(
        self,
        room_id: str,
        position: int | None = None,
    ) -> dict:
        """Force timeout for current player (triggers auto-fold).

        ⚠️ DEV API: 프로덕션에서 비활성화됨

        Args:
            room_id: Table ID
            position: Specific position to timeout (None for current turn)

        Returns:
            Result dict with action result
        """
        # 프로덕션 환경에서 차단
        if get_settings().app_env == "production":
            logger.warning(f"[DEV_API] force_timeout blocked in production (room: {room_id})")
            return {"success": False, "error": "Not available in production environment"}

        table = self._tables.get(room_id)
        if not table:
            return {"success": False, "error": "Table not found"}
        
        # Determine which position to timeout
        target_position = position if position is not None else table.current_player_seat
        
        if target_position is None:
            return {"success": False, "error": "No active turn to timeout"}
        
        player = table.players.get(target_position)
        if not player:
            return {"success": False, "error": f"No player at position {target_position}"}
        
        # Check if it's actually this player's turn
        if table.current_player_seat != target_position:
            return {
                "success": False,
                "error": f"Position {target_position} is not the current turn",
            }
        
        # Force fold action (timeout = auto-fold)
        result = table.process_action(player.user_id, "fold", 0)
        
        if result.get("success"):
            result["timeout"] = True
            result["timed_out_position"] = target_position
        
        return result

    def set_timer(
        self,
        room_id: str,
        remaining_seconds: int,
        paused: bool | None = None,
    ) -> dict:
        """Set timer value for current turn.

        ⚠️ DEV API: 프로덕션에서 비활성화됨

        Args:
            room_id: Table ID
            remaining_seconds: Remaining time in seconds
            paused: Whether to pause the timer

        Returns:
            Result dict with timer info
        """
        # 프로덕션 환경에서 차단
        if get_settings().app_env == "production":
            logger.warning(f"[DEV_API] set_timer blocked in production (room: {room_id})")
            return {"success": False, "error": "Not available in production environment"}

        from datetime import datetime, timedelta

        table = self._tables.get(room_id)
        if not table:
            return {"success": False, "error": "Table not found"}
        
        if table.current_player_seat is None:
            return {"success": False, "error": "No active turn"}
        
        # Store timer override on table
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(seconds=remaining_seconds)
        
        if not hasattr(table, '_timer_override'):
            table._timer_override = {}
        
        table._timer_override = {
            "remaining_seconds": remaining_seconds,
            "paused": paused if paused is not None else False,
            "deadline": deadline.isoformat(),
            "set_at": now.isoformat(),
            "position": table.current_player_seat,
        }
        
        return {
            "success": True,
            "position": table.current_player_seat,
            "remaining_seconds": remaining_seconds,
            "paused": table._timer_override["paused"],
            "deadline": table._timer_override["deadline"],
        }

    # =========================================================================
    # 메모리 정리 기능
    # =========================================================================

    async def start_cleanup_task(self) -> None:
        """백그라운드 정리 태스크 시작."""
        if self._cleanup_running:
            return

        self._cleanup_running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("[CLEANUP] 메모리 정리 태스크 시작")

    async def stop_cleanup_task(self) -> None:
        """백그라운드 정리 태스크 중지."""
        self._cleanup_running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        logger.info("[CLEANUP] 메모리 정리 태스크 중지")

    async def _cleanup_loop(self) -> None:
        """주기적으로 메모리 정리 수행."""
        while self._cleanup_running:
            try:
                await asyncio.sleep(CLEANUP_CHECK_INTERVAL_SECONDS)

                if not self._cleanup_running:
                    break

                # 1. 빈 테이블 정리
                await self._cleanup_empty_tables()

                # 2. 메모리 사용량 로깅
                self._log_memory_usage()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[CLEANUP] 정리 루프 에러: {e}")

    async def _cleanup_empty_tables(self) -> int:
        """빈 테이블 정리 (30분 후).

        Returns:
            정리된 테이블 수
        """
        now = datetime.now(timezone.utc)
        cleanup_threshold = now - timedelta(minutes=EMPTY_TABLE_CLEANUP_MINUTES)
        tables_to_remove: List[str] = []

        async with self._lock:
            for room_id, table in self._tables.items():
                # 플레이어 수 확인
                active_players = sum(
                    1 for p in table.players.values() if p is not None
                )

                if active_players == 0:
                    # 마지막 활동 시간 확인
                    last_activity = self._table_last_activity.get(room_id)
                    if last_activity is None:
                        # 처음 확인 시 현재 시간 기록
                        self._table_last_activity[room_id] = now
                    elif last_activity < cleanup_threshold:
                        # 30분 이상 빈 테이블
                        tables_to_remove.append(room_id)
                else:
                    # 플레이어가 있으면 활동 시간 갱신
                    self._table_last_activity[room_id] = now

        # 테이블 제거 (락 밖에서)
        removed_count = 0
        for room_id in tables_to_remove:
            success = await self.remove_table(room_id)
            if success:
                removed_count += 1
                # 관련 메타데이터 정리
                self._table_last_activity.pop(room_id, None)
                self._table_hand_history.pop(room_id, None)
                logger.info(f"[CLEANUP] 빈 테이블 자동 정리: {room_id}")

        if removed_count > 0:
            logger.info(f"[CLEANUP] {removed_count}개 빈 테이블 정리 완료")

        return removed_count

    def update_table_activity(self, room_id: str) -> None:
        """테이블 활동 시간 갱신 (착석, 액션 등에서 호출)."""
        self._table_last_activity[room_id] = datetime.now(timezone.utc)

    def save_hand_history(
        self,
        room_id: str,
        hand_data: Dict,
    ) -> None:
        """핸드 히스토리 저장 (최근 N개만 유지).

        Args:
            room_id: 테이블 ID
            hand_data: 핸드 데이터 (hand_number, actions, result 등)
        """
        if room_id not in self._table_hand_history:
            self._table_hand_history[room_id] = []

        history = self._table_hand_history[room_id]
        history.append(hand_data)

        # 최대 개수 초과 시 오래된 것 제거
        if len(history) > MAX_HAND_HISTORY_PER_TABLE:
            removed = len(history) - MAX_HAND_HISTORY_PER_TABLE
            self._table_hand_history[room_id] = history[-MAX_HAND_HISTORY_PER_TABLE:]
            logger.debug(
                f"[CLEANUP] 테이블 {room_id} 핸드 히스토리 {removed}개 정리 "
                f"(유지: {MAX_HAND_HISTORY_PER_TABLE}개)"
            )

    def get_hand_history(self, room_id: str) -> List[Dict]:
        """테이블의 핸드 히스토리 조회."""
        return self._table_hand_history.get(room_id, [])

    def cleanup_hand_data(self, table: PokerTable) -> None:
        """핸드 완료 후 테이블 내 임시 데이터 정리.

        Args:
            table: 정리할 테이블
        """
        # 핸드 액션 리스트 비우기
        if hasattr(table, '_hand_actions'):
            table._hand_actions = []

        # 핸드 시작 스택 정리
        if hasattr(table, '_hand_starting_stacks'):
            table._hand_starting_stacks = {}

        # 핸드 시작 시간 리셋
        if hasattr(table, '_hand_start_time'):
            table._hand_start_time = None

        # 주입된 카드 정리
        if hasattr(table, '_injected_cards'):
            table._injected_cards = {"hole_cards": {}, "community_cards": []}

        logger.debug(f"[CLEANUP] 테이블 {table.room_id} 핸드 데이터 정리 완료")

    def _log_memory_usage(self) -> None:
        """메모리 사용량 로깅."""
        try:
            # 프로세스 메모리 사용량 (MB)
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            memory_mb = usage.ru_maxrss / 1024 / 1024  # macOS: bytes, Linux: KB

            # 테이블 통계
            table_count = len(self._tables)
            total_players = sum(
                sum(1 for p in t.players.values() if p is not None)
                for t in self._tables.values()
            )

            log_msg = (
                f"[MEMORY] 테이블: {table_count}, "
                f"플레이어: {total_players}, "
                f"메모리: {memory_mb:.1f}MB"
            )

            if memory_mb > MEMORY_WARNING_THRESHOLD_MB:
                logger.warning(f"{log_msg} (임계값 초과!)")
            else:
                logger.info(log_msg)

        except ImportError:
            # resource 모듈 없는 경우 (Windows 등)
            table_count = len(self._tables)
            logger.info(f"[MEMORY] 테이블: {table_count}")
        except Exception as e:
            logger.debug(f"[MEMORY] 메모리 사용량 조회 실패: {e}")

    def get_memory_stats(self) -> Dict:
        """메모리 통계 조회."""
        table_count = len(self._tables)
        total_players = sum(
            sum(1 for p in t.players.values() if p is not None)
            for t in self._tables.values()
        )
        total_hands = sum(
            len(h) for h in self._table_hand_history.values()
        )

        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            memory_mb = usage.ru_maxrss / 1024 / 1024
        except (ImportError, Exception):
            memory_mb = None

        return {
            "table_count": table_count,
            "total_players": total_players,
            "total_hand_history": total_hands,
            "memory_mb": memory_mb,
            "cleanup_running": self._cleanup_running,
        }

    # =========================================================================
    # P0-4: Redis 영속성 기능
    # =========================================================================

    async def save_table_state(self, room_id: str) -> bool:
        """테이블 상태를 Redis에 저장.

        플레이어 착석/이탈, 핸드 완료 시 호출됩니다.

        Args:
            room_id: 테이블 ID

        Returns:
            저장 성공 여부
        """
        try:
            from app.game.table_persistence import get_table_persistence_service

            persistence = await get_table_persistence_service()
            if not persistence:
                return False

            table = self._tables.get(room_id)
            if not table:
                return False

            return await persistence.save_table(table)

        except Exception as e:
            logger.error(f"[PERSISTENCE] 테이블 저장 실패: {room_id}, {e}")
            return False

    async def delete_table_state(self, room_id: str) -> bool:
        """테이블 상태를 Redis에서 삭제.

        Args:
            room_id: 테이블 ID

        Returns:
            삭제 성공 여부
        """
        try:
            from app.game.table_persistence import get_table_persistence_service

            persistence = await get_table_persistence_service()
            if not persistence:
                return False

            return await persistence.delete_table(room_id)

        except Exception as e:
            logger.error(f"[PERSISTENCE] 테이블 상태 삭제 실패: {room_id}, {e}")
            return False

    async def restore_tables_from_redis(self) -> int:
        """Redis에서 테이블 상태 복원.

        서버 재시작 시 호출됩니다.

        Returns:
            복원된 테이블 수
        """
        try:
            from app.game.table_persistence import get_table_persistence_service

            persistence = await get_table_persistence_service()
            if not persistence:
                logger.warning("[PERSISTENCE] Redis 연결 없음, 복원 스킵")
                return 0

            restored = await persistence.restore_to_manager(self)
            logger.info(f"[PERSISTENCE] {restored}개 테이블 복원 완료")
            return restored

        except Exception as e:
            logger.error(f"[PERSISTENCE] 테이블 복원 실패: {e}")
            return 0

    async def save_all_tables(self) -> int:
        """모든 테이블 상태를 Redis에 저장.

        Graceful shutdown 시 호출됩니다.

        Returns:
            저장된 테이블 수
        """
        saved = 0
        for room_id in list(self._tables.keys()):
            if await self.save_table_state(room_id):
                saved += 1
        logger.info(f"[PERSISTENCE] {saved}개 테이블 저장 완료")
        return saved


# Singleton instance
game_manager = GameManager()
