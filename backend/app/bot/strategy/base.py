"""Base strategy class for bot decision making."""

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from app.game.hand_evaluator import evaluate_hand_for_bot


ActionType = Literal["fold", "check", "call", "bet", "raise", "all_in"]


@dataclass
class Decision:
    """Bot decision result."""

    action: ActionType
    amount: int = 0

    def to_tuple(self) -> tuple[str, int]:
        """Convert to tuple format for action handler."""
        return (self.action, self.amount)


@dataclass
class GameContext:
    """Context for making a decision."""

    # Available actions
    actions: list[str]
    call_amount: int
    min_raise: int
    max_raise: int

    # Player state
    stack: int
    current_bet: int
    position: int  # 0-based seat position

    # Hand state
    hole_cards: list[str]
    community_cards: list[str]
    pot: int
    phase: str  # preflop, flop, turn, river

    # Table state
    big_blind: int
    num_players: int
    num_active: int


class BaseStrategy(ABC):
    """Base class for bot strategies."""

    name: str = "base"
    description: str = "Base strategy"

    # Default parameters (override in subclasses)
    vpip: float = 0.25  # Voluntarily Put money In Pot %
    pfr: float = 0.18   # Pre-Flop Raise %
    aggression_factor: float = 2.0  # Bet+Raise / Call ratio

    def decide(self, context: GameContext) -> Decision:
        """Make a decision based on the game context.

        This method evaluates hand strength and delegates to
        phase-specific methods.

        Args:
            context: Current game context

        Returns:
            Decision with action and amount
        """
        # Evaluate hand strength
        eval_result = evaluate_hand_for_bot(
            hole_cards=context.hole_cards,
            community_cards=context.community_cards,
            pot=context.pot,
            to_call=context.call_amount,
        )

        strength = eval_result["strength"]
        has_draw = eval_result["has_draw"]

        # Add some randomness to make less predictable
        strength_variance = random.uniform(-0.05, 0.05)
        adjusted_strength = max(0.0, min(1.0, strength + strength_variance))

        # Delegate to phase-specific method
        if context.phase == "preflop":
            return self._decide_preflop(context, adjusted_strength)
        else:
            return self._decide_postflop(context, adjusted_strength, has_draw)

    @abstractmethod
    def _decide_preflop(
        self,
        context: GameContext,
        strength: float,
    ) -> Decision:
        """Make a preflop decision.

        Args:
            context: Game context
            strength: Evaluated hand strength (0.0-1.0)

        Returns:
            Decision
        """
        pass

    @abstractmethod
    def _decide_postflop(
        self,
        context: GameContext,
        strength: float,
        has_draw: bool,
    ) -> Decision:
        """Make a postflop decision.

        Args:
            context: Game context
            strength: Evaluated hand strength (0.0-1.0)
            has_draw: Whether we have a draw

        Returns:
            Decision
        """
        pass

    def _fold(self) -> Decision:
        """Return fold decision."""
        return Decision(action="fold", amount=0)

    def _check(self) -> Decision:
        """Return check decision."""
        return Decision(action="check", amount=0)

    def _call(self, amount: int) -> Decision:
        """Return call decision."""
        return Decision(action="call", amount=amount)

    def _bet(self, amount: int) -> Decision:
        """Return bet decision."""
        return Decision(action="bet", amount=amount)

    def _raise(self, amount: int) -> Decision:
        """Return raise decision."""
        return Decision(action="raise", amount=amount)

    def _all_in(self, stack: int) -> Decision:
        """Return all-in decision."""
        return Decision(action="all_in", amount=stack)

    def _calculate_bet_size(
        self,
        pot: int,
        min_bet: int,
        max_bet: int,
        strength: float,
        multiplier_range: tuple[float, float] = (0.3, 0.8),
    ) -> int:
        """Calculate bet size based on pot and strength.

        Args:
            pot: Current pot size
            min_bet: Minimum allowed bet
            max_bet: Maximum allowed bet (stack)
            strength: Hand strength (0.0-1.0)
            multiplier_range: (min_mult, max_mult) for pot-based sizing

        Returns:
            Bet amount
        """
        # Base bet is percentage of pot
        min_mult, max_mult = multiplier_range
        multiplier = min_mult + (strength * (max_mult - min_mult))
        base_bet = int(pot * multiplier)

        # Add some randomness
        variance = random.uniform(0.85, 1.15)
        bet_amount = int(base_bet * variance)

        # Clamp to valid range
        return max(min_bet, min(max_bet, bet_amount))

    def _should_call_with_draw(
        self,
        pot: int,
        call_amount: int,
        stack: int,
        implied_odds_factor: float = 2.0,
    ) -> bool:
        """Decide if we should call with a draw based on pot odds.

        Args:
            pot: Current pot size
            call_amount: Amount to call
            stack: Our remaining stack
            implied_odds_factor: Multiplier for implied odds

        Returns:
            True if we should call
        """
        if call_amount == 0:
            return True

        # Calculate pot odds (call / (pot + call))
        pot_odds = call_amount / (pot + call_amount) if (pot + call_amount) > 0 else 1.0

        # Implied odds consideration
        effective_pot = pot * implied_odds_factor

        # For draws, we need about 4:1 odds (20%) for flush/straight draws
        # Be more willing to call if bet is small relative to pot
        required_odds = 0.25  # 25% = need about 3:1

        return pot_odds <= required_odds and call_amount <= stack * 0.30
