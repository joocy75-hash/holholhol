"""Database models."""

from app.models.audit import AuditLog
from app.models.base import Base, TimestampMixin
from app.models.checkin import DailyCheckin, CHECKIN_REWARDS
from app.models.hand import Hand, HandEvent, HandParticipant
from app.models.referral import ReferralReward, REFERRAL_REWARDS
from app.models.partner import (
    CommissionType,
    Partner,
    PartnerSettlement,
    PartnerStatus,
    SettlementPeriod,
    SettlementStatus,
)
from app.models.rake import RakeConfig
from app.models.room import Room
from app.models.table import Table
from app.models.user import Session, User
from app.models.wallet import (
    CryptoAddress,
    CryptoType,
    TransactionStatus,
    TransactionType,
    WalletTransaction,
)

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    # Checkin (이벤트)
    "DailyCheckin",
    "CHECKIN_REWARDS",
    # Referral (친구추천)
    "ReferralReward",
    "REFERRAL_REWARDS",
    # User
    "User",
    "Session",
    # Room & Table
    "Room",
    "Table",
    # Hand
    "Hand",
    "HandEvent",
    "HandParticipant",
    # Audit
    "AuditLog",
    # Wallet (Phase 5)
    "WalletTransaction",
    "CryptoAddress",
    "CryptoType",
    "TransactionType",
    "TransactionStatus",
    # Rake (Phase P1-1)
    "RakeConfig",
    # Partner (총판)
    "Partner",
    "PartnerSettlement",
    "PartnerStatus",
    "CommissionType",
    "SettlementStatus",
    "SettlementPeriod",
]
