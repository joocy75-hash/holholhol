"""Game engine state models - immutable data classes."""
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import Self


class Rank(Enum):
    """Card rank."""

    TWO = (2, "2")
    THREE = (3, "3")
    FOUR = (4, "4")
    FIVE = (5, "5")
    SIX = (6, "6")
    SEVEN = (7, "7")
    EIGHT = (8, "8")
    NINE = (9, "9")
    TEN = (10, "T")
    JACK = (11, "J")
    QUEEN = (12, "Q")
    KING = (13, "K")
    ACE = (14, "A")

    @property
    def value(self) -> int:
        return self._value_[0]

    @property
    def symbol(self) -> str:
        return self._value_[1]

    @classmethod
    def from_symbol(cls, symbol: str) -> "Rank":
        for rank in cls:
            if rank.symbol == symbol.upper():
                return rank
        raise ValueError(f"Invalid rank symbol: {symbol}")
