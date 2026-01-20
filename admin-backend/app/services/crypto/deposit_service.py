"""Deposit Service for admin crypto deposit management.

Handles the deposit monitoring and management workflow including:
- Listing and filtering deposit records
- Statistics and pending counts
- Manual approval (for stuck or manual deposits)
- Rejection (for fraudulent deposits)
- Comprehensive audit logging
"""

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from app.config import get_settings
from app.models.crypto import CryptoDeposit, TransactionStatus
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)
settings = get_settings()


# ============================================================
# Custom Exceptions
# ============================================================

class DepositServiceError(Exception):
    """입금 서비스 기본 예외"""
    pass


class DepositNotFoundError(DepositServiceError):
    """입금 기록을 찾을 수 없음"""
    pass


class DepositStatusError(DepositServiceError):
    """입금 상태가 작업에 적합하지 않음"""
    pass


class MainAPIError(DepositServiceError):
    """메인 백엔드 API 호출 실패"""
    pass


# ============================================================
# Deposit Service
# ============================================================

class DepositService:
    """Admin-side crypto deposit management service.

    Responsibilities:
    - Query deposit records from admin DB
    - Provide statistics and pending counts
    - Manual approve deposits (for stuck transactions)
    - Reject fraudulent deposits
    - Create audit logs for all actions

    Does NOT handle:
    - Automatic deposit detection (handled by TonDepositMonitor)
    - Blockchain confirmations (handled by TonDepositMonitor)
    """

    def __init__(
        self,
        db: AsyncSession,
        main_api_url: Optional[str] = None,
        main_api_key: Optional[str] = None,
    ):
        """Initialize deposit service.

        Args:
            db: Database session
            main_api_url: Main backend API URL for balance updates
            main_api_key: API key for main backend
        """
        self.db = db
        self.main_api_url = main_api_url or settings.main_api_url
        self.main_api_key = main_api_key or settings.main_api_key
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                headers={"X-API-Key": self.main_api_key},
            )
        return self._http_client

    async def close(self):
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    # ============================================================
    # Query Methods
    # ============================================================

    async def list_deposits(
        self,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """List deposit records with pagination and filters.

        Args:
            status: Filter by status (pending, confirming, confirmed, etc.)
            user_id: Filter by user ID
            page: Page number (1-indexed)
            limit: Items per page

        Returns:
            dict: {items, total, page, page_size, total_pages}
        """
        offset = (page - 1) * limit

        # Build query conditions
        conditions = []
        if status:
            conditions.append(CryptoDeposit.status == status)
        if user_id:
            conditions.append(CryptoDeposit.user_id == user_id)

        # Count query
        count_query = select(func.count()).select_from(CryptoDeposit)
        if conditions:
            count_query = count_query.where(and_(*conditions))

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # List query
        list_query = (
            select(CryptoDeposit)
            .order_by(CryptoDeposit.detected_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if conditions:
            list_query = list_query.where(and_(*conditions))

        result = await self.db.execute(list_query)
        deposits = result.scalars().all()

        items = [self._deposit_to_dict(d) for d in deposits]
        total_pages = (total + limit - 1) // limit if total > 0 else 1

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": limit,
            "total_pages": total_pages,
        }

    async def get_deposit_detail(self, deposit_id: UUID) -> Optional[dict]:
        """Get detailed information about a specific deposit.

        Args:
            deposit_id: Deposit UUID

        Returns:
            dict or None if not found
        """
        result = await self.db.execute(
            select(CryptoDeposit).where(CryptoDeposit.id == deposit_id)
        )
        deposit = result.scalar_one_or_none()

        if not deposit:
            return None

        return self._deposit_to_dict(deposit, include_details=True)

    async def get_deposit_stats(self, period_days: int = 7) -> dict:
        """Get deposit statistics.

        Args:
            period_days: Number of days to look back

        Returns:
            dict: Statistics including pending, completed counts and amounts
        """
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_start = now - timedelta(days=period_days)

        # Pending/Confirming count and amount
        pending_query = select(
            func.count(),
            func.coalesce(func.sum(CryptoDeposit.amount_krw), 0)
        ).where(
            CryptoDeposit.status.in_([
                TransactionStatus.PENDING,
                TransactionStatus.CONFIRMING
            ])
        )

        pending_result = await self.db.execute(pending_query)
        pending_row = pending_result.one()
        pending_count = pending_row[0] or 0
        pending_amount_krw = int(pending_row[1]) if pending_row[1] else 0

        # Today's confirmed/completed
        today_completed_query = select(
            func.count(),
            func.coalesce(func.sum(CryptoDeposit.amount_krw), 0)
        ).where(
            and_(
                CryptoDeposit.status.in_([
                    TransactionStatus.CONFIRMED,
                    TransactionStatus.COMPLETED
                ]),
                CryptoDeposit.credited_at >= today_start
            )
        )

        today_result = await self.db.execute(today_completed_query)
        today_row = today_result.one()
        today_completed_count = today_row[0] or 0
        today_completed_amount_krw = int(today_row[1]) if today_row[1] else 0

        # Total completed (all time)
        total_completed_query = select(
            func.count(),
            func.coalesce(func.sum(CryptoDeposit.amount_krw), 0)
        ).where(
            CryptoDeposit.status.in_([
                TransactionStatus.CONFIRMED,
                TransactionStatus.COMPLETED
            ])
        )

        total_result = await self.db.execute(total_completed_query)
        total_row = total_result.one()
        total_completed_count = total_row[0] or 0
        total_completed_amount_krw = int(total_row[1]) if total_row[1] else 0

        # Today's rejected/failed
        today_failed_query = select(func.count()).where(
            and_(
                CryptoDeposit.status.in_([
                    TransactionStatus.REJECTED,
                    TransactionStatus.FAILED
                ]),
                CryptoDeposit.confirmed_at >= today_start
            )
        )

        failed_result = await self.db.execute(today_failed_query)
        today_failed_count = failed_result.scalar() or 0

        # Confirming count (blockchain confirmations in progress)
        confirming_query = select(func.count()).where(
            CryptoDeposit.status == TransactionStatus.CONFIRMING
        )

        confirming_result = await self.db.execute(confirming_query)
        confirming_count = confirming_result.scalar() or 0

        return {
            "pending_count": pending_count,
            "pending_amount_krw": pending_amount_krw,
            "confirming_count": confirming_count,
            "today_completed_count": today_completed_count,
            "today_completed_amount_krw": today_completed_amount_krw,
            "today_failed_count": today_failed_count,
            "total_completed_count": total_completed_count,
            "total_completed_amount_krw": total_completed_amount_krw,
        }

    async def get_pending_count(self) -> int:
        """Get count of pending/confirming deposit records.

        Returns:
            int: Number of pending deposits
        """
        result = await self.db.execute(
            select(func.count()).select_from(CryptoDeposit).where(
                CryptoDeposit.status.in_([
                    TransactionStatus.PENDING,
                    TransactionStatus.CONFIRMING
                ])
            )
        )
        return result.scalar() or 0

    # ============================================================
    # Action Methods
    # ============================================================

    async def approve_deposit_manual(
        self,
        deposit_id: UUID,
        admin_id: str,
        note: Optional[str] = None,
        ip_address: str = "unknown",
    ) -> dict:
        """Manually approve a pending deposit.

        Use this for deposits that are stuck or need manual intervention.
        This calls the main backend API to credit the user's balance.

        Args:
            deposit_id: Deposit UUID
            admin_id: Admin user ID performing the action
            note: Optional admin note
            ip_address: IP address of the admin

        Returns:
            dict: Updated deposit data

        Raises:
            DepositNotFoundError: Deposit not found
            DepositStatusError: Deposit is not in pending/confirming status
            MainAPIError: Main backend API call failed
        """
        # Get deposit
        result = await self.db.execute(
            select(CryptoDeposit).where(CryptoDeposit.id == deposit_id)
        )
        deposit = result.scalar_one_or_none()

        if not deposit:
            raise DepositNotFoundError(f"입금 기록을 찾을 수 없습니다: {deposit_id}")

        # 이미 완료된 입금은 다시 승인할 수 없음
        if deposit.status in [TransactionStatus.CONFIRMED, TransactionStatus.COMPLETED]:
            raise DepositStatusError(
                f"입금이 이미 완료되었습니다. 현재 상태: {deposit.status}"
            )

        if deposit.status == TransactionStatus.REJECTED:
            raise DepositStatusError("거부된 입금은 승인할 수 없습니다.")

        try:
            # 멱등성 키 생성 (중복 처리 방지)
            idempotency_key = f"deposit_approve_{deposit_id}_{admin_id}"

            # Call main backend API to credit user balance
            api_response = await self._call_main_api_with_retry(
                endpoint="/api/wallet/deposit/credit",
                method="POST",
                data={
                    "deposit_id": str(deposit_id),
                    "user_id": deposit.user_id,
                    "amount_krw": int(deposit.amount_krw),
                    "amount_usdt": str(deposit.amount_usdt),
                    "tx_hash": deposit.tx_hash,
                    "admin_id": admin_id,
                    "note": note,
                    "idempotency_key": idempotency_key,
                }
            )

            # Update local record
            deposit.status = TransactionStatus.CONFIRMED
            deposit.confirmed_at = datetime.now(timezone.utc)
            deposit.credited_at = datetime.now(timezone.utc)

            # Create audit log
            await self._create_audit_log(
                action="deposit_approved_manual",
                target_id=str(deposit_id),
                admin_id=admin_id,
                ip_address=ip_address,
                details={
                    "user_id": deposit.user_id,
                    "tx_hash": deposit.tx_hash,
                    "from_address": deposit.from_address,
                    "amount_usdt": str(deposit.amount_usdt),
                    "amount_krw": str(deposit.amount_krw),
                    "note": note,
                    "api_response": api_response,
                },
            )

            await self.db.commit()
            await self.db.refresh(deposit)

            logger.info(
                f"입금 수동 승인 완료: {deposit_id} by admin {admin_id} from IP {ip_address}"
            )

            return self._deposit_to_dict(deposit, include_details=True)

        except MainAPIError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"입금 수동 승인 실패: {deposit_id} - {e}")
            raise DepositServiceError(f"입금 승인 처리 중 오류 발생: {e}")

    async def reject_deposit(
        self,
        deposit_id: UUID,
        admin_id: str,
        reason: str,
        ip_address: str = "unknown",
    ) -> dict:
        """Reject a deposit (for fraudulent or invalid deposits).

        This marks the deposit as rejected and does NOT credit the user.
        Use with caution - legitimate deposits should not be rejected.

        Args:
            deposit_id: Deposit UUID
            admin_id: Admin user ID performing the action
            reason: Rejection reason (required)
            ip_address: IP address of the admin

        Returns:
            dict: Updated deposit data

        Raises:
            DepositNotFoundError: Deposit not found
            DepositStatusError: Deposit is not in pending status
            DepositServiceError: Reason is empty
        """
        if not reason or not reason.strip():
            raise DepositServiceError("거부 사유를 입력해주세요.")

        # Get deposit
        result = await self.db.execute(
            select(CryptoDeposit).where(CryptoDeposit.id == deposit_id)
        )
        deposit = result.scalar_one_or_none()

        if not deposit:
            raise DepositNotFoundError(f"입금 기록을 찾을 수 없습니다: {deposit_id}")

        # 이미 완료된 입금은 거부할 수 없음
        if deposit.status in [TransactionStatus.CONFIRMED, TransactionStatus.COMPLETED]:
            raise DepositStatusError(
                f"이미 완료된 입금은 거부할 수 없습니다. 현재 상태: {deposit.status}"
            )

        if deposit.status == TransactionStatus.REJECTED:
            raise DepositStatusError("이미 거부된 입금입니다.")

        try:
            # Update local record (입금 거부는 메인 API 호출 불필요 - 잔액 변경 없음)
            deposit.status = TransactionStatus.REJECTED
            deposit.confirmed_at = datetime.now(timezone.utc)

            # Create audit log
            await self._create_audit_log(
                action="deposit_rejected",
                target_id=str(deposit_id),
                admin_id=admin_id,
                ip_address=ip_address,
                details={
                    "user_id": deposit.user_id,
                    "tx_hash": deposit.tx_hash,
                    "from_address": deposit.from_address,
                    "amount_usdt": str(deposit.amount_usdt),
                    "amount_krw": str(deposit.amount_krw),
                    "reason": reason.strip(),
                },
            )

            await self.db.commit()
            await self.db.refresh(deposit)

            logger.info(
                f"입금 거부 완료: {deposit_id} by admin {admin_id} - 사유: {reason}"
            )

            return self._deposit_to_dict(deposit, include_details=True)

        except Exception as e:
            await self.db.rollback()
            logger.error(f"입금 거부 실패: {deposit_id} - {e}")
            raise DepositServiceError(f"입금 거부 처리 중 오류 발생: {e}")

    # ============================================================
    # Helper Methods
    # ============================================================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def _call_main_api_with_retry(
        self,
        endpoint: str,
        method: str = "POST",
        data: Optional[dict] = None,
    ) -> dict:
        """Call main backend API with retry logic.

        Args:
            endpoint: API endpoint path
            method: HTTP method
            data: Request body data

        Returns:
            dict: API response data

        Raises:
            MainAPIError: If API call fails after retries
        """
        try:
            client = await self._get_http_client()

            response = await client.request(
                method=method,
                url=f"{self.main_api_url}{endpoint}",
                json=data,
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise DepositNotFoundError("메인 서버에서 입금 기록을 찾을 수 없습니다.")
            elif response.status_code == 409:
                # Conflict - already processed
                error_detail = response.json().get("detail", "이미 처리된 입금입니다.")
                raise DepositStatusError(error_detail)
            else:
                error_detail = response.json().get("detail", "알 수 없는 오류")
                raise MainAPIError(
                    f"메인 API 오류 ({response.status_code}): {error_detail}"
                )

        except (DepositNotFoundError, DepositStatusError):
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP 오류 발생: {e}")
            raise MainAPIError(f"메인 서버 통신 오류: {e}")

    async def _create_audit_log(
        self,
        action: str,
        target_id: str,
        admin_id: str,
        ip_address: str,
        details: dict,
    ):
        """Create audit log entry.

        Args:
            action: Action type (e.g., "deposit_approved_manual")
            target_id: Target deposit ID
            admin_id: Admin user ID
            ip_address: Admin IP address
            details: Additional details as JSONB
        """
        audit_log = AuditLog(
            action=action,
            target_type="crypto_deposit",
            target_id=target_id,
            admin_user_id=admin_id,
            ip_address=ip_address,
            details=details,
        )
        self.db.add(audit_log)

    def _deposit_to_dict(
        self,
        deposit: CryptoDeposit,
        include_details: bool = False,
    ) -> dict:
        """Convert deposit model to dictionary.

        Args:
            deposit: CryptoDeposit model instance
            include_details: Include additional details for detail view

        Returns:
            dict: Deposit data
        """
        data = {
            "id": str(deposit.id),
            "user_id": deposit.user_id,
            "tx_hash": deposit.tx_hash,
            "from_address": deposit.from_address,
            "to_address": deposit.to_address,
            "amount_usdt": float(deposit.amount_usdt),
            "amount_krw": int(deposit.amount_krw),
            "exchange_rate": float(deposit.exchange_rate),
            "confirmations": deposit.confirmations,
            "status": deposit.status.value if deposit.status else None,
            "detected_at": deposit.detected_at.isoformat() if deposit.detected_at else None,
            "confirmed_at": deposit.confirmed_at.isoformat() if deposit.confirmed_at else None,
            "credited_at": deposit.credited_at.isoformat() if deposit.credited_at else None,
        }

        if include_details:
            data["created_at"] = deposit.created_at.isoformat() if deposit.created_at else None
            data["updated_at"] = deposit.updated_at.isoformat() if deposit.updated_at else None

        return data
