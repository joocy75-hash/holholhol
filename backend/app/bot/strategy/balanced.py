"""Balanced strategy.

A middle-ground approach:
- Plays moderate number of hands
- Mix of aggressive and passive play
"""

import random
from app.bot.strategy.base import BaseStrategy, Decision, GameContext


class BalancedStrategy(BaseStrategy):
    """Balanced strategy - moderate and adaptable."""

    name = "balanced"
    description = "Middle ground between tight and loose, aggressive and passive"

    vpip = 0.28  # Plays ~28% of hands
    pfr = 0.20   # Moderate raise frequency
    aggression_factor = 2.0

    def _decide_preflop(
        self,
        context: GameContext,
        strength: float,
    ) -> Decision:
        """Balanced preflop: Standard ranges, mix of plays."""

        # Premium hands - raise
        if strength >= 0.80:
            if "raise" in context.actions:
                raise_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.5, 0.8),
                )
                return self._raise(raise_amount)
            if "call" in context.actions:
                return self._call(context.call_amount)

        # Strong hands - mix of raise and call
        elif strength >= 0.60:
            if "raise" in context.actions and random.random() < 0.55:
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
            if "check" in context.actions:
                return self._check()

        # Playable hands - context-dependent
        elif strength >= 0.45:
            if "check" in context.actions:
                return self._check()
            # Sometimes raise
            if "raise" in context.actions and random.random() < 0.25:
                raise_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.35, 0.55),
                )
                return self._raise(raise_amount)
            if "call" in context.actions:
                if context.call_amount <= context.stack * 0.06:
                    return self._call(context.call_amount)

        # Speculative hands - occasional play
        elif strength >= 0.30:
            if "check" in context.actions:
                return self._check()
            if "call" in context.actions:
                # Only limp cheap
                if context.call_amount <= context.stack * 0.03:
                    return self._call(context.call_amount)

        # Weak hands
        if "check" in context.actions:
            return self._check()

        return self._fold()

    def _decide_postflop(
        self,
        context: GameContext,
        strength: float,
        has_draw: bool,
    ) -> Decision:
        """Balanced postflop: Standard solid play."""

        # Strong hands - value bet
        if strength >= 0.70:
            if "bet" in context.actions:
                bet_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.45, 0.75),
                )
                return self._bet(bet_amount)
            if "raise" in context.actions:
                raise_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.5, 0.85),
                )
                return self._raise(raise_amount)
            if "call" in context.actions:
                return self._call(context.call_amount)

        # Medium hands - mix of bet/check/call
        elif strength >= 0.50:
            if "check" in context.actions:
                # Sometimes check to control pot
                if random.random() < 0.4:
                    return self._check()
            if "bet" in context.actions:
                bet_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.4, 0.6),
                )
                return self._bet(bet_amount)
            if "call" in context.actions:
                if context.call_amount <= context.pot * 0.6:
                    return self._call(context.call_amount)
                if has_draw and self._should_call_with_draw(
                    context.pot, context.call_amount, context.stack, 2.0
                ):
                    return self._call(context.call_amount)

        # Draw hands
        elif has_draw and strength >= 0.30:
            if "check" in context.actions:
                # Sometimes semi-bluff
                if random.random() < 0.65:
                    return self._check()
            if "bet" in context.actions and random.random() < 0.35:
                bet_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    0.5,
                    (0.4, 0.6),
                )
                return self._bet(bet_amount)
            if "call" in context.actions:
                if self._should_call_with_draw(
                    context.pot, context.call_amount, context.stack, 2.0
                ):
                    return self._call(context.call_amount)

        # Weak hands
        else:
            if "check" in context.actions:
                return self._check()
            # Occasional bluff
            if "bet" in context.actions and random.random() < 0.10:
                bet_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    0.5,
                    (0.4, 0.6),
                )
                return self._bet(bet_amount)

        return self._fold()
