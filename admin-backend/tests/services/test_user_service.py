"""
User Service Tests - 사용자 조회 및 자산 관리 서비스 테스트
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.services.user_service import (
    UserService,
    UserServiceError,
    UserNotFoundError,
    InsufficientBalanceError
)


class TestUserServiceSearchUsers:
    """search_users 메서드 테스트"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        db = AsyncMock()
        return db
    
    @pytest.fixture
    def service(self, mock_db):
        """UserService instance with mock db"""
        return UserService(mock_db)
    
    @pytest.mark.asyncio
    async def test_search_users_returns_paginated_result(self, service, mock_db):
        """검색 결과가 페이지네이션 형식으로 반환되어야 함"""
        # Mock count query
        count_result = MagicMock()
        count_result.scalar.return_value = 50
        
        # Mock list query
        mock_row = MagicMock()
        mock_row.id = "user-123"
        mock_row.username = "testuser"
        mock_row.email = "test@example.com"
        mock_row.balance = 1000.0
        mock_row.created_at = datetime(2026, 1, 1)
        mock_row.last_login = datetime(2026, 1, 15)
        mock_row.is_banned = False
        
        list_result = MagicMock()
        list_result.fetchall.return_value = [mock_row]
        
        mock_db.execute.side_effect = [count_result, list_result]
        
        result = await service.search_users(page=1, page_size=20)
        
        assert "items" in result
        assert "total" in result
        assert "page" in result
        assert "page_size" in result
        assert "total_pages" in result
        assert result["total"] == 50
        assert result["page"] == 1
        assert result["page_size"] == 20
        assert result["total_pages"] == 3
    
    @pytest.mark.asyncio
    async def test_search_users_with_search_term(self, service, mock_db):
        """검색어로 필터링되어야 함"""
        count_result = MagicMock()
        count_result.scalar.return_value = 1
        
        mock_row = MagicMock()
        mock_row.id = "user-123"
        mock_row.username = "searchuser"
        mock_row.email = "search@example.com"
        mock_row.balance = 500.0
        mock_row.created_at = datetime(2026, 1, 1)
        mock_row.last_login = None
        mock_row.is_banned = False
        
        list_result = MagicMock()
        list_result.fetchall.return_value = [mock_row]
        
        mock_db.execute.side_effect = [count_result, list_result]
        
        result = await service.search_users(search="searchuser")
        
        assert len(result["items"]) == 1
        assert result["items"][0]["username"] == "searchuser"
    
    @pytest.mark.asyncio
    async def test_search_users_with_ban_filter(self, service, mock_db):
        """제재 상태로 필터링되어야 함"""
        count_result = MagicMock()
        count_result.scalar.return_value = 2
        
        mock_row = MagicMock()
        mock_row.id = "banned-user"
        mock_row.username = "banneduser"
        mock_row.email = "banned@example.com"
        mock_row.balance = 0.0
        mock_row.created_at = datetime(2026, 1, 1)
        mock_row.last_login = datetime(2026, 1, 10)
        mock_row.is_banned = True
        
        list_result = MagicMock()
        list_result.fetchall.return_value = [mock_row]
        
        mock_db.execute.side_effect = [count_result, list_result]
        
        result = await service.search_users(is_banned=True)
        
        assert result["items"][0]["is_banned"] is True
    
    @pytest.mark.asyncio
    async def test_search_users_pagination(self, service, mock_db):
        """페이지네이션이 올바르게 동작해야 함"""
        count_result = MagicMock()
        count_result.scalar.return_value = 100
        
        list_result = MagicMock()
        list_result.fetchall.return_value = []
        
        mock_db.execute.side_effect = [count_result, list_result]
        
        result = await service.search_users(page=3, page_size=10)
        
        assert result["page"] == 3
        assert result["page_size"] == 10
        assert result["total_pages"] == 10
    
    @pytest.mark.asyncio
    async def test_search_users_sort_validation(self, service, mock_db):
        """유효하지 않은 정렬 필드는 기본값으로 대체되어야 함"""
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        
        list_result = MagicMock()
        list_result.fetchall.return_value = []
        
        mock_db.execute.side_effect = [count_result, list_result]
        
        # Invalid sort field should not raise error
        result = await service.search_users(sort_by="invalid_field")
        
        assert result["items"] == []
    
    @pytest.mark.asyncio
    async def test_search_users_handles_exception(self, service, mock_db):
        """예외 발생 시 빈 결과를 반환해야 함"""
        mock_db.execute.side_effect = Exception("Database error")
        
        result = await service.search_users()
        
        assert result["items"] == []
        assert result["total"] == 0
    
    @pytest.mark.asyncio
    async def test_search_users_formats_dates(self, service, mock_db):
        """날짜가 ISO 형식으로 변환되어야 함"""
        count_result = MagicMock()
        count_result.scalar.return_value = 1
        
        mock_row = MagicMock()
        mock_row.id = "user-123"
        mock_row.username = "testuser"
        mock_row.email = "test@example.com"
        mock_row.balance = 1000.0
        mock_row.created_at = datetime(2026, 1, 15, 10, 30, 0)
        mock_row.last_login = datetime(2026, 1, 16, 14, 0, 0)
        mock_row.is_banned = False
        
        list_result = MagicMock()
        list_result.fetchall.return_value = [mock_row]
        
        mock_db.execute.side_effect = [count_result, list_result]
        
        result = await service.search_users()
        
        assert result["items"][0]["created_at"] == "2026-01-15T10:30:00"
        assert result["items"][0]["last_login"] == "2026-01-16T14:00:00"


class TestUserServiceGetUserDetail:
    """get_user_detail 메서드 테스트"""
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        return db
    
    @pytest.fixture
    def service(self, mock_db):
        return UserService(mock_db)
    
    @pytest.mark.asyncio
    async def test_get_user_detail_returns_user(self, service, mock_db):
        """사용자 상세 정보를 반환해야 함"""
        mock_row = MagicMock()
        mock_row.id = "user-123"
        mock_row.username = "testuser"
        mock_row.email = "test@example.com"
        mock_row.balance = 1500.0
        mock_row.created_at = datetime(2026, 1, 1)
        mock_row.last_login = datetime(2026, 1, 15)
        mock_row.is_banned = False
        mock_row.ban_reason = None
        mock_row.ban_expires_at = None
        
        result = MagicMock()
        result.fetchone.return_value = mock_row
        mock_db.execute.return_value = result
        
        user = await service.get_user_detail("user-123")
        
        assert user is not None
        assert user["id"] == "user-123"
        assert user["username"] == "testuser"
        assert user["balance"] == 1500.0
    
    @pytest.mark.asyncio
    async def test_get_user_detail_not_found(self, service, mock_db):
        """존재하지 않는 사용자는 None을 반환해야 함"""
        result = MagicMock()
        result.fetchone.return_value = None
        mock_db.execute.return_value = result
        
        user = await service.get_user_detail("nonexistent")
        
        assert user is None
    
    @pytest.mark.asyncio
    async def test_get_user_detail_banned_user(self, service, mock_db):
        """제재된 사용자의 제재 정보를 포함해야 함"""
        mock_row = MagicMock()
        mock_row.id = "banned-user"
        mock_row.username = "banneduser"
        mock_row.email = "banned@example.com"
        mock_row.balance = 0.0
        mock_row.created_at = datetime(2026, 1, 1)
        mock_row.last_login = datetime(2026, 1, 10)
        mock_row.is_banned = True
        mock_row.ban_reason = "Cheating"
        mock_row.ban_expires_at = datetime(2026, 2, 1)
        
        result = MagicMock()
        result.fetchone.return_value = mock_row
        mock_db.execute.return_value = result
        
        user = await service.get_user_detail("banned-user")
        
        assert user["is_banned"] is True
        assert user["ban_reason"] == "Cheating"
        assert user["ban_expires_at"] == "2026-02-01T00:00:00"
    
    @pytest.mark.asyncio
    async def test_get_user_detail_handles_exception(self, service, mock_db):
        """예외 발생 시 None을 반환해야 함"""
        mock_db.execute.side_effect = Exception("Database error")
        
        user = await service.get_user_detail("user-123")
        
        assert user is None


class TestUserServiceGetUserTransactions:
    """get_user_transactions 메서드 테스트"""
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        return db
    
    @pytest.fixture
    def service(self, mock_db):
        return UserService(mock_db)
    
    @pytest.mark.asyncio
    async def test_get_user_transactions_returns_list(self, service, mock_db):
        """거래 내역 목록을 반환해야 함"""
        count_result = MagicMock()
        count_result.scalar.return_value = 5
        
        mock_row = MagicMock()
        mock_row.id = "tx-123"
        mock_row.type = "deposit"
        mock_row.amount = 100.0
        mock_row.balance_before = 900.0
        mock_row.balance_after = 1000.0
        mock_row.description = "USDT Deposit"
        mock_row.created_at = datetime(2026, 1, 15)
        
        list_result = MagicMock()
        list_result.fetchall.return_value = [mock_row]
        
        mock_db.execute.side_effect = [count_result, list_result]
        
        result = await service.get_user_transactions("user-123")
        
        assert "items" in result
        assert "total" in result
        assert result["total"] == 5
        assert len(result["items"]) == 1
        assert result["items"][0]["type"] == "deposit"
    
    @pytest.mark.asyncio
    async def test_get_user_transactions_with_type_filter(self, service, mock_db):
        """거래 유형으로 필터링되어야 함"""
        count_result = MagicMock()
        count_result.scalar.return_value = 2
        
        list_result = MagicMock()
        list_result.fetchall.return_value = []
        
        mock_db.execute.side_effect = [count_result, list_result]
        
        result = await service.get_user_transactions("user-123", tx_type="withdrawal")
        
        assert result["total"] == 2
    
    @pytest.mark.asyncio
    async def test_get_user_transactions_handles_exception(self, service, mock_db):
        """예외 발생 시 빈 결과를 반환해야 함"""
        mock_db.execute.side_effect = Exception("Database error")
        
        result = await service.get_user_transactions("user-123")
        
        assert result["items"] == []
        assert result["total"] == 0


class TestUserServiceGetUserLoginHistory:
    """get_user_login_history 메서드 테스트"""
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        return db
    
    @pytest.fixture
    def service(self, mock_db):
        return UserService(mock_db)
    
    @pytest.mark.asyncio
    async def test_get_user_login_history_returns_list(self, service, mock_db):
        """로그인 기록 목록을 반환해야 함"""
        count_result = MagicMock()
        count_result.scalar.return_value = 10
        
        mock_row = MagicMock()
        mock_row.id = "login-123"
        mock_row.ip_address = "192.168.1.1"
        mock_row.user_agent = "Mozilla/5.0"
        mock_row.success = True
        mock_row.created_at = datetime(2026, 1, 15)
        
        list_result = MagicMock()
        list_result.fetchall.return_value = [mock_row]
        
        mock_db.execute.side_effect = [count_result, list_result]
        
        result = await service.get_user_login_history("user-123")
        
        assert result["total"] == 10
        assert len(result["items"]) == 1
        assert result["items"][0]["ip_address"] == "192.168.1.1"
        assert result["items"][0]["success"] is True
    
    @pytest.mark.asyncio
    async def test_get_user_login_history_handles_exception(self, service, mock_db):
        """예외 발생 시 빈 결과를 반환해야 함"""
        mock_db.execute.side_effect = Exception("Database error")
        
        result = await service.get_user_login_history("user-123")
        
        assert result["items"] == []
        assert result["total"] == 0


class TestUserServiceGetUserHands:
    """get_user_hands 메서드 테스트"""
    
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        return db
    
    @pytest.fixture
    def service(self, mock_db):
        return UserService(mock_db)
    
    @pytest.mark.asyncio
    async def test_get_user_hands_returns_list(self, service, mock_db):
        """핸드 기록 목록을 반환해야 함"""
        count_result = MagicMock()
        count_result.scalar.return_value = 100
        
        mock_row = MagicMock()
        mock_row.id = "hp-123"
        mock_row.hand_id = "hand-456"
        mock_row.room_id = "room-789"
        mock_row.position = 2
        mock_row.cards = "As Kh"
        mock_row.bet_amount = 50.0
        mock_row.won_amount = 120.0
        mock_row.pot_size = 200.0
        mock_row.created_at = datetime(2026, 1, 15)
        
        list_result = MagicMock()
        list_result.fetchall.return_value = [mock_row]
        
        mock_db.execute.side_effect = [count_result, list_result]
        
        result = await service.get_user_hands("user-123")
        
        assert result["total"] == 100
        assert len(result["items"]) == 1
        assert result["items"][0]["cards"] == "As Kh"
        assert result["items"][0]["won_amount"] == 120.0
    
    @pytest.mark.asyncio
    async def test_get_user_hands_handles_exception(self, service, mock_db):
        """예외 발생 시 빈 결과를 반환해야 함"""
        mock_db.execute.side_effect = Exception("Database error")

        result = await service.get_user_hands("user-123")

        assert result["items"] == []
        assert result["total"] == 0


class TestUserServiceCreditChips:
    """credit_chips 메서드 테스트"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return UserService(mock_db)

    @pytest.mark.asyncio
    async def test_credit_chips_success(self, service, mock_db):
        """칩 지급 성공"""
        mock_row = MagicMock()
        mock_row.id = "user-123"
        mock_row.username = "testuser"
        mock_row.balance = 1000.0

        user_result = MagicMock()
        user_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = user_result

        result = await service.credit_chips(
            user_id="user-123",
            amount=500.0,
            reason="이벤트 보상",
            admin_user_id="admin-1",
            admin_username="admin"
        )

        assert result["user_id"] == "user-123"
        assert result["type"] == "credit"
        assert result["amount"] == 500.0
        assert result["balance_before"] == 1000.0
        assert result["balance_after"] == 1500.0
        assert result["reason"] == "이벤트 보상"
        assert "transaction_id" in result
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_credit_chips_user_not_found(self, service, mock_db):
        """존재하지 않는 사용자에게 지급 시도"""
        user_result = MagicMock()
        user_result.fetchone.return_value = None
        mock_db.execute.return_value = user_result

        with pytest.raises(UserNotFoundError):
            await service.credit_chips(
                user_id="nonexistent",
                amount=100.0,
                reason="테스트",
                admin_user_id="admin-1",
                admin_username="admin"
            )

        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_credit_chips_invalid_amount(self, service, mock_db):
        """유효하지 않은 금액 지급 시도"""
        with pytest.raises(ValueError, match="지급 금액은 양수여야 합니다"):
            await service.credit_chips(
                user_id="user-123",
                amount=0,
                reason="테스트",
                admin_user_id="admin-1",
                admin_username="admin"
            )

        with pytest.raises(ValueError, match="지급 금액은 양수여야 합니다"):
            await service.credit_chips(
                user_id="user-123",
                amount=-100,
                reason="테스트",
                admin_user_id="admin-1",
                admin_username="admin"
            )

    @pytest.mark.asyncio
    async def test_credit_chips_zero_balance_user(self, service, mock_db):
        """잔액이 0인 사용자에게 지급"""
        mock_row = MagicMock()
        mock_row.id = "user-123"
        mock_row.username = "newuser"
        mock_row.balance = 0.0

        user_result = MagicMock()
        user_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = user_result

        result = await service.credit_chips(
            user_id="user-123",
            amount=1000.0,
            reason="신규 가입 보너스",
            admin_user_id="admin-1",
            admin_username="admin"
        )

        assert result["balance_before"] == 0.0
        assert result["balance_after"] == 1000.0


class TestUserServiceDebitChips:
    """debit_chips 메서드 테스트"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return UserService(mock_db)

    @pytest.mark.asyncio
    async def test_debit_chips_success(self, service, mock_db):
        """칩 회수 성공"""
        mock_row = MagicMock()
        mock_row.id = "user-123"
        mock_row.username = "testuser"
        mock_row.balance = 1000.0

        user_result = MagicMock()
        user_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = user_result

        result = await service.debit_chips(
            user_id="user-123",
            amount=300.0,
            reason="부정 행위 발견",
            admin_user_id="admin-1",
            admin_username="admin"
        )

        assert result["user_id"] == "user-123"
        assert result["type"] == "debit"
        assert result["amount"] == 300.0
        assert result["balance_before"] == 1000.0
        assert result["balance_after"] == 700.0
        assert result["reason"] == "부정 행위 발견"
        assert "transaction_id" in result
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_debit_chips_user_not_found(self, service, mock_db):
        """존재하지 않는 사용자로부터 회수 시도"""
        user_result = MagicMock()
        user_result.fetchone.return_value = None
        mock_db.execute.return_value = user_result

        with pytest.raises(UserNotFoundError):
            await service.debit_chips(
                user_id="nonexistent",
                amount=100.0,
                reason="테스트",
                admin_user_id="admin-1",
                admin_username="admin"
            )

        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_debit_chips_insufficient_balance(self, service, mock_db):
        """잔액 부족 시 에러"""
        mock_row = MagicMock()
        mock_row.id = "user-123"
        mock_row.username = "testuser"
        mock_row.balance = 100.0

        user_result = MagicMock()
        user_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = user_result

        with pytest.raises(InsufficientBalanceError, match="잔액 부족"):
            await service.debit_chips(
                user_id="user-123",
                amount=500.0,
                reason="테스트",
                admin_user_id="admin-1",
                admin_username="admin"
            )

        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_debit_chips_invalid_amount(self, service, mock_db):
        """유효하지 않은 금액 회수 시도"""
        with pytest.raises(ValueError, match="회수 금액은 양수여야 합니다"):
            await service.debit_chips(
                user_id="user-123",
                amount=0,
                reason="테스트",
                admin_user_id="admin-1",
                admin_username="admin"
            )

        with pytest.raises(ValueError, match="회수 금액은 양수여야 합니다"):
            await service.debit_chips(
                user_id="user-123",
                amount=-100,
                reason="테스트",
                admin_user_id="admin-1",
                admin_username="admin"
            )

    @pytest.mark.asyncio
    async def test_debit_chips_exact_balance(self, service, mock_db):
        """정확히 잔액만큼 회수"""
        mock_row = MagicMock()
        mock_row.id = "user-123"
        mock_row.username = "testuser"
        mock_row.balance = 500.0

        user_result = MagicMock()
        user_result.fetchone.return_value = mock_row
        mock_db.execute.return_value = user_result

        result = await service.debit_chips(
            user_id="user-123",
            amount=500.0,
            reason="전액 회수",
            admin_user_id="admin-1",
            admin_username="admin"
        )

        assert result["balance_before"] == 500.0
        assert result["balance_after"] == 0.0

    @pytest.mark.asyncio
    async def test_debit_chips_db_error(self, service, mock_db):
        """DB 에러 시 UserServiceError 발생"""
        mock_row = MagicMock()
        mock_row.id = "user-123"
        mock_row.username = "testuser"
        mock_row.balance = 1000.0

        # 첫 번째 쿼리(사용자 조회)는 성공, 이후 에러
        user_result = MagicMock()
        user_result.fetchone.return_value = mock_row
        mock_db.execute.side_effect = [user_result, Exception("DB Error")]

        with pytest.raises(UserServiceError, match="칩 회수 실패"):
            await service.debit_chips(
                user_id="user-123",
                amount=100.0,
                reason="테스트",
                admin_user_id="admin-1",
                admin_username="admin"
            )

        mock_db.rollback.assert_called_once()


class TestUserServiceGetUserActivity:
    """get_user_activity 메서드 테스트"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return UserService(mock_db)

    @pytest.mark.asyncio
    async def test_get_user_activity_returns_unified_list(self, service, mock_db):
        """통합 활동 로그가 반환되어야 함"""
        count_result = MagicMock()
        count_result.scalar.return_value = 15

        mock_row = MagicMock()
        mock_row.id = "activity-123"
        mock_row.activity_type = "login"
        mock_row.description = "로그인 성공"
        mock_row.amount = None
        mock_row.ip_address = "192.168.1.1"
        mock_row.device_info = "Mozilla/5.0"
        mock_row.room_id = None
        mock_row.hand_id = None
        mock_row.created_at = datetime(2026, 1, 15, 10, 30, 0)

        list_result = MagicMock()
        list_result.fetchall.return_value = [mock_row]

        mock_db.execute.side_effect = [count_result, list_result]

        result = await service.get_user_activity("user-123")

        assert "items" in result
        assert "total" in result
        assert "total_pages" in result
        assert result["total"] == 15
        assert len(result["items"]) == 1
        assert result["items"][0]["activity_type"] == "login"

    @pytest.mark.asyncio
    async def test_get_user_activity_with_type_filter(self, service, mock_db):
        """활동 타입으로 필터링되어야 함"""
        count_result = MagicMock()
        count_result.scalar.return_value = 5

        mock_row = MagicMock()
        mock_row.id = "tx-123"
        mock_row.activity_type = "transaction"
        mock_row.description = "[관리자 지급] 이벤트 보상"
        mock_row.amount = 1000.0
        mock_row.ip_address = None
        mock_row.device_info = "admin_credit"
        mock_row.room_id = None
        mock_row.hand_id = None
        mock_row.created_at = datetime(2026, 1, 15, 14, 0, 0)

        list_result = MagicMock()
        list_result.fetchall.return_value = [mock_row]

        mock_db.execute.side_effect = [count_result, list_result]

        result = await service.get_user_activity("user-123", activity_type="transaction")

        assert result["total"] == 5
        assert result["items"][0]["activity_type"] == "transaction"
        assert result["items"][0]["amount"] == 1000.0

    @pytest.mark.asyncio
    async def test_get_user_activity_with_date_range(self, service, mock_db):
        """날짜 범위로 필터링되어야 함"""
        count_result = MagicMock()
        count_result.scalar.return_value = 3

        list_result = MagicMock()
        list_result.fetchall.return_value = []

        mock_db.execute.side_effect = [count_result, list_result]

        start_date = datetime(2026, 1, 1)
        end_date = datetime(2026, 1, 31)

        result = await service.get_user_activity(
            "user-123",
            start_date=start_date,
            end_date=end_date
        )

        assert result["total"] == 3

    @pytest.mark.asyncio
    async def test_get_user_activity_hand_type(self, service, mock_db):
        """핸드 타입 활동 로그"""
        count_result = MagicMock()
        count_result.scalar.return_value = 10

        mock_row = MagicMock()
        mock_row.id = "hp-123"
        mock_row.activity_type = "hand"
        mock_row.description = "핸드 승리"
        mock_row.amount = 150.0  # won_amount - bet_amount
        mock_row.ip_address = None
        mock_row.device_info = "As Kh"  # cards
        mock_row.room_id = "room-456"
        mock_row.hand_id = "hand-789"
        mock_row.created_at = datetime(2026, 1, 15, 16, 30, 0)

        list_result = MagicMock()
        list_result.fetchall.return_value = [mock_row]

        mock_db.execute.side_effect = [count_result, list_result]

        result = await service.get_user_activity("user-123", activity_type="hand")

        assert result["items"][0]["activity_type"] == "hand"
        assert result["items"][0]["room_id"] == "room-456"
        assert result["items"][0]["hand_id"] == "hand-789"

    @pytest.mark.asyncio
    async def test_get_user_activity_pagination(self, service, mock_db):
        """페이지네이션이 올바르게 동작해야 함"""
        count_result = MagicMock()
        count_result.scalar.return_value = 100

        list_result = MagicMock()
        list_result.fetchall.return_value = []

        mock_db.execute.side_effect = [count_result, list_result]

        result = await service.get_user_activity("user-123", page=3, page_size=10)

        assert result["page"] == 3
        assert result["page_size"] == 10
        assert result["total_pages"] == 10

    @pytest.mark.asyncio
    async def test_get_user_activity_handles_exception(self, service, mock_db):
        """예외 발생 시 빈 결과를 반환해야 함"""
        mock_db.execute.side_effect = Exception("Database error")

        result = await service.get_user_activity("user-123")

        assert result["items"] == []
        assert result["total"] == 0
        assert result["total_pages"] == 0

    @pytest.mark.asyncio
    async def test_get_user_activity_invalid_type_returns_empty(self, service, mock_db):
        """유효하지 않은 타입 필터 시 빈 결과 반환"""
        # activity_type이 login, transaction, hand 중 하나가 아닌 경우
        # union_parts가 비어있어 빈 결과 반환
        result = await service.get_user_activity("user-123", activity_type="invalid")

        assert result["items"] == []
        assert result["total"] == 0
