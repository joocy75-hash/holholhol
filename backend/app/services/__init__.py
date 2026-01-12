"""Business logic services."""

from app.services.audit import AuditService, get_audit_service
from app.services.auth import AuthError, AuthService
from app.services.crypto_deposit import CryptoDepositService, DepositError
from app.services.crypto_withdrawal import (
    CryptoWithdrawalService,
    InsufficientBalanceError as WithdrawalInsufficientError,
    WithdrawalError,
    WithdrawalLimitError,
)
from app.services.exchange_rate import (
    ExchangeRateError,
    ExchangeRateService,
    get_exchange_rate_service,
)
from app.services.room import RoomError, RoomService
from app.services.user import UserError, UserService
from app.services.wallet import (
    InsufficientBalanceError,
    WalletError,
    WalletService,
)

__all__ = [
    # Auth
    "AuthError",
    "AuthService",
    # Room
    "RoomError",
    "RoomService",
    # User
    "UserError",
    "UserService",
    # Wallet (Phase 5)
    "WalletService",
    "WalletError",
    "InsufficientBalanceError",
    # Crypto Deposit
    "CryptoDepositService",
    "DepositError",
    # Crypto Withdrawal
    "CryptoWithdrawalService",
    "WithdrawalError",
    "WithdrawalLimitError",
    "WithdrawalInsufficientError",
    # Exchange Rate
    "ExchangeRateService",
    "ExchangeRateError",
    "get_exchange_rate_service",
    # Audit
    "AuditService",
    "get_audit_service",
]
