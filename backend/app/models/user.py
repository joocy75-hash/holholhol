"""User and Session models."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.wallet import CryptoAddress, WalletTransaction


class UserStatus(str, Enum):
    """User account status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class User(Base, UUIDMixin, TimestampMixin):
    """User account model."""

    __tablename__ = "users"

    # Profile
    nickname: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default=UserStatus.ACTIVE.value,
        nullable=False,
    )

    # Balance - user's current chip balance (legacy, kept for compatibility)
    balance: Mapped[int] = mapped_column(
        default=10000,  # Initial chips for new users
        nullable=False,
    )

    # KRW Balance System (Phase 5) - Primary game currency
    krw_balance: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
        comment="Game balance in KRW (원화) - deposits converted from crypto",
    )

    # Pending withdrawal amount (locked during 24h withdrawal process)
    pending_withdrawal_krw: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
        comment="KRW amount locked for pending withdrawals",
    )

    # Stats (denormalized for quick access)
    total_hands: Mapped[int] = mapped_column(default=0)
    total_winnings: Mapped[int] = mapped_column(default=0)

    # VIP/Rakeback tracking (Phase 6)
    total_rake_paid_krw: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
        comment="Total rake paid in KRW (for VIP level calculation)",
    )

    # Relationships
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Wallet relationships (Phase 5)
    transactions: Mapped[list["WalletTransaction"]] = relationship(
        "WalletTransaction",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="desc(WalletTransaction.created_at)",
    )

    crypto_addresses: Mapped[list["CryptoAddress"]] = relationship(
        "CryptoAddress",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User {self.nickname}>"


class Session(Base, UUIDMixin):
    """User session model for token management."""

    __tablename__ = "sessions"

    # Foreign key
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Token info
    refresh_token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Metadata
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")

    def __repr__(self) -> str:
        return f"<Session {self.id[:8]}... user={self.user_id[:8]}...>"


class UserTwoFactor(Base, UUIDMixin):
    """User two-factor authentication configuration.
    
    Stores TOTP secrets and backup codes for 2FA.
    """

    __tablename__ = "user_two_factor"

    # Foreign key to user
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One 2FA config per user
        index=True,
    )

    # Encrypted TOTP secret (Base32 encoded)
    # In production, this should be encrypted at rest
    secret_encrypted: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="Encrypted TOTP secret (Base32)",
    )

    # Whether 2FA is enabled for this user
    is_enabled: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )

    # Hashed backup codes (JSON array of SHA-256 hashes)
    backup_codes_hash: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON array of hashed backup codes",
    )

    # Number of backup codes remaining
    backup_codes_remaining: Mapped[int] = mapped_column(
        default=10,
        nullable=False,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Last time 2FA was used successfully
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Last time a backup code was used
    last_backup_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationship back to user
    user: Mapped["User"] = relationship("User", backref="two_factor")

    def __repr__(self) -> str:
        return f"<UserTwoFactor user={self.user_id[:8]}... enabled={self.is_enabled}>"
