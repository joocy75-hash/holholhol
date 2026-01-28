"""Tight-Aggressive (TAG) strategy.

The most common winning strategy:
- Plays few hands (tight)
- Plays them aggressively (raises instead of calls)
"""

import random
from app.bot.strategy.base import BaseStrategy, Decision, GameContext


class TightAggressiveStrategy(BaseStrategy):
    """Tight-Aggressive strategy - selective but aggressive."""

    name = "tight_aggressive"
    description = "Plays few hands but plays them aggressively"

    vpip = 0.22  # Only plays ~22% of hands
    pfr = 0.18   # Raises most of the hands played
    aggression_factor = 3.0

    def _decide_preflop(
        self,
        context: GameContext,
        strength: float,
    ) -> Decision:
        """TAG preflop: Only play strong hands, raise when we do."""

        # Premium hands (AA, KK, QQ, AKs, AKo) - always raise
        if strength >= 0.80:
            if "raise" in context.actions:
                # 3-bet or raise big with premiums
                raise_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.6, 1.0),  # 60-100% pot for premiums
                )
                return self._raise(raise_amount)
            if "call" in context.actions:
                return self._call(context.call_amount)

        # Strong hands (JJ, TT, AQs, AQo, KQs) - raise or call depending on position
        elif strength >= 0.60:
            if "raise" in context.actions and random.random() < 0.7:
                raise_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.4, 0.7),
                )
                return self._raise(raise_amount)
            if "call" in context.actions:
                # Only call if raise is reasonable (less than 10% stack)
                if context.call_amount <= context.stack * 0.10:
                    return self._call(context.call_amount)

        # Playable hands (99-77, AJs, KJs, QJs, suited connectors)
        elif strength >= 0.45:
            # Only play in position or with good pot odds
            if "check" in context.actions:
                return self._check()
            if "call" in context.actions:
                # Only call small raises
                if context.call_amount <= context.stack * 0.05:
                    return self._call(context.call_amount)

        # Marginal hands - rarely play
        elif strength >= 0.35:
            if "check" in context.actions:
                return self._check()
            # Very occasionally bluff raise
            if "raise" in context.actions and random.random() < 0.05:
                raise_amount = context.min_raise
                return self._raise(raise_amount)

        # Weak hands - fold
        if "check" in context.actions:
            return self._check()

        return self._fold()

    def _decide_postflop(
        self,
        context: GameContext,
        strength: float,
        has_draw: bool,
    ) -> Decision:
        """TAG postflop: Bet/raise with strong hands, fold weak hands."""

        # Very strong hands (two pair+, strong top pair) - bet for value
        if strength >= 0.70:
            if "bet" in context.actions:
                bet_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.5, 0.85),  # Value bet 50-85% pot
                )
                return self._bet(bet_amount)
            if "raise" in context.actions:
                raise_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.5, 1.0),
                )
                return self._raise(raise_amount)
            if "call" in context.actions:
                return self._call(context.call_amount)
            if "check" in context.actions:
                # Slow play occasionally with monsters
                if random.random() < 0.2 and strength >= 0.85:
                    return self._check()

        # Medium-strong hands (top pair good kicker, overpair)
        elif strength >= 0.50:
            if "check" in context.actions:
                # Check-raise sometimes with strong hands
                if random.random() < 0.3:
                    return self._check()
            if "bet" in context.actions:
                bet_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.4, 0.65),
                )
                return self._bet(bet_amount)
            if "call" in context.actions:
                # Call if bet is reasonable
                if context.call_amount <= context.pot * 0.5:
                    return self._call(context.call_amount)
                # With draws, use pot odds
                if has_draw and self._should_call_with_draw(
                    context.pot, context.call_amount, context.stack
                ):
                    return self._call(context.call_amount)
                return self._fold()

        # Draw hands
        elif has_draw and strength >= 0.30:
            if "check" in context.actions:
                return self._check()
            if "call" in context.actions:
                if self._should_call_with_draw(
                    context.pot, context.call_amount, context.stack
                ):
                    return self._call(context.call_amount)
            # Semi-bluff occasionally
            if "bet" in context.actions and random.random() < 0.25:
                bet_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    0.5,  # Use medium strength for sizing
                    (0.4, 0.6),
                )
                return self._bet(bet_amount)

        # Weak hands - mostly fold, occasional bluff
        else:
            if "check" in context.actions:
                return self._check()
            # Bluff very rarely
            if "bet" in context.actions and random.random() < 0.08:
                bet_amount = context.min_raise
                return self._bet(bet_amount)

        return self._fold()
