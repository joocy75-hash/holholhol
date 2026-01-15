from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()


# Exchange Rate
class ExchangeRateResponse(BaseModel):
    rate: float
    source: str
    timestamp: str


class ExchangeRateHistory(BaseModel):
    items: list[ExchangeRateResponse]


# Deposits
class DepositResponse(BaseModel):
    id: str
    user_id: str
    username: str
    tx_hash: str
    from_address: str
    to_address: str
    amount_usdt: float
    amount_krw: float
    exchange_rate: float
    confirmations: int
    status: str
    detected_at: str
    confirmed_at: str | None
    credited_at: str | None


class PaginatedDeposits(BaseModel):
    items: list[DepositResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# Withdrawals
class WithdrawalResponse(BaseModel):
    id: str
    user_id: str
    username: str
    to_address: str
    amount_usdt: float
    amount_krw: float
    exchange_rate: float
    network_fee_usdt: float
    network_fee_krw: float
    tx_hash: str | None
    status: str
    requested_at: str
    approved_by: str | None
    approved_at: str | None
    processed_at: str | None
    rejection_reason: str | None


class PaginatedWithdrawals(BaseModel):
    items: list[WithdrawalResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class WithdrawalActionRequest(BaseModel):
    two_factor_code: str
    reason: str | None = None


# Wallet
class WalletBalanceResponse(BaseModel):
    address: str
    balance_usdt: float
    balance_krw: float
    pending_withdrawals_usdt: float
    pending_withdrawals_krw: float
    exchange_rate: float
    last_updated: str


# Statistics
class CryptoStatsResponse(BaseModel):
    total_deposits_usdt: float
    total_deposits_krw: float
    total_withdrawals_usdt: float
    total_withdrawals_krw: float
    deposit_count: int
    withdrawal_count: int
    period: str


# Exchange Rate Endpoints
@router.get("/exchange-rate", response_model=ExchangeRateResponse)
async def get_exchange_rate():
    """Get current USDT/KRW exchange rate"""
    # TODO: Implement actual exchange rate fetching
    return ExchangeRateResponse(
        rate=1380.0,
        source="Upbit",
        timestamp="2026-01-15T12:00:00Z",
    )


@router.get("/exchange-rate/history", response_model=ExchangeRateHistory)
async def get_exchange_rate_history(
    hours: int = Query(24, ge=1, le=168),
):
    """Get exchange rate history"""
    # TODO: Implement actual history retrieval
    return ExchangeRateHistory(items=[])


# Deposit Endpoints
@router.get("/deposits", response_model=PaginatedDeposits)
async def list_deposits(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List deposits"""
    return PaginatedDeposits(
        items=[],
        total=0,
        page=page,
        page_size=page_size,
        total_pages=0,
    )


@router.get("/deposits/{deposit_id}", response_model=DepositResponse)
async def get_deposit(deposit_id: str):
    """Get deposit details"""
    # TODO: Implement actual deposit retrieval
    return DepositResponse(
        id=deposit_id,
        user_id="user-1",
        username="test_user",
        tx_hash="0x...",
        from_address="T...",
        to_address="T...",
        amount_usdt=100.0,
        amount_krw=138000.0,
        exchange_rate=1380.0,
        confirmations=20,
        status="confirmed",
        detected_at="2026-01-15T12:00:00Z",
        confirmed_at="2026-01-15T12:05:00Z",
        credited_at="2026-01-15T12:05:00Z",
    )


@router.post("/deposits/{deposit_id}/approve")
async def approve_deposit(deposit_id: str):
    """Manually approve a deposit"""
    return {"message": f"Deposit {deposit_id} approved"}


@router.post("/deposits/{deposit_id}/reject")
async def reject_deposit(deposit_id: str, request: WithdrawalActionRequest):
    """Reject a deposit"""
    return {"message": f"Deposit {deposit_id} rejected", "reason": request.reason}


# Withdrawal Endpoints
@router.get("/withdrawals", response_model=PaginatedWithdrawals)
async def list_withdrawals(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List withdrawals"""
    return PaginatedWithdrawals(
        items=[],
        total=0,
        page=page,
        page_size=page_size,
        total_pages=0,
    )


@router.get("/withdrawals/{withdrawal_id}", response_model=WithdrawalResponse)
async def get_withdrawal(withdrawal_id: str):
    """Get withdrawal details"""
    # TODO: Implement actual withdrawal retrieval
    return WithdrawalResponse(
        id=withdrawal_id,
        user_id="user-1",
        username="test_user",
        to_address="T...",
        amount_usdt=100.0,
        amount_krw=138000.0,
        exchange_rate=1380.0,
        network_fee_usdt=1.0,
        network_fee_krw=1380.0,
        tx_hash=None,
        status="pending",
        requested_at="2026-01-15T12:00:00Z",
        approved_by=None,
        approved_at=None,
        processed_at=None,
        rejection_reason=None,
    )


@router.post("/withdrawals/{withdrawal_id}/approve")
async def approve_withdrawal(withdrawal_id: str, request: WithdrawalActionRequest):
    """Approve a withdrawal"""
    return {"message": f"Withdrawal {withdrawal_id} approved"}


@router.post("/withdrawals/{withdrawal_id}/reject")
async def reject_withdrawal(withdrawal_id: str, request: WithdrawalActionRequest):
    """Reject a withdrawal"""
    return {"message": f"Withdrawal {withdrawal_id} rejected", "reason": request.reason}


# Wallet Endpoints
@router.get("/wallet/balance", response_model=WalletBalanceResponse)
async def get_wallet_balance():
    """Get hot wallet balance"""
    return WalletBalanceResponse(
        address="T...",
        balance_usdt=50000.0,
        balance_krw=69000000.0,
        pending_withdrawals_usdt=1000.0,
        pending_withdrawals_krw=1380000.0,
        exchange_rate=1380.0,
        last_updated="2026-01-15T12:00:00Z",
    )


@router.get("/wallet/transactions")
async def get_wallet_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Get wallet transaction history"""
    return {"items": [], "total": 0, "page": page, "page_size": page_size}


# Statistics Endpoints
@router.get("/stats/summary", response_model=CryptoStatsResponse)
async def get_crypto_stats_summary():
    """Get crypto transaction statistics summary"""
    return CryptoStatsResponse(
        total_deposits_usdt=100000.0,
        total_deposits_krw=138000000.0,
        total_withdrawals_usdt=80000.0,
        total_withdrawals_krw=110400000.0,
        deposit_count=500,
        withdrawal_count=300,
        period="all_time",
    )


@router.get("/stats/daily")
async def get_crypto_stats_daily(
    days: int = Query(30, ge=1, le=90),
):
    """Get daily crypto statistics"""
    return {"items": [], "days": days}
