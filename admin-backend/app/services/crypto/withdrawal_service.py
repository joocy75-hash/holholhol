"""Withdrawal Service for admin crypto withdrawal management.

Handles the withdrawal approval/rejection workflow including:
- Listing and filtering withdrawal requests
- Statistics and pending counts
- Approval (with main backend API call for blockchain execution)
- Rejection (with balance restoration)
- Comprehensive audit logging
"""

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy import select, func, text, and_
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from app.config import get_settings
from app.models.crypto import CryptoWithdrawal, TransactionStatus
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)
settings = get_settings()


# ============================================================
# Custom Exceptions
# ============================================================

class WithdrawalServiceError(Exception):
    """출금 서비스 기본 예외"""
    pass


class WithdrawalNotFoundError(WithdrawalServiceError):
    """출금 요청을 찾을 수 없음"""
    pass


class WithdrawalStatusError(WithdrawalServiceError):
    """출금 상태가 작업에 적합하지 않음"""
    pass


class MainAPIError(WithdrawalServiceError):
    """메인 백엔드 API 호출 실패"""
    pass


# ============================================================
# Withdrawal Service
# ============================================================

class WithdrawalService:
    """Admin-side crypto withdrawal management service.

    Responsibilities:
    - Query withdrawal requests from admin DB
    - Provide statistics and pending counts
    - Approve withdrawals (call main backend API)
    - Reject withdrawals (call main backend API)
    - Create audit logs for all actions

    Does NOT handle:
    - Blockchain transactions (handled by main backend)
    - User-facing withdrawal creation (handled by main backend)
    """

    def __init__(
        self,
        db: AsyncSession,
        main_api_url: Optional[str] = None,
        main_api_key: Optional[str] = None,
    ):
        """Initialize withdrawal service.

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

    async def list_withdrawals(
        self,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """List withdrawal requests with pagination and filters.

        Args:
            status: Filter by status (pending, processing, completed, rejected, etc.)
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
            conditions.append(CryptoWithdrawal.status == status)
        if user_id:
            conditions.append(CryptoWithdrawal.user_id == user_id)

        # Count query
        count_query = select(func.count()).select_from(CryptoWithdrawal)
        if conditions:
            count_query = count_query.where(and_(*conditions))

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # List query
        list_query = (
            select(CryptoWithdrawal)
            .order_by(CryptoWithdrawal.requested_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if conditions:
            list_query = list_query.where(and_(*conditions))

        result = await self.db.execute(list_query)
        withdrawals = result.scalars().all()

        items = [self._withdrawal_to_dict(w) for w in withdrawals]
        total_pages = (total + limit - 1) // limit if total > 0 else 1

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": limit,
            "total_pages": total_pages,
        }

    async def get_withdrawal_detail(self, withdrawal_id: UUID) -> Optional[dict]:
        """Get detailed information about a specific withdrawal.

        Args:
            withdrawal_id: Withdrawal UUID

        Returns:
            dict or None if not found
        """
        result = await self.db.execute(
            select(CryptoWithdrawal).where(CryptoWithdrawal.id == withdrawal_id)
        )
        withdrawal = result.scalar_one_or_none()

        if not withdrawal:
            return None

        return self._withdrawal_to_dict(withdrawal, include_details=True)

    async def get_withdrawal_stats(self, period_days: int = 7) -> dict:
        """Get withdrawal statistics.

        Args:
            period_days: Number of days to look back for "today" and "period" stats

        Returns:
            dict: Statistics including pending, completed, rejected counts and amounts
        """
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_start = now - timedelta(days=period_days)

        # Pending count and amount
        pending_query = select(
            func.count(),
            func.coalesce(func.sum(CryptoWithdrawal.amount_krw), 0)
        ).where(CryptoWithdrawal.status == TransactionStatus.PENDING)

        pending_result = await self.db.execute(pending_query)
        pending_row = pending_result.one()
        pending_count = pending_row[0] or 0
        pending_amount_krw = int(pending_row[1]) if pending_row[1] else 0

        # Today's completed
        today_completed_query = select(
            func.count(),
            func.coalesce(func.sum(CryptoWithdrawal.amount_krw), 0)
        ).where(
            and_(
                CryptoWithdrawal.status == TransactionStatus.COMPLETED,
                CryptoWithdrawal.processed_at >= today_start
            )
        )

        today_result = await self.db.execute(today_completed_query)
        today_row = today_result.one()
        today_completed_count = today_row[0] or 0
        today_completed_amount_krw = int(today_row[1]) if today_row[1] else 0

        # Total completed (all time)
        total_completed_query = select(
            func.count(),
            func.coalesce(func.sum(CryptoWithdrawal.amount_krw), 0)
        ).where(CryptoWithdrawal.status == TransactionStatus.COMPLETED)

        total_result = await self.db.execute(total_completed_query)
        total_row = total_result.one()
        total_completed_count = total_row[0] or 0
        total_completed_amount_krw = int(total_row[1]) if total_row[1] else 0

        # Today's rejected
        today_rejected_query = select(func.count()).where(
            and_(
                CryptoWithdrawal.status == TransactionStatus.REJECTED,
                CryptoWithdrawal.processed_at >= today_start
            )
        )

        rejected_result = await self.db.execute(today_rejected_query)
        today_rejected_count = rejected_result.scalar() or 0

        # Processing count (in progress)
        processing_query = select(func.count()).where(
            CryptoWithdrawal.status == TransactionStatus.PROCESSING
        )

        processing_result = await self.db.execute(processing_query)
        processing_count = processing_result.scalar() or 0

        return {
            "pending_count": pending_count,
            "pending_amount_krw": pending_amount_krw,
            "processing_count": processing_count,
            "today_completed_count": today_completed_count,
            "today_completed_amount_krw": today_completed_amount_krw,
            "today_rejected_count": today_rejected_count,
            "total_completed_count": total_completed_count,
            "total_completed_amount_krw": total_completed_amount_krw,
        }

    async def get_pending_count(self) -> int:
        """Get count of pending withdrawal requests.

        Returns:
            int: Number of pending withdrawals
        """
        result = await self.db.execute(
            select(func.count()).select_from(CryptoWithdrawal).where(
                CryptoWithdrawal.status == TransactionStatus.PENDING
            )
        )
        return result.scalar() or 0

    # ============================================================
    # Action Methods
    # ============================================================

    async def approve_withdrawal(
        self,
        withdrawal_id: UUID,
        admin_id: str,
        tx_hash: Optional[str] = None,
        note: Optional[str] = None,
        ip_address: str = "unknown",
    ) -> dict:
        """Approve a pending withdrawal request.

        This calls the main backend API to execute the withdrawal.
        The main backend handles blockchain transaction and balance updates.

        Args:
            withdrawal_id: Withdrawal UUID
            admin_id: Admin user ID performing the action
            tx_hash: Optional transaction hash (if manually processed)
            note: Optional admin note
            ip_address: IP address of the admin

        Returns:
            dict: Updated withdrawal data

        Raises:
            WithdrawalNotFoundError: Withdrawal not found
            WithdrawalStatusError: Withdrawal is not in pending status
            MainAPIError: Main backend API call failed
        """
        # Get withdrawal
        result = await self.db.execute(
            select(CryptoWithdrawal).where(CryptoWithdrawal.id == withdrawal_id)
        )
        withdrawal = result.scalar_one_or_none()

        if not withdrawal:
            raise WithdrawalNotFoundError(f"출금 요청을 찾을 수 없습니다: {withdrawal_id}")

        if withdrawal.status != TransactionStatus.PENDING:
            raise WithdrawalStatusError(
                f"출금 상태가 승인 가능한 상태가 아닙니다. 현재 상태: {withdrawal.status}"
            )

        try:
            # 멱등성 키 생성 (중복 처리 방지)
            idempotency_key = f"withdrawal_approve_{withdrawal_id}_{admin_id}"

            # Call main backend API to process withdrawal
            api_response = await self._call_main_api_with_retry(
                endpoint="/api/wallet/withdrawal/approve",
                method="POST",
                data={
                    "withdrawal_id": str(withdrawal_id),
                    "admin_id": admin_id,
                    "tx_hash": tx_hash,
                    "note": note,
                    "idempotency_key": idempotency_key,
                }
            )

            # Update local record
            withdrawal.status = TransactionStatus.PROCESSING
            withdrawal.approved_by = admin_id
            withdrawal.approved_at = datetime.now(timezone.utc)

            if tx_hash:
                withdrawal.tx_hash = tx_hash

            # Create audit log
            await self._create_audit_log(
                action="withdrawal_approved",
                target_id=str(withdrawal_id),
                admin_id=admin_id,
                ip_address=ip_address,
                details={
                    "user_id": withdrawal.user_id,
                    "to_address": withdrawal.to_address,
                    "amount_usdt": str(withdrawal.amount_usdt),
                    "amount_krw": str(withdrawal.amount_krw),
                    "tx_hash": tx_hash,
                    "note": note,
                    "api_response": api_response,
                },
            )

            await self.db.commit()
            await self.db.refresh(withdrawal)

            logger.info(
                f"출금 승인 완료: {withdrawal_id} by admin {admin_id} from IP {ip_address}"
            )

            return self._withdrawal_to_dict(withdrawal, include_details=True)

        except MainAPIError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"출금 승인 실패: {withdrawal_id} - {e}")
            raise WithdrawalServiceError(f"출금 승인 처리 중 오류 발생: {e}")

    async def reject_withdrawal(
        self,
        withdrawal_id: UUID,
        admin_id: str,
        reason: str,
        ip_address: str = "unknown",
    ) -> dict:
        """Reject a pending withdrawal request.

        This calls the main backend API to reject the withdrawal
        and restore the user's balance.

        Args:
            withdrawal_id: Withdrawal UUID
            admin_id: Admin user ID performing the action
            reason: Rejection reason (required)
            ip_address: IP address of the admin

        Returns:
            dict: Updated withdrawal data

        Raises:
            WithdrawalNotFoundError: Withdrawal not found
            WithdrawalStatusError: Withdrawal is not in pending status
            WithdrawalServiceError: Reason is empty
            MainAPIError: Main backend API call failed
        """
        if not reason or not reason.strip():
            raise WithdrawalServiceError("거부 사유를 입력해주세요.")

        # Get withdrawal
        result = await self.db.execute(
            select(CryptoWithdrawal).where(CryptoWithdrawal.id == withdrawal_id)
        )
        withdrawal = result.scalar_one_or_none()

        if not withdrawal:
            raise WithdrawalNotFoundError(f"출금 요청을 찾을 수 없습니다: {withdrawal_id}")

        if withdrawal.status != TransactionStatus.PENDING:
            raise WithdrawalStatusError(
                f"출금 상태가 거부 가능한 상태가 아닙니다. 현재 상태: {withdrawal.status}"
            )

        try:
            # 멱등성 키 생성 (중복 처리 방지)
            idempotency_key = f"withdrawal_reject_{withdrawal_id}_{admin_id}"

            # Call main backend API to reject and restore balance
            api_response = await self._call_main_api_with_retry(
                endpoint="/api/wallet/withdrawal/reject",
                method="POST",
                data={
                    "withdrawal_id": str(withdrawal_id),
                    "admin_id": admin_id,
                    "reason": reason.strip(),
                    "idempotency_key": idempotency_key,
                }
            )

            # Update local record
            withdrawal.status = TransactionStatus.REJECTED
            withdrawal.rejection_reason = reason.strip()
            withdrawal.processed_at = datetime.now(timezone.utc)
            withdrawal.approved_by = admin_id  # 거부한 관리자도 기록
            withdrawal.approved_at = datetime.now(timezone.utc)

            # Create audit log
            await self._create_audit_log(
                action="withdrawal_rejected",
                target_id=str(withdrawal_id),
                admin_id=admin_id,
                ip_address=ip_address,
                details={
                    "user_id": withdrawal.user_id,
                    "to_address": withdrawal.to_address,
                    "amount_usdt": str(withdrawal.amount_usdt),
                    "amount_krw": str(withdrawal.amount_krw),
                    "reason": reason.strip(),
                    "api_response": api_response,
                },
            )

            await self.db.commit()
            await self.db.refresh(withdrawal)

            logger.info(
                f"출금 거부 완료: {withdrawal_id} by admin {admin_id} - 사유: {reason}"
            )

            return self._withdrawal_to_dict(withdrawal, include_details=True)

        except MainAPIError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"출금 거부 실패: {withdrawal_id} - {e}")
            raise WithdrawalServiceError(f"출금 거부 처리 중 오류 발생: {e}")

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
                raise WithdrawalNotFoundError("메인 서버에서 출금 요청을 찾을 수 없습니다.")
            elif response.status_code == 409:
                # Conflict - already processed
                error_detail = response.json().get("detail", "이미 처리된 요청입니다.")
                raise WithdrawalStatusError(error_detail)
            else:
                error_detail = response.json().get("detail", "알 수 없는 오류")
                raise MainAPIError(
                    f"메인 API 오류 ({response.status_code}): {error_detail}"
                )

        except (WithdrawalNotFoundError, WithdrawalStatusError):
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
            action: Action type (e.g., "withdrawal_approved")
            target_id: Target withdrawal ID
            admin_id: Admin user ID
            ip_address: Admin IP address
            details: Additional details as JSONB
        """
        audit_log = AuditLog(
            action=action,
            target_type="crypto_withdrawal",
            target_id=target_id,
            admin_user_id=admin_id,
            ip_address=ip_address,
            details=details,
        )
        self.db.add(audit_log)

    def _withdrawal_to_dict(
        self,
        withdrawal: CryptoWithdrawal,
        include_details: bool = False,
    ) -> dict:
        """Convert withdrawal model to dictionary.

        Args:
            withdrawal: CryptoWithdrawal model instance
            include_details: Include additional details for detail view

        Returns:
            dict: Withdrawal data
        """
        data = {
            "id": str(withdrawal.id),
            "user_id": withdrawal.user_id,
            "to_address": withdrawal.to_address,
            "amount_usdt": float(withdrawal.amount_usdt),
            "amount_krw": int(withdrawal.amount_krw),
            "exchange_rate": float(withdrawal.exchange_rate),
            "network_fee_usdt": float(withdrawal.network_fee_usdt),
            "network_fee_krw": int(withdrawal.network_fee_krw),
            "tx_hash": withdrawal.tx_hash,
            "status": withdrawal.status.value if withdrawal.status else None,
            "requested_at": withdrawal.requested_at.isoformat() if withdrawal.requested_at else None,
            "approved_by": withdrawal.approved_by,
            "approved_at": withdrawal.approved_at.isoformat() if withdrawal.approved_at else None,
            "processed_at": withdrawal.processed_at.isoformat() if withdrawal.processed_at else None,
        }

        if include_details:
            data["rejection_reason"] = withdrawal.rejection_reason
            data["created_at"] = withdrawal.created_at.isoformat() if withdrawal.created_at else None
            data["updated_at"] = withdrawal.updated_at.isoformat() if withdrawal.updated_at else None
            # 순 출금액 계산
            data["net_amount_usdt"] = float(
                withdrawal.amount_usdt - withdrawal.network_fee_usdt
            )
            data["net_amount_krw"] = int(
                withdrawal.amount_krw - withdrawal.network_fee_krw
            )

        return data
