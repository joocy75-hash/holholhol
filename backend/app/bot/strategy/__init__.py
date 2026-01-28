"""Bot strategy system.

Provides different playing styles for bots:
- Tight-Aggressive (TAG): Plays few hands but aggressively
- Loose-Aggressive (LAG): Plays many hands aggressively
- Tight-Passive: Plays few hands passively
- Loose-Passive: Plays many hands passively
- Balanced: Middle ground between tight and loose
"""

from app.bot.strategy.base import BaseStrategy, Decision
from app.bot.strategy.tight_aggressive import TightAggressiveStrategy
from app.bot.strategy.loose_aggressive import LooseAggressiveStrategy
from app.bot.strategy.tight_passive import TightPassiveStrategy
from app.bot.strategy.loose_passive import LoosePassiveStrategy
from app.bot.strategy.balanced import BalancedStrategy

__all__ = [
    "BaseStrategy",
    "Decision",
    "TightAggressiveStrategy",
    "LooseAggressiveStrategy",
    "TightPassiveStrategy",
    "LoosePassiveStrategy",
    "BalancedStrategy",
    "get_strategy",
]


def get_strategy(strategy_name: str) -> BaseStrategy:
    """Get a strategy instance by name.

    Args:
        strategy_name: One of tight_aggressive, loose_aggressive,
                      tight_passive, loose_passive, balanced

    Returns:
        Strategy instance
    """
    strategies = {
        "tight_aggressive": TightAggressiveStrategy,
        "loose_aggressive": LooseAggressiveStrategy,
        "tight_passive": TightPassiveStrategy,
        "loose_passive": LoosePassiveStrategy,
        "balanced": BalancedStrategy,
    }

    strategy_class = strategies.get(strategy_name, BalancedStrategy)
    return strategy_class()
