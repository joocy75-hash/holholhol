"""Wallet and Transaction models for KRW + Cryptocurrency support.

Phase 5: KRW Balance + Cryptocurrency Deposit/Withdrawal System
- CryptoType: Supported cryptocurrencies (BTC, ETH, USDT, USDC)
- TransactionType: All transaction types for the gaming platform
- WalletTransaction: Full transaction history with crypto details
- CryptoAddress: User deposit address management
"""

from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, Enum as SQLEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class CryptoType(str, Enum):
    """Supported cryptocurrency types."""

    BTC = "btc"
    ETH = "eth"
    USDT = "usdt"
    USDC = "usdc"


class TransactionType(str, Enum):
    """Transaction types for wallet operations."""

    # Cryptocurrency operations
    CRYPTO_DEPOSIT = "crypto_deposit"
    CRYPTO_WITHDRAWAL = "crypto_withdrawal"

    # Game operations
    BUY_IN = "buy_in"
    CASH_OUT = "cash_out"
    WIN = "win"
    LOSE = "lose"

    # Platform fees
    RAKE = "rake"
    RAKEBACK = "rakeback"

    # Admin operations
    ADMIN_ADJUST = "admin_adjust"
    BONUS = "bonus"


class TransactionStatus(str, Enum):
    """Transaction status for async operations."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WalletTransaction(Base, UUIDMixin, TimestampMixin):
    """Wallet transaction record with full audit trail.

    All financial transactions are recorded here with:
    - KRW amounts for game display
    - Crypto details for deposits/withdrawals
    - Exchange rate at time of transaction
    - Integrity hash for tamper detection
    """

    __tablename__ = "wallet_transactions"

    # User reference
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Transaction type and status
    tx_type: Mapped[TransactionType] = mapped_column(
        SQLEnum(TransactionType),
        nullable=False,
        index=True,
    )
    status: Mapped[TransactionStatus] = mapped_column(
        SQLEnum(TransactionStatus),
        default=TransactionStatus.COMPLETED,
        nullable=False,
        index=True,
    )

    # KRW amounts (game currency)
    krw_amount: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Transaction amount in KRW (+credit/-debit)",
    )
    krw_balance_before: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="User KRW balance before transaction",
    )
    krw_balance_after: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="User KRW balance after transaction",
    )

    # Cryptocurrency information (for crypto transactions only)
    crypto_type: Mapped[CryptoType | None] = mapped_column(
        SQLEnum(CryptoType),
        nullable=True,
    )
    crypto_amount: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Crypto amount with full precision",
    )
    crypto_tx_hash: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Blockchain transaction hash",
    )
    crypto_address: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Crypto address for this transaction",
    )

    # Exchange rate (for crypto transactions)
    exchange_rate_krw: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Rate: 1 crypto = X KRW at transaction time",
    )

    # Game reference (for game-related transactions)
    hand_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("hands.id", ondelete="SET NULL"),
        nullable=True,
        comment="Related hand for game transactions",
    )
    table_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tables.id", ondelete="SET NULL"),
        nullable=True,
        comment="Related table for game transactions",
    )

    # Withdrawal specific
    withdrawal_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When withdrawal was requested (24h pending)",
    )
    withdrawal_processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When withdrawal was processed",
    )

    # Description and notes
    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    admin_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Admin notes for manual adjustments",
    )

    # Integrity verification
    integrity_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash for tamper detection",
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="transactions")

    def __repr__(self) -> str:
        return (
            f"<WalletTransaction {self.id[:8]}... "
            f"type={self.tx_type.value} amount={self.krw_amount}>"
        )


class CryptoAddress(Base, UUIDMixin, TimestampMixin):
    """User cryptocurrency deposit addresses.

    Each user gets a unique deposit address per crypto type.
    Addresses are generated on first request and reused.
    """

    __tablename__ = "crypto_addresses"

    # User reference
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Crypto type and address
    crypto_type: Mapped[CryptoType] = mapped_column(
        SQLEnum(CryptoType),
        nullable=False,
    )
    address: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )

    # Tracking
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )
    total_deposits: Mapped[int] = mapped_column(
        default=0,
        comment="Number of deposits received",
    )
    last_deposit_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="crypto_addresses")

    __table_args__ = ({"comment": "User cryptocurrency deposit addresses"},)

    def __repr__(self) -> str:
        return f"<CryptoAddress {self.crypto_type.value}:{self.address[:12]}...>"
