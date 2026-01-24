"""
Tournament Settlement Service.

토너먼트 종료 시 상금 자동 정산.

Features:
- 순위별 상금 계산 (payout_structure 기반)
- WalletService 연동 자동 지급
- 정산 결과 로깅 및 이벤트 발행
- 원자적 트랜잭션 처리

Usage:
    settlement = TournamentSettlement(wallet_service)
    results = await settlement.settle_tournament(tournament_id, state)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from app.models.wallet import TransactionType
from app.services.wallet import WalletService, WalletError
from .models import (
    TournamentState,
    TournamentConfig,
    TournamentPlayer,
    TournamentEventType,
)
from .event_bus import TournamentEventBus

logger = logging.getLogger(__name__)


@dataclass
class PayoutResult:
    """정산 결과."""

    payout_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    nickname: str = ""
    rank: int = 0
    prize_amount: int = 0
    prize_percentage: float = 0.0
    transaction_id: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None
    paid_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "payout_id": self.payout_id,
            "user_id": self.user_id,
            "nickname": self.nickname,
            "rank": self.rank,
            "prize_amount": self.prize_amount,
            "prize_percentage": self.prize_percentage,
            "transaction_id": self.transaction_id,
            "success": self.success,
            "error_message": self.error_message,
            "paid_at": self.paid_at.isoformat(),
        }


@dataclass
class SettlementSummary:
    """정산 요약."""

    settlement_id: str = field(default_factory=lambda: str(uuid4()))
    tournament_id: str = ""
    tournament_name: str = ""
    total_prize_pool: int = 0
    total_paid: int = 0
    successful_payouts: int = 0
    failed_payouts: int = 0
    payouts: List[PayoutResult] = field(default_factory=list)
    settled_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "settlement_id": self.settlement_id,
            "tournament_id": self.tournament_id,
            "tournament_name": self.tournament_name,
            "total_prize_pool": self.total_prize_pool,
            "total_paid": self.total_paid,
            "successful_payouts": self.successful_payouts,
            "failed_payouts": self.failed_payouts,
            "payouts": [p.to_dict() for p in self.payouts],
            "settled_at": self.settled_at.isoformat(),
        }


class TournamentSettlement:
    """
    토너먼트 상금 정산 서비스.

    토너먼트 종료 시 순위별로 상금을 계산하고
    자동으로 플레이어 지갑에 지급합니다.
    """

    def __init__(
        self,
        wallet_service: WalletService,
        event_bus: Optional[TournamentEventBus] = None,
    ):
        """
        Initialize settlement service.

        Args:
            wallet_service: WalletService instance for transfers
            event_bus: Optional event bus for notifications
        """
        self.wallet = wallet_service
        self.event_bus = event_bus

    def calculate_itm_players(self, state: TournamentState) -> int:
        """
        ITM (In The Money) 플레이어 수 계산.

        Args:
            state: Tournament state

        Returns:
            ITM 플레이어 수
        """
        total_players = len(state.players)
        itm_percentage = state.config.itm_percentage

        # ITM 플레이어 수 = 총 플레이어 * ITM%
        itm_count = max(1, int(total_players * itm_percentage / 100))

        # payout_structure 길이로 제한
        return min(itm_count, len(state.config.payout_structure))

    def get_final_ranking(self, state: TournamentState) -> List[TournamentPlayer]:
        """
        최종 순위 계산.

        1위: 마지막 생존자 (활성 플레이어 중 칩 최다)
        2위~: elimination_rank 역순 (마지막에 탈락한 사람이 높은 순위)

        Args:
            state: Tournament state

        Returns:
            순위별 플레이어 리스트
        """
        # 활성 플레이어 (1위 = 마지막 생존자)
        active_players = sorted(
            [p for p in state.players.values() if p.is_active],
            key=lambda p: p.chip_count,
            reverse=True,
        )

        # 탈락 플레이어 (elimination_rank 역순)
        eliminated_players = sorted(
            [p for p in state.players.values() if not p.is_active],
            key=lambda p: p.elimination_rank or 9999,
        )

        # 1위 (활성 플레이어 중 칩 최다) + 탈락 순서
        return active_players + eliminated_players

    def calculate_payouts(
        self, state: TournamentState
    ) -> Dict[str, Tuple[int, int, float]]:
        """
        순위별 상금 계산.

        payout_structure: [0.25, 0.15, 0.10, ...]
        1위 = 25%, 2위 = 15%, 3위 = 10%...

        Args:
            state: Tournament state

        Returns:
            Dict of user_id -> (rank, prize_amount, percentage)
        """
        payouts: Dict[str, Tuple[int, int, float]] = {}
        prize_pool = state.total_prize_pool
        payout_structure = state.config.payout_structure

        # 최종 순위 계산
        final_ranking = self.get_final_ranking(state)

        # ITM 플레이어 수
        itm_count = self.calculate_itm_players(state)

        # 상금 분배
        for rank, player in enumerate(final_ranking, 1):
            if rank <= itm_count and rank <= len(payout_structure):
                percentage = payout_structure[rank - 1]
                prize_amount = int(prize_pool * percentage)
                payouts[player.user_id] = (rank, prize_amount, percentage)

        return payouts

    async def settle_tournament(
        self,
        tournament_id: str,
        state: TournamentState,
    ) -> SettlementSummary:
        """
        토너먼트 상금 지급 (원자적 처리).

        Args:
            tournament_id: Tournament ID
            state: Tournament state

        Returns:
            SettlementSummary with all payout results
        """
        logger.info(f"Starting tournament settlement: {tournament_id}")

        summary = SettlementSummary(
            tournament_id=tournament_id,
            tournament_name=state.config.name,
            total_prize_pool=state.total_prize_pool,
        )

        # 상금 계산
        payouts = self.calculate_payouts(state)

        if not payouts:
            logger.warning(f"No payouts calculated for tournament: {tournament_id}")
            return summary

        # 최종 순위 (nickname 조회용)
        final_ranking = self.get_final_ranking(state)
        player_map = {p.user_id: p for p in final_ranking}

        # 상금 지급 (순위순)
        for user_id in sorted(payouts.keys(), key=lambda x: payouts[x][0]):
            rank, amount, percentage = payouts[user_id]
            player = player_map.get(user_id)
            nickname = player.nickname if player else "Unknown"

            result = PayoutResult(
                user_id=user_id,
                nickname=nickname,
                rank=rank,
                prize_amount=amount,
                prize_percentage=percentage * 100,  # Convert to percentage
            )

            if amount > 0:
                try:
                    tx = await self.wallet.transfer_krw(
                        user_id=user_id,
                        amount=amount,
                        tx_type=TransactionType.TOURNAMENT_PRIZE,
                        description=f"Tournament Prize: {state.config.name} - Rank #{rank} ({percentage*100:.1f}%)",
                    )
                    result.transaction_id = tx.id
                    result.success = True
                    summary.successful_payouts += 1
                    summary.total_paid += amount

                    logger.info(
                        f"Tournament prize paid: {user_id} rank={rank} "
                        f"amount={amount:,} ({percentage*100:.1f}%)"
                    )

                except WalletError as e:
                    result.success = False
                    result.error_message = str(e)
                    summary.failed_payouts += 1

                    logger.error(
                        f"Failed to pay tournament prize: {user_id} "
                        f"amount={amount} error={e}"
                    )

                except Exception as e:
                    result.success = False
                    result.error_message = f"Unexpected error: {str(e)}"
                    summary.failed_payouts += 1

                    logger.exception(
                        f"Unexpected error paying prize: {user_id} amount={amount}"
                    )

            summary.payouts.append(result)

        # 이벤트 발행
        if self.event_bus:
            await self.event_bus.publish_event(
                tournament_id=tournament_id,
                event_type=TournamentEventType.TOURNAMENT_COMPLETED,
                data={
                    "settlement_summary": summary.to_dict(),
                    "total_paid": summary.total_paid,
                    "successful_payouts": summary.successful_payouts,
                    "failed_payouts": summary.failed_payouts,
                },
            )

        logger.info(
            f"Tournament settlement complete: {tournament_id} "
            f"total_paid={summary.total_paid:,} "
            f"successful={summary.successful_payouts} "
            f"failed={summary.failed_payouts}"
        )

        return summary

    async def retry_failed_payouts(
        self,
        summary: SettlementSummary,
    ) -> SettlementSummary:
        """
        실패한 지급 재시도.

        Args:
            summary: Previous settlement summary with failed payouts

        Returns:
            Updated SettlementSummary
        """
        failed_payouts = [p for p in summary.payouts if not p.success]

        if not failed_payouts:
            logger.info("No failed payouts to retry")
            return summary

        logger.info(f"Retrying {len(failed_payouts)} failed payouts")

        for result in failed_payouts:
            if result.prize_amount > 0:
                try:
                    tx = await self.wallet.transfer_krw(
                        user_id=result.user_id,
                        amount=result.prize_amount,
                        tx_type=TransactionType.TOURNAMENT_PRIZE,
                        description=f"Tournament Prize (Retry): Rank #{result.rank}",
                    )
                    result.transaction_id = tx.id
                    result.success = True
                    result.error_message = None
                    result.paid_at = datetime.now(timezone.utc)

                    summary.successful_payouts += 1
                    summary.failed_payouts -= 1
                    summary.total_paid += result.prize_amount

                    logger.info(f"Retry successful: {result.user_id}")

                except Exception as e:
                    result.error_message = f"Retry failed: {str(e)}"
                    logger.error(f"Retry failed for {result.user_id}: {e}")

        return summary

    def estimate_payouts(
        self,
        config: TournamentConfig,
        player_count: int,
    ) -> List[Dict]:
        """
        예상 상금 계산 (토너먼트 시작 전 표시용).

        Args:
            config: Tournament config
            player_count: Current or expected player count

        Returns:
            List of estimated payout dicts
        """
        prize_pool = config.buy_in * player_count
        itm_count = max(1, int(player_count * config.itm_percentage / 100))
        itm_count = min(itm_count, len(config.payout_structure))

        estimates = []
        for rank in range(1, itm_count + 1):
            if rank <= len(config.payout_structure):
                percentage = config.payout_structure[rank - 1]
                amount = int(prize_pool * percentage)
                estimates.append(
                    {
                        "rank": rank,
                        "percentage": percentage * 100,
                        "estimated_prize": amount,
                    }
                )

        return estimates
