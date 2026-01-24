"""Partner (총판) service."""

import secrets
import string
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models.partner import (
    CommissionType,
    Partner,
    PartnerStatus,
)
from app.models.user import User
from app.utils.sql import escape_like_pattern

logger = get_logger(__name__)


class PartnerError(Exception):
    """Partner operation error."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class PartnerService:
    """Service for partner (총판) operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _generate_partner_code(length: int = 8) -> str:
        """Generate a unique partner code.

        8자리 영문 대문자 + 숫자 조합
        """
        alphabet = string.ascii_uppercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    async def create_partner(
        self,
        user_id: str,
        name: str,
        commission_type: CommissionType = CommissionType.RAKEBACK,
        commission_rate: Decimal = Decimal("0.30"),
        contact_info: str | None = None,
    ) -> Partner:
        """Create a new partner.

        Args:
            user_id: User ID to register as partner
            name: Partner name
            commission_type: Commission type (rakeback/revshare/turnover)
            commission_rate: Commission rate (0.30 = 30%)
            contact_info: Contact information

        Returns:
            Created Partner object

        Raises:
            PartnerError: If user not found or already a partner
        """
        # Check if user exists
        user = await self.db.get(User, user_id)
        if not user:
            raise PartnerError("USER_NOT_FOUND", "사용자를 찾을 수 없습니다")

        # Check if already a partner
        existing = await self.db.execute(
            select(Partner).where(Partner.user_id == user_id)
        )
        if existing.scalar_one_or_none():
            raise PartnerError("ALREADY_PARTNER", "이미 파트너로 등록된 사용자입니다")

        # Generate unique partner code
        max_attempts = 10
        for _ in range(max_attempts):
            partner_code = self._generate_partner_code()
            existing_code = await self.db.execute(
                select(Partner).where(Partner.partner_code == partner_code)
            )
            if not existing_code.scalar_one_or_none():
                break
        else:
            raise PartnerError("CODE_GENERATION_FAILED", "파트너 코드 생성에 실패했습니다")

        partner = Partner(
            user_id=user_id,
            partner_code=partner_code,
            name=name,
            commission_type=commission_type,
            commission_rate=commission_rate,
            contact_info=contact_info,
            status=PartnerStatus.ACTIVE,
        )
        self.db.add(partner)
        await self.db.flush()

        logger.info(
            "partner_created",
            partner_id=partner.id,
            partner_code=partner_code,
            user_id=user_id,
        )

        return partner

    async def get_partner(self, partner_id: str) -> Partner | None:
        """Get partner by ID."""
        return await self.db.get(Partner, partner_id)

    async def get_partner_by_code(self, code: str) -> Partner | None:
        """Get partner by code."""
        result = await self.db.execute(
            select(Partner).where(Partner.partner_code == code)
        )
        return result.scalar_one_or_none()

    async def get_partner_by_user(self, user_id: str) -> Partner | None:
        """Get partner by user ID."""
        result = await self.db.execute(
            select(Partner).where(Partner.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_partners(
        self,
        page: int = 1,
        page_size: int = 20,
        status: PartnerStatus | None = None,
        search: str | None = None,
    ) -> tuple[list[Partner], int]:
        """List partners with pagination.

        Args:
            page: Page number (1-indexed)
            page_size: Items per page
            status: Filter by status
            search: Search by name or partner code

        Returns:
            Tuple of (partners list, total count)
        """
        query = select(Partner)
        count_query = select(func.count(Partner.id))

        if status:
            query = query.where(Partner.status == status)
            count_query = count_query.where(Partner.status == status)

        if search:
            # Escape LIKE pattern special characters to prevent SQL injection
            escaped_search = escape_like_pattern(search)
            search_filter = (
                Partner.name.ilike(f"%{escaped_search}%", escape="\\")
                | Partner.partner_code.ilike(f"%{escaped_search}%", escape="\\")
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        # Get total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated results
        offset = (page - 1) * page_size
        query = query.order_by(Partner.created_at.desc()).offset(offset).limit(page_size)
        result = await self.db.execute(query)
        partners = list(result.scalars().all())

        return partners, total

    async def update_partner(
        self,
        partner_id: str,
        name: str | None = None,
        commission_type: CommissionType | None = None,
        commission_rate: Decimal | None = None,
        contact_info: str | None = None,
        status: PartnerStatus | None = None,
    ) -> Partner:
        """Update partner information.

        Args:
            partner_id: Partner ID
            name: Partner name
            commission_type: Commission type
            commission_rate: Commission rate
            contact_info: Contact information
            status: Partner status

        Returns:
            Updated Partner object

        Raises:
            PartnerError: If partner not found
        """
        partner = await self.get_partner(partner_id)
        if not partner:
            raise PartnerError("PARTNER_NOT_FOUND", "파트너를 찾을 수 없습니다")

        if name is not None:
            partner.name = name
        if commission_type is not None:
            partner.commission_type = commission_type
        if commission_rate is not None:
            partner.commission_rate = commission_rate
        if contact_info is not None:
            partner.contact_info = contact_info
        if status is not None:
            partner.status = status

        await self.db.flush()

        logger.info(
            "partner_updated",
            partner_id=partner_id,
            updates={
                "name": name,
                "commission_type": commission_type.value if commission_type else None,
                "commission_rate": str(commission_rate) if commission_rate else None,
                "status": status.value if status else None,
            },
        )

        return partner

    async def regenerate_code(self, partner_id: str) -> str:
        """Regenerate partner code.

        Args:
            partner_id: Partner ID

        Returns:
            New partner code

        Raises:
            PartnerError: If partner not found
        """
        partner = await self.get_partner(partner_id)
        if not partner:
            raise PartnerError("PARTNER_NOT_FOUND", "파트너를 찾을 수 없습니다")

        old_code = partner.partner_code

        # Generate new unique code
        max_attempts = 10
        for _ in range(max_attempts):
            new_code = self._generate_partner_code()
            existing = await self.db.execute(
                select(Partner).where(Partner.partner_code == new_code)
            )
            if not existing.scalar_one_or_none():
                break
        else:
            raise PartnerError("CODE_GENERATION_FAILED", "파트너 코드 생성에 실패했습니다")

        partner.partner_code = new_code
        await self.db.flush()

        logger.info(
            "partner_code_regenerated",
            partner_id=partner_id,
            old_code=old_code,
            new_code=new_code,
        )

        return new_code

    async def delete_partner(self, partner_id: str) -> None:
        """Soft delete partner (set status to TERMINATED).

        Args:
            partner_id: Partner ID

        Raises:
            PartnerError: If partner not found
        """
        partner = await self.get_partner(partner_id)
        if not partner:
            raise PartnerError("PARTNER_NOT_FOUND", "파트너를 찾을 수 없습니다")

        partner.status = PartnerStatus.TERMINATED
        await self.db.flush()

        logger.info("partner_deleted", partner_id=partner_id)

    async def get_referrals(
        self,
        partner_id: str,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
    ) -> tuple[list[User], int]:
        """Get referrals (추천 회원) for a partner.

        Args:
            partner_id: Partner ID
            page: Page number (1-indexed)
            page_size: Items per page
            search: Search by nickname or email

        Returns:
            Tuple of (users list, total count)
        """
        query = select(User).where(User.partner_id == partner_id)
        count_query = select(func.count(User.id)).where(User.partner_id == partner_id)

        if search:
            # Escape LIKE pattern special characters to prevent SQL injection
            escaped_search = escape_like_pattern(search)
            search_filter = (
                User.nickname.ilike(f"%{escaped_search}%", escape="\\")
                | User.email.ilike(f"%{escaped_search}%", escape="\\")
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        # Get total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated results
        offset = (page - 1) * page_size
        query = query.order_by(User.created_at.desc()).offset(offset).limit(page_size)
        result = await self.db.execute(query)
        users = list(result.scalars().all())

        return users, total

    async def get_referral_stats(
        self,
        partner_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> dict[str, Any]:
        """Get referral statistics for a period.

        Args:
            partner_id: Partner ID
            period_start: Start of period
            period_end: End of period

        Returns:
            Dictionary with statistics
        """
        # 전체 추천 회원 수
        total_query = select(func.count(User.id)).where(User.partner_id == partner_id)
        total_result = await self.db.execute(total_query)
        total_referrals = total_result.scalar() or 0

        # 기간 내 신규 추천 회원 수
        new_query = select(func.count(User.id)).where(
            User.partner_id == partner_id,
            User.created_at >= period_start,
            User.created_at < period_end,
        )
        new_result = await self.db.execute(new_query)
        new_referrals = new_result.scalar() or 0

        # 레이크, 베팅량, 순손실 합계
        stats_query = select(
            func.coalesce(func.sum(User.total_rake_paid_krw), 0).label("total_rake"),
            func.coalesce(func.sum(User.total_bet_amount_krw), 0).label("total_bet"),
            func.coalesce(
                func.sum(
                    func.greatest(-User.total_net_profit_krw, 0)  # 순손실만 (음수 → 양수)
                ),
                0,
            ).label("total_loss"),
        ).where(User.partner_id == partner_id)
        stats_result = await self.db.execute(stats_query)
        stats = stats_result.one()

        return {
            "total_referrals": total_referrals,
            "new_referrals_this_period": new_referrals,
            "total_rake": stats.total_rake,
            "total_bet_amount": stats.total_bet,
            "total_net_loss": stats.total_loss,
            "period_start": period_start,
            "period_end": period_end,
        }

    async def increment_referral_count(self, partner_id: str) -> None:
        """Increment the referral count for a partner.

        Called when a new user registers with this partner's code.

        Args:
            partner_id: Partner ID
        """
        partner = await self.get_partner(partner_id)
        if partner:
            partner.total_referrals += 1
            await self.db.flush()

            logger.info(
                "partner_referral_count_incremented",
                partner_id=partner_id,
                new_count=partner.total_referrals,
            )
