"""
Tournament Settlement Tests.

토너먼트 상금 정산 기능 테스트.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.tournament.settlement import (
    TournamentSettlement,
    PayoutResult,
    SettlementSummary,
)
from app.tournament.models import (
    TournamentConfig,
    TournamentState,
    TournamentPlayer,
    TournamentStatus,
)
from app.models.wallet import TransactionType


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tournament_config() -> TournamentConfig:
    """기본 토너먼트 설정."""
    return TournamentConfig(
        tournament_id="test-tournament-001",
        name="Test Tournament",
        min_players=2,
        max_players=100,
        buy_in=10000,
        starting_chips=10000,
        payout_structure=(0.25, 0.15, 0.10, 0.08, 0.07, 0.06, 0.05, 0.04),
        itm_percentage=15.0,
    )


@pytest.fixture
def completed_tournament_state(tournament_config: TournamentConfig) -> TournamentState:
    """10명 참가, 2명 남은 토너먼트 상태."""
    players = {}

    # 1위: 활성 플레이어 (가장 많은 칩)
    players["user-1"] = TournamentPlayer(
        user_id="user-1",
        nickname="Winner",
        chip_count=50000,
        is_active=True,
        table_id="table-1",
        seat_position=0,
    )

    # 2위: 활성 플레이어 (두번째 칩)
    players["user-2"] = TournamentPlayer(
        user_id="user-2",
        nickname="RunnerUp",
        chip_count=30000,
        is_active=True,
        table_id="table-1",
        seat_position=1,
    )

    # 3위~10위: 탈락 플레이어 (elimination_rank 순)
    for i in range(3, 11):
        players[f"user-{i}"] = TournamentPlayer(
            user_id=f"user-{i}",
            nickname=f"Player{i}",
            chip_count=0,
            is_active=False,
            elimination_rank=i,
            elimination_time=datetime.utcnow(),
        )

    return TournamentState(
        tournament_id="test-tournament-001",
        config=tournament_config,
        status=TournamentStatus.HEADS_UP,
        players=players,
        total_prize_pool=100000,  # 10명 * 10000 buy-in
    )


@pytest.fixture
def mock_wallet_service():
    """Mock WalletService."""
    wallet = MagicMock()
    wallet.transfer_krw = AsyncMock()

    # 성공 응답 반환
    tx_mock = MagicMock()
    tx_mock.id = "tx-12345"
    wallet.transfer_krw.return_value = tx_mock

    return wallet


# =============================================================================
# Unit Tests: 순위 계산
# =============================================================================


class TestFinalRanking:
    """최종 순위 계산 테스트."""

    def test_final_ranking_active_players_first(
        self, completed_tournament_state: TournamentState
    ):
        """활성 플레이어가 순위 상위에 위치."""
        settlement = TournamentSettlement(wallet_service=None)
        ranking = settlement.get_final_ranking(completed_tournament_state)

        # 1위, 2위는 활성 플레이어
        assert ranking[0].user_id == "user-1"
        assert ranking[0].is_active is True
        assert ranking[1].user_id == "user-2"
        assert ranking[1].is_active is True

        # 3위부터는 탈락 플레이어
        assert ranking[2].elimination_rank == 3
        assert ranking[2].is_active is False

    def test_active_players_sorted_by_chips(
        self, completed_tournament_state: TournamentState
    ):
        """활성 플레이어는 칩 수 기준 정렬."""
        settlement = TournamentSettlement(wallet_service=None)
        ranking = settlement.get_final_ranking(completed_tournament_state)

        # user-1이 50000칩, user-2가 30000칩
        assert ranking[0].chip_count > ranking[1].chip_count

    def test_eliminated_players_sorted_by_rank(
        self, completed_tournament_state: TournamentState
    ):
        """탈락 플레이어는 elimination_rank 순 정렬."""
        settlement = TournamentSettlement(wallet_service=None)
        ranking = settlement.get_final_ranking(completed_tournament_state)

        # 3위부터 순서 확인
        eliminated = [p for p in ranking if not p.is_active]
        for i, player in enumerate(eliminated):
            assert player.elimination_rank == i + 3


# =============================================================================
# Unit Tests: 상금 계산
# =============================================================================


class TestPayoutCalculation:
    """상금 계산 테스트."""

    def test_calculate_itm_players_10_percent(
        self, completed_tournament_state: TournamentState
    ):
        """15% ITM = 10명 중 1.5명 → 1명 (최소 1명)."""
        settlement = TournamentSettlement(wallet_service=None)
        itm_count = settlement.calculate_itm_players(completed_tournament_state)

        # 10명 * 15% = 1.5 → 1명
        assert itm_count >= 1

    def test_calculate_payouts_distribution(
        self, completed_tournament_state: TournamentState
    ):
        """상금 분배 검증."""
        settlement = TournamentSettlement(wallet_service=None)
        payouts = settlement.calculate_payouts(completed_tournament_state)

        # 상금을 받는 플레이어가 있어야 함
        assert len(payouts) > 0

        # 1위 상금 확인 (25% = 25000)
        if "user-1" in payouts:
            rank, amount, percentage = payouts["user-1"]
            assert rank == 1
            assert amount == 25000  # 100000 * 0.25
            assert percentage == 0.25

    def test_total_payout_matches_prize_pool(
        self, completed_tournament_state: TournamentState
    ):
        """총 상금이 상금풀의 일정 비율."""
        settlement = TournamentSettlement(wallet_service=None)
        payouts = settlement.calculate_payouts(completed_tournament_state)

        total_payout = sum(amount for _, (_, amount, _) in payouts.items())
        prize_pool = completed_tournament_state.total_prize_pool

        # 총 상금이 상금풀 이하
        assert total_payout <= prize_pool

    def test_payout_structure_order(self, completed_tournament_state: TournamentState):
        """상금 순서: 1위 > 2위 > 3위..."""
        settlement = TournamentSettlement(wallet_service=None)
        payouts = settlement.calculate_payouts(completed_tournament_state)

        sorted_payouts = sorted(payouts.items(), key=lambda x: x[1][0])

        prev_amount = float("inf")
        for user_id, (rank, amount, _) in sorted_payouts:
            assert amount <= prev_amount
            prev_amount = amount


# =============================================================================
# Integration Tests: 정산 실행
# =============================================================================


class TestSettleTournament:
    """토너먼트 정산 통합 테스트."""

    @pytest.mark.asyncio
    async def test_settle_tournament_success(
        self,
        completed_tournament_state: TournamentState,
        mock_wallet_service,
    ):
        """정산 성공 시나리오."""
        settlement = TournamentSettlement(wallet_service=mock_wallet_service)

        summary = await settlement.settle_tournament(
            "test-tournament-001",
            completed_tournament_state,
        )

        # 정산 결과 확인
        assert summary.tournament_id == "test-tournament-001"
        assert summary.total_prize_pool == 100000
        assert summary.successful_payouts > 0
        assert summary.failed_payouts == 0

    @pytest.mark.asyncio
    async def test_settle_tournament_creates_transactions(
        self,
        completed_tournament_state: TournamentState,
        mock_wallet_service,
    ):
        """정산 시 WalletService.transfer_krw 호출 확인."""
        settlement = TournamentSettlement(wallet_service=mock_wallet_service)

        await settlement.settle_tournament(
            "test-tournament-001",
            completed_tournament_state,
        )

        # transfer_krw가 호출되었는지 확인
        assert mock_wallet_service.transfer_krw.called

        # TOURNAMENT_PRIZE 타입으로 호출되었는지 확인
        calls = mock_wallet_service.transfer_krw.call_args_list
        for call in calls:
            assert call.kwargs["tx_type"] == TransactionType.TOURNAMENT_PRIZE

    @pytest.mark.asyncio
    async def test_settle_tournament_handles_wallet_error(
        self,
        completed_tournament_state: TournamentState,
    ):
        """WalletError 발생 시 처리."""
        from app.services.wallet import WalletError

        wallet = MagicMock()
        wallet.transfer_krw = AsyncMock(
            side_effect=WalletError("Insufficient balance", "INSUFFICIENT_BALANCE")
        )

        settlement = TournamentSettlement(wallet_service=wallet)

        summary = await settlement.settle_tournament(
            "test-tournament-001",
            completed_tournament_state,
        )

        # 실패한 지급이 있어야 함
        assert summary.failed_payouts > 0

        # 오류 메시지 확인
        failed_payouts = [p for p in summary.payouts if not p.success]
        assert len(failed_payouts) > 0
        assert failed_payouts[0].error_message is not None


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """엣지 케이스 테스트."""

    def test_empty_tournament_no_payouts(self, tournament_config: TournamentConfig):
        """플레이어 없는 토너먼트."""
        state = TournamentState(
            tournament_id="empty-tournament",
            config=tournament_config,
            status=TournamentStatus.CANCELLED,
            players={},
            total_prize_pool=0,
        )

        settlement = TournamentSettlement(wallet_service=None)
        payouts = settlement.calculate_payouts(state)

        assert len(payouts) == 0

    def test_single_player_tournament(self, tournament_config: TournamentConfig):
        """1명만 참가한 토너먼트."""
        players = {
            "solo-player": TournamentPlayer(
                user_id="solo-player",
                nickname="SoloWinner",
                chip_count=10000,
                is_active=True,
            )
        }

        state = TournamentState(
            tournament_id="solo-tournament",
            config=tournament_config,
            status=TournamentStatus.COMPLETED,
            players=players,
            total_prize_pool=10000,
        )

        settlement = TournamentSettlement(wallet_service=None)
        payouts = settlement.calculate_payouts(state)

        # 1명도 상금 수령 가능
        assert "solo-player" in payouts

    def test_estimate_payouts_before_start(self, tournament_config: TournamentConfig):
        """토너먼트 시작 전 예상 상금."""
        settlement = TournamentSettlement(wallet_service=None)

        estimates = settlement.estimate_payouts(tournament_config, player_count=50)

        # 예상 상금 확인
        assert len(estimates) > 0
        assert estimates[0]["rank"] == 1
        # 50명 * 10000 buy-in = 500000, 1위 = 25% = 125000
        assert estimates[0]["estimated_prize"] == 125000


# =============================================================================
# Retry Tests
# =============================================================================


class TestRetryPayouts:
    """실패한 지급 재시도 테스트."""

    @pytest.mark.asyncio
    async def test_retry_failed_payouts(self, mock_wallet_service):
        """실패한 지급 재시도 성공."""
        settlement = TournamentSettlement(wallet_service=mock_wallet_service)

        # 실패한 지급이 있는 요약
        summary = SettlementSummary(
            tournament_id="test-tournament",
            tournament_name="Test",
            total_prize_pool=100000,
            total_paid=0,
            successful_payouts=0,
            failed_payouts=1,
            payouts=[
                PayoutResult(
                    user_id="user-1",
                    nickname="Player1",
                    rank=1,
                    prize_amount=25000,
                    success=False,
                    error_message="Previous failure",
                )
            ],
        )

        # 재시도
        updated_summary = await settlement.retry_failed_payouts(summary)

        # 성공으로 변경
        assert updated_summary.successful_payouts == 1
        assert updated_summary.failed_payouts == 0
        assert updated_summary.payouts[0].success is True

    @pytest.mark.asyncio
    async def test_retry_no_failed_payouts(self, mock_wallet_service):
        """실패한 지급이 없으면 스킵."""
        settlement = TournamentSettlement(wallet_service=mock_wallet_service)

        # 모두 성공한 요약
        summary = SettlementSummary(
            tournament_id="test-tournament",
            tournament_name="Test",
            total_prize_pool=100000,
            total_paid=25000,
            successful_payouts=1,
            failed_payouts=0,
            payouts=[
                PayoutResult(
                    user_id="user-1",
                    nickname="Player1",
                    rank=1,
                    prize_amount=25000,
                    success=True,
                    transaction_id="tx-123",
                )
            ],
        )

        # 재시도해도 변화 없음
        updated_summary = await settlement.retry_failed_payouts(summary)

        assert updated_summary.successful_payouts == 1
        assert mock_wallet_service.transfer_krw.call_count == 0
