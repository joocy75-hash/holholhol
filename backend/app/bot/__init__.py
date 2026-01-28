"""Live Bot System for poker tables.

This module provides a live bot system that simulates realistic player behavior.
Bots join and leave tables naturally, have varying playing sessions, and use
different strategies.

Key components:
- BotOrchestrator: Manages the overall bot count and lifecycle
- BotSession: Represents a single bot's playing session
- RoomMatcher: Selects appropriate rooms for bots based on stack size
- Profile: Generates bot nicknames and behavioral parameters
- Strategy: Different playing styles (TAG, LAG, etc.)
"""

from app.bot.orchestrator import BotOrchestrator, get_bot_orchestrator
from app.bot.game_loop import BotGameLoop, get_bot_game_loop

__all__ = ["BotOrchestrator", "get_bot_orchestrator", "BotGameLoop", "get_bot_game_loop"]
