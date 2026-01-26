"""Partner Settlement Service Tests - 파트너 정산 서비스 테스트.

프로덕션 배포 전 필수 테스트:
- generate_settlements() 정산 생성 로직
- calculate_commission() 수수료 계산 (rakeback, revshare, turnover)
- 정산 상태 변경 (approve, reject, pay)
- 정산 지급 및 잔액 업데이트
- 에러 처리 및 롤백
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

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
from app.services.partner_settlement import (
    PartnerSettlementService,
    SettlementError,
)


class TestSettlementError:
    """SettlementError 단위 테스트."""

    def test_error_properties(self):
        """에러 속성 확인."""
        error = SettlementError(
            code="TEST_ERROR",
            message="테스트 에러",
            details={"key": "value"},
        )

        assert error.code == "TEST_ERROR"
        assert error.message == "테스트 에러"
        assert error.details == {"key": "value"}
        assert str(error) == "테스트 에러"

    def test_error_without_details(self):
        """details 없이 생성."""
        error = SettlementError("CODE", "message")
        assert error.details == {}


class TestCalculateCommission:
    """수수료 계산 단위 테스트."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        """PartnerSettlementService 인스턴스."""
        return PartnerSettlementService(mock_db)

    @pytest.mark.asyncio
    async def test_calculate_rakeback(self, service, mock_db):
        """레이크백 수수료 계산."""
        partner = Partner(
            id=str(uuid4()),
            user_id=str(uuid4()),
            code="TEST001",
            name="Test Partner",
            commission_type=CommissionType.RAKEBACK,
            commission_rate=Decimal("0.3"),  # 30%
            status=PartnerStatus.ACTIVE,
        )

        # Mock 쿼리 결과: 2명의 유저가 각각 10000, 5000 레이크 지불
        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(user_id="user1", nickname="Player1", rake_amount=10000),
            MagicMock(user_id="user2", nickname="Player2", rake_amount=5000),
        ]
        mock_db.execute.return_value = mock_result

        period_start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        period_end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        base_amount, commission, detail = await service.calculate_commission(
            partner, period_start, period_end
        )

        assert base_amount == 15000  # 10000 + 5000
        assert commission == 4500  # 15000 * 0.3
        assert len(detail) == 2

    @pytest.mark.asyncio
    async def test_calculate_revshare(self, service, mock_db):
        """수익 분배 수수료 계산."""
        partner = Partner(
            id=str(uuid4()),
            user_id=str(uuid4()),
            code="TEST002",
            name="Test Partner",
            commission_type=CommissionType.REVSHARE,
            commission_rate=Decimal("0.5"),  # 50%
            status=PartnerStatus.ACTIVE,
        )

        # Mock 쿼리 결과: 순손실 유저만 포함
        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(user_id="user1", nickname="Player1", net_profit=-20000),  # 20000 손실
            MagicMock(user_id="user2", nickname="Player2", net_profit=5000),  # 이익 (제외)
            MagicMock(user_id="user3", nickname="Player3", net_profit=-10000),  # 10000 손실
        ]
        mock_db.execute.return_value = mock_result

        period_start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        period_end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        base_amount, commission, detail = await service.calculate_commission(
            partner, period_start, period_end
        )

        assert base_amount == 30000  # 20000 + 10000 (손실만)
        assert commission == 15000  # 30000 * 0.5
        assert len(detail) == 2  # 손실 유저만

    @pytest.mark.asyncio
    async def test_calculate_turnover(self, service, mock_db):
        """턴오버(거래량) 수수료 계산."""
        partner = Partner(
            id=str(uuid4()),
            user_id=str(uuid4()),
            code="TEST003",
            name="Test Partner",
            commission_type=CommissionType.TURNOVER,
            commission_rate=Decimal("0.01"),  # 1%
            status=PartnerStatus.ACTIVE,
        )

        # Mock 쿼리 결과: BUY_IN 금액
        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(user_id="user1", nickname="Player1", bet_amount=100000),
            MagicMock(user_id="user2", nickname="Player2", bet_amount=50000),
        ]
        mock_db.execute.return_value = mock_result

        period_start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        period_end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        base_amount, commission, detail = await service.calculate_commission(
            partner, period_start, period_end
        )

        assert base_amount == 150000  # 100000 + 50000
        assert commission == 1500  # 150000 * 0.01
        assert len(detail) == 2

    @pytest.mark.asyncio
    async def test_calculate_invalid_commission_type(self, service, mock_db):
        """잘못된 수수료 타입."""
        partner = Partner(
            id=str(uuid4()),
            user_id=str(uuid4()),
            code="TEST004",
            name="Test Partner",
            commission_type="INVALID",  # 잘못된 타입
            commission_rate=Decimal("0.1"),
            status=PartnerStatus.ACTIVE,
        )

        period_start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        period_end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        with pytest.raises(SettlementError) as exc_info:
            await service.calculate_commission(partner, period_start, period_end)

        assert exc_info.value.code == "INVALID_COMMISSION_TYPE"


class TestGenerateSettlements:
    """정산 생성 테스트."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        return PartnerSettlementService(mock_db)

    @pytest.mark.asyncio
    async def test_generate_settlements_multiple_partners(self, service, mock_db):
        """여러 파트너에 대한 정산 생성."""
        partner1 = Partner(
            id=str(uuid4()),
            user_id=str(uuid4()),
            code="P001",
            name="Partner 1",
            commission_type=CommissionType.RAKEBACK,
            commission_rate=Decimal("0.3"),
            status=PartnerStatus.ACTIVE,
        )
        partner2 = Partner(
            id=str(uuid4()),
            user_id=str(uuid4()),
            code="P002",
            name="Partner 2",
            commission_type=CommissionType.REVSHARE,
            commission_rate=Decimal("0.5"),
            status=PartnerStatus.ACTIVE,
        )

        # Mock partners query
        partners_result = MagicMock()
        partners_result.scalars.return_value.all.return_value = [partner1, partner2]

        # Mock commission calculation query
        commission_result = MagicMock()
        commission_result.all.return_value = [
            MagicMock(user_id="user1", nickname="Player1", rake_amount=10000),
        ]

        mock_db.execute.side_effect = [partners_result, commission_result, commission_result]

        period_start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        period_end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        settlements = await service.generate_settlements(
            period_type=SettlementPeriod.MONTHLY,
            period_start=period_start,
            period_end=period_end,
        )

        # 2명의 파트너에 대한 정산이 생성되어야 함
        assert len(settlements) == 2
        assert mock_db.add.call_count == 2
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_settlements_skip_no_activity(self, service, mock_db):
        """활동 없는 파트너는 건너뜀."""
        partner = Partner(
            id=str(uuid4()),
            user_id=str(uuid4()),
            code="P001",
            name="Partner 1",
            commission_type=CommissionType.RAKEBACK,
            commission_rate=Decimal("0.3"),
            status=PartnerStatus.ACTIVE,
        )

        # Mock partners query
        partners_result = MagicMock()
        partners_result.scalars.return_value.all.return_value = [partner]

        # Mock commission calculation query - 활동 없음
        commission_result = MagicMock()
        commission_result.all.return_value = []

        mock_db.execute.side_effect = [partners_result, commission_result]

        period_start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        period_end = datetime(2024, 1, 31, tzinfo=timezone.utc)

        settlements = await service.generate_settlements(
            period_type=SettlementPeriod.MONTHLY,
            period_start=period_start,
            period_end=period_end,
        )

        assert len(settlements) == 0
        assert mock_db.add.call_count == 0


class TestApproveRejectSettlement:
    """정산 승인/거부 테스트."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        return PartnerSettlementService(mock_db)

    @pytest.mark.asyncio
    async def test_approve_settlement_success(self, service, mock_db):
        """정산 승인 성공."""
        settlement_id = str(uuid4())
        settlement = PartnerSettlement(
            id=settlement_id,
            partner_id=str(uuid4()),
            period_type=SettlementPeriod.MONTHLY,
            period_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2024, 1, 31, tzinfo=timezone.utc),
            commission_type=CommissionType.RAKEBACK,
            commission_rate=Decimal("0.3"),
            base_amount=10000,
            commission_amount=3000,
            status=SettlementStatus.PENDING,
        )
        mock_db.get.return_value = settlement

        result = await service.approve_settlement(settlement_id, "admin-user-id")

        assert result.status == SettlementStatus.APPROVED
        assert result.approved_by == "admin-user-id"
        assert result.approved_at is not None
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_approve_settlement_not_found(self, service, mock_db):
        """존재하지 않는 정산 승인 시도."""
        mock_db.get.return_value = None

        with pytest.raises(SettlementError) as exc_info:
            await service.approve_settlement("nonexistent", "admin")

        assert exc_info.value.code == "SETTLEMENT_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_approve_already_approved_settlement(self, service, mock_db):
        """이미 승인된 정산 재승인 시도."""
        settlement = PartnerSettlement(
            id=str(uuid4()),
            partner_id=str(uuid4()),
            period_type=SettlementPeriod.MONTHLY,
            period_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2024, 1, 31, tzinfo=timezone.utc),
            commission_type=CommissionType.RAKEBACK,
            commission_rate=Decimal("0.3"),
            base_amount=10000,
            commission_amount=3000,
            status=SettlementStatus.APPROVED,  # 이미 승인됨
        )
        mock_db.get.return_value = settlement

        with pytest.raises(SettlementError) as exc_info:
            await service.approve_settlement(settlement.id, "admin")

        assert exc_info.value.code == "INVALID_SETTLEMENT_STATUS"

    @pytest.mark.asyncio
    async def test_reject_settlement_success(self, service, mock_db):
        """정산 거부 성공."""
        settlement = PartnerSettlement(
            id=str(uuid4()),
            partner_id=str(uuid4()),
            period_type=SettlementPeriod.MONTHLY,
            period_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2024, 1, 31, tzinfo=timezone.utc),
            commission_type=CommissionType.RAKEBACK,
            commission_rate=Decimal("0.3"),
            base_amount=10000,
            commission_amount=3000,
            status=SettlementStatus.PENDING,
        )
        mock_db.get.return_value = settlement

        result = await service.reject_settlement(
            settlement.id, "admin-user-id", "테스트 거부 사유"
        )

        assert result.status == SettlementStatus.REJECTED
        assert result.approved_by == "admin-user-id"
        assert result.rejection_reason == "테스트 거부 사유"
        mock_db.flush.assert_called_once()


class TestPaySettlement:
    """정산 지급 테스트."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        return PartnerSettlementService(mock_db)

    @pytest.mark.asyncio
    async def test_pay_settlement_success(self, service, mock_db):
        """정산 지급 성공."""
        partner_id = str(uuid4())
        user_id = str(uuid4())

        partner = Partner(
            id=partner_id,
            user_id=user_id,
            code="P001",
            name="Test Partner",
            commission_type=CommissionType.RAKEBACK,
            commission_rate=Decimal("0.3"),
            status=PartnerStatus.ACTIVE,
            total_commission_earned=0,
        )

        user = User(
            id=user_id,
            nickname="partner_user",
            krw_balance=100000,
        )

        settlement = PartnerSettlement(
            id=str(uuid4()),
            partner_id=partner_id,
            period_type=SettlementPeriod.MONTHLY,
            period_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2024, 1, 31, tzinfo=timezone.utc),
            commission_type=CommissionType.RAKEBACK,
            commission_rate=Decimal("0.3"),
            base_amount=10000,
            commission_amount=3000,
            status=SettlementStatus.APPROVED,  # 승인됨
        )

        # Mock get 호출 순서
        mock_db.get.side_effect = [settlement, partner, user]

        result = await service.pay_settlement(settlement.id, "admin-user-id")

        # 검증
        assert result.status == SettlementStatus.PAID
        assert result.paid_at is not None
        assert user.krw_balance == 103000  # 100000 + 3000
        assert partner.total_commission_earned == 3000
        mock_db.add.assert_called_once()  # WalletTransaction 추가
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_pay_settlement_not_approved(self, service, mock_db):
        """승인되지 않은 정산 지급 시도."""
        settlement = PartnerSettlement(
            id=str(uuid4()),
            partner_id=str(uuid4()),
            period_type=SettlementPeriod.MONTHLY,
            period_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2024, 1, 31, tzinfo=timezone.utc),
            commission_type=CommissionType.RAKEBACK,
            commission_rate=Decimal("0.3"),
            base_amount=10000,
            commission_amount=3000,
            status=SettlementStatus.PENDING,  # 아직 승인 안됨
        )
        mock_db.get.return_value = settlement

        with pytest.raises(SettlementError) as exc_info:
            await service.pay_settlement(settlement.id, "admin")

        assert exc_info.value.code == "INVALID_SETTLEMENT_STATUS"

    @pytest.mark.asyncio
    async def test_pay_settlement_partner_not_found(self, service, mock_db):
        """파트너를 찾을 수 없는 경우."""
        settlement = PartnerSettlement(
            id=str(uuid4()),
            partner_id=str(uuid4()),
            period_type=SettlementPeriod.MONTHLY,
            period_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2024, 1, 31, tzinfo=timezone.utc),
            commission_type=CommissionType.RAKEBACK,
            commission_rate=Decimal("0.3"),
            base_amount=10000,
            commission_amount=3000,
            status=SettlementStatus.APPROVED,
        )

        # settlement은 있지만 partner는 없음
        mock_db.get.side_effect = [settlement, None]

        with pytest.raises(SettlementError) as exc_info:
            await service.pay_settlement(settlement.id, "admin")

        assert exc_info.value.code == "PARTNER_NOT_FOUND"


class TestListSettlements:
    """정산 목록 조회 테스트."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        return PartnerSettlementService(mock_db)

    @pytest.mark.asyncio
    async def test_list_settlements_with_pagination(self, service, mock_db):
        """페이지네이션 포함 정산 목록 조회."""
        settlements = [
            PartnerSettlement(
                id=str(uuid4()),
                partner_id=str(uuid4()),
                period_type=SettlementPeriod.DAILY,
                period_start=datetime(2024, 1, i, tzinfo=timezone.utc),
                period_end=datetime(2024, 1, i + 1, tzinfo=timezone.utc),
                commission_type=CommissionType.RAKEBACK,
                commission_rate=Decimal("0.3"),
                base_amount=10000,
                commission_amount=3000,
                status=SettlementStatus.PENDING,
            )
            for i in range(1, 6)
        ]

        # Mock count query
        count_result = MagicMock()
        count_result.scalar.return_value = 25

        # Mock list query
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = settlements[:5]

        mock_db.execute.side_effect = [count_result, list_result]

        result_settlements, total = await service.list_settlements(
            page=1, page_size=5
        )

        assert len(result_settlements) == 5
        assert total == 25

    @pytest.mark.asyncio
    async def test_list_settlements_with_filters(self, service, mock_db):
        """필터 적용 정산 목록 조회."""
        # Mock count query
        count_result = MagicMock()
        count_result.scalar.return_value = 3

        # Mock list query
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [count_result, list_result]

        partner_id = str(uuid4())
        result_settlements, total = await service.list_settlements(
            partner_id=partner_id,
            status=SettlementStatus.PENDING,
            page=1,
            page_size=10,
        )

        assert total == 3
        # execute가 2번 호출되었는지 확인
        assert mock_db.execute.call_count == 2


class TestGetSettlementSummary:
    """정산 요약 조회 테스트."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        return PartnerSettlementService(mock_db)

    @pytest.mark.asyncio
    async def test_get_settlement_summary(self, service, mock_db):
        """정산 요약 조회."""
        partner_id = str(uuid4())

        # Mock 4개의 쿼리 결과 (total, pending, approved, this_month)
        mock_db.execute.side_effect = [
            MagicMock(scalar=lambda: 100000),  # total_earned
            MagicMock(scalar=lambda: 15000),   # pending_amount
            MagicMock(scalar=lambda: 5000),    # approved_amount
            MagicMock(scalar=lambda: 25000),   # this_month_amount
        ]

        summary = await service.get_settlement_summary(partner_id)

        assert summary["total_earned"] == 100000
        assert summary["pending_amount"] == 15000
        assert summary["approved_amount"] == 5000
        assert summary["paid_amount"] == 100000
        assert summary["this_month_amount"] == 25000


class TestCommissionRateEdgeCases:
    """수수료율 엣지 케이스 테스트."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        return PartnerSettlementService(mock_db)

    @pytest.mark.asyncio
    async def test_zero_commission_rate(self, service, mock_db):
        """0% 수수료율."""
        partner = Partner(
            id=str(uuid4()),
            user_id=str(uuid4()),
            code="P001",
            name="Test Partner",
            commission_type=CommissionType.RAKEBACK,
            commission_rate=Decimal("0"),  # 0%
            status=PartnerStatus.ACTIVE,
        )

        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(user_id="user1", nickname="Player1", rake_amount=10000),
        ]
        mock_db.execute.return_value = mock_result

        base_amount, commission, _ = await service.calculate_commission(
            partner,
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 31, tzinfo=timezone.utc),
        )

        assert base_amount == 10000
        assert commission == 0

    @pytest.mark.asyncio
    async def test_high_commission_rate(self, service, mock_db):
        """높은 수수료율 (100%)."""
        partner = Partner(
            id=str(uuid4()),
            user_id=str(uuid4()),
            code="P001",
            name="Test Partner",
            commission_type=CommissionType.RAKEBACK,
            commission_rate=Decimal("1.0"),  # 100%
            status=PartnerStatus.ACTIVE,
        )

        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(user_id="user1", nickname="Player1", rake_amount=10000),
        ]
        mock_db.execute.return_value = mock_result

        base_amount, commission, _ = await service.calculate_commission(
            partner,
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 31, tzinfo=timezone.utc),
        )

        assert base_amount == 10000
        assert commission == 10000  # 100%

    @pytest.mark.asyncio
    async def test_decimal_precision(self, service, mock_db):
        """소수점 정밀도 테스트."""
        partner = Partner(
            id=str(uuid4()),
            user_id=str(uuid4()),
            code="P001",
            name="Test Partner",
            commission_type=CommissionType.RAKEBACK,
            commission_rate=Decimal("0.333"),  # 33.3%
            status=PartnerStatus.ACTIVE,
        )

        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(user_id="user1", nickname="Player1", rake_amount=10000),
        ]
        mock_db.execute.return_value = mock_result

        base_amount, commission, _ = await service.calculate_commission(
            partner,
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 31, tzinfo=timezone.utc),
        )

        assert base_amount == 10000
        assert commission == 3330  # int(10000 * 0.333)


class TestMultiplePartnerSettlements:
    """다중 파트너 정산 테스트."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        return PartnerSettlementService(mock_db)

    @pytest.mark.asyncio
    async def test_generate_settlements_for_specific_partners(self, service, mock_db):
        """특정 파트너만 정산 생성."""
        partner1_id = str(uuid4())
        partner2_id = str(uuid4())

        partner1 = Partner(
            id=partner1_id,
            user_id=str(uuid4()),
            code="P001",
            name="Partner 1",
            commission_type=CommissionType.RAKEBACK,
            commission_rate=Decimal("0.3"),
            status=PartnerStatus.ACTIVE,
        )

        partners_result = MagicMock()
        partners_result.scalars.return_value.all.return_value = [partner1]

        commission_result = MagicMock()
        commission_result.all.return_value = [
            MagicMock(user_id="user1", nickname="Player1", rake_amount=10000),
        ]

        mock_db.execute.side_effect = [partners_result, commission_result]

        settlements = await service.generate_settlements(
            period_type=SettlementPeriod.DAILY,
            period_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2024, 1, 2, tzinfo=timezone.utc),
            partner_ids=[partner1_id],  # 특정 파트너만
        )

        assert len(settlements) == 1
        assert settlements[0].partner_id == partner1_id
