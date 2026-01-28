"""Bot session state machine.

Manages the lifecycle of a single bot:
IDLE → JOINING → PLAYING → RESTING → IDLE
                    ↓
                REBUYING → PLAYING
                    ↓
                 LEAVING
"""

import asyncio
import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from typing import TYPE_CHECKING, Callable, Awaitable, Optional

from app.bot.profile import BotProfile, create_bot_profile
from app.bot.room_matcher import (
    select_room_for_bot,
    calculate_buy_in_for_room,
    should_leave_table,
)
from app.config import get_settings

if TYPE_CHECKING:
    from app.game.poker_table import PokerTable

logger = logging.getLogger(__name__)


class BotState(Enum):
    """Bot session states."""

    IDLE = auto()      # Not in any room, waiting to join
    JOINING = auto()   # In the process of joining a room
    PLAYING = auto()   # Actively playing at a table
    RESTING = auto()   # Taking a break between sessions
    REBUYING = auto()  # Getting more chips
    LEAVING = auto()   # In the process of leaving


@dataclass
class BotSession:
    """Represents a single bot's playing session.

    Manages the bot's lifecycle from creation to retirement.
    """

    # Identity
    profile: BotProfile

    # State
    state: BotState = BotState.IDLE
    room_id: Optional[str] = None
    seat: Optional[int] = None
    stack: int = 0
    initial_stack: int = 0

    # Timing
    session_start: Optional[datetime] = None
    session_end_target: Optional[datetime] = None
    rest_end_target: Optional[datetime] = None
    last_action_time: Optional[datetime] = None

    # Statistics
    hands_played: int = 0
    rebuys_count: int = 0
    total_won: int = 0
    total_lost: int = 0

    # Callbacks (set by orchestrator)
    on_state_change: Optional[Callable[["BotSession", BotState, BotState], Awaitable[None]]] = None

    # Internal
    _retire_requested: bool = field(default=False, repr=False)
    _previous_room_id: Optional[str] = field(default=None, repr=False)

    @property
    def bot_id(self) -> str:
        """Get bot's unique identifier."""
        return self.profile.bot_id

    @property
    def user_id(self) -> str:
        """Get bot's user ID (livebot_ prefix)."""
        return self.profile.user_id

    @property
    def nickname(self) -> str:
        """Get bot's display name."""
        return self.profile.nickname

    @property
    def strategy(self) -> str:
        """Get bot's strategy name."""
        return self.profile.strategy

    @property
    def is_active(self) -> bool:
        """Check if bot is currently active (playing or joining)."""
        return self.state in (BotState.JOINING, BotState.PLAYING, BotState.REBUYING)

    @property
    def can_be_retired(self) -> bool:
        """Check if bot can be safely retired."""
        return self.state in (BotState.IDLE, BotState.RESTING)

    async def _set_state(self, new_state: BotState) -> None:
        """Set new state and trigger callback."""
        old_state = self.state
        if old_state == new_state:
            return

        self.state = new_state
        logger.info(
            f"[BOT_SESSION] {self.nickname} ({self.bot_id}) "
            f"state: {old_state.name} → {new_state.name}"
        )

        if self.on_state_change:
            try:
                await self.on_state_change(self, old_state, new_state)
            except Exception as e:
                logger.error(f"[BOT_SESSION] State change callback error: {e}")

    def request_retire(self) -> None:
        """Request this bot to retire gracefully.

        The bot will finish its current hand and then leave.
        """
        self._retire_requested = True
        logger.info(f"[BOT_SESSION] Retire requested for {self.nickname}")

    async def start_session(self) -> bool:
        """Start a new playing session.

        Finds a room, joins it, and begins playing.

        Returns:
            True if successfully started
        """
        if self.state != BotState.IDLE:
            logger.warning(
                f"[BOT_SESSION] Cannot start session, current state: {self.state.name}"
            )
            return False

        if self._retire_requested:
            return False

        await self._set_state(BotState.JOINING)

        # Calculate buy-in based on profile
        settings = get_settings()
        # Bots have "infinite" funds, so we use a reasonable default
        default_stack = 10000  # 10,000 chips default

        # Find a suitable room (50% 확률로 이전 방 제외 → 방 이동)
        exclude = []
        if self._previous_room_id and random.random() < 0.5:
            exclude = [self._previous_room_id]
        result = await select_room_for_bot(default_stack, exclude_room_ids=exclude)
        if result is None:
            logger.info(f"[BOT_SESSION] {self.nickname} - No suitable room found")
            await self._set_state(BotState.IDLE)
            return False

        table, seat = result

        # Calculate buy-in
        target_bb = random.randint(80, 120)  # 80-120 BB
        buy_in = calculate_buy_in_for_room(table, target_bb)

        # Store session info
        self.room_id = table.room_id
        self.seat = seat
        self.stack = buy_in
        self.initial_stack = buy_in
        self.session_start = datetime.now(timezone.utc)
        self.session_end_target = self.session_start + self.profile.session_duration

        logger.info(
            f"[BOT_SESSION] {self.nickname} joining room {table.room_id}, "
            f"seat {seat}, buy-in {buy_in} "
            f"(session until {self.session_end_target.isoformat()})"
        )

        return True

    async def on_joined(self) -> None:
        """Called when bot has successfully joined the table."""
        await self._set_state(BotState.PLAYING)
        self.last_action_time = datetime.now(timezone.utc)

    async def on_hand_complete(
        self,
        new_stack: int,
        won_amount: int,
    ) -> str:
        """Called when a hand completes.

        Args:
            new_stack: Bot's new stack after the hand
            won_amount: Amount won (negative if lost)

        Returns:
            Action to take: "continue", "rebuy", or "leave"
        """
        self.hands_played += 1
        self.stack = new_stack
        self.last_action_time = datetime.now(timezone.utc)

        if won_amount > 0:
            self.total_won += won_amount
        else:
            self.total_lost += abs(won_amount)

        # Check if retire was requested
        if self._retire_requested:
            return "leave"

        # Check session timeout
        now = datetime.now(timezone.utc)
        if self.session_end_target and now >= self.session_end_target:
            logger.info(f"[BOT_SESSION] {self.nickname} session timeout")
            return "leave"

        # Check if should leave (big win, no humans, etc.)
        if self.room_id:
            from app.game.manager import game_manager
            table = game_manager.get_table(self.room_id)
            if table:
                should_go, reason = should_leave_table(
                    table,
                    self.user_id,
                    self.stack,
                    self.initial_stack,
                    big_win_threshold=2.0,
                )
                if should_go:
                    # For big wins, apply leave probability
                    if reason == "big_win":
                        if random.random() < self.profile.leave_on_win_tendency:
                            logger.info(f"[BOT_SESSION] {self.nickname} leaving after big win")
                            return "leave"
                    else:
                        return "leave"

        # Check if need rebuy
        if self.room_id:
            from app.game.manager import game_manager
            table = game_manager.get_table(self.room_id)
            if table:
                settings = get_settings()
                bb = table.big_blind
                bb_count = self.stack / bb if bb > 0 else 0

                if bb_count < settings.livebot_rebuy_threshold_bb:
                    # Check if bot wants to rebuy
                    if random.random() < self.profile.rebuy_tendency:
                        return "rebuy"
                    else:
                        return "leave"

        return "continue"

    async def do_rebuy(self, amount: int) -> None:
        """Perform a rebuy.

        Args:
            amount: Amount to add to stack
        """
        await self._set_state(BotState.REBUYING)
        self.stack += amount
        self.rebuys_count += 1
        logger.info(
            f"[BOT_SESSION] {self.nickname} rebuy +{amount}, "
            f"new stack: {self.stack}, rebuys: {self.rebuys_count}"
        )
        await self._set_state(BotState.PLAYING)

    async def leave_table(self) -> None:
        """Leave the current table and start resting."""
        await self._set_state(BotState.LEAVING)

        # Clear table info
        old_room = self.room_id
        self._previous_room_id = old_room
        self.room_id = None
        self.seat = None

        # Calculate rest time
        now = datetime.now(timezone.utc)
        self.rest_end_target = now + self.profile.rest_duration

        # If retire requested, go to idle
        if self._retire_requested:
            await self._set_state(BotState.IDLE)
            logger.info(
                f"[BOT_SESSION] {self.nickname} retired from room {old_room}"
            )
        else:
            await self._set_state(BotState.RESTING)
            logger.info(
                f"[BOT_SESSION] {self.nickname} left room {old_room}, "
                f"resting until {self.rest_end_target.isoformat()}"
            )

    async def check_rest_complete(self) -> bool:
        """Check if rest period is complete.

        Returns:
            True if rest is done and bot should play again
        """
        if self.state != BotState.RESTING:
            return False

        if self._retire_requested:
            await self._set_state(BotState.IDLE)
            return False

        now = datetime.now(timezone.utc)
        if self.rest_end_target and now >= self.rest_end_target:
            await self._set_state(BotState.IDLE)
            return True

        return False

    def get_status_dict(self) -> dict:
        """Get bot status as dictionary."""
        return {
            "bot_id": self.bot_id,
            "nickname": self.nickname,
            "strategy": self.strategy,
            "state": self.state.name,
            "room_id": self.room_id,
            "seat": self.seat,
            "stack": self.stack,
            "hands_played": self.hands_played,
            "rebuys_count": self.rebuys_count,
            "total_won": self.total_won,
            "total_lost": self.total_lost,
            "session_start": self.session_start.isoformat() if self.session_start else None,
            "retire_requested": self._retire_requested,
        }


def create_bot_session() -> BotSession:
    """Create a new bot session with a generated profile.

    Returns:
        New BotSession instance
    """
    bot_id = uuid.uuid4().hex[:12]
    profile = create_bot_profile(bot_id)
    return BotSession(profile=profile)
