"""Main Database models for read-only access.

These models mirror the main game database schema for read-only queries.
Used by admin dashboard to access hand history, user data, etc.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class MainBase(DeclarativeBase):
    """Separate base class for Main DB models.

    This keeps Main DB models separate from Admin DB models.
    """
    pass


class MainUUIDMixin:
    """UUID primary key mixin for Main DB models."""
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
    )


class Hand(MainBase, MainUUIDMixin):
    """Poker hand model (read-only from main DB)."""

    __tablename__ = "hands"

    table_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
        index=True,
    )
    hand_number: Mapped[int] = mapped_column(nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    initial_state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    events: Mapped[list["HandEvent"]] = relationship(
        "HandEvent",
        back_populates="hand",
        order_by="HandEvent.seq_no",
    )
    participants: Mapped[list["HandParticipant"]] = relationship(
        "HandParticipant",
        back_populates="hand",
    )


class HandEvent(MainBase, MainUUIDMixin):
    """Hand event model (read-only from main DB)."""

    __tablename__ = "hand_events"

    hand_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("hands.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq_no: Mapped[int] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    state_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    hand: Mapped["Hand"] = relationship("Hand", back_populates="events")


class HandParticipant(MainBase, MainUUIDMixin):
    """Hand participant model (read-only from main DB)."""

    __tablename__ = "hand_participants"

    hand_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("hands.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
        index=True,
    )
    seat: Mapped[int] = mapped_column(nullable=False)
    hole_cards: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bet_amount: Mapped[int] = mapped_column(nullable=False, default=0)
    won_amount: Mapped[int] = mapped_column(nullable=False, default=0)
    final_action: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="fold",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    hand: Mapped["Hand"] = relationship("Hand", back_populates="participants")


class User(MainBase, MainUUIDMixin):
    """User model (read-only from main DB) - minimal fields for joins."""

    __tablename__ = "users"

    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_banned: Mapped[bool] = mapped_column(nullable=False, default=False)


class Table(MainBase, MainUUIDMixin):
    """Table model (read-only from main DB) - minimal fields for joins."""

    __tablename__ = "tables"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    small_blind: Mapped[int] = mapped_column(nullable=False)
    big_blind: Mapped[int] = mapped_column(nullable=False)
    max_players: Mapped[int] = mapped_column(nullable=False, default=9)
