"""Partner Settlement (정산) service."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models.partner import (
    CommissionType,
    Partner,
    PartnerSettlement,
    PartnerStatus,
    SettlementPeriod,
    SettlementStatus,
)
from app.models.user import User
from app.models.wallet import TransactionStatus, TransactionType, WalletTransaction

logger = get_logger(__name__)


class SettlementError(Exception):
    """Settlement operation error."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class PartnerSettlementService:
    """Service for partner settlement (정산) operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_settlements(
        self,
        period_type: SettlementPeriod,
        period_start: datetime,
        period_end: datetime,
        partner_ids: list[str] | None = None,
    ) -> list[PartnerSettlement]:
        """Generate settlements for all active partners.

        Args:
            period_type: Settlement period type (daily/weekly/monthly)
            period_start: Start of settlement period
            period_end: End of settlement period
            partner_ids: Optional list of specific partner IDs to settle

        Returns:
            List of created PartnerSettlement objects
        """
        # Get partners to settle
        query = select(Partner).where(Partner.status == PartnerStatus.ACTIVE)
        if partner_ids:
            query = query.where(Partner.id.in_(partner_ids))

        result = await self.db.execute(query)
        partners = list(result.scalars().all())

        settlements = []
        for partner in partners:
            try:
                # Calculate commission
                base_amount, commission_amount, detail = await self.calculate_commission(
                    partner, period_start, period_end
                )

                # Skip if no commission
                if base_amount == 0:
                    logger.info(
                        "settlement_skipped_no_activity",
                        partner_id=partner.id,
                        period_start=period_start.isoformat(),
                        period_end=period_end.isoformat(),
                    )
                    continue

                # Create settlement
                settlement = PartnerSettlement(
                    partner_id=partner.id,
                    period_type=period_type,
                    period_start=period_start,
                    period_end=period_end,
                    commission_type=partner.commission_type,
                    commission_rate=partner.commission_rate,
                    base_amount=base_amount,
                    commission_amount=commission_amount,
                    status=SettlementStatus.PENDING,
                    detail=detail,
                )
                self.db.add(settlement)
                settlements.append(settlement)

                logger.info(
                    "settlement_generated",
                    partner_id=partner.id,
                    period_type=period_type.value,
                    base_amount=base_amount,
                    commission_amount=commission_amount,
                )

            except Exception as e:
                logger.error(
                    "settlement_generation_failed",
                    partner_id=partner.id,
                    error=str(e),
                )
                continue

        await self.db.flush()
        return settlements

    async def calculate_commission(
        self,
        partner: Partner,
        period_start: datetime,
        period_end: datetime,
    ) -> tuple[int, int, list[dict[str, Any]]]:
        """Calculate commission for a partner.

        Args:
            partner: Partner object
            period_start: Start of period
            period_end: End of period

        Returns:
            Tuple of (base_amount, commission_amount, detail)
        """
        if partner.commission_type == CommissionType.RAKEBACK:
            return await self._calculate_rakeback(
                partner.id, partner.commission_rate, period_start, period_end
            )
        elif partner.commission_type == CommissionType.REVSHARE:
            return await self._calculate_revshare(
                partner.id, partner.commission_rate, period_start, period_end
            )
        elif partner.commission_type == CommissionType.TURNOVER:
            return await self._calculate_turnover(
                partner.id, partner.commission_rate, period_start, period_end
            )
        else:
            raise SettlementError(
                "INVALID_COMMISSION_TYPE",
                f"알 수 없는 수수료 타입: {partner.commission_type}",
            )

    async def _calculate_rakeback(
        self,
        partner_id: str,
        rate: Decimal,
        period_start: datetime,
        period_end: datetime,
    ) -> tuple[int, int, list[dict[str, Any]]]:
        """Calculate rakeback commission.

        하위 유저가 기간 내 지불한 레이크의 합계 × 수수료율

        참고: 현재 구현에서는 User.total_rake_paid_krw를 사용하지만,
        기간별 정확한 레이크 계산을 위해서는 WalletTransaction 레코드를 사용해야 함.
        여기서는 기간 내 RAKE 트랜잭션을 조회합니다.
        """
        # 기간 내 하위 유저들의 레이크 트랜잭션 조회
        query = (
            select(
                User.id.label("user_id"),
                User.nickname,
                func.coalesce(func.sum(-WalletTransaction.krw_amount), 0).label("rake_amount"),
            )
            .join(WalletTransaction, User.id == WalletTransaction.user_id)
            .where(
                User.partner_id == partner_id,
                WalletTransaction.tx_type == TransactionType.RAKE,
                WalletTransaction.status == TransactionStatus.COMPLETED,
                WalletTransaction.created_at >= period_start,
                WalletTransaction.created_at < period_end,
            )
            .group_by(User.id, User.nickname)
        )

        result = await self.db.execute(query)
        rows = result.all()

        detail = []
        total_rake = 0
        for row in rows:
            if row.rake_amount > 0:
                detail.append({
                    "user_id": row.user_id,
                    "nickname": row.nickname,
                    "amount": row.rake_amount,
                })
                total_rake += row.rake_amount

        commission = int(total_rake * rate)
        return total_rake, commission, detail

    async def _calculate_revshare(
        self,
        partner_id: str,
        rate: Decimal,
        period_start: datetime,
        period_end: datetime,
    ) -> tuple[int, int, list[dict[str, Any]]]:
        """Calculate revenue share commission.

        하위 유저의 순손실 합계 × 수수료율
        (순손실 = 베팅액 - 획득액, 손실인 경우만 양수)

        참고: 기간별 정확한 순손익 계산을 위해 WalletTransaction을 조회합니다.
        """
        # 기간 내 하위 유저들의 게임 트랜잭션 (BUY_IN, WIN) 조회
        query = (
            select(
                User.id.label("user_id"),
                User.nickname,
                func.coalesce(
                    func.sum(
                        func.case(
                            (WalletTransaction.tx_type == TransactionType.BUY_IN, -WalletTransaction.krw_amount),
                            (WalletTransaction.tx_type == TransactionType.CASH_OUT, WalletTransaction.krw_amount),
                            (WalletTransaction.tx_type == TransactionType.WIN, WalletTransaction.krw_amount),
                            (WalletTransaction.tx_type == TransactionType.LOSE, -WalletTransaction.krw_amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("net_profit"),
            )
            .join(WalletTransaction, User.id == WalletTransaction.user_id)
            .where(
                User.partner_id == partner_id,
                WalletTransaction.tx_type.in_([
                    TransactionType.BUY_IN,
                    TransactionType.CASH_OUT,
                    TransactionType.WIN,
                    TransactionType.LOSE,
                ]),
                WalletTransaction.status == TransactionStatus.COMPLETED,
                WalletTransaction.created_at >= period_start,
                WalletTransaction.created_at < period_end,
            )
            .group_by(User.id, User.nickname)
        )

        result = await self.db.execute(query)
        rows = result.all()

        detail = []
        total_loss = 0
        for row in rows:
            # 순손실만 (순이익은 0으로 처리)
            net_loss = max(-row.net_profit, 0)
            if net_loss > 0:
                detail.append({
                    "user_id": row.user_id,
                    "nickname": row.nickname,
                    "amount": net_loss,
                })
                total_loss += net_loss

        commission = int(total_loss * rate)
        return total_loss, commission, detail

    async def _calculate_turnover(
        self,
        partner_id: str,
        rate: Decimal,
        period_start: datetime,
        period_end: datetime,
    ) -> tuple[int, int, list[dict[str, Any]]]:
        """Calculate turnover commission.

        하위 유저의 베팅량 합계 × 수수료율

        참고: 기간별 정확한 베팅량 계산을 위해 WalletTransaction (BUY_IN) 조회합니다.
        """
        # 기간 내 하위 유저들의 BUY_IN 트랜잭션 조회
        query = (
            select(
                User.id.label("user_id"),
                User.nickname,
                func.coalesce(func.sum(-WalletTransaction.krw_amount), 0).label("bet_amount"),
            )
            .join(WalletTransaction, User.id == WalletTransaction.user_id)
            .where(
                User.partner_id == partner_id,
                WalletTransaction.tx_type == TransactionType.BUY_IN,
                WalletTransaction.status == TransactionStatus.COMPLETED,
                WalletTransaction.created_at >= period_start,
                WalletTransaction.created_at < period_end,
            )
            .group_by(User.id, User.nickname)
        )

        result = await self.db.execute(query)
        rows = result.all()

        detail = []
        total_bet = 0
        for row in rows:
            if row.bet_amount > 0:
                detail.append({
                    "user_id": row.user_id,
                    "nickname": row.nickname,
                    "amount": row.bet_amount,
                })
                total_bet += row.bet_amount

        commission = int(total_bet * rate)
        return total_bet, commission, detail

    async def get_settlement(self, settlement_id: str) -> PartnerSettlement | None:
        """Get settlement by ID."""
        return await self.db.get(PartnerSettlement, settlement_id)

    async def list_settlements(
        self,
        partner_id: str | None = None,
        status: SettlementStatus | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[PartnerSettlement], int]:
        """List settlements with pagination.

        Args:
            partner_id: Filter by partner ID
            status: Filter by status
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Tuple of (settlements list, total count)
        """
        query = select(PartnerSettlement)
        count_query = select(func.count(PartnerSettlement.id))

        if partner_id:
            query = query.where(PartnerSettlement.partner_id == partner_id)
            count_query = count_query.where(PartnerSettlement.partner_id == partner_id)

        if status:
            query = query.where(PartnerSettlement.status == status)
            count_query = count_query.where(PartnerSettlement.status == status)

        # Get total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated results
        offset = (page - 1) * page_size
        query = (
            query.order_by(PartnerSettlement.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        settlements = list(result.scalars().all())

        return settlements, total

    async def approve_settlement(
        self,
        settlement_id: str,
        admin_user_id: str,
    ) -> PartnerSettlement:
        """Approve a settlement.

        Args:
            settlement_id: Settlement ID
            admin_user_id: Admin user ID who approved

        Returns:
            Updated PartnerSettlement object

        Raises:
            SettlementError: If settlement not found or already processed
        """
        settlement = await self.get_settlement(settlement_id)
        if not settlement:
            raise SettlementError("SETTLEMENT_NOT_FOUND", "정산을 찾을 수 없습니다")

        if settlement.status != SettlementStatus.PENDING:
            raise SettlementError(
                "INVALID_SETTLEMENT_STATUS",
                f"정산 상태가 올바르지 않습니다: {settlement.status.value}",
            )

        settlement.status = SettlementStatus.APPROVED
        settlement.approved_by = admin_user_id
        settlement.approved_at = datetime.now(timezone.utc)

        await self.db.flush()

        logger.info(
            "settlement_approved",
            settlement_id=settlement_id,
            approved_by=admin_user_id,
        )

        return settlement

    async def reject_settlement(
        self,
        settlement_id: str,
        admin_user_id: str,
        reason: str,
    ) -> PartnerSettlement:
        """Reject a settlement.

        Args:
            settlement_id: Settlement ID
            admin_user_id: Admin user ID who rejected
            reason: Rejection reason

        Returns:
            Updated PartnerSettlement object

        Raises:
            SettlementError: If settlement not found or already processed
        """
        settlement = await self.get_settlement(settlement_id)
        if not settlement:
            raise SettlementError("SETTLEMENT_NOT_FOUND", "정산을 찾을 수 없습니다")

        if settlement.status != SettlementStatus.PENDING:
            raise SettlementError(
                "INVALID_SETTLEMENT_STATUS",
                f"정산 상태가 올바르지 않습니다: {settlement.status.value}",
            )

        settlement.status = SettlementStatus.REJECTED
        settlement.approved_by = admin_user_id
        settlement.approved_at = datetime.now(timezone.utc)
        settlement.rejection_reason = reason

        await self.db.flush()

        logger.info(
            "settlement_rejected",
            settlement_id=settlement_id,
            rejected_by=admin_user_id,
            reason=reason,
        )

        return settlement

    async def pay_settlement(
        self,
        settlement_id: str,
        admin_user_id: str,
    ) -> PartnerSettlement:
        """Mark settlement as paid and transfer commission to partner.

        Args:
            settlement_id: Settlement ID
            admin_user_id: Admin user ID who processed

        Returns:
            Updated PartnerSettlement object

        Raises:
            SettlementError: If settlement not found or not approved
        """
        settlement = await self.get_settlement(settlement_id)
        if not settlement:
            raise SettlementError("SETTLEMENT_NOT_FOUND", "정산을 찾을 수 없습니다")

        if settlement.status != SettlementStatus.APPROVED:
            raise SettlementError(
                "INVALID_SETTLEMENT_STATUS",
                f"정산 상태가 올바르지 않습니다: {settlement.status.value}",
            )

        # Get partner and user
        partner = await self.db.get(Partner, settlement.partner_id)
        if not partner:
            raise SettlementError("PARTNER_NOT_FOUND", "파트너를 찾을 수 없습니다")

        user = await self.db.get(User, partner.user_id)
        if not user:
            raise SettlementError("USER_NOT_FOUND", "사용자를 찾을 수 없습니다")

        # Create wallet transaction
        import hashlib

        balance_before = user.krw_balance
        balance_after = balance_before + settlement.commission_amount

        # Generate integrity hash
        hash_data = f"{user.id}:{TransactionType.PARTNER_COMMISSION.value}:{settlement.commission_amount}:{balance_before}:{balance_after}"
        integrity_hash = hashlib.sha256(hash_data.encode()).hexdigest()

        transaction = WalletTransaction(
            user_id=user.id,
            tx_type=TransactionType.PARTNER_COMMISSION,
            status=TransactionStatus.COMPLETED,
            krw_amount=settlement.commission_amount,
            krw_balance_before=balance_before,
            krw_balance_after=balance_after,
            description=f"파트너 정산 지급 ({settlement.period_start.strftime('%Y-%m-%d')} ~ {settlement.period_end.strftime('%Y-%m-%d')})",
            integrity_hash=integrity_hash,
        )
        self.db.add(transaction)

        # Update user balance
        user.krw_balance = balance_after

        # Update partner statistics
        partner.total_commission_earned += settlement.commission_amount

        # Update settlement status
        settlement.status = SettlementStatus.PAID
        settlement.paid_at = datetime.now(timezone.utc)

        await self.db.flush()

        logger.info(
            "settlement_paid",
            settlement_id=settlement_id,
            partner_id=partner.id,
            amount=settlement.commission_amount,
            processed_by=admin_user_id,
        )

        return settlement

    async def get_settlement_summary(self, partner_id: str) -> dict[str, int]:
        """Get settlement summary for a partner.

        Args:
            partner_id: Partner ID

        Returns:
            Dictionary with summary statistics
        """
        # Total earned (all paid settlements)
        total_query = select(
            func.coalesce(func.sum(PartnerSettlement.commission_amount), 0)
        ).where(
            PartnerSettlement.partner_id == partner_id,
            PartnerSettlement.status == SettlementStatus.PAID,
        )
        total_result = await self.db.execute(total_query)
        total_earned = total_result.scalar() or 0

        # Pending amount
        pending_query = select(
            func.coalesce(func.sum(PartnerSettlement.commission_amount), 0)
        ).where(
            PartnerSettlement.partner_id == partner_id,
            PartnerSettlement.status == SettlementStatus.PENDING,
        )
        pending_result = await self.db.execute(pending_query)
        pending_amount = pending_result.scalar() or 0

        # Approved amount (waiting for payment)
        approved_query = select(
            func.coalesce(func.sum(PartnerSettlement.commission_amount), 0)
        ).where(
            PartnerSettlement.partner_id == partner_id,
            PartnerSettlement.status == SettlementStatus.APPROVED,
        )
        approved_result = await self.db.execute(approved_query)
        approved_amount = approved_result.scalar() or 0

        # This month amount
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_query = select(
            func.coalesce(func.sum(PartnerSettlement.commission_amount), 0)
        ).where(
            PartnerSettlement.partner_id == partner_id,
            PartnerSettlement.status == SettlementStatus.PAID,
            PartnerSettlement.paid_at >= month_start,
        )
        month_result = await self.db.execute(month_query)
        this_month_amount = month_result.scalar() or 0

        return {
            "total_earned": total_earned,
            "pending_amount": pending_amount,
            "approved_amount": approved_amount,
            "paid_amount": total_earned,  # Same as total_earned
            "this_month_amount": this_month_amount,
        }
