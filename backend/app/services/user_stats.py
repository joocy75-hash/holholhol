"""User statistics service for partner settlement.

핸드 완료 시 사용자의 베팅량 및 순손익 통계를 업데이트합니다.
파트너 정산에 사용됩니다.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models.user import User

logger = get_logger(__name__)


class UserStatsService:
    """Service for updating user statistics.

    핸드 완료 시 호출되어 사용자의 통계 필드를 업데이트합니다:
    - total_bet_amount_krw: 누적 베팅량 (턴오버 정산용)
    - total_net_profit_krw: 누적 순손익 (레브쉐어 정산용)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_hand_stats(
        self,
        user_id: str,
        bet_amount: int,
        won_amount: int,
    ) -> None:
        """Update user statistics after hand completion.

        Args:
            user_id: User ID
            bet_amount: Total amount bet in the hand
            won_amount: Total amount won in the hand (0 if lost)
        """
        user = await self.db.get(User, user_id)
        if not user:
            logger.warning(
                "user_stats_update_failed_user_not_found",
                user_id=user_id,
            )
            return

        # Update statistics
        # 베팅량은 항상 증가
        user.total_bet_amount_krw += bet_amount

        # 순손익 = 획득액 - 베팅액
        # 승리: positive, 패배: negative
        net_profit = won_amount - bet_amount
        user.total_net_profit_krw += net_profit

        await self.db.flush()

        logger.debug(
            "user_stats_updated",
            user_id=user_id,
            bet_amount=bet_amount,
            won_amount=won_amount,
            net_profit=net_profit,
            total_bet=user.total_bet_amount_krw,
            total_net_profit=user.total_net_profit_krw,
        )

    async def batch_update_hand_stats(
        self,
        participants: list[dict],
    ) -> None:
        """Batch update statistics for multiple users.

        Args:
            participants: List of dicts with user_id, bet_amount, won_amount
        """
        for participant in participants:
            user_id = participant.get("user_id")
            bet_amount = participant.get("bet_amount", 0)
            won_amount = participant.get("won_amount", 0)

            if user_id and (bet_amount > 0 or won_amount > 0):
                await self.update_hand_stats(user_id, bet_amount, won_amount)
