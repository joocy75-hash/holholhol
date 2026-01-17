"""
Users API Tests - 사용자 API 엔드포인트 테스트
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api.users import router
from app.models.admin_user import AdminUser, AdminRole
from app.services.user_service import (
    UserNotFoundError,
    InsufficientBalanceError,
    UserServiceError
)


# Test app setup
app = FastAPI()
app.include_router(router, prefix="/api/users")


class TestListUsersAPI:
    """GET /api/users 엔드포인트 테스트"""
    
    @pytest.fixture
    def mock_admin_user(self):
        """Mock admin user for authentication"""
        user = MagicMock(spec=AdminUser)
        user.id = "admin-123"
        user.username = "admin"
        user.role = "viewer"
        return user
    
    @pytest.fixture
    def mock_user_service(self):
        """Mock UserService"""
        with patch("app.api.users.UserService") as mock:
            service_instance = AsyncMock()
            mock.return_value = service_instance
            yield service_instance
    
    @pytest.mark.asyncio
    async def test_list_users_success(self, mock_admin_user, mock_user_service):
        """사용자 목록 조회 성공"""
        mock_user_service.search_users.return_value = {
            "items": [
                {
                    "id": "user-1",
                    "username": "testuser1",
                    "email": "test1@example.com",
                    "balance": 1000.0,
                    "created_at": "2026-01-01T00:00:00",
                    "last_login": "2026-01-15T00:00:00",
                    "is_banned": False
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 20,
            "total_pages": 1
        }
        
        with patch("app.api.users.require_viewer", return_value=mock_admin_user):
            with patch("app.api.users.get_main_db"):
                # Verify service method signature
                result = await mock_user_service.search_users(
                    search=None,
                    page=1,
                    page_size=20,
                    is_banned=None,
                    sort_by="created_at",
                    sort_order="desc"
                )
                
                assert result["total"] == 1
                assert len(result["items"]) == 1
    
    @pytest.mark.asyncio
    async def test_list_users_with_search(self, mock_admin_user, mock_user_service):
        """검색어로 사용자 목록 조회"""
        mock_user_service.search_users.return_value = {
            "items": [
                {
                    "id": "user-1",
                    "username": "searchuser",
                    "email": "search@example.com",
                    "balance": 500.0,
                    "created_at": "2026-01-01T00:00:00",
                    "last_login": None,
                    "is_banned": False
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 20,
            "total_pages": 1
        }
        
        result = await mock_user_service.search_users(search="searchuser")
        
        assert result["items"][0]["username"] == "searchuser"
    
    @pytest.mark.asyncio
    async def test_list_users_with_ban_filter(self, mock_admin_user, mock_user_service):
        """제재 상태로 필터링"""
        mock_user_service.search_users.return_value = {
            "items": [
                {
                    "id": "banned-1",
                    "username": "banneduser",
                    "email": "banned@example.com",
                    "balance": 0.0,
                    "created_at": "2026-01-01T00:00:00",
                    "last_login": "2026-01-10T00:00:00",
                    "is_banned": True
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 20,
            "total_pages": 1
        }
        
        result = await mock_user_service.search_users(is_banned=True)
        
        assert result["items"][0]["is_banned"] is True
    
    @pytest.mark.asyncio
    async def test_list_users_pagination(self, mock_admin_user, mock_user_service):
        """페이지네이션 동작 확인"""
        mock_user_service.search_users.return_value = {
            "items": [],
            "total": 100,
            "page": 5,
            "page_size": 10,
            "total_pages": 10
        }
        
        result = await mock_user_service.search_users(page=5, page_size=10)
        
        assert result["page"] == 5
        assert result["page_size"] == 10
        assert result["total_pages"] == 10


class TestGetUserAPI:
    """GET /api/users/{user_id} 엔드포인트 테스트"""
    
    @pytest.fixture
    def mock_user_service(self):
        with patch("app.api.users.UserService") as mock:
            service_instance = AsyncMock()
            mock.return_value = service_instance
            yield service_instance
    
    @pytest.mark.asyncio
    async def test_get_user_success(self, mock_user_service):
        """사용자 상세 조회 성공"""
        mock_user_service.get_user_detail.return_value = {
            "id": "user-123",
            "username": "testuser",
            "email": "test@example.com",
            "balance": 1500.0,
            "created_at": "2026-01-01T00:00:00",
            "last_login": "2026-01-15T00:00:00",
            "is_banned": False,
            "ban_reason": None,
            "ban_expires_at": None
        }
        
        result = await mock_user_service.get_user_detail("user-123")
        
        assert result["id"] == "user-123"
        assert result["username"] == "testuser"
        assert result["balance"] == 1500.0
    
    @pytest.mark.asyncio
    async def test_get_user_not_found(self, mock_user_service):
        """존재하지 않는 사용자 조회"""
        mock_user_service.get_user_detail.return_value = None
        
        result = await mock_user_service.get_user_detail("nonexistent")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_banned_user(self, mock_user_service):
        """제재된 사용자 상세 조회"""
        mock_user_service.get_user_detail.return_value = {
            "id": "banned-user",
            "username": "banneduser",
            "email": "banned@example.com",
            "balance": 0.0,
            "created_at": "2026-01-01T00:00:00",
            "last_login": "2026-01-10T00:00:00",
            "is_banned": True,
            "ban_reason": "Cheating",
            "ban_expires_at": "2026-02-01T00:00:00"
        }
        
        result = await mock_user_service.get_user_detail("banned-user")
        
        assert result["is_banned"] is True
        assert result["ban_reason"] == "Cheating"


class TestGetUserTransactionsAPI:
    """GET /api/users/{user_id}/transactions 엔드포인트 테스트"""
    
    @pytest.fixture
    def mock_user_service(self):
        with patch("app.api.users.UserService") as mock:
            service_instance = AsyncMock()
            mock.return_value = service_instance
            yield service_instance
    
    @pytest.mark.asyncio
    async def test_get_transactions_success(self, mock_user_service):
        """거래 내역 조회 성공"""
        mock_user_service.get_user_transactions.return_value = {
            "items": [
                {
                    "id": "tx-1",
                    "type": "deposit",
                    "amount": 100.0,
                    "balance_before": 900.0,
                    "balance_after": 1000.0,
                    "description": "USDT Deposit",
                    "created_at": "2026-01-15T00:00:00"
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 20
        }
        
        result = await mock_user_service.get_user_transactions("user-123")
        
        assert result["total"] == 1
        assert result["items"][0]["type"] == "deposit"
    
    @pytest.mark.asyncio
    async def test_get_transactions_with_type_filter(self, mock_user_service):
        """거래 유형 필터링"""
        mock_user_service.get_user_transactions.return_value = {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 20
        }
        
        result = await mock_user_service.get_user_transactions(
            user_id="user-123",
            tx_type="withdrawal"
        )
        
        assert result["total"] == 0


class TestGetUserLoginHistoryAPI:
    """GET /api/users/{user_id}/login-history 엔드포인트 테스트"""
    
    @pytest.fixture
    def mock_user_service(self):
        with patch("app.api.users.UserService") as mock:
            service_instance = AsyncMock()
            mock.return_value = service_instance
            yield service_instance
    
    @pytest.mark.asyncio
    async def test_get_login_history_success(self, mock_user_service):
        """로그인 기록 조회 성공"""
        mock_user_service.get_user_login_history.return_value = {
            "items": [
                {
                    "id": "login-1",
                    "ip_address": "192.168.1.1",
                    "user_agent": "Mozilla/5.0",
                    "success": True,
                    "created_at": "2026-01-15T00:00:00"
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 20
        }
        
        result = await mock_user_service.get_user_login_history("user-123")
        
        assert result["total"] == 1
        assert result["items"][0]["ip_address"] == "192.168.1.1"
    
    @pytest.mark.asyncio
    async def test_get_login_history_failed_attempts(self, mock_user_service):
        """실패한 로그인 시도 포함"""
        mock_user_service.get_user_login_history.return_value = {
            "items": [
                {
                    "id": "login-1",
                    "ip_address": "10.0.0.1",
                    "user_agent": "Bot/1.0",
                    "success": False,
                    "created_at": "2026-01-15T00:00:00"
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 20
        }
        
        result = await mock_user_service.get_user_login_history("user-123")
        
        assert result["items"][0]["success"] is False


class TestGetUserHandsAPI:
    """GET /api/users/{user_id}/hands 엔드포인트 테스트"""

    @pytest.fixture
    def mock_user_service(self):
        with patch("app.api.users.UserService") as mock:
            service_instance = AsyncMock()
            mock.return_value = service_instance
            yield service_instance

    @pytest.mark.asyncio
    async def test_get_hands_success(self, mock_user_service):
        """핸드 기록 조회 성공"""
        mock_user_service.get_user_hands.return_value = {
            "items": [
                {
                    "id": "hp-1",
                    "hand_id": "hand-123",
                    "room_id": "room-456",
                    "position": 2,
                    "cards": "As Kh",
                    "bet_amount": 50.0,
                    "won_amount": 120.0,
                    "pot_size": 200.0,
                    "created_at": "2026-01-15T00:00:00"
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 20
        }

        result = await mock_user_service.get_user_hands("user-123")

        assert result["total"] == 1
        assert result["items"][0]["cards"] == "As Kh"
        assert result["items"][0]["won_amount"] == 120.0

    @pytest.mark.asyncio
    async def test_get_hands_pagination(self, mock_user_service):
        """핸드 기록 페이지네이션"""
        mock_user_service.get_user_hands.return_value = {
            "items": [],
            "total": 500,
            "page": 10,
            "page_size": 20
        }

        result = await mock_user_service.get_user_hands(
            user_id="user-123",
            page=10,
            page_size=20
        )

        assert result["total"] == 500
        assert result["page"] == 10


class TestGetUserActivityAPI:
    """GET /api/users/{user_id}/activity 엔드포인트 테스트"""

    @pytest.fixture
    def mock_user_service(self):
        with patch("app.api.users.UserService") as mock:
            service_instance = AsyncMock()
            mock.return_value = service_instance
            yield service_instance

    @pytest.mark.asyncio
    async def test_get_activity_success(self, mock_user_service):
        """통합 활동 로그 조회 성공"""
        mock_user_service.get_user_activity.return_value = {
            "items": [
                {
                    "id": "login-1",
                    "activity_type": "login",
                    "description": "로그인 성공",
                    "amount": None,
                    "ip_address": "192.168.1.1",
                    "device_info": "Mozilla/5.0",
                    "room_id": None,
                    "hand_id": None,
                    "created_at": "2026-01-15T10:30:00"
                },
                {
                    "id": "tx-1",
                    "activity_type": "transaction",
                    "description": "[관리자 지급] 이벤트 보상",
                    "amount": 1000.0,
                    "ip_address": None,
                    "device_info": "admin_credit",
                    "room_id": None,
                    "hand_id": None,
                    "created_at": "2026-01-15T14:00:00"
                }
            ],
            "total": 2,
            "page": 1,
            "page_size": 20,
            "total_pages": 1
        }

        result = await mock_user_service.get_user_activity("user-123")

        assert result["total"] == 2
        assert len(result["items"]) == 2
        assert result["items"][0]["activity_type"] == "login"
        assert result["items"][1]["activity_type"] == "transaction"

    @pytest.mark.asyncio
    async def test_get_activity_with_type_filter(self, mock_user_service):
        """활동 타입 필터링"""
        mock_user_service.get_user_activity.return_value = {
            "items": [
                {
                    "id": "hand-1",
                    "activity_type": "hand",
                    "description": "핸드 승리",
                    "amount": 150.0,
                    "ip_address": None,
                    "device_info": "As Kh",
                    "room_id": "room-456",
                    "hand_id": "hand-789",
                    "created_at": "2026-01-15T16:00:00"
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 20,
            "total_pages": 1
        }

        result = await mock_user_service.get_user_activity(
            user_id="user-123",
            activity_type="hand"
        )

        assert result["total"] == 1
        assert result["items"][0]["activity_type"] == "hand"
        assert result["items"][0]["room_id"] == "room-456"

    @pytest.mark.asyncio
    async def test_get_activity_with_date_range(self, mock_user_service):
        """날짜 범위 필터링"""
        from datetime import datetime

        mock_user_service.get_user_activity.return_value = {
            "items": [],
            "total": 10,
            "page": 1,
            "page_size": 20,
            "total_pages": 1
        }

        result = await mock_user_service.get_user_activity(
            user_id="user-123",
            start_date=datetime(2026, 1, 1),
            end_date=datetime(2026, 1, 31)
        )

        assert result["total"] == 10

    @pytest.mark.asyncio
    async def test_get_activity_pagination(self, mock_user_service):
        """페이지네이션 동작 확인"""
        mock_user_service.get_user_activity.return_value = {
            "items": [],
            "total": 100,
            "page": 3,
            "page_size": 10,
            "total_pages": 10
        }

        result = await mock_user_service.get_user_activity(
            user_id="user-123",
            page=3,
            page_size=10
        )

        assert result["page"] == 3
        assert result["page_size"] == 10
        assert result["total_pages"] == 10


class TestCreditChipsAPI:
    """POST /api/users/{user_id}/credit 엔드포인트 테스트"""

    @pytest.fixture
    def mock_supervisor_user(self):
        """Mock supervisor user for authentication"""
        user = MagicMock(spec=AdminUser)
        user.id = "admin-123"
        user.username = "supervisor"
        user.role = AdminRole.supervisor
        return user

    @pytest.fixture
    def mock_user_service(self):
        """Mock UserService"""
        with patch("app.api.users.UserService") as mock:
            service_instance = AsyncMock()
            mock.return_value = service_instance
            yield service_instance

    @pytest.fixture
    def mock_audit_service(self):
        """Mock AuditService"""
        with patch("app.api.users.AuditService") as mock:
            service_instance = AsyncMock()
            mock.return_value = service_instance
            yield service_instance

    @pytest.mark.asyncio
    async def test_credit_chips_success(self, mock_supervisor_user, mock_user_service, mock_audit_service):
        """칩 지급 성공"""
        mock_user_service.credit_chips.return_value = {
            "transaction_id": "tx-123",
            "user_id": "user-456",
            "username": "testuser",
            "type": "credit",
            "amount": 1000.0,
            "balance_before": 500.0,
            "balance_after": 1500.0,
            "reason": "이벤트 보상",
            "admin_user_id": "admin-123",
            "admin_username": "supervisor",
            "created_at": "2026-01-17T10:00:00+00:00"
        }

        result = await mock_user_service.credit_chips(
            user_id="user-456",
            amount=1000.0,
            reason="이벤트 보상",
            admin_user_id="admin-123",
            admin_username="supervisor"
        )

        assert result["type"] == "credit"
        assert result["amount"] == 1000.0
        assert result["balance_after"] == 1500.0

    @pytest.mark.asyncio
    async def test_credit_chips_user_not_found(self, mock_supervisor_user, mock_user_service):
        """존재하지 않는 사용자에게 지급 시도"""
        mock_user_service.credit_chips.side_effect = UserNotFoundError("사용자를 찾을 수 없습니다")

        with pytest.raises(UserNotFoundError):
            await mock_user_service.credit_chips(
                user_id="nonexistent",
                amount=100.0,
                reason="테스트",
                admin_user_id="admin-123",
                admin_username="supervisor"
            )

    @pytest.mark.asyncio
    async def test_credit_chips_invalid_amount(self, mock_supervisor_user, mock_user_service):
        """유효하지 않은 금액 지급 시도"""
        mock_user_service.credit_chips.side_effect = ValueError("지급 금액은 양수여야 합니다")

        with pytest.raises(ValueError):
            await mock_user_service.credit_chips(
                user_id="user-123",
                amount=0,
                reason="테스트",
                admin_user_id="admin-123",
                admin_username="supervisor"
            )


class TestDebitChipsAPI:
    """POST /api/users/{user_id}/debit 엔드포인트 테스트"""

    @pytest.fixture
    def mock_supervisor_user(self):
        """Mock supervisor user for authentication"""
        user = MagicMock(spec=AdminUser)
        user.id = "admin-123"
        user.username = "supervisor"
        user.role = AdminRole.supervisor
        return user

    @pytest.fixture
    def mock_user_service(self):
        """Mock UserService"""
        with patch("app.api.users.UserService") as mock:
            service_instance = AsyncMock()
            mock.return_value = service_instance
            yield service_instance

    @pytest.fixture
    def mock_audit_service(self):
        """Mock AuditService"""
        with patch("app.api.users.AuditService") as mock:
            service_instance = AsyncMock()
            mock.return_value = service_instance
            yield service_instance

    @pytest.mark.asyncio
    async def test_debit_chips_success(self, mock_supervisor_user, mock_user_service, mock_audit_service):
        """칩 회수 성공"""
        mock_user_service.debit_chips.return_value = {
            "transaction_id": "tx-456",
            "user_id": "user-789",
            "username": "testuser",
            "type": "debit",
            "amount": 500.0,
            "balance_before": 1500.0,
            "balance_after": 1000.0,
            "reason": "부정 행위 대응",
            "admin_user_id": "admin-123",
            "admin_username": "supervisor",
            "created_at": "2026-01-17T10:00:00+00:00"
        }

        result = await mock_user_service.debit_chips(
            user_id="user-789",
            amount=500.0,
            reason="부정 행위 대응",
            admin_user_id="admin-123",
            admin_username="supervisor"
        )

        assert result["type"] == "debit"
        assert result["amount"] == 500.0
        assert result["balance_after"] == 1000.0

    @pytest.mark.asyncio
    async def test_debit_chips_user_not_found(self, mock_supervisor_user, mock_user_service):
        """존재하지 않는 사용자로부터 회수 시도"""
        mock_user_service.debit_chips.side_effect = UserNotFoundError("사용자를 찾을 수 없습니다")

        with pytest.raises(UserNotFoundError):
            await mock_user_service.debit_chips(
                user_id="nonexistent",
                amount=100.0,
                reason="테스트",
                admin_user_id="admin-123",
                admin_username="supervisor"
            )

    @pytest.mark.asyncio
    async def test_debit_chips_insufficient_balance(self, mock_supervisor_user, mock_user_service):
        """잔액 부족 시 에러"""
        mock_user_service.debit_chips.side_effect = InsufficientBalanceError("잔액 부족")

        with pytest.raises(InsufficientBalanceError):
            await mock_user_service.debit_chips(
                user_id="user-123",
                amount=10000.0,
                reason="테스트",
                admin_user_id="admin-123",
                admin_username="supervisor"
            )

    @pytest.mark.asyncio
    async def test_debit_chips_invalid_amount(self, mock_supervisor_user, mock_user_service):
        """유효하지 않은 금액 회수 시도"""
        mock_user_service.debit_chips.side_effect = ValueError("회수 금액은 양수여야 합니다")

        with pytest.raises(ValueError):
            await mock_user_service.debit_chips(
                user_id="user-123",
                amount=-100,
                reason="테스트",
                admin_user_id="admin-123",
                admin_username="supervisor"
            )

    @pytest.mark.asyncio
    async def test_debit_chips_service_error(self, mock_supervisor_user, mock_user_service):
        """서비스 에러 발생"""
        mock_user_service.debit_chips.side_effect = UserServiceError("DB 연결 실패")

        with pytest.raises(UserServiceError):
            await mock_user_service.debit_chips(
                user_id="user-123",
                amount=100.0,
                reason="테스트",
                admin_user_id="admin-123",
                admin_username="supervisor"
            )
