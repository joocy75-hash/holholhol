"""VIP Service for player loyalty and rakeback system.

Phase 6.2: VIP & Rakeback System

Features:
- VIP level calculation based on total rake paid
- Rakeback percentage per VIP level
- Weekly rakeback settlement
- VIP level caching for performance
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.wallet import TransactionStatus, TransactionType, WalletTransaction
from app.services.wallet import WalletService
from app.utils.redis_client import get_redis

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class VIPLevel(str, Enum):
    """VIP level tiers."""
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    DIAMOND = "diamond"


@dataclass(frozen=True)
class VIPTierConfig:
    """Configuration for a VIP tier.
    
    Attributes:
        level: VIP level enum
        min_rake_krw: Minimum total rake paid to reach this level
        rakeback_pct: Rakeback percentage (e.g., 0.20 = 20%)
        display_name: Human-readable name
    """
    level: VIPLevel
    min_rake_krw: int
    rakeback_pct: Decimal
    display_name: str


# VIP tier configurations (ordered by min_rake ascending)
VIP_TIERS: list[VIPTierConfig] = [
    VIPTierConfig(
        level=VIPLevel.BRONZE,
        min_rake_krw=0,
        rakeback_pct=Decimal("0.20"),
        display_name="Bronze",
    ),
    VIPTierConfig(
        level=VIPLevel.SILVER,
        min_rake_krw=100_000,  # ₩100,000
        rakeback_pct=Decimal("0.25"),
        display_name="Silver",
    ),
    VIPTierConfig(
        level=VIPLevel.GOLD,
        min_rake_krw=500_000,  # ₩500,000
        rakeback_pct=Decimal("0.30"),
        display_name="Gold",
    ),
    VIPTierConfig(
        level=VIPLevel.PLATINUM,
        min_rake_krw=2_000_000,  # ₩2,000,000
        rakeback_pct=Decimal("0.35"),
        display_name="Platinum",
    ),
    VIPTierConfig(
        level=VIPLevel.DIAMOND,
        min_rake_krw=5_000_000,  # ₩5,000,000
        rakeback_pct=Decimal("0.40"),
        display_name="Diamond",
    ),
]

# Quick lookup by level
VIP_TIER_MAP: dict[VIPLevel, VIPTierConfig] = {
    tier.level: tier for tier in VIP_TIERS
}


@dataclass
class VIPStatus:
    """Current VIP status for a user.
    
    Attributes:
        level: Current VIP level
        tier_config: Full tier configuration
        total_rake_paid: Total rake paid (lifetime)
        next_level: Next VIP level (None if at max)
        rake_to_next: Rake needed to reach next level
        progress_pct: Progress percentage to next level
    """
    level: VIPLevel
    tier_config: VIPTierConfig
    total_rake_paid: int
    next_level: VIPLevel | None
    rake_to_next: int
    progress_pct: float


@dataclass
class RakebackResult:
    """Result of rakeback calculation/settlement.
    
    Attributes:
        user_id: User ID
        period_start: Start of rakeback period
        period_end: End of rakeback period
        rake_paid: Total rake paid in period
        vip_level: VIP level at settlement
        rakeback_pct: Rakeback percentage applied
        rakeback_amount: Rakeback amount credited
        transaction_id: Transaction ID if settled
    """
    user_id: str
    period_start: datetime
    period_end: datetime
    rake_paid: int
    vip_level: VIPLevel
    rakeback_pct: Decimal
    rakeback_amount: int
    transaction_id: str | None = None


class VIPService:
    """Service for VIP level management and rakeback.
    
    Features:
    - Calculate VIP level from total rake paid
    - Cache VIP levels in Redis for performance
    - Calculate and settle weekly rakeback
    """
    
    VIP_CACHE_PREFIX = "vip:level:"
    VIP_CACHE_TTL = 3600  # 1 hour cache
    
    def __init__(self, session: AsyncSession) -> None:
        """Initialize VIP service.
        
        Args:
            session: Database session
        """
        self.session = session
        self._redis = get_redis()
        self._wallet_service = WalletService(session)
    
    def calculate_vip_level(self, total_rake_paid: int) -> VIPTierConfig:
        """Calculate VIP level from total rake paid.
        
        Args:
            total_rake_paid: Total rake paid in KRW (lifetime)
            
        Returns:
            VIPTierConfig for the user's level
        """
        # Find highest tier user qualifies for
        current_tier = VIP_TIERS[0]  # Default to Bronze
        
        for tier in VIP_TIERS:
            if total_rake_paid >= tier.min_rake_krw:
                current_tier = tier
            else:
                break
        
        return current_tier
    
    async def get_vip_status(self, user_id: str) -> VIPStatus:
        """Get full VIP status for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            VIPStatus with level, progress, and next tier info
        """
        # Try cache first
        cache_key = f"{self.VIP_CACHE_PREFIX}{user_id}"
        cached = await self._redis.hgetall(cache_key)
        
        if cached:
            total_rake = int(cached.get(b"total_rake", 0))
        else:
            # Fetch from database
            user = await self.session.get(User, user_id)
            if not user:
                # Return default Bronze status for unknown users
                return VIPStatus(
                    level=VIPLevel.BRONZE,
                    tier_config=VIP_TIERS[0],
                    total_rake_paid=0,
                    next_level=VIPLevel.SILVER,
                    rake_to_next=VIP_TIERS[1].min_rake_krw,
                    progress_pct=0.0,
                )
            total_rake = user.total_rake_paid_krw
            
            # Cache the result
            await self._redis.hset(
                cache_key,
                mapping={
                    "total_rake": str(total_rake),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            await self._redis.expire(cache_key, self.VIP_CACHE_TTL)
        
        # Calculate current tier
        current_tier = self.calculate_vip_level(total_rake)
        
        # Find next tier
        next_tier = None
        rake_to_next = 0
        progress_pct = 100.0
        
        current_idx = VIP_TIERS.index(current_tier)
        if current_idx < len(VIP_TIERS) - 1:
            next_tier_config = VIP_TIERS[current_idx + 1]
            next_tier = next_tier_config.level
            rake_to_next = next_tier_config.min_rake_krw - total_rake
            
            # Calculate progress percentage
            tier_range = next_tier_config.min_rake_krw - current_tier.min_rake_krw
            progress_in_tier = total_rake - current_tier.min_rake_krw
            progress_pct = min(100.0, (progress_in_tier / tier_range) * 100)
        
        return VIPStatus(
            level=current_tier.level,
            tier_config=current_tier,
            total_rake_paid=total_rake,
            next_level=next_tier,
            rake_to_next=max(0, rake_to_next),
            progress_pct=progress_pct,
        )
    
    async def invalidate_vip_cache(self, user_id: str) -> None:
        """Invalidate VIP cache for a user.
        
        Call this after rake is collected to ensure fresh data.
        
        Args:
            user_id: User ID
        """
        cache_key = f"{self.VIP_CACHE_PREFIX}{user_id}"
        await self._redis.delete(cache_key)
    
    async def calculate_weekly_rakeback(
        self,
        user_id: str,
        week_start: datetime | None = None,
    ) -> RakebackResult:
        """Calculate rakeback for a user for a specific week.
        
        Args:
            user_id: User ID
            week_start: Start of the week (Monday 00:00 UTC)
                       If None, uses the previous week
                       
        Returns:
            RakebackResult with calculated rakeback
        """
        # Determine week boundaries
        if week_start is None:
            # Previous week (Monday to Sunday)
            today = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            days_since_monday = today.weekday()
            this_monday = today - timedelta(days=days_since_monday)
            week_start = this_monday - timedelta(days=7)
        
        week_end = week_start + timedelta(days=7)
        
        # Get rake transactions for the week
        query = (
            select(WalletTransaction)
            .where(WalletTransaction.user_id == user_id)
            .where(WalletTransaction.tx_type == TransactionType.RAKE)
            .where(WalletTransaction.status == TransactionStatus.COMPLETED)
            .where(WalletTransaction.created_at >= week_start)
            .where(WalletTransaction.created_at < week_end)
        )
        
        result = await self.session.execute(query)
        rake_transactions = list(result.scalars().all())
        
        # Sum up rake paid (amounts are negative for rake deductions)
        total_rake_paid = sum(abs(tx.krw_amount) for tx in rake_transactions)
        
        # Get user's VIP status
        vip_status = await self.get_vip_status(user_id)
        
        # Calculate rakeback
        rakeback_amount = int(
            Decimal(total_rake_paid) * vip_status.tier_config.rakeback_pct
        )
        
        return RakebackResult(
            user_id=user_id,
            period_start=week_start,
            period_end=week_end,
            rake_paid=total_rake_paid,
            vip_level=vip_status.level,
            rakeback_pct=vip_status.tier_config.rakeback_pct,
            rakeback_amount=rakeback_amount,
        )
    
    async def settle_rakeback(
        self,
        rakeback: RakebackResult,
    ) -> RakebackResult:
        """Settle rakeback by crediting user's balance.
        
        Args:
            rakeback: Calculated rakeback result
            
        Returns:
            Updated RakebackResult with transaction ID
        """
        if rakeback.rakeback_amount <= 0:
            logger.info(
                f"No rakeback to settle for user {rakeback.user_id[:8]}... "
                f"(rake_paid={rakeback.rake_paid})"
            )
            return rakeback
        
        # Credit rakeback to user
        tx = await self._wallet_service.transfer_krw(
            user_id=rakeback.user_id,
            amount=rakeback.rakeback_amount,
            tx_type=TransactionType.RAKEBACK,
            description=(
                f"Weekly rakeback ({rakeback.vip_level.value}): "
                f"{rakeback.rakeback_pct*100:.0f}% of {rakeback.rake_paid:,} KRW"
            ),
        )
        
        logger.info(
            f"Rakeback settled: user={rakeback.user_id[:8]}... "
            f"amount={rakeback.rakeback_amount:,} KRW "
            f"({rakeback.vip_level.value}, {rakeback.rakeback_pct*100:.0f}%)"
        )
        
        return RakebackResult(
            user_id=rakeback.user_id,
            period_start=rakeback.period_start,
            period_end=rakeback.period_end,
            rake_paid=rakeback.rake_paid,
            vip_level=rakeback.vip_level,
            rakeback_pct=rakeback.rakeback_pct,
            rakeback_amount=rakeback.rakeback_amount,
            transaction_id=tx.id,
        )
    
    async def process_weekly_rakeback_all(
        self,
        week_start: datetime | None = None,
        batch_size: int = 100,
    ) -> list[RakebackResult]:
        """Process weekly rakeback for all eligible users.
        
        This is the main entry point for the weekly settlement job.
        
        Args:
            week_start: Start of the week to process
            batch_size: Number of users to process per batch
            
        Returns:
            List of RakebackResults for all processed users
        """
        # Determine week boundaries
        if week_start is None:
            today = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            days_since_monday = today.weekday()
            this_monday = today - timedelta(days=days_since_monday)
            week_start = this_monday - timedelta(days=7)
        
        week_end = week_start + timedelta(days=7)
        
        logger.info(
            f"Processing weekly rakeback: {week_start.date()} to {week_end.date()}"
        )
        
        # Find all users who paid rake in the period
        query = (
            select(WalletTransaction.user_id)
            .where(WalletTransaction.tx_type == TransactionType.RAKE)
            .where(WalletTransaction.status == TransactionStatus.COMPLETED)
            .where(WalletTransaction.created_at >= week_start)
            .where(WalletTransaction.created_at < week_end)
            .distinct()
        )
        
        result = await self.session.execute(query)
        user_ids = [row[0] for row in result.fetchall()]
        
        logger.info(f"Found {len(user_ids)} users with rake in period")
        
        results = []
        
        for user_id in user_ids:
            try:
                # Calculate rakeback
                rakeback = await self.calculate_weekly_rakeback(
                    user_id=user_id,
                    week_start=week_start,
                )
                
                # Settle if there's rakeback to pay
                if rakeback.rakeback_amount > 0:
                    rakeback = await self.settle_rakeback(rakeback)
                
                results.append(rakeback)
                
            except Exception as e:
                logger.error(
                    f"Failed to process rakeback for user {user_id}: {e}"
                )
        
        # Commit all transactions
        await self.session.commit()
        
        total_rakeback = sum(r.rakeback_amount for r in results)
        logger.info(
            f"Weekly rakeback complete: {len(results)} users, "
            f"total={total_rakeback:,} KRW"
        )
        
        return results
