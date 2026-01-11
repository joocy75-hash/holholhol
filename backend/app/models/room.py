"""Room model."""

from enum import Enum

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class RoomStatus(str, Enum):
    """Room status."""

    WAITING = "waiting"  # Waiting for players
    PLAYING = "playing"  # Game in progress
    PAUSED = "paused"  # Temporarily paused
    CLOSED = "closed"  # Room closed


class Room(Base, UUIDMixin, TimestampMixin):
    """Game room model."""

    __tablename__ = "rooms"

    # Basic info
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Owner
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Configuration
    config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    """
    Config structure:
    {
        "max_seats": 6,
        "small_blind": 10,
        "big_blind": 20,
        "buy_in_min": 400,
        "buy_in_max": 2000,
        "turn_timeout": 30,
        "is_private": false,
        "password_hash": null
    }
    """

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default=RoomStatus.WAITING.value,
        nullable=False,
        index=True,
    )

    # Stats
    current_players: Mapped[int] = mapped_column(default=0)

    # Relationships
    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])
    tables: Mapped[list["Table"]] = relationship(
        "Table",
        back_populates="room",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Room {self.name} ({self.status})>"

    @property
    def max_seats(self) -> int:
        return self.config.get("max_seats", 6)

    @property
    def small_blind(self) -> int:
        return self.config.get("small_blind", 10)

    @property
    def big_blind(self) -> int:
        return self.config.get("big_blind", 20)

    @property
    def is_full(self) -> bool:
        return self.current_players >= self.max_seats


# Import for type hints
from app.models.user import User  # noqa: E402
from app.models.table import Table  # noqa: E402
