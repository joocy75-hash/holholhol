from datetime import datetime
from decimal import Decimal
from enum import Enum
from sqlalchemy import String, DateTime, Numeric, ForeignKey, Integer, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class TransactionStatus(str, Enum):
    PENDING = "pending"
    CONFIRMING = "confirming"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class CryptoDeposit(Base, UUIDMixin, TimestampMixin):
    """USDT TRC-20 deposit record"""
    __tablename__ = "crypto_deposits"

    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    tx_hash: Mapped[str] = mapped_column(String(66), unique=True, nullable=False)
    from_address: Mapped[str] = mapped_column(String(42), nullable=False)
    to_address: Mapped[str] = mapped_column(String(42), nullable=False)
    amount_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    amount_krw: Mapped[Decimal] = mapped_column(Numeric(20, 0), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    confirmations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(
        SQLEnum(TransactionStatus),
        default=TransactionStatus.PENDING,
        nullable=False,
        index=True,
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    credited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<CryptoDeposit {self.tx_hash[:10]}... {self.amount_usdt} USDT>"


class CryptoWithdrawal(Base, UUIDMixin, TimestampMixin):
    """USDT TRC-20 withdrawal record"""
    __tablename__ = "crypto_withdrawals"

    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    to_address: Mapped[str] = mapped_column(String(42), nullable=False)
    amount_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    amount_krw: Mapped[Decimal] = mapped_column(Numeric(20, 0), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    network_fee_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    network_fee_krw: Mapped[Decimal] = mapped_column(Numeric(20, 0), nullable=False)
    tx_hash: Mapped[str | None] = mapped_column(String(66), unique=True, nullable=True)
    status: Mapped[TransactionStatus] = mapped_column(
        SQLEnum(TransactionStatus),
        default=TransactionStatus.PENDING,
        nullable=False,
        index=True,
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<CryptoWithdrawal {self.id[:8]}... {self.amount_usdt} USDT to {self.to_address[:10]}...>"


class HotWalletBalance(Base, UUIDMixin):
    """Hot wallet balance snapshot"""
    __tablename__ = "hot_wallet_balances"

    address: Mapped[str] = mapped_column(String(42), nullable=False)
    balance_usdt: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    balance_krw: Mapped[Decimal] = mapped_column(Numeric(20, 0), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return f"<HotWalletBalance {self.balance_usdt} USDT at {self.recorded_at}>"


class ExchangeRateHistory(Base, UUIDMixin):
    """Exchange rate history"""
    __tablename__ = "exchange_rate_history"

    rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<ExchangeRateHistory {self.rate} KRW/USDT at {self.recorded_at}>"
