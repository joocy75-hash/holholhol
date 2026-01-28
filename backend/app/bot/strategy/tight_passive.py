"""Tight-Passive strategy.

A cautious style common among recreational players:
- Plays few hands (tight)
- Prefers calling over betting/raising (passive)
"""

import random
from app.bot.strategy.base import BaseStrategy, Decision, GameContext


class TightPassiveStrategy(BaseStrategy):
    """Tight-Passive strategy - selective and cautious."""

    name = "tight_passive"
    description = "Plays few hands and prefers to call rather than raise"

    vpip = 0.18  # Only plays ~18% of hands
    pfr = 0.08   # Rarely raises
    aggression_factor = 1.0

    def _decide_preflop(
        self,
        context: GameContext,
        strength: float,
    ) -> Decision:
        """Tight-Passive preflop: Only premiums, mostly limp/call."""

        # Premium hands - actually raise these
        if strength >= 0.85:
            if "raise" in context.actions and random.random() < 0.7:
                raise_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.4, 0.6),  # Smaller raises than aggressive
                )
                return self._raise(raise_amount)
            if "call" in context.actions:
                return self._call(context.call_amount)

        # Strong hands - mostly call, occasionally raise
        elif strength >= 0.65:
            if "raise" in context.actions and random.random() < 0.25:
                raise_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.3, 0.5),
                )
                return self._raise(raise_amount)
            if "call" in context.actions:
                if context.call_amount <= context.stack * 0.08:
                    return self._call(context.call_amount)
            if "check" in context.actions:
                return self._check()

        # Playable hands - only call small bets
        elif strength >= 0.50:
            if "check" in context.actions:
                return self._check()
            if "call" in context.actions:
                # Only call if very cheap
                if context.call_amount <= context.stack * 0.04:
                    return self._call(context.call_amount)

        # Marginal hands - rarely play
        elif strength >= 0.40:
            if "check" in context.actions:
                return self._check()

        # Weak hands - always fold to any bet
        if "check" in context.actions:
            return self._check()

        return self._fold()

    def _decide_postflop(
        self,
        context: GameContext,
        strength: float,
        has_draw: bool,
    ) -> Decision:
        """Tight-Passive postflop: Check/call with good hands, fold weak."""

        # Monster hands - finally bet!
        if strength >= 0.85:
            if "bet" in context.actions:
                bet_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.4, 0.6),  # Still smaller bets
                )
                return self._bet(bet_amount)
            if "raise" in context.actions:
                raise_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.4, 0.7),
                )
                return self._raise(raise_amount)
            if "call" in context.actions:
                return self._call(context.call_amount)

        # Strong hands - mostly check/call
        elif strength >= 0.60:
            if "check" in context.actions:
                # Check most of the time, let others bet
                if random.random() < 0.7:
                    return self._check()
            if "bet" in context.actions and random.random() < 0.3:
                bet_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.3, 0.5),
                )
                return self._bet(bet_amount)
            if "call" in context.actions:
                # Call fairly large bets with strong hands
                if context.call_amount <= context.pot * 0.8:
                    return self._call(context.call_amount)

        # Medium hands - check/call small bets
        elif strength >= 0.45:
            if "check" in context.actions:
                return self._check()
            if "call" in context.actions:
                # Only call smaller bets
                if context.call_amount <= context.pot * 0.4:
                    return self._call(context.call_amount)
                # With draws, might call more
                if has_draw and context.call_amount <= context.pot * 0.6:
                    return self._call(context.call_amount)

        # Draw hands - call if cheap
        elif has_draw and strength >= 0.30:
            if "check" in context.actions:
                return self._check()
            if "call" in context.actions:
                if self._should_call_with_draw(
                    context.pot, context.call_amount, context.stack, 1.5
                ):
                    return self._call(context.call_amount)

        # Weak hands - check/fold
        else:
            if "check" in context.actions:
                return self._check()
            # Very rarely bluff (not typical for this style)
            if "bet" in context.actions and random.random() < 0.02:
                return self._bet(context.min_raise)

        return self._fold()
