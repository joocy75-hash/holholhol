"""Loose-Aggressive (LAG) strategy.

A more unpredictable, aggressive style:
- Plays many hands (loose)
- Plays them aggressively (lots of betting and raising)
"""

import random
from app.bot.strategy.base import BaseStrategy, Decision, GameContext


class LooseAggressiveStrategy(BaseStrategy):
    """Loose-Aggressive strategy - plays many hands aggressively."""

    name = "loose_aggressive"
    description = "Plays many hands and plays them aggressively"

    vpip = 0.35  # Plays ~35% of hands
    pfr = 0.28   # High preflop raise frequency
    aggression_factor = 4.0

    def _decide_preflop(
        self,
        context: GameContext,
        strength: float,
    ) -> Decision:
        """LAG preflop: Wide range, lots of raising."""

        # Premium hands - always raise big
        if strength >= 0.80:
            if "raise" in context.actions:
                raise_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.7, 1.2),  # LAGs raise bigger
                )
                return self._raise(raise_amount)
            if "call" in context.actions:
                return self._call(context.call_amount)

        # Strong hands - raise most of the time
        elif strength >= 0.55:
            if "raise" in context.actions and random.random() < 0.85:
                raise_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.5, 0.9),
                )
                return self._raise(raise_amount)
            if "call" in context.actions:
                return self._call(context.call_amount)

        # Playable hands - still raise often
        elif strength >= 0.40:
            # LAGs raise with marginal hands too
            if "raise" in context.actions and random.random() < 0.5:
                raise_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.4, 0.7),
                )
                return self._raise(raise_amount)
            if "call" in context.actions:
                if context.call_amount <= context.stack * 0.08:
                    return self._call(context.call_amount)

        # Speculative hands (suited connectors, small pairs)
        elif strength >= 0.25:
            if "check" in context.actions:
                return self._check()
            # Bluff raise sometimes
            if "raise" in context.actions and random.random() < 0.15:
                raise_amount = context.min_raise
                return self._raise(raise_amount)
            if "call" in context.actions:
                if context.call_amount <= context.stack * 0.04:
                    return self._call(context.call_amount)

        # Weak hands - mostly fold but occasional steal
        else:
            if "check" in context.actions:
                return self._check()
            # Steal attempt from late position
            if "raise" in context.actions and random.random() < 0.08:
                raise_amount = context.min_raise
                return self._raise(raise_amount)

        return self._fold()

    def _decide_postflop(
        self,
        context: GameContext,
        strength: float,
        has_draw: bool,
    ) -> Decision:
        """LAG postflop: Aggressive betting, lots of bluffs."""

        # Strong hands - bet big for value
        if strength >= 0.65:
            if "bet" in context.actions:
                bet_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.6, 1.0),  # LAGs bet bigger
                )
                return self._bet(bet_amount)
            if "raise" in context.actions:
                raise_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.6, 1.2),
                )
                return self._raise(raise_amount)
            if "call" in context.actions:
                return self._call(context.call_amount)

        # Medium hands - still aggressive
        elif strength >= 0.45:
            if "bet" in context.actions:
                # LAGs bet medium hands for value/protection
                bet_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.5, 0.75),
                )
                return self._bet(bet_amount)
            if "check" in context.actions:
                # Sometimes check to trap or induce bluffs
                if random.random() < 0.25:
                    return self._check()
            if "call" in context.actions:
                if context.call_amount <= context.pot * 0.7:
                    return self._call(context.call_amount)
                if has_draw and self._should_call_with_draw(
                    context.pot, context.call_amount, context.stack, 2.5
                ):
                    return self._call(context.call_amount)

        # Draw hands - semi-bluff aggressively
        elif has_draw and strength >= 0.25:
            if "bet" in context.actions and random.random() < 0.6:
                # LAGs semi-bluff frequently
                bet_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    0.55,  # Bet as if medium strength
                    (0.5, 0.8),
                )
                return self._bet(bet_amount)
            if "raise" in context.actions and random.random() < 0.35:
                raise_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    0.55,
                    (0.5, 0.9),
                )
                return self._raise(raise_amount)
            if "check" in context.actions:
                return self._check()
            if "call" in context.actions:
                if self._should_call_with_draw(
                    context.pot, context.call_amount, context.stack, 2.5
                ):
                    return self._call(context.call_amount)

        # Weak hands - still aggressive (bluffing)
        else:
            if "check" in context.actions:
                return self._check()
            # LAGs bluff more often
            if "bet" in context.actions and random.random() < 0.20:
                bet_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    0.5,  # Bet sizing doesn't reveal weakness
                    (0.5, 0.7),
                )
                return self._bet(bet_amount)
            if "raise" in context.actions and random.random() < 0.10:
                return self._raise(context.min_raise)

        return self._fold()
