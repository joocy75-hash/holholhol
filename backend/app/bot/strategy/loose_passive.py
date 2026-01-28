"""Loose-Passive strategy.

A "calling station" style:
- Plays many hands (loose)
- Prefers calling over betting/raising (passive)
"""

import random
from app.bot.strategy.base import BaseStrategy, Decision, GameContext


class LoosePassiveStrategy(BaseStrategy):
    """Loose-Passive strategy - plays many hands, mostly calls."""

    name = "loose_passive"
    description = "Plays many hands but prefers to call rather than bet"

    vpip = 0.40  # Plays ~40% of hands
    pfr = 0.12   # Rarely raises
    aggression_factor = 0.8

    def _decide_preflop(
        self,
        context: GameContext,
        strength: float,
    ) -> Decision:
        """Loose-Passive preflop: Limp/call with wide range."""

        # Premium hands - actually raise
        if strength >= 0.80:
            if "raise" in context.actions and random.random() < 0.6:
                raise_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.35, 0.55),  # Small-medium raises
                )
                return self._raise(raise_amount)
            if "call" in context.actions:
                return self._call(context.call_amount)

        # Strong hands - mostly call
        elif strength >= 0.55:
            if "raise" in context.actions and random.random() < 0.20:
                raise_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.3, 0.5),
                )
                return self._raise(raise_amount)
            if "call" in context.actions:
                if context.call_amount <= context.stack * 0.10:
                    return self._call(context.call_amount)
            if "check" in context.actions:
                return self._check()

        # Playable hands - call liberally
        elif strength >= 0.35:
            if "check" in context.actions:
                return self._check()
            if "call" in context.actions:
                # Calling station tendency
                if context.call_amount <= context.stack * 0.08:
                    return self._call(context.call_amount)

        # Speculative hands - still might limp/call
        elif strength >= 0.20:
            if "check" in context.actions:
                return self._check()
            if "call" in context.actions:
                # "See a flop" mentality
                if context.call_amount <= context.stack * 0.04:
                    return self._call(context.call_amount)

        # Very weak hands
        if "check" in context.actions:
            return self._check()

        return self._fold()

    def _decide_postflop(
        self,
        context: GameContext,
        strength: float,
        has_draw: bool,
    ) -> Decision:
        """Loose-Passive postflop: Check/call too much, rarely fold."""

        # Monster hands - bet (finally!)
        if strength >= 0.80:
            if "bet" in context.actions:
                bet_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.35, 0.55),
                )
                return self._bet(bet_amount)
            if "raise" in context.actions and random.random() < 0.5:
                raise_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.4, 0.6),
                )
                return self._raise(raise_amount)
            if "call" in context.actions:
                return self._call(context.call_amount)

        # Strong hands - check/call
        elif strength >= 0.55:
            if "check" in context.actions:
                if random.random() < 0.8:
                    return self._check()
            if "bet" in context.actions and random.random() < 0.20:
                bet_amount = self._calculate_bet_size(
                    context.pot,
                    context.min_raise,
                    context.max_raise,
                    strength,
                    (0.3, 0.5),
                )
                return self._bet(bet_amount)
            if "call" in context.actions:
                # Call pretty much anything
                if context.call_amount <= context.pot * 1.0:
                    return self._call(context.call_amount)

        # Medium hands - calling station behavior
        elif strength >= 0.40:
            if "check" in context.actions:
                return self._check()
            if "call" in context.actions:
                # Calls too much - classic calling station
                if context.call_amount <= context.pot * 0.7:
                    return self._call(context.call_amount)
                # Even calls larger bets sometimes
                if random.random() < 0.3:
                    return self._call(context.call_amount)

        # Weak/draw hands - still calls too much
        elif has_draw or strength >= 0.25:
            if "check" in context.actions:
                return self._check()
            if "call" in context.actions:
                # Chasing draws/hoping to improve
                if context.call_amount <= context.pot * 0.5:
                    return self._call(context.call_amount)
                if random.random() < 0.25:
                    return self._call(context.call_amount)

        # Very weak hands - finally fold (sometimes)
        else:
            if "check" in context.actions:
                return self._check()
            if "call" in context.actions:
                # Still might "keep them honest"
                if context.call_amount <= context.pot * 0.25 and random.random() < 0.3:
                    return self._call(context.call_amount)

        return self._fold()
