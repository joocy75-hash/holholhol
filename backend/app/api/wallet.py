"""Wallet API endpoints for deposit/withdrawal operations.

Phase 5.9: REST API for wallet operations.

Endpoints:
- GET /wallet/balance - Get user balance
- GET /wallet/deposit-address/{crypto_type} - Get deposit address
- POST /wallet/withdraw - Request withdrawal
- POST /wallet/withdraw/{id}/cancel - Cancel pending withdrawal
- GET /wallet/transactions - Get transaction history
- GET /wallet/rates - Get current exchange rates
- POST /wallet/webhook/deposit - Internal deposit webhook (secured)
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wallet import CryptoType, TransactionStatus, TransactionType
from app.services.audit import get_audit_service
from app.services.crypto_deposit import CryptoDepositService, DepositError
from app.services.crypto_withdrawal import (
    CryptoWithdrawalService,
    InsufficientBalanceError,
    WithdrawalError,
    WithdrawalLimitError,
)
from app.services.exchange_rate import (
    ExchangeRateError,
    get_exchange_rate_service,
)
from app.services.wallet import WalletService
from app.utils.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wallet", tags=["Wallet"])


# ============================================================
# Pydantic Schemas
# ============================================================


class BalanceResponse(BaseModel):
    """Balance response."""

    krw_balance: int = Field(..., description="Available KRW balance")
    pending_withdrawal: int = Field(
        ..., description="KRW locked for pending withdrawals"
    )
    total_balance: int = Field(..., description="Total KRW (available + pending)")


class DepositAddressResponse(BaseModel):
    """Deposit address response."""

    crypto_type: CryptoType
    address: str
    min_deposit: str = Field(..., description="Minimum deposit amount")


class WithdrawRequest(BaseModel):
    """Withdrawal request."""

    krw_amount: int = Field(
        ..., ge=10000, le=100000000, description="Amount in KRW (min: 10000)"
    )
    crypto_type: CryptoType
    crypto_address: str = Field(
        ..., min_length=26, max_length=100, description="Destination address"
    )


class WithdrawResponse(BaseModel):
    """Withdrawal response."""

    transaction_id: str
    status: TransactionStatus
    krw_amount: int
    crypto_type: CryptoType
    crypto_amount: str
    crypto_address: str
    estimated_arrival: str = Field(
        ..., description="Estimated processing time (24h pending)"
    )


class TransactionResponse(BaseModel):
    """Transaction response."""

    id: str
    tx_type: TransactionType
    status: TransactionStatus
    krw_amount: int
    krw_balance_after: int
    crypto_type: CryptoType | None = None
    crypto_amount: str | None = None
    crypto_tx_hash: str | None = None
    description: str | None = None
    created_at: str


class ExchangeRatesResponse(BaseModel):
    """Exchange rates response."""

    btc_krw: int | None = None
    eth_krw: int | None = None
    usdt_krw: int | None = None
    usdc_krw: int | None = None
    updated_at: str


class DepositWebhookRequest(BaseModel):
    """Internal deposit webhook request."""

    crypto_type: CryptoType
    tx_hash: str = Field(..., min_length=10)
    address: str
    amount: str
    confirmations: int = Field(..., ge=0)
    secret: str = Field(..., description="Webhook secret for authentication")


# ============================================================
# Dependency for getting current user ID
# ============================================================


async def get_current_user_id(request: Request) -> str:
    """Get current user ID from request state.

    This should be set by authentication middleware.
    """
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user_id


# ============================================================
# Endpoints
# ============================================================


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> BalanceResponse:
    """Get user's wallet balance."""
    from app.models.user import User

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return BalanceResponse(
        krw_balance=user.krw_balance,
        pending_withdrawal=user.pending_withdrawal_krw,
        total_balance=user.krw_balance + user.pending_withdrawal_krw,
    )


@router.get(
    "/deposit-address/{crypto_type}",
    response_model=DepositAddressResponse,
)
async def get_deposit_address(
    crypto_type: CryptoType,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> DepositAddressResponse:
    """Get deposit address for a cryptocurrency."""
    service = CryptoDepositService(session)

    address = await service.get_deposit_address(user_id, crypto_type)

    min_deposits = {
        CryptoType.BTC: "0.0001",
        CryptoType.ETH: "0.001",
        CryptoType.USDT: "10",
        CryptoType.USDC: "10",
    }

    return DepositAddressResponse(
        crypto_type=crypto_type,
        address=address,
        min_deposit=min_deposits[crypto_type],
    )


@router.post("/withdraw", response_model=WithdrawResponse)
async def request_withdrawal(
    request_data: WithdrawRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> WithdrawResponse:
    """Request cryptocurrency withdrawal."""
    service = CryptoWithdrawalService(session)

    try:
        tx = await service.request_withdrawal(
            user_id=user_id,
            krw_amount=request_data.krw_amount,
            crypto_type=request_data.crypto_type,
            crypto_address=request_data.crypto_address,
        )
        await session.commit()

        # Log to audit
        audit = get_audit_service()
        await audit.log_transaction(tx)

        return WithdrawResponse(
            transaction_id=tx.id,
            status=tx.status,
            krw_amount=abs(tx.krw_amount),
            crypto_type=tx.crypto_type,
            crypto_amount=tx.crypto_amount,
            crypto_address=tx.crypto_address,
            estimated_arrival="24 hours (security pending period)",
        )

    except InsufficientBalanceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except WithdrawalLimitError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except WithdrawalError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/withdraw/{transaction_id}/cancel")
async def cancel_withdrawal(
    transaction_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Cancel a pending withdrawal."""
    service = CryptoWithdrawalService(session)

    try:
        await service.cancel_withdrawal(user_id, transaction_id)
        await session.commit()

        return {"status": "cancelled", "transaction_id": transaction_id}

    except WithdrawalError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/transactions", response_model=list[TransactionResponse])
async def get_transactions(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
    tx_type: TransactionType | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[TransactionResponse]:
    """Get user's transaction history."""
    service = WalletService(session)

    transactions = await service.get_transactions(
        user_id=user_id,
        limit=limit,
        offset=offset,
        tx_type=tx_type,
    )

    return [
        TransactionResponse(
            id=tx.id,
            tx_type=tx.tx_type,
            status=tx.status,
            krw_amount=tx.krw_amount,
            krw_balance_after=tx.krw_balance_after,
            crypto_type=tx.crypto_type,
            crypto_amount=tx.crypto_amount,
            crypto_tx_hash=tx.crypto_tx_hash,
            description=tx.description,
            created_at=tx.created_at.isoformat(),
        )
        for tx in transactions
    ]


@router.get("/rates", response_model=ExchangeRatesResponse)
async def get_exchange_rates() -> ExchangeRatesResponse:
    """Get current cryptocurrency exchange rates."""
    service = get_exchange_rate_service()

    try:
        rates = await service.get_all_rates()

        from datetime import datetime

        return ExchangeRatesResponse(
            btc_krw=rates.get(CryptoType.BTC),
            eth_krw=rates.get(CryptoType.ETH),
            usdt_krw=rates.get(CryptoType.USDT),
            usdc_krw=rates.get(CryptoType.USDC),
            updated_at=datetime.utcnow().isoformat(),
        )

    except ExchangeRateError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/webhook/deposit", include_in_schema=False)
async def deposit_webhook(
    webhook: DepositWebhookRequest,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Internal webhook for deposit notifications.

    This endpoint is called by the payment gateway when a deposit is detected.
    It's secured by a secret token and not exposed in API docs.
    """
    import os

    # Validate webhook secret
    expected_secret = os.environ.get("DEPOSIT_WEBHOOK_SECRET", "dev-secret")
    if webhook.secret != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    service = CryptoDepositService(session)

    try:
        tx = await service.handle_deposit_webhook(
            crypto_type=webhook.crypto_type,
            tx_hash=webhook.tx_hash,
            address=webhook.address,
            amount=webhook.amount,
            confirmations=webhook.confirmations,
        )

        if tx:
            await session.commit()

            # Log to audit
            audit = get_audit_service()
            await audit.log_transaction(tx)

            return {
                "status": "processed",
                "transaction_id": tx.id,
                "krw_amount": tx.krw_amount,
            }
        else:
            return {
                "status": "pending",
                "message": "Waiting for confirmations",
            }

    except DepositError as e:
        logger.error(f"Deposit webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
