"""다중 승인 서비스.

고액 출금에 대한 n-of-m 다중 관리자 승인 시스템을 구현합니다.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.multi_approval import (
    ApprovalPolicy,
    WithdrawalApprovalRequest,
    ApprovalRecord,
    ApprovalStatus,
    ApprovalAction,
)
from app.models.crypto import CryptoWithdrawal, TransactionStatus
from app.services.notification_service import (
    NotificationService,
    NotificationType,
    NotificationPriority,
)

logger = logging.getLogger(__name__)


class MultiApprovalError(Exception):
    """다중 승인 서비스 오류."""
    pass


class ApprovalNotFoundError(MultiApprovalError):
    """승인 요청을 찾을 수 없음."""
    pass


class ApprovalExpiredError(MultiApprovalError):
    """승인 요청이 만료됨."""
    pass


class DuplicateApprovalError(MultiApprovalError):
    """이미 승인/거부한 요청."""
    pass


class InsufficientPolicyError(MultiApprovalError):
    """적용 가능한 정책이 없음."""
    pass


class MultiApprovalService:
    """다중 승인 서비스.

    고액 출금에 대해 여러 관리자의 승인을 요구하는 시스템입니다.

    사용 흐름:
    1. 출금 승인 시 check_requires_multi_approval() 호출
    2. 필요 시 create_approval_request() 호출
    3. 관리자가 approve() 또는 reject() 호출
    4. 필요 승인 수 충족 시 출금 실행 가능

    Example:
        ```python
        service = MultiApprovalService(db, redis)

        # 다중 승인 필요 여부 확인
        policy = await service.check_requires_multi_approval(withdrawal)
        if policy:
            # 다중 승인 요청 생성
            request = await service.create_approval_request(withdrawal, policy)

            # 관리자들이 승인
            await service.approve(request.id, admin1_id, "승인", ip)
            await service.approve(request.id, admin2_id, "확인", ip)

            # 최종 승인 확인
            if await service.is_fully_approved(request.id):
                # 출금 실행 가능
                pass
        ```
    """

    def __init__(
        self,
        db: AsyncSession,
        redis_client=None,
    ):
        """초기화.

        Args:
            db: 데이터베이스 세션
            redis_client: Redis 클라이언트 (알림용, 선택)
        """
        self.db = db
        self.redis = redis_client
        self._notification_service = None

    @property
    def notification_service(self) -> Optional[NotificationService]:
        """알림 서비스 (lazy loading)."""
        if self._notification_service is None and self.redis:
            self._notification_service = NotificationService(self.redis)
        return self._notification_service

    # =========================================================================
    # 정책 관리
    # =========================================================================

    async def get_active_policies(self) -> list[ApprovalPolicy]:
        """활성 승인 정책 목록 조회."""
        stmt = (
            select(ApprovalPolicy)
            .where(ApprovalPolicy.is_active == True)
            .order_by(ApprovalPolicy.priority.desc(), ApprovalPolicy.min_amount_usdt.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_policy_for_amount(self, amount_usdt: Decimal) -> Optional[ApprovalPolicy]:
        """금액에 맞는 정책 조회.

        Args:
            amount_usdt: 출금 금액 (USDT)

        Returns:
            적용 가능한 정책 (없으면 None)
        """
        stmt = (
            select(ApprovalPolicy)
            .where(
                and_(
                    ApprovalPolicy.is_active == True,
                    ApprovalPolicy.min_amount_usdt <= amount_usdt,
                    or_(
                        ApprovalPolicy.max_amount_usdt.is_(None),
                        ApprovalPolicy.max_amount_usdt >= amount_usdt,
                    ),
                )
            )
            .order_by(ApprovalPolicy.priority.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_policy(
        self,
        name: str,
        min_amount_usdt: Decimal,
        required_approvals: int,
        max_amount_usdt: Optional[Decimal] = None,
        expiry_minutes: int = 60,
        description: Optional[str] = None,
        priority: int = 0,
    ) -> ApprovalPolicy:
        """승인 정책 생성.

        Args:
            name: 정책 이름
            min_amount_usdt: 최소 금액
            required_approvals: 필요 승인 수
            max_amount_usdt: 최대 금액 (None이면 무제한)
            expiry_minutes: 만료 시간 (분)
            description: 설명
            priority: 우선순위

        Returns:
            생성된 정책
        """
        policy = ApprovalPolicy(
            name=name,
            description=description,
            min_amount_usdt=min_amount_usdt,
            max_amount_usdt=max_amount_usdt,
            required_approvals=required_approvals,
            expiry_minutes=expiry_minutes,
            priority=priority,
            is_active=True,
        )
        self.db.add(policy)
        await self.db.commit()
        await self.db.refresh(policy)

        logger.info(
            f"Approval policy created: {name} "
            f"({min_amount_usdt}-{max_amount_usdt} USDT, {required_approvals} approvals)"
        )
        return policy

    async def update_policy(
        self,
        policy_id: UUID,
        **kwargs,
    ) -> ApprovalPolicy:
        """정책 업데이트."""
        stmt = select(ApprovalPolicy).where(ApprovalPolicy.id == str(policy_id))
        result = await self.db.execute(stmt)
        policy = result.scalar_one_or_none()

        if not policy:
            raise ApprovalNotFoundError(f"정책을 찾을 수 없습니다: {policy_id}")

        for key, value in kwargs.items():
            if hasattr(policy, key) and value is not None:
                setattr(policy, key, value)

        await self.db.commit()
        await self.db.refresh(policy)
        return policy

    async def deactivate_policy(self, policy_id: UUID) -> None:
        """정책 비활성화."""
        await self.update_policy(policy_id, is_active=False)

    # =========================================================================
    # 승인 요청 관리
    # =========================================================================

    async def check_requires_multi_approval(
        self,
        withdrawal: CryptoWithdrawal,
    ) -> Optional[ApprovalPolicy]:
        """다중 승인 필요 여부 확인.

        Args:
            withdrawal: 출금 요청

        Returns:
            적용 정책 (다중 승인 불필요 시 None)
        """
        return await self.get_policy_for_amount(withdrawal.amount_usdt)

    async def create_approval_request(
        self,
        withdrawal: CryptoWithdrawal,
        policy: ApprovalPolicy,
    ) -> WithdrawalApprovalRequest:
        """다중 승인 요청 생성.

        Args:
            withdrawal: 출금 요청
            policy: 적용할 정책

        Returns:
            생성된 승인 요청
        """
        # 이미 승인 요청이 있는지 확인
        existing = await self.get_approval_request_by_withdrawal(str(withdrawal.id))
        if existing and existing.status == ApprovalStatus.PENDING:
            return existing

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=policy.expiry_minutes)

        request = WithdrawalApprovalRequest(
            withdrawal_id=str(withdrawal.id),
            policy_id=str(policy.id),
            amount_usdt=withdrawal.amount_usdt,
            amount_krw=withdrawal.amount_krw,
            to_address=withdrawal.to_address,
            user_id=withdrawal.user_id,
            required_approvals=policy.required_approvals,
            current_approvals=0,
            status=ApprovalStatus.PENDING,
            expires_at=expires_at,
        )
        self.db.add(request)
        await self.db.commit()
        await self.db.refresh(request)

        logger.info(
            f"Multi-approval request created: {request.id} "
            f"for withdrawal {withdrawal.id} ({policy.required_approvals} approvals required)"
        )

        # 알림 발송
        if self.notification_service:
            await self.notification_service.create_notification(
                notification_type=NotificationType.WITHDRAWAL_PENDING,
                priority=NotificationPriority.HIGH,
                title="🔐 다중 승인 필요",
                message=(
                    f"고액 출금 {float(withdrawal.amount_usdt):,.2f} USDT에 대해 "
                    f"{policy.required_approvals}명의 승인이 필요합니다."
                ),
                data={
                    "approvalRequestId": str(request.id),
                    "withdrawalId": str(withdrawal.id),
                    "amountUsdt": float(withdrawal.amount_usdt),
                    "requiredApprovals": policy.required_approvals,
                    "expiresAt": expires_at.isoformat(),
                },
            )

        return request

    async def get_approval_request(
        self,
        request_id: UUID,
    ) -> Optional[WithdrawalApprovalRequest]:
        """승인 요청 조회."""
        stmt = (
            select(WithdrawalApprovalRequest)
            .options(selectinload(WithdrawalApprovalRequest.approval_records))
            .where(WithdrawalApprovalRequest.id == str(request_id))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_approval_request_by_withdrawal(
        self,
        withdrawal_id: str,
    ) -> Optional[WithdrawalApprovalRequest]:
        """출금 ID로 승인 요청 조회."""
        stmt = (
            select(WithdrawalApprovalRequest)
            .options(selectinload(WithdrawalApprovalRequest.approval_records))
            .where(WithdrawalApprovalRequest.withdrawal_id == withdrawal_id)
            .order_by(WithdrawalApprovalRequest.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pending_requests(
        self,
        limit: int = 50,
    ) -> list[WithdrawalApprovalRequest]:
        """대기 중인 승인 요청 목록."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(WithdrawalApprovalRequest)
            .options(selectinload(WithdrawalApprovalRequest.approval_records))
            .where(
                and_(
                    WithdrawalApprovalRequest.status.in_([
                        ApprovalStatus.PENDING,
                        ApprovalStatus.PARTIALLY_APPROVED,
                    ]),
                    WithdrawalApprovalRequest.expires_at > now,
                )
            )
            .order_by(WithdrawalApprovalRequest.created_at.asc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # =========================================================================
    # 승인/거부 처리
    # =========================================================================

    async def approve(
        self,
        request_id: UUID,
        admin_id: str,
        admin_name: str,
        ip_address: str,
        note: Optional[str] = None,
    ) -> WithdrawalApprovalRequest:
        """승인 처리.

        Args:
            request_id: 승인 요청 ID
            admin_id: 관리자 ID
            admin_name: 관리자 이름
            ip_address: IP 주소
            note: 메모

        Returns:
            업데이트된 승인 요청

        Raises:
            ApprovalNotFoundError: 요청을 찾을 수 없음
            ApprovalExpiredError: 만료된 요청
            DuplicateApprovalError: 이미 승인함
        """
        request = await self.get_approval_request(request_id)
        if not request:
            raise ApprovalNotFoundError(f"승인 요청을 찾을 수 없습니다: {request_id}")

        # 상태 검증
        await self._validate_request_state(request, admin_id)

        # 승인 기록 생성
        record = ApprovalRecord(
            approval_request_id=str(request.id),
            admin_id=admin_id,
            admin_name=admin_name,
            action=ApprovalAction.APPROVE,
            note=note,
            ip_address=ip_address,
        )
        self.db.add(record)

        # 승인 수 증가
        request.current_approvals += 1

        # 상태 업데이트
        if request.current_approvals >= request.required_approvals:
            request.status = ApprovalStatus.APPROVED
            request.final_decision = "approved"
            request.final_decision_at = datetime.now(timezone.utc)
            request.final_decision_by = admin_id

            logger.info(
                f"Multi-approval request fully approved: {request_id} "
                f"({request.current_approvals}/{request.required_approvals})"
            )

            # 최종 승인 알림
            if self.notification_service:
                await self.notification_service.create_notification(
                    notification_type=NotificationType.WITHDRAWAL_PENDING,
                    priority=NotificationPriority.MEDIUM,
                    title="✅ 다중 승인 완료",
                    message=(
                        f"출금 {float(request.amount_usdt):,.2f} USDT가 "
                        f"모든 승인을 받았습니다. 자동 실행 대기 중입니다."
                    ),
                    data={
                        "approvalRequestId": str(request.id),
                        "withdrawalId": request.withdrawal_id,
                        "status": "approved",
                    },
                )
        else:
            request.status = ApprovalStatus.PARTIALLY_APPROVED

            logger.info(
                f"Multi-approval request partially approved: {request_id} "
                f"({request.current_approvals}/{request.required_approvals})"
            )

        await self.db.commit()
        await self.db.refresh(request)
        return request

    async def reject(
        self,
        request_id: UUID,
        admin_id: str,
        admin_name: str,
        ip_address: str,
        reason: str,
    ) -> WithdrawalApprovalRequest:
        """거부 처리.

        Args:
            request_id: 승인 요청 ID
            admin_id: 관리자 ID
            admin_name: 관리자 이름
            ip_address: IP 주소
            reason: 거부 사유

        Returns:
            업데이트된 승인 요청
        """
        request = await self.get_approval_request(request_id)
        if not request:
            raise ApprovalNotFoundError(f"승인 요청을 찾을 수 없습니다: {request_id}")

        # 상태 검증
        await self._validate_request_state(request, admin_id)

        # 거부 기록 생성
        record = ApprovalRecord(
            approval_request_id=str(request.id),
            admin_id=admin_id,
            admin_name=admin_name,
            action=ApprovalAction.REJECT,
            note=reason,
            ip_address=ip_address,
        )
        self.db.add(record)

        # 즉시 거부 상태로 변경
        request.status = ApprovalStatus.REJECTED
        request.final_decision = "rejected"
        request.final_decision_at = datetime.now(timezone.utc)
        request.final_decision_by = admin_id

        logger.warning(
            f"Multi-approval request rejected: {request_id} "
            f"by {admin_name} - {reason}"
        )

        # 거부 알림
        if self.notification_service:
            await self.notification_service.create_notification(
                notification_type=NotificationType.WITHDRAWAL_PENDING,
                priority=NotificationPriority.HIGH,
                title="❌ 다중 승인 거부",
                message=(
                    f"출금 {float(request.amount_usdt):,.2f} USDT가 "
                    f"{admin_name}에 의해 거부되었습니다: {reason}"
                ),
                data={
                    "approvalRequestId": str(request.id),
                    "withdrawalId": request.withdrawal_id,
                    "status": "rejected",
                    "reason": reason,
                    "rejectedBy": admin_name,
                },
            )

        await self.db.commit()
        await self.db.refresh(request)
        return request

    async def _validate_request_state(
        self,
        request: WithdrawalApprovalRequest,
        admin_id: str,
    ) -> None:
        """요청 상태 검증."""
        # 이미 완료된 요청
        if request.status in [ApprovalStatus.APPROVED, ApprovalStatus.REJECTED]:
            raise MultiApprovalError(f"이미 처리 완료된 요청입니다: {request.status.value}")

        # 만료 확인
        now = datetime.now(timezone.utc)
        if request.expires_at < now:
            request.status = ApprovalStatus.EXPIRED
            await self.db.commit()
            raise ApprovalExpiredError(
                f"승인 요청이 만료되었습니다 (만료: {request.expires_at.isoformat()})"
            )

        # 중복 승인 확인
        for record in request.approval_records:
            if record.admin_id == admin_id:
                raise DuplicateApprovalError(
                    f"이미 이 요청에 대해 {record.action.value}했습니다"
                )

    # =========================================================================
    # 상태 조회
    # =========================================================================

    async def is_fully_approved(self, request_id: UUID) -> bool:
        """완전 승인 여부 확인."""
        request = await self.get_approval_request(request_id)
        if not request:
            return False
        return request.status == ApprovalStatus.APPROVED

    async def get_approval_status(self, request_id: UUID) -> dict:
        """승인 상태 상세 조회."""
        request = await self.get_approval_request(request_id)
        if not request:
            raise ApprovalNotFoundError(f"승인 요청을 찾을 수 없습니다: {request_id}")

        return {
            "id": str(request.id),
            "withdrawal_id": request.withdrawal_id,
            "status": request.status.value,
            "required_approvals": request.required_approvals,
            "current_approvals": request.current_approvals,
            "remaining_approvals": max(0, request.required_approvals - request.current_approvals),
            "is_fully_approved": request.is_fully_approved,
            "is_expired": request.is_expired,
            "expires_at": request.expires_at.isoformat(),
            "approval_records": [
                {
                    "admin_id": r.admin_id,
                    "admin_name": r.admin_name,
                    "action": r.action.value,
                    "note": r.note,
                    "created_at": r.created_at.isoformat(),
                }
                for r in request.approval_records
            ],
        }

    async def expire_old_requests(self) -> int:
        """만료된 요청 정리.

        Returns:
            만료 처리된 요청 수
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(WithdrawalApprovalRequest)
            .where(
                and_(
                    WithdrawalApprovalRequest.status.in_([
                        ApprovalStatus.PENDING,
                        ApprovalStatus.PARTIALLY_APPROVED,
                    ]),
                    WithdrawalApprovalRequest.expires_at < now,
                )
            )
        )
        result = await self.db.execute(stmt)
        expired_requests = result.scalars().all()

        for request in expired_requests:
            request.status = ApprovalStatus.EXPIRED
            logger.info(f"Approval request expired: {request.id}")

        if expired_requests:
            await self.db.commit()

        return len(expired_requests)

    async def get_stats(self) -> dict:
        """다중 승인 통계."""
        # 대기 중
        pending_stmt = select(WithdrawalApprovalRequest).where(
            WithdrawalApprovalRequest.status.in_([
                ApprovalStatus.PENDING,
                ApprovalStatus.PARTIALLY_APPROVED,
            ])
        )
        pending_result = await self.db.execute(pending_stmt)
        pending_count = len(pending_result.scalars().all())

        # 오늘 승인
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        approved_stmt = select(WithdrawalApprovalRequest).where(
            and_(
                WithdrawalApprovalRequest.status == ApprovalStatus.APPROVED,
                WithdrawalApprovalRequest.final_decision_at >= today_start,
            )
        )
        approved_result = await self.db.execute(approved_stmt)
        today_approved = len(approved_result.scalars().all())

        # 오늘 거부
        rejected_stmt = select(WithdrawalApprovalRequest).where(
            and_(
                WithdrawalApprovalRequest.status == ApprovalStatus.REJECTED,
                WithdrawalApprovalRequest.final_decision_at >= today_start,
            )
        )
        rejected_result = await self.db.execute(rejected_stmt)
        today_rejected = len(rejected_result.scalars().all())

        return {
            "pending_count": pending_count,
            "today_approved": today_approved,
            "today_rejected": today_rejected,
        }
