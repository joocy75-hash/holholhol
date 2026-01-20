"""Crypto API endpoints for deposit/withdrawal management.

Provides endpoints for:
- Exchange rate queries and history
- Deposit management (list, detail, approve, reject)
- Withdrawal management (list, detail, approve, reject)
- Hot wallet balance monitoring
- Transaction statistics
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_admin_db

router = APIRouter()


# ============================================================
# Pydantic Models
# ============================================================

# Exchange Rate
class ExchangeRateResponse(BaseModel):
    rate: float
    source: str
    timestamp: str


class ExchangeRateHistoryResponse(BaseModel):
    items: list[ExchangeRateResponse]


# Deposits
class DepositResponse(BaseModel):
    id: str
    user_id: str
    tx_hash: str
    from_address: str
    to_address: str
    amount_usdt: float
    amount_krw: int
    exchange_rate: float
    confirmations: int
    status: str
    detected_at: str
    confirmed_at: Optional[str]
    credited_at: Optional[str]


class PaginatedDeposits(BaseModel):
    items: list[dict]
    total: int
    page: int
    page_size: int
    total_pages: int


class DepositActionRequest(BaseModel):
    reason: Optional[str] = None
    note: Optional[str] = None


# Withdrawals
class WithdrawalResponse(BaseModel):
    id: str
    user_id: str
    to_address: str
    amount_usdt: float
    amount_krw: int
    exchange_rate: float
    network_fee_usdt: float
    network_fee_krw: int
    tx_hash: Optional[str]
    status: str
    requested_at: str
    approved_by: Optional[str]
    approved_at: Optional[str]
    processed_at: Optional[str]
    rejection_reason: Optional[str]


class PaginatedWithdrawals(BaseModel):
    items: list[dict]
    total: int
    page: int
    page_size: int
    total_pages: int


class WithdrawalActionRequest(BaseModel):
    two_factor_code: str
    reason: Optional[str] = None


# Wallet
class WalletBalanceResponse(BaseModel):
    address: str
    balance_usdt: float
    balance_krw: int
    pending_withdrawals_usdt: float
    pending_withdrawals_krw: int
    available_usdt: float
    available_krw: int
    exchange_rate: float
    last_updated: str


# Statistics
class CryptoStatsResponse(BaseModel):
    total_deposits_usdt: float
    total_deposits_krw: int
    total_withdrawals_usdt: float
    total_withdrawals_krw: int
    deposit_count: int
    withdrawal_count: int
    period: str


# ============================================================
# Exchange Rate Endpoints
# ============================================================

@router.get("/exchange-rate", response_model=ExchangeRateResponse)
async def get_exchange_rate():
    """Get current USDT/KRW exchange rate.

    Uses CoinGecko API with Binance fallback.
    Rates are cached in Redis for 30 seconds.
    """
    from app.services.crypto.ton_exchange_rate import TonExchangeRateService

    rate_service = TonExchangeRateService()
    try:
        rate = await rate_service.get_usdt_krw_rate()
        return ExchangeRateResponse(
            rate=float(rate),
            source="coingecko",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"환율 조회 실패: {e}")
    finally:
        await rate_service.close()


@router.get("/exchange-rate/history", response_model=ExchangeRateHistoryResponse)
async def get_exchange_rate_history(
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_admin_db),
):
    """Get exchange rate history.

    Args:
        hours: Number of hours to look back (max 168 = 1 week)
    """
    from app.models.crypto import ExchangeRateHistory

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    result = await db.execute(
        select(ExchangeRateHistory)
        .where(ExchangeRateHistory.recorded_at >= cutoff)
        .order_by(ExchangeRateHistory.recorded_at.asc())
    )
    records = result.scalars().all()

    items = [
        ExchangeRateResponse(
            rate=float(r.rate),
            source=r.source,
            timestamp=r.recorded_at.isoformat()
        )
        for r in records
    ]

    return ExchangeRateHistoryResponse(items=items)


# ============================================================
# Deposit Endpoints
# ============================================================

@router.get("/deposits", response_model=PaginatedDeposits)
async def list_deposits(
    status: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_admin_db),
):
    """List deposits with pagination and filtering.

    Query Parameters:
    - status: Filter by status (pending, confirming, confirmed, rejected)
    - user_id: Filter by user ID
    - page: Page number (1-indexed)
    - page_size: Items per page (max 100)
    """
    from app.services.crypto.deposit_service import DepositService

    service = DepositService(db)
    try:
        result = await service.list_deposits(
            status=status,
            user_id=user_id,
            page=page,
            limit=page_size,
        )
        return result
    finally:
        await service.close()


@router.get("/deposits/stats", response_model=dict)
async def get_deposit_stats(
    period_days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_admin_db),
):
    """Get deposit statistics.

    Returns pending, completed, and failed deposit counts and amounts.
    """
    from app.services.crypto.deposit_service import DepositService

    service = DepositService(db)
    try:
        stats = await service.get_deposit_stats(period_days=period_days)
        return stats
    finally:
        await service.close()


@router.get("/deposits/pending/count", response_model=dict)
async def get_pending_deposit_count(
    db: AsyncSession = Depends(get_admin_db),
):
    """Get count of pending deposit records.

    Useful for dashboard badges and notifications.
    """
    from app.services.crypto.deposit_service import DepositService

    service = DepositService(db)
    try:
        count = await service.get_pending_count()
        return {"count": count}
    finally:
        await service.close()


@router.get("/deposits/{deposit_id}")
async def get_deposit(
    deposit_id: str,
    db: AsyncSession = Depends(get_admin_db),
):
    """Get deposit details."""
    from app.services.crypto.deposit_service import DepositService

    service = DepositService(db)
    try:
        deposit = await service.get_deposit_detail(UUID(deposit_id))
        if not deposit:
            raise HTTPException(status_code=404, detail="입금 기록을 찾을 수 없습니다")
        return deposit
    except ValueError:
        raise HTTPException(status_code=400, detail="잘못된 입금 ID 형식입니다")
    finally:
        await service.close()


@router.post("/deposits/{deposit_id}/approve")
async def approve_deposit(
    deposit_id: str,
    request: Request,
    body: DepositActionRequest,
    db: AsyncSession = Depends(get_admin_db),
):
    """Manually approve a deposit.

    Use for stuck deposits that need manual intervention.
    """
    from app.services.crypto.deposit_service import (
        DepositService,
        DepositNotFoundError,
        DepositStatusError,
        MainAPIError,
    )

    # TODO: Add proper admin auth
    admin_id = "admin"
    ip_address = request.client.host if request.client else "unknown"

    service = DepositService(db)
    try:
        deposit = await service.approve_deposit_manual(
            deposit_id=UUID(deposit_id),
            admin_id=admin_id,
            note=body.note,
            ip_address=ip_address,
        )
        return {
            "message": "입금 승인이 완료되었습니다",
            "deposit": deposit,
        }
    except DepositNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DepositStatusError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except MainAPIError as e:
        raise HTTPException(status_code=502, detail=f"메인 서버 오류: {e}")
    except ValueError:
        raise HTTPException(status_code=400, detail="잘못된 입금 ID 형식입니다")
    finally:
        await service.close()


@router.post("/deposits/{deposit_id}/reject")
async def reject_deposit(
    deposit_id: str,
    request: Request,
    body: DepositActionRequest,
    db: AsyncSession = Depends(get_admin_db),
):
    """Reject a fraudulent or invalid deposit."""
    from app.services.crypto.deposit_service import (
        DepositService,
        DepositNotFoundError,
        DepositStatusError,
        DepositServiceError,
    )

    # TODO: Add proper admin auth
    admin_id = "admin"
    ip_address = request.client.host if request.client else "unknown"

    if not body.reason:
        raise HTTPException(status_code=400, detail="거부 사유를 입력해주세요")

    service = DepositService(db)
    try:
        deposit = await service.reject_deposit(
            deposit_id=UUID(deposit_id),
            admin_id=admin_id,
            reason=body.reason,
            ip_address=ip_address,
        )
        return {
            "message": "입금 거부가 완료되었습니다",
            "deposit": deposit,
        }
    except DepositNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DepositStatusError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except DepositServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError:
        raise HTTPException(status_code=400, detail="잘못된 입금 ID 형식입니다")
    finally:
        await service.close()


# ============================================================
# Withdrawal Endpoints
# ============================================================

@router.get("/withdrawals", response_model=PaginatedWithdrawals)
async def list_withdrawals(
    status: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_admin_db),
):
    """List withdrawals with pagination and filtering.

    Query Parameters:
    - status: Filter by status (pending, processing, completed, rejected)
    - user_id: Filter by user ID
    - page: Page number (1-indexed)
    - page_size: Items per page (max 100)
    """
    from app.services.crypto.withdrawal_service import WithdrawalService

    service = WithdrawalService(db)
    try:
        result = await service.list_withdrawals(
            status=status,
            user_id=user_id,
            page=page,
            limit=page_size,
        )
        return result
    finally:
        await service.close()


@router.get("/withdrawals/stats", response_model=dict)
async def get_withdrawal_stats(
    period_days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_admin_db),
):
    """Get withdrawal statistics.

    Returns pending, processing, completed, and rejected withdrawal counts and amounts.
    """
    from app.services.crypto.withdrawal_service import WithdrawalService

    service = WithdrawalService(db)
    try:
        stats = await service.get_withdrawal_stats(period_days=period_days)
        return stats
    finally:
        await service.close()


@router.get("/withdrawals/pending/count", response_model=dict)
async def get_pending_withdrawal_count(
    db: AsyncSession = Depends(get_admin_db),
):
    """Get count of pending withdrawal requests.

    Useful for dashboard badges and notifications.
    """
    from app.services.crypto.withdrawal_service import WithdrawalService

    service = WithdrawalService(db)
    try:
        count = await service.get_pending_count()
        return {"count": count}
    finally:
        await service.close()


@router.get("/withdrawals/{withdrawal_id}")
async def get_withdrawal(
    withdrawal_id: str,
    db: AsyncSession = Depends(get_admin_db),
):
    """Get detailed withdrawal information."""
    from app.services.crypto.withdrawal_service import WithdrawalService

    service = WithdrawalService(db)
    try:
        withdrawal = await service.get_withdrawal_detail(UUID(withdrawal_id))
        if not withdrawal:
            raise HTTPException(status_code=404, detail="출금 요청을 찾을 수 없습니다")
        return withdrawal
    except ValueError:
        raise HTTPException(status_code=400, detail="잘못된 출금 ID 형식입니다")
    finally:
        await service.close()


@router.post("/withdrawals/{withdrawal_id}/approve")
async def approve_withdrawal(
    withdrawal_id: str,
    request: Request,
    body: WithdrawalActionRequest,
    db: AsyncSession = Depends(get_admin_db),
):
    """Approve a pending withdrawal request.

    Requires 2FA code for security verification.
    Calls main backend to execute blockchain transaction.
    """
    from app.services.crypto.withdrawal_service import (
        WithdrawalService,
        WithdrawalNotFoundError,
        WithdrawalStatusError,
        MainAPIError,
    )

    # TODO: Add proper admin auth and 2FA verification
    admin_id = "admin"
    ip_address = request.client.host if request.client else "unknown"

    service = WithdrawalService(db)
    try:
        withdrawal = await service.approve_withdrawal(
            withdrawal_id=UUID(withdrawal_id),
            admin_id=admin_id,
            tx_hash=None,
            note=None,
            ip_address=ip_address,
        )
        return {
            "message": "출금 승인이 완료되었습니다",
            "withdrawal": withdrawal,
        }
    except WithdrawalNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WithdrawalStatusError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except MainAPIError as e:
        raise HTTPException(status_code=502, detail=f"메인 서버 오류: {e}")
    except ValueError:
        raise HTTPException(status_code=400, detail="잘못된 출금 ID 형식입니다")
    finally:
        await service.close()


@router.post("/withdrawals/{withdrawal_id}/reject")
async def reject_withdrawal(
    withdrawal_id: str,
    request: Request,
    body: WithdrawalActionRequest,
    db: AsyncSession = Depends(get_admin_db),
):
    """Reject a pending withdrawal request.

    Requires 2FA code and rejection reason.
    Refunds balance to user via main backend API.
    """
    from app.services.crypto.withdrawal_service import (
        WithdrawalService,
        WithdrawalNotFoundError,
        WithdrawalStatusError,
        MainAPIError,
        WithdrawalServiceError,
    )

    # TODO: Add proper admin auth and 2FA verification
    admin_id = "admin"
    ip_address = request.client.host if request.client else "unknown"

    service = WithdrawalService(db)
    try:
        withdrawal = await service.reject_withdrawal(
            withdrawal_id=UUID(withdrawal_id),
            admin_id=admin_id,
            reason=body.reason or "",
            ip_address=ip_address,
        )
        return {
            "message": "출금 거부가 완료되었습니다",
            "withdrawal": withdrawal,
        }
    except WithdrawalNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except WithdrawalStatusError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except MainAPIError as e:
        raise HTTPException(status_code=502, detail=f"메인 서버 오류: {e}")
    except WithdrawalServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError:
        raise HTTPException(status_code=400, detail="잘못된 출금 ID 형식입니다")
    finally:
        await service.close()


# ============================================================
# Wallet Endpoints
# ============================================================

@router.get("/wallet/balance", response_model=WalletBalanceResponse)
async def get_wallet_balance(
    db: AsyncSession = Depends(get_admin_db),
):
    """Get hot wallet balance with pending withdrawals.

    Returns:
    - Current blockchain balance (USDT)
    - Pending withdrawal sum (USDT)
    - Available balance (balance - pending)
    - KRW equivalents at current rate
    """
    from app.services.crypto.wallet_balance_service import (
        WalletBalanceService,
        WalletBalanceServiceError,
    )

    service = WalletBalanceService(db=db)
    try:
        balance = await service.get_current_balance()
        return WalletBalanceResponse(**balance)
    except WalletBalanceServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))
    finally:
        await service.close()


@router.get("/wallet/balance/history")
async def get_wallet_balance_history(
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_admin_db),
):
    """Get hot wallet balance history from snapshots."""
    from app.services.crypto.wallet_balance_service import WalletBalanceService

    service = WalletBalanceService(db=db)
    try:
        history = await service.get_balance_history(hours=hours)
        return {"items": history}
    finally:
        await service.close()


@router.get("/wallet/threshold")
async def check_wallet_threshold(
    db: AsyncSession = Depends(get_admin_db),
):
    """Check if wallet balance is below threshold."""
    from app.services.crypto.wallet_balance_service import (
        WalletBalanceService,
        WalletBalanceServiceError,
    )

    service = WalletBalanceService(db=db)
    try:
        result = await service.check_balance_threshold()
        return result
    except WalletBalanceServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))
    finally:
        await service.close()


# ============================================================
# Combined Statistics Endpoints
# ============================================================

@router.get("/stats/summary", response_model=CryptoStatsResponse)
async def get_crypto_stats_summary(
    db: AsyncSession = Depends(get_admin_db),
):
    """Get combined deposit and withdrawal statistics."""
    from app.services.crypto.deposit_service import DepositService
    from app.services.crypto.withdrawal_service import WithdrawalService

    deposit_service = DepositService(db)
    withdrawal_service = WithdrawalService(db)

    try:
        deposit_stats = await deposit_service.get_deposit_stats(period_days=365)
        withdrawal_stats = await withdrawal_service.get_withdrawal_stats(period_days=365)

        return CryptoStatsResponse(
            total_deposits_usdt=0.0,  # TODO: Calculate from stats
            total_deposits_krw=deposit_stats.get("total_completed_amount_krw", 0),
            total_withdrawals_usdt=0.0,  # TODO: Calculate from stats
            total_withdrawals_krw=withdrawal_stats.get("total_completed_amount_krw", 0),
            deposit_count=deposit_stats.get("total_completed_count", 0),
            withdrawal_count=withdrawal_stats.get("total_completed_count", 0),
            period="all_time",
        )
    finally:
        await deposit_service.close()
        await withdrawal_service.close()


@router.get("/stats/daily")
async def get_crypto_stats_daily(
    days: int = Query(30, ge=1, le=90),
):
    """Get daily crypto statistics.

    TODO: Implement aggregation by date.
    """
    return {"items": [], "days": days}


# ============================================================
# Withdrawal Automation Endpoints (Phase 8)
# ============================================================

class WithdrawalAutomationStatus(BaseModel):
    """Withdrawal automation status response."""
    executor_enabled: bool
    executor_running: bool
    executor_pending_count: int
    executor_retry_queue_size: int
    executor_auto_threshold_usdt: float
    monitor_running: bool
    monitor_tracking_count: int
    monitor_today_completed: int
    hot_wallet_usdt: float


@router.get("/automation/status", response_model=WithdrawalAutomationStatus)
async def get_automation_status(
    db: AsyncSession = Depends(get_admin_db),
):
    """Get withdrawal automation status.

    Returns status of:
    - WithdrawalExecutor (auto-execution of approved withdrawals)
    - WithdrawalMonitor (transaction confirmation tracking)
    """
    from app.config import get_settings
    settings = get_settings()

    # Get executor status
    executor_status = {
        "enabled": settings.withdrawal_auto_enabled,
        "running": False,
        "pending_count": 0,
        "retry_queue_size": 0,
        "auto_threshold_usdt": settings.withdrawal_auto_threshold_usdt,
        "hot_wallet_usdt": 0.0,
    }

    # Get monitor status
    monitor_status = {
        "running": False,
        "monitoring_count": 0,
        "today_completed": 0,
    }

    # Try to get live status from global instances
    try:
        from app.main import _withdrawal_executor, _withdrawal_monitor

        if _withdrawal_executor:
            executor_status = await _withdrawal_executor.get_executor_status()

        if _withdrawal_monitor:
            monitor_status = await _withdrawal_monitor.get_monitor_status()
    except ImportError:
        pass

    return WithdrawalAutomationStatus(
        executor_enabled=executor_status.get("enabled", False),
        executor_running=executor_status.get("running", False),
        executor_pending_count=executor_status.get("pending_count", 0),
        executor_retry_queue_size=executor_status.get("retry_queue_size", 0),
        executor_auto_threshold_usdt=executor_status.get("auto_threshold_usdt", 0.0),
        monitor_running=monitor_status.get("running", False),
        monitor_tracking_count=monitor_status.get("monitoring_count", 0),
        monitor_today_completed=monitor_status.get("today_completed", 0),
        hot_wallet_usdt=executor_status.get("hot_wallet_usdt", 0.0),
    )


@router.post("/withdrawals/{withdrawal_id}/execute")
async def execute_withdrawal(
    withdrawal_id: str,
    request: Request,
    db: AsyncSession = Depends(get_admin_db),
):
    """Manually execute a single withdrawal.

    This endpoint manually triggers execution for an approved withdrawal.
    Requires supervisor role.
    """
    from app.config import get_settings
    from app.database import AdminSessionLocal

    settings = get_settings()

    if not settings.withdrawal_auto_enabled:
        raise HTTPException(
            status_code=400,
            detail="출금 자동화가 비활성화되어 있습니다. WITHDRAWAL_AUTO_ENABLED=true로 설정하세요."
        )

    # TODO: Add proper admin auth and role check (supervisor required)
    admin_id = "admin"

    try:
        from app.services.crypto.withdrawal_executor import WithdrawalExecutor

        executor = WithdrawalExecutor(session_factory=AdminSessionLocal)
        try:
            success = await executor.execute_single(
                withdrawal_id=UUID(withdrawal_id),
                admin_id=admin_id,
            )

            if success:
                return {
                    "message": "출금 실행이 성공적으로 처리되었습니다",
                    "withdrawal_id": withdrawal_id,
                }
            else:
                raise HTTPException(
                    status_code=500,
                    detail="출금 실행에 실패했습니다. 로그를 확인하세요."
                )
        finally:
            await executor.close()

    except ValueError:
        raise HTTPException(status_code=400, detail="잘못된 출금 ID 형식입니다")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"출금 실행 오류: {str(e)}")


# ============================================================
# Crypto Statistics Endpoints (Phase 9)
# ============================================================

@router.get("/stats/summary/v2")
async def get_crypto_stats_summary_v2(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_admin_db),
):
    """암호화폐 요약 통계 조회 (v2).

    기간별 입출금 통계, 오늘 통계, 대기 건수를 포함합니다.
    """
    from app.services.crypto.crypto_stats_service import CryptoStatsService

    service = CryptoStatsService(db)
    try:
        return await service.get_summary_stats(days=days)
    finally:
        await service.close()


@router.get("/stats/daily/v2")
async def get_crypto_stats_daily_v2(
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_admin_db),
):
    """일별 입출금 통계 조회.

    날짜별 입금/출금 건수, 금액, 순유입량을 제공합니다.
    """
    from app.services.crypto.crypto_stats_service import CryptoStatsService

    service = CryptoStatsService(db)
    try:
        items = await service.get_daily_stats(days=days)
        return {"items": items, "days": days}
    finally:
        await service.close()


@router.get("/stats/hourly-patterns")
async def get_hourly_patterns(
    days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_admin_db),
):
    """시간대별 입출금 패턴 분석.

    0-23시 시간대별 입출금 패턴을 분석합니다.
    """
    from app.services.crypto.crypto_stats_service import CryptoStatsService

    service = CryptoStatsService(db)
    try:
        items = await service.get_hourly_patterns(days=days)
        return {"items": items, "analysis_days": days}
    finally:
        await service.close()


@router.get("/stats/top-users")
async def get_top_users(
    days: int = Query(30, ge=1, le=90),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_admin_db),
):
    """볼륨 상위 사용자 조회.

    지정 기간 동안 거래량이 가장 많은 사용자 목록입니다.
    """
    from app.services.crypto.crypto_stats_service import CryptoStatsService

    service = CryptoStatsService(db)
    try:
        items = await service.get_top_users(days=days, limit=limit)
        return {"items": items, "days": days, "limit": limit}
    finally:
        await service.close()


@router.get("/stats/exchange-rate-history")
async def get_exchange_rate_history(
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_admin_db),
):
    """환율 변동 히스토리 조회.

    지정 기간 동안의 USDT/KRW 환율 변동을 조회합니다.
    """
    from app.services.crypto.crypto_stats_service import CryptoStatsService

    service = CryptoStatsService(db)
    try:
        items = await service.get_exchange_rate_history(hours=hours)
        return {"items": items, "hours": hours}
    finally:
        await service.close()


@router.get("/stats/trend")
async def get_trend_analysis(
    days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_admin_db),
):
    """트렌드 분석.

    최근 N일과 그 이전 N일을 비교하여 트렌드를 분석합니다.
    """
    from app.services.crypto.crypto_stats_service import CryptoStatsService

    service = CryptoStatsService(db)
    try:
        return await service.get_trend_analysis(days=days)
    finally:
        await service.close()


# ============================================================
# Wallet Alert Endpoints (Phase 9)
# ============================================================

class WalletAlertStatusResponse(BaseModel):
    """지갑 알림 상태 응답."""
    is_low_balance: bool
    is_critical_balance: bool
    thresholds: dict
    last_alerts: dict
    last_alerted_balance_usdt: Optional[float]


class WalletAlertThresholdsRequest(BaseModel):
    """지갑 알림 임계값 업데이트 요청."""
    warning_usdt: Optional[float] = None
    critical_usdt: Optional[float] = None
    recovery_margin_usdt: Optional[float] = None
    cooldown_seconds: Optional[int] = None


@router.get("/wallet/alerts/status", response_model=WalletAlertStatusResponse)
async def get_wallet_alert_status():
    """지갑 잔액 알림 상태 조회.

    현재 알림 상태, 임계값, 마지막 알림 시간을 조회합니다.
    """
    try:
        from app.main import _wallet_alert_service

        if not _wallet_alert_service:
            raise HTTPException(
                status_code=503,
                detail="지갑 알림 서비스가 초기화되지 않았습니다"
            )

        status = await _wallet_alert_service.get_current_status()
        return WalletAlertStatusResponse(**status)

    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="지갑 알림 서비스를 불러올 수 없습니다"
        )


@router.put("/wallet/alerts/thresholds")
async def update_wallet_alert_thresholds(
    body: WalletAlertThresholdsRequest,
):
    """지갑 알림 임계값 업데이트.

    경고/위험 임계값, 복구 마진, 쿨다운 시간을 설정합니다.
    """
    try:
        from app.main import _wallet_alert_service

        if not _wallet_alert_service:
            raise HTTPException(
                status_code=503,
                detail="지갑 알림 서비스가 초기화되지 않았습니다"
            )

        updated = await _wallet_alert_service.update_thresholds(
            warning_usdt=body.warning_usdt,
            critical_usdt=body.critical_usdt,
            recovery_margin_usdt=body.recovery_margin_usdt,
            cooldown_seconds=body.cooldown_seconds,
        )

        return {
            "message": "알림 임계값이 업데이트되었습니다",
            "thresholds": updated,
        }

    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="지갑 알림 서비스를 불러올 수 없습니다"
        )


@router.post("/wallet/alerts/force-check")
async def force_wallet_alert_check(
    db: AsyncSession = Depends(get_admin_db),
):
    """지갑 잔액 수동 체크 및 알림 트리거.

    현재 잔액을 조회하고 알림 조건을 체크합니다.
    """
    from app.services.crypto.wallet_balance_service import (
        WalletBalanceService,
        WalletBalanceServiceError,
    )

    try:
        from app.main import _wallet_alert_service

        if not _wallet_alert_service:
            raise HTTPException(
                status_code=503,
                detail="지갑 알림 서비스가 초기화되지 않았습니다"
            )

        # Get current balance
        balance_service = WalletBalanceService(db=db)
        try:
            balance_data = await balance_service.get_current_balance()
        finally:
            await balance_service.close()

        # Force check
        result = await _wallet_alert_service.force_check(
            balance_usdt=balance_data["balance_usdt"],
            pending_usdt=balance_data["pending_withdrawals_usdt"],
        )

        return {
            "message": "지갑 잔액 체크가 완료되었습니다",
            "balance": {
                "balance_usdt": balance_data["balance_usdt"],
                "available_usdt": balance_data["available_usdt"],
                "pending_usdt": balance_data["pending_withdrawals_usdt"],
            },
            "alert_status": result,
        }

    except WalletBalanceServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="지갑 알림 서비스를 불러올 수 없습니다"
        )


# ============================================================
# Multi-Approval Endpoints (Phase 10)
# ============================================================

class ApprovalPolicyCreate(BaseModel):
    """승인 정책 생성 요청."""
    name: str
    description: Optional[str] = None
    min_amount_usdt: float
    max_amount_usdt: Optional[float] = None
    required_approvals: int
    expiry_minutes: int = 60
    priority: int = 0


class ApprovalPolicyUpdate(BaseModel):
    """승인 정책 업데이트 요청."""
    name: Optional[str] = None
    description: Optional[str] = None
    min_amount_usdt: Optional[float] = None
    max_amount_usdt: Optional[float] = None
    required_approvals: Optional[int] = None
    expiry_minutes: Optional[int] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class ApprovalActionRequest(BaseModel):
    """승인/거부 요청."""
    note: Optional[str] = None
    reason: Optional[str] = None  # 거부 시 필수


@router.get("/approvals/policies")
async def list_approval_policies(
    db: AsyncSession = Depends(get_admin_db),
):
    """승인 정책 목록 조회."""
    from app.services.crypto.multi_approval_service import MultiApprovalService

    service = MultiApprovalService(db)
    policies = await service.get_active_policies()

    return {
        "items": [
            {
                "id": str(p.id),
                "name": p.name,
                "description": p.description,
                "min_amount_usdt": float(p.min_amount_usdt),
                "max_amount_usdt": float(p.max_amount_usdt) if p.max_amount_usdt else None,
                "required_approvals": p.required_approvals,
                "expiry_minutes": p.expiry_minutes,
                "priority": p.priority,
                "is_active": p.is_active,
            }
            for p in policies
        ]
    }


@router.post("/approvals/policies")
async def create_approval_policy(
    body: ApprovalPolicyCreate,
    db: AsyncSession = Depends(get_admin_db),
):
    """승인 정책 생성."""
    from decimal import Decimal
    from app.services.crypto.multi_approval_service import MultiApprovalService

    service = MultiApprovalService(db)
    policy = await service.create_policy(
        name=body.name,
        description=body.description,
        min_amount_usdt=Decimal(str(body.min_amount_usdt)),
        max_amount_usdt=Decimal(str(body.max_amount_usdt)) if body.max_amount_usdt else None,
        required_approvals=body.required_approvals,
        expiry_minutes=body.expiry_minutes,
        priority=body.priority,
    )

    return {
        "message": "승인 정책이 생성되었습니다",
        "policy": {
            "id": str(policy.id),
            "name": policy.name,
        }
    }


@router.put("/approvals/policies/{policy_id}")
async def update_approval_policy(
    policy_id: str,
    body: ApprovalPolicyUpdate,
    db: AsyncSession = Depends(get_admin_db),
):
    """승인 정책 업데이트."""
    from decimal import Decimal
    from app.services.crypto.multi_approval_service import (
        MultiApprovalService,
        ApprovalNotFoundError,
    )

    service = MultiApprovalService(db)

    update_data = body.model_dump(exclude_unset=True)
    if "min_amount_usdt" in update_data and update_data["min_amount_usdt"] is not None:
        update_data["min_amount_usdt"] = Decimal(str(update_data["min_amount_usdt"]))
    if "max_amount_usdt" in update_data and update_data["max_amount_usdt"] is not None:
        update_data["max_amount_usdt"] = Decimal(str(update_data["max_amount_usdt"]))

    try:
        policy = await service.update_policy(UUID(policy_id), **update_data)
        return {
            "message": "승인 정책이 업데이트되었습니다",
            "policy": {
                "id": str(policy.id),
                "name": policy.name,
                "is_active": policy.is_active,
            }
        }
    except ApprovalNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError:
        raise HTTPException(status_code=400, detail="잘못된 정책 ID 형식입니다")


@router.get("/approvals/pending")
async def list_pending_approvals(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_admin_db),
):
    """대기 중인 다중 승인 요청 목록."""
    from app.services.crypto.multi_approval_service import MultiApprovalService

    service = MultiApprovalService(db)
    requests = await service.get_pending_requests(limit=limit)

    return {
        "items": [
            {
                "id": str(r.id),
                "withdrawal_id": r.withdrawal_id,
                "user_id": r.user_id,
                "amount_usdt": float(r.amount_usdt),
                "amount_krw": int(r.amount_krw),
                "to_address": r.to_address,
                "status": r.status.value,
                "required_approvals": r.required_approvals,
                "current_approvals": r.current_approvals,
                "expires_at": r.expires_at.isoformat(),
                "created_at": r.created_at.isoformat(),
                "approval_records": [
                    {
                        "admin_name": rec.admin_name,
                        "action": rec.action.value,
                        "note": rec.note,
                        "created_at": rec.created_at.isoformat(),
                    }
                    for rec in r.approval_records
                ],
            }
            for r in requests
        ],
        "total": len(requests),
    }


@router.get("/approvals/{request_id}")
async def get_approval_status(
    request_id: str,
    db: AsyncSession = Depends(get_admin_db),
):
    """승인 요청 상세 조회."""
    from app.services.crypto.multi_approval_service import (
        MultiApprovalService,
        ApprovalNotFoundError,
    )

    service = MultiApprovalService(db)

    try:
        status = await service.get_approval_status(UUID(request_id))
        return status
    except ApprovalNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError:
        raise HTTPException(status_code=400, detail="잘못된 요청 ID 형식입니다")


@router.post("/approvals/{request_id}/approve")
async def approve_withdrawal_request(
    request_id: str,
    request: Request,
    body: ApprovalActionRequest,
    db: AsyncSession = Depends(get_admin_db),
):
    """다중 승인 요청 승인."""
    from app.services.crypto.multi_approval_service import (
        MultiApprovalService,
        ApprovalNotFoundError,
        ApprovalExpiredError,
        DuplicateApprovalError,
        MultiApprovalError,
    )

    # TODO: 실제 인증된 관리자 정보 사용
    admin_id = "admin"
    admin_name = "관리자"
    ip_address = request.client.host if request.client else "unknown"

    service = MultiApprovalService(db)

    try:
        approval_request = await service.approve(
            request_id=UUID(request_id),
            admin_id=admin_id,
            admin_name=admin_name,
            ip_address=ip_address,
            note=body.note,
        )

        return {
            "message": "승인이 완료되었습니다",
            "status": approval_request.status.value,
            "current_approvals": approval_request.current_approvals,
            "required_approvals": approval_request.required_approvals,
            "is_fully_approved": approval_request.is_fully_approved,
        }

    except ApprovalNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ApprovalExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e))
    except DuplicateApprovalError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except MultiApprovalError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError:
        raise HTTPException(status_code=400, detail="잘못된 요청 ID 형식입니다")


@router.post("/approvals/{request_id}/reject")
async def reject_withdrawal_request(
    request_id: str,
    request: Request,
    body: ApprovalActionRequest,
    db: AsyncSession = Depends(get_admin_db),
):
    """다중 승인 요청 거부."""
    from app.services.crypto.multi_approval_service import (
        MultiApprovalService,
        ApprovalNotFoundError,
        ApprovalExpiredError,
        DuplicateApprovalError,
        MultiApprovalError,
    )

    if not body.reason:
        raise HTTPException(status_code=400, detail="거부 사유를 입력해주세요")

    # TODO: 실제 인증된 관리자 정보 사용
    admin_id = "admin"
    admin_name = "관리자"
    ip_address = request.client.host if request.client else "unknown"

    service = MultiApprovalService(db)

    try:
        approval_request = await service.reject(
            request_id=UUID(request_id),
            admin_id=admin_id,
            admin_name=admin_name,
            ip_address=ip_address,
            reason=body.reason,
        )

        return {
            "message": "거부가 완료되었습니다",
            "status": approval_request.status.value,
        }

    except ApprovalNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ApprovalExpiredError as e:
        raise HTTPException(status_code=410, detail=str(e))
    except DuplicateApprovalError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except MultiApprovalError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError:
        raise HTTPException(status_code=400, detail="잘못된 요청 ID 형식입니다")


@router.get("/approvals/stats")
async def get_approval_stats(
    db: AsyncSession = Depends(get_admin_db),
):
    """다중 승인 통계."""
    from app.services.crypto.multi_approval_service import MultiApprovalService

    service = MultiApprovalService(db)
    stats = await service.get_stats()

    return stats


# ============================================================
# Withdrawal Limit Endpoints (Phase 10)
# ============================================================

@router.get("/limits/vip-levels")
async def list_vip_limits(
    db: AsyncSession = Depends(get_admin_db),
):
    """VIP 등급별 출금 한도 목록 조회."""
    from app.services.crypto.withdrawal_limit_service import WithdrawalLimitService

    service = WithdrawalLimitService(db)
    limits = await service.get_all_vip_limits()

    return {"items": limits}


@router.get("/limits/user/{user_id}")
async def get_user_withdrawal_limits(
    user_id: str,
    vip_level: int = Query(0, ge=0, le=4),
    db: AsyncSession = Depends(get_admin_db),
):
    """사용자 출금 한도 현황 조회."""
    from app.services.crypto.withdrawal_limit_service import WithdrawalLimitService

    service = WithdrawalLimitService(db)
    status = await service.get_user_limit_status(user_id, vip_level)

    return status


@router.post("/limits/check")
async def check_withdrawal_limit(
    user_id: str = Query(...),
    amount_usdt: float = Query(..., gt=0),
    vip_level: int = Query(0, ge=0, le=4),
    db: AsyncSession = Depends(get_admin_db),
):
    """출금 한도 사전 확인.

    출금 요청 전에 한도를 확인합니다.
    """
    from decimal import Decimal
    from app.services.crypto.withdrawal_limit_service import (
        WithdrawalLimitService,
        WithdrawalLimitError,
        DailyLimitExceededError,
        TransactionLimitExceededError,
    )

    service = WithdrawalLimitService(db)

    try:
        result = await service.check_withdrawal_limit(
            user_id=user_id,
            amount_usdt=Decimal(str(amount_usdt)),
            vip_level=vip_level,
        )
        return result

    except TransactionLimitExceededError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DailyLimitExceededError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except WithdrawalLimitError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/limits/daily-stats")
async def get_daily_withdrawal_stats(
    db: AsyncSession = Depends(get_admin_db),
):
    """전체 일별 출금 통계 조회."""
    from app.services.crypto.withdrawal_limit_service import WithdrawalLimitService

    service = WithdrawalLimitService(db)
    stats = await service.get_global_daily_stats()

    return stats


# ============================================================
# Telegram Alert Endpoints (Phase 10)
# ============================================================

class TelegramTestRequest(BaseModel):
    """Telegram 테스트 알림 요청."""
    title: str = "테스트 알림"
    message: str = "Admin Backend에서 전송한 테스트 메시지입니다."
    level: str = "info"  # info, warning, critical


@router.get("/telegram/status")
async def get_telegram_status():
    """Telegram 알림 설정 상태 조회."""
    from app.services.telegram_alert_service import get_telegram_service

    service = get_telegram_service()

    return {
        "configured": service.is_configured,
        "bot_token_set": bool(service.bot_token),
        "chat_id_set": bool(service.chat_id),
    }


@router.post("/telegram/test")
async def send_telegram_test(
    body: TelegramTestRequest,
):
    """Telegram 테스트 알림 전송."""
    from app.services.telegram_alert_service import (
        get_telegram_service,
        AlertLevel,
    )

    service = get_telegram_service()

    if not service.is_configured:
        raise HTTPException(
            status_code=400,
            detail="Telegram이 설정되지 않았습니다. TELEGRAM_BOT_TOKEN과 TELEGRAM_ADMIN_CHAT_ID를 설정하세요."
        )

    level_map = {
        "info": AlertLevel.INFO,
        "warning": AlertLevel.WARNING,
        "critical": AlertLevel.CRITICAL,
    }
    level = level_map.get(body.level, AlertLevel.INFO)

    success = await service.send_alert(
        title=body.title,
        message=body.message,
        level=level,
    )

    if success:
        return {"message": "테스트 알림이 전송되었습니다", "success": True}
    else:
        raise HTTPException(
            status_code=500,
            detail="Telegram 알림 전송에 실패했습니다. 로그를 확인하세요."
        )
