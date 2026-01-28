"""Bot Orchestrator - Main engine for live bot management.

Manages the overall bot count and lifecycle:
- Spawns new bots to meet target count
- Retires bots when reducing count
- Monitors bot sessions and restarts as needed
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.bot.session import BotSession, BotState, create_bot_session
from app.bot.room_matcher import calculate_buy_in_for_room
from app.config import get_settings
from app.game.manager import game_manager
from app.game.poker_table import Player

logger = logging.getLogger(__name__)

# Singleton instance
_orchestrator: Optional["BotOrchestrator"] = None


class BotOrchestrator:
    """Manages all live bots in the system.

    Features:
    - Target count management (via admin slider)
    - Rate-limited spawning/retiring (prevents flooding)
    - Automatic session management
    - Health monitoring
    """

    def __init__(self):
        self._sessions: dict[str, BotSession] = {}
        self._target_count: int = 0
        self._running: bool = False
        self._main_loop_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

        # Rate limiting
        self._last_spawn_time: datetime = datetime.now(timezone.utc) - timedelta(minutes=1)
        self._last_retire_time: datetime = datetime.now(timezone.utc) - timedelta(minutes=1)
        self._spawns_this_minute: int = 0
        self._retires_this_minute: int = 0

        # Settings
        self._settings = get_settings()

    @property
    def is_running(self) -> bool:
        """Check if orchestrator is running."""
        return self._running

    @property
    def active_bot_count(self) -> int:
        """Get count of currently active bots (playing or joining)."""
        return sum(1 for s in self._sessions.values() if s.is_active)

    @property
    def total_bot_count(self) -> int:
        """Get total count of bot sessions (including resting)."""
        return len(self._sessions)

    @property
    def target_count(self) -> int:
        """Get target bot count."""
        return self._target_count

    async def start(self) -> None:
        """Start the orchestrator.

        Should be called during application startup.
        """
        if self._running:
            logger.warning("[BOT_ORCH] Already running")
            return

        self._running = True

        # Load target count from settings
        self._target_count = self._settings.livebot_target_count

        # Start main loop
        self._main_loop_task = asyncio.create_task(self._main_loop())

        logger.info(
            f"[BOT_ORCH] Started with target count: {self._target_count}"
        )

    async def stop(self) -> None:
        """Stop the orchestrator and cleanup all bots.

        Should be called during application shutdown.
        """
        if not self._running:
            return

        logger.info("[BOT_ORCH] Stopping...")
        self._running = False

        # Cancel main loop
        if self._main_loop_task:
            self._main_loop_task.cancel()
            try:
                await self._main_loop_task
            except asyncio.CancelledError:
                pass

        # Retire all bots
        for session in list(self._sessions.values()):
            await self._remove_bot_from_game(session)

        self._sessions.clear()
        logger.info("[BOT_ORCH] Stopped")

    async def set_target_count(self, count: int) -> dict:
        """Set the target number of active bots.

        Called by admin API.

        Args:
            count: Target number of bots (0 to disable)

        Returns:
            Status dictionary
        """
        if count < 0:
            count = 0
        if count > 100:
            count = 100  # Reasonable upper limit

        old_count = self._target_count
        self._target_count = count

        logger.info(f"[BOT_ORCH] Target count changed: {old_count} → {count}")

        return {
            "success": True,
            "old_target": old_count,
            "new_target": count,
            "current_active": self.active_bot_count,
            "current_total": self.total_bot_count,
        }

    async def force_remove_all_bots(self) -> dict:
        """Force remove all bots immediately.

        Called by admin API for emergency cleanup.
        Removes all bots from tables regardless of game state.

        Returns:
            Status dictionary with removal count
        """
        async with self._lock:
            removed_count = len(self._sessions)
            removed_bots = []

            for session in list(self._sessions.values()):
                removed_bots.append({
                    "nickname": session.nickname,
                    "room_id": session.room_id,
                    "state": session.state.name,
                })
                await self._remove_bot_from_game(session)

            self._sessions.clear()
            self._target_count = 0  # Reset target to 0

            logger.info(f"[BOT_ORCH] Force removed {removed_count} bots")

            return {
                "success": True,
                "removed_count": removed_count,
                "removed_bots": removed_bots,
                "new_target": 0,
            }

    def get_status(self) -> dict:
        """Get orchestrator status.

        Returns:
            Status dictionary for admin UI
        """
        # Count by state
        state_counts = {state.name: 0 for state in BotState}
        for session in self._sessions.values():
            state_counts[session.state.name] += 1

        return {
            "enabled": self._settings.livebot_enabled,
            "running": self._running,
            "target_count": self._target_count,
            "active_count": self.active_bot_count,
            "total_count": self.total_bot_count,
            "state_counts": state_counts,
            "bots": [s.get_status_dict() for s in self._sessions.values()],
        }

    async def _main_loop(self) -> None:
        """Main orchestrator loop.

        Runs every few seconds to:
        - Adjust bot count towards target
        - Monitor bot sessions
        - Restart rested bots
        """
        logger.info("[BOT_ORCH] Main loop started")

        while self._running:
            try:
                await asyncio.sleep(3)  # Check every 3 seconds

                if not self._settings.livebot_enabled:
                    continue

                async with self._lock:
                    # Reset rate limiters if minute has passed
                    now = datetime.now(timezone.utc)
                    if (now - self._last_spawn_time).total_seconds() >= 60:
                        self._spawns_this_minute = 0
                        self._last_spawn_time = now
                    if (now - self._last_retire_time).total_seconds() >= 60:
                        self._retires_this_minute = 0
                        self._last_retire_time = now

                    # Adjust bot count
                    await self._adjust_bot_count()

                    # Check resting bots
                    await self._check_resting_bots()

                    # Cleanup retire-requested bots that are not in a hand
                    await self._cleanup_retired_bots()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[BOT_ORCH] Main loop error: {e}", exc_info=True)
                await asyncio.sleep(5)  # Back off on error

        logger.info("[BOT_ORCH] Main loop stopped")

    async def _adjust_bot_count(self) -> None:
        """Adjust bot count towards target.

        Rate-limited to prevent flooding.
        """
        current = self.active_bot_count
        target = self._target_count
        spawn_rate = self._settings.livebot_spawn_rate_per_minute
        retire_rate = self._settings.livebot_retire_rate_per_minute

        if current < target:
            # Need more bots
            needed = target - current
            can_spawn = min(needed, spawn_rate - self._spawns_this_minute)

            for _ in range(can_spawn):
                if await self._spawn_bot():
                    self._spawns_this_minute += 1

        elif current > target:
            # Too many bots
            excess = current - target
            can_retire = min(excess, retire_rate - self._retires_this_minute)

            for _ in range(can_retire):
                if await self._retire_one_bot():
                    self._retires_this_minute += 1

    async def _spawn_bot(self) -> bool:
        """Spawn a new bot.

        Returns:
            True if bot was successfully spawned
        """
        # Create new session
        session = create_bot_session()
        session.on_state_change = self._on_session_state_change

        # Try to start session
        if not await session.start_session():
            return False

        # Add bot to game
        success = await self._add_bot_to_game(session)
        if not success:
            return False

        # Register session
        self._sessions[session.bot_id] = session
        await session.on_joined()

        logger.info(
            f"[BOT_ORCH] Spawned bot: {session.nickname} ({session.bot_id}) "
            f"at {session.room_id} seat {session.seat}"
        )

        return True

    async def _retire_one_bot(self) -> bool:
        """Retire one bot (preferring resting bots).

        Returns:
            True if a bot was retired
        """
        # First try to retire a resting bot (immediate removal)
        for bot_id, session in list(self._sessions.items()):
            if session.state == BotState.RESTING:
                session.request_retire()
                del self._sessions[bot_id]
                logger.info(f"[BOT_ORCH] Retired resting bot {session.nickname}")
                return True

        # Then try an idle bot (immediate removal)
        for bot_id, session in list(self._sessions.items()):
            if session.state == BotState.IDLE:
                session.request_retire()
                del self._sessions[bot_id]
                logger.info(f"[BOT_ORCH] Retired idle bot {session.nickname}")
                return True

        # For playing bots, check if hand is in progress
        for session in self._sessions.values():
            if session.state == BotState.PLAYING and not session._retire_requested:
                session.request_retire()

                # Check if game is actually in progress
                if session.room_id:
                    table = game_manager.get_table(session.room_id)
                    if table:
                        from app.game.poker_table import GamePhase

                        # If no hand in progress, remove immediately
                        if table.phase == GamePhase.WAITING:
                            await self._remove_bot_from_game(session)
                            await session.leave_table()
                            del self._sessions[session.bot_id]
                            logger.info(
                                f"[BOT_ORCH] Retired waiting bot {session.nickname} "
                                f"(no hand in progress)"
                            )
                        else:
                            logger.info(
                                f"[BOT_ORCH] Bot {session.nickname} will retire "
                                f"after current hand"
                            )
                return True

        return False

    async def _check_resting_bots(self) -> None:
        """Check if any resting bots should restart."""
        for session in list(self._sessions.values()):
            if await session.check_rest_complete():
                # Bot finished resting, check if we still need it
                if self.active_bot_count < self._target_count:
                    # Restart the bot
                    if await session.start_session():
                        success = await self._add_bot_to_game(session)
                        if success:
                            await session.on_joined()
                else:
                    # We have enough bots, retire this one
                    session.request_retire()
                    del self._sessions[session.bot_id]

    async def _cleanup_retired_bots(self) -> None:
        """Cleanup bots that have retire requested and are not in a hand.

        This handles bots that were requested to retire but the game
        never started or completed.
        """
        from app.game.poker_table import GamePhase

        for bot_id, session in list(self._sessions.items()):
            if not session._retire_requested:
                continue

            # Skip if not in PLAYING state
            if session.state != BotState.PLAYING:
                continue

            # Check if hand is in progress
            if session.room_id:
                table = game_manager.get_table(session.room_id)
                if table and table.phase != GamePhase.WAITING:
                    # Hand in progress, wait for completion
                    continue

            # No hand in progress, remove immediately
            await self._remove_bot_from_game(session)
            await session.leave_table()
            del self._sessions[bot_id]
            logger.info(
                f"[BOT_ORCH] Cleaned up retired bot {session.nickname} "
                f"(no hand in progress)"
            )

    async def _add_bot_to_game(self, session: BotSession) -> bool:
        """Add a bot to the GameManager.

        Args:
            session: Bot session to add

        Returns:
            True if successfully added
        """
        if not session.room_id or session.seat is None:
            return False

        table = game_manager.get_table(session.room_id)
        if not table:
            logger.warning(f"[BOT_ORCH] Table not found: {session.room_id}")
            return False

        # Check if seat is still available
        if table.players.get(session.seat) is not None:
            logger.warning(
                f"[BOT_ORCH] Seat {session.seat} no longer available at {session.room_id}"
            )
            return False

        # Create player object
        player = Player(
            user_id=session.user_id,
            username=session.nickname,
            seat=session.seat,
            stack=session.stack,
            is_bot=True,
        )

        # Seat the bot
        success = table.seat_player(session.seat, player)
        if not success:
            logger.error(f"[BOT_ORCH] Failed to seat bot at {session.room_id}")
            return False

        # Activate immediately (no BB wait for bots)
        table.sit_in(session.seat)

        logger.debug(
            f"[BOT_ORCH] Bot {session.nickname} seated at "
            f"{session.room_id} seat {session.seat}"
        )

        # Trigger game start check
        from app.bot.game_loop import get_bot_game_loop

        game_loop = get_bot_game_loop()
        asyncio.create_task(game_loop.try_start_game(session.room_id))

        return True

    async def _remove_bot_from_game(self, session: BotSession) -> bool:
        """Remove a bot from the GameManager.

        Args:
            session: Bot session to remove

        Returns:
            True if successfully removed
        """
        if not session.room_id or session.seat is None:
            return True  # Already not in a room

        table = game_manager.get_table(session.room_id)
        if not table:
            return True  # Table doesn't exist

        # Check if bot is actually at this seat
        player = table.players.get(session.seat)
        if player and player.user_id == session.user_id:
            # Remove from table
            table.players[session.seat] = None
            logger.debug(
                f"[BOT_ORCH] Bot {session.nickname} removed from "
                f"{session.room_id} seat {session.seat}"
            )

        return True

    async def _on_session_state_change(
        self,
        session: BotSession,
        old_state: BotState,
        new_state: BotState,
    ) -> None:
        """Handle session state changes.

        Called when a bot session transitions between states.
        """
        # Handle leaving state
        if new_state == BotState.LEAVING:
            await self._remove_bot_from_game(session)

        # Handle idle state (retired)
        if new_state == BotState.IDLE and session._retire_requested:
            # Remove from sessions
            if session.bot_id in self._sessions:
                del self._sessions[session.bot_id]
                logger.info(f"[BOT_ORCH] Bot retired: {session.nickname}")

    async def notify_hand_complete(
        self,
        room_id: str,
        user_id: str,
        new_stack: int,
        won_amount: int,
    ) -> None:
        """Notify orchestrator that a hand completed for a bot.

        Called from the action handler.

        Args:
            room_id: Room where hand completed
            user_id: Bot's user ID
            new_stack: Bot's new stack
            won_amount: Amount won (negative if lost)
        """
        # Find the session
        for session in self._sessions.values():
            if session.user_id == user_id and session.room_id == room_id:
                # Update stack in session
                action = await session.on_hand_complete(new_stack, won_amount)

                if action == "leave":
                    await session.leave_table()
                elif action == "rebuy":
                    # Calculate rebuy amount
                    table = game_manager.get_table(room_id)
                    if table:
                        target_bb = random.randint(80, 120)
                        rebuy_amount = calculate_buy_in_for_room(table, target_bb)
                        await session.do_rebuy(rebuy_amount)

                        # Update in GameManager
                        player = table.players.get(session.seat)
                        if player:
                            player.stack = session.stack
                break

    def get_bot_strategy(self, user_id: str) -> Optional[str]:
        """Get the strategy name for a bot.

        Args:
            user_id: Bot's user ID

        Returns:
            Strategy name or None if not found
        """
        for session in self._sessions.values():
            if session.user_id == user_id:
                return session.strategy
        return None


def get_bot_orchestrator() -> BotOrchestrator:
    """Get or create the singleton orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = BotOrchestrator()
    return _orchestrator


async def init_bot_orchestrator() -> BotOrchestrator:
    """Initialize and start the bot orchestrator.

    Should be called during application startup.
    """
    orchestrator = get_bot_orchestrator()
    await orchestrator.start()
    return orchestrator


async def shutdown_bot_orchestrator() -> None:
    """Shutdown the bot orchestrator.

    Should be called during application shutdown.
    """
    global _orchestrator
    if _orchestrator:
        await _orchestrator.stop()
        _orchestrator = None
