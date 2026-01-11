"""Table model."""

from enum import Enum

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class TableStatus(str, Enum):
    """Table status."""

    WAITING = "waiting"  # Waiting for players
    PLAYING = "playing"  # Hand in progress
    BETWEEN_HANDS = "between_hands"  # Between hands
    PAUSED = "paused"  # Paused


class Table(Base, UUIDMixin, TimestampMixin):
    """Poker table model."""

    __tablename__ = "tables"

    # Foreign key
    room_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Configuration
    max_seats: Mapped[int] = mapped_column(default=6)

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default=TableStatus.WAITING.value,
        nullable=False,
    )

    # State version for consistency
    state_version: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )

    # Current hand number
    hand_number: Mapped[int] = mapped_column(default=0)

    # Dealer position (0-based seat index)
    dealer_position: Mapped[int] = mapped_column(default=0)

    # Seats state (JSON for flexibility)
    seats: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    """
    Seats structure:
    {
        "0": {"user_id": "...", "nickname": "...", "stack": 1000, "status": "active"},
        "1": null,
        "2": {"user_id": "...", "nickname": "...", "stack": 500, "status": "sitting_out"},
        ...
    }
    """

    # Relationships
    room: Mapped["Room"] = relationship("Room", back_populates="tables")
    hands: Mapped[list["Hand"]] = relationship(
        "Hand",
        back_populates="table",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Table {self.id[:8]}... room={self.room_id[:8]}...>"

    @property
    def active_players_count(self) -> int:
        """Count active players at the table."""
        count = 0
        for seat in self.seats.values():
            if seat and seat.get("status") == "active":
                count += 1
        return count

    def get_seat(self, position: int) -> dict | None:
        """Get seat data at position."""
        return self.seats.get(str(position))

    def is_seat_empty(self, position: int) -> bool:
        """Check if seat is empty."""
        return self.seats.get(str(position)) is None


# Import for type hints
from app.models.room import Room  # noqa: E402
from app.models.hand import Hand  # noqa: E402
