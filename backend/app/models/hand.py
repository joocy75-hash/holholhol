"""Hand and HandEvent models."""

from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class HandPhase(str, Enum):
    """Hand phase."""

    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    FINISHED = "finished"


class Hand(Base, UUIDMixin):
    """Poker hand model."""

    __tablename__ = "hands"

    # Foreign key
    table_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tables.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Hand number (within table)
    hand_number: Mapped[int] = mapped_column(nullable=False, index=True)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Initial state snapshot
    initial_state: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )
    """
    Initial state:
    {
        "dealer_position": 0,
        "small_blind": 10,
        "big_blind": 20,
        "players": [
            {"seat": 0, "user_id": "...", "stack": 1000},
            ...
        ],
        "deck_seed": "..."  # For replay verification
    }
    """

    # Final result (populated after hand ends)
    result: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    """
    Result structure:
    {
        "winners": [
            {"user_id": "...", "seat": 0, "amount": 150, "hand_rank": "Two Pair"},
            ...
        ],
        "pot_total": 150,
        "community_cards": ["Ah", "Kd", "Qc", "Js", "Th"],
        "showdown_hands": {
            "0": ["As", "Ad"],
            "2": ["Kh", "Kc"]
        }
    }
    """

    # Relationships
    table: Mapped["Table"] = relationship("Table", back_populates="hands")
    events: Mapped[list["HandEvent"]] = relationship(
        "HandEvent",
        back_populates="hand",
        cascade="all, delete-orphan",
        order_by="HandEvent.seq_no",
    )

    def __repr__(self) -> str:
        return f"<Hand #{self.hand_number} table={self.table_id[:8]}...>"


class EventType(str, Enum):
    """Hand event types."""

    # Betting actions
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"

    # Automatic actions
    POST_BLIND = "post_blind"
    POST_ANTE = "post_ante"

    # Phase changes
    DEAL_HOLE_CARDS = "deal_hole_cards"
    DEAL_FLOP = "deal_flop"
    DEAL_TURN = "deal_turn"
    DEAL_RIVER = "deal_river"

    # End events
    SHOWDOWN = "showdown"
    POT_WON = "pot_won"
    HAND_END = "hand_end"

    # Player events
    PLAYER_TIMEOUT = "player_timeout"
    PLAYER_DISCONNECT = "player_disconnect"


class HandEvent(Base, UUIDMixin):
    """Individual event within a hand."""

    __tablename__ = "hand_events"

    # Foreign key
    hand_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("hands.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Sequence number (for ordering)
    seq_no: Mapped[int] = mapped_column(nullable=False)

    # Event type
    event_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    # Event payload
    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    """
    Payload examples:
    - fold: {"seat": 0, "user_id": "..."}
    - raise: {"seat": 0, "user_id": "...", "amount": 40, "total_bet": 60}
    - deal_flop: {"cards": ["Ah", "Kd", "Qc"]}
    - pot_won: {"seat": 0, "user_id": "...", "amount": 150}
    """

    # State version after this event
    state_version: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    hand: Mapped["Hand"] = relationship("Hand", back_populates="events")

    def __repr__(self) -> str:
        return f"<HandEvent #{self.seq_no} {self.event_type}>"


# Import for type hints
from app.models.table import Table  # noqa: E402
