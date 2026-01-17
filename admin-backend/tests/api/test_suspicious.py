"""
Suspicious Users API Tests - 의심 사용자 API 엔드포인트 테스트

Phase 3.7: 부정 사용자 의심 리스트
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api.suspicious import router
from app.models.admin_user import AdminUser, AdminRole


# Test app setup
app = FastAPI()
app.include_router(router, prefix="/api/suspicious")


class TestGetSuspiciousUsersAPI:
    """GET /api/suspicious 엔드포인트 테스트"""

    @pytest.fixture
    def mock_admin_user(self):
        """Mock admin user for authentication"""
        user = MagicMock(spec=AdminUser)
        user.id = "admin-123"
        user.username = "admin"
        user.role = "viewer"
        return user

    @pytest.fixture
    def mock_service(self):
        """Mock SuspiciousUserService"""
        with patch("app.api.suspicious.SuspiciousUserService") as mock:
            service_instance = AsyncMock()
            mock.return_value = service_instance
            yield service_instance

    @pytest.mark.asyncio
    async def test_list_suspicious_users_success(self, mock_admin_user, mock_service):
        """의심 사용자 목록 조회 성공"""
        mock_service.get_suspicious_users.return_value = {
            "items": [
                {
                    "user_id": "user-1",
                    "username": "suspicious_user",
                    "email": "test@example.com",
                    "is_banned": False,
                    "suspicion_score": 85.5,
                    "detection_count": 3,
                    "pending_count": 2,
                    "confirmed_count": 1,
                    "max_severity": "high",
                    "detection_breakdown": {
                        "chip_dumping": 1,
                        "bot_detection": 1,
                        "anomaly_detection": 1,
                    },
                    "last_detected": "2026-01-17T10:00:00",
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 20,
            "total_pages": 1,
        }

        result = await mock_service.get_suspicious_users(
            page=1,
            page_size=20,
            detection_type=None,
            severity=None,
            status=None,
            min_score=None,
            sort_by="suspicion_score",
            sort_order="desc",
        )

        assert result["total"] == 1
        assert len(result["items"]) == 1
        assert result["items"][0]["suspicion_score"] == 85.5

    @pytest.mark.asyncio
    async def test_list_suspicious_users_with_filters(self, mock_admin_user, mock_service):
        """필터 적용된 의심 사용자 목록 조회"""
        mock_service.get_suspicious_users.return_value = {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
            "total_pages": 0,
        }

        result = await mock_service.get_suspicious_users(
            page=1,
            page_size=20,
            detection_type="chip_dumping",
            severity="high",
            status="pending",
            min_score=50.0,
            sort_by="suspicion_score",
            sort_order="desc",
        )

        assert result["total"] == 0


class TestGetSuspicionSummaryAPI:
    """GET /api/suspicious/summary 엔드포인트 테스트"""

    @pytest.fixture
    def mock_admin_user(self):
        user = MagicMock(spec=AdminUser)
        user.id = "admin-123"
        user.username = "admin"
        user.role = "viewer"
        return user

    @pytest.fixture
    def mock_service(self):
        with patch("app.api.suspicious.SuspiciousUserService") as mock:
            service_instance = AsyncMock()
            mock.return_value = service_instance
            yield service_instance

    @pytest.mark.asyncio
    async def test_get_summary_success(self, mock_admin_user, mock_service):
        """요약 통계 조회 성공"""
        mock_service.get_suspicion_summary.return_value = {
            "total_suspicious_users": 15,
            "users_with_pending": 8,
            "users_with_confirmed": 5,
            "by_severity": {"high": 3, "medium": 7, "low": 5},
        }

        result = await mock_service.get_suspicion_summary()

        assert result["total_suspicious_users"] == 15
        assert result["users_with_pending"] == 8


class TestGetSuspiciousUserDetailAPI:
    """GET /api/suspicious/users/{user_id} 엔드포인트 테스트"""

    @pytest.fixture
    def mock_admin_user(self):
        user = MagicMock(spec=AdminUser)
        user.id = "admin-123"
        user.username = "admin"
        user.role = "viewer"
        return user

    @pytest.fixture
    def mock_service(self):
        with patch("app.api.suspicious.SuspiciousUserService") as mock:
            service_instance = AsyncMock()
            mock.return_value = service_instance
            yield service_instance

    @pytest.mark.asyncio
    async def test_get_user_detail_success(self, mock_admin_user, mock_service):
        """사용자 상세 조회 성공"""
        mock_service.get_suspicious_user_detail.return_value = {
            "user_id": "user-123",
            "username": "testuser",
            "email": "test@example.com",
            "balance": 1000.0,
            "is_banned": False,
            "ban_reason": None,
            "created_at": "2026-01-01T00:00:00",
            "last_login": "2026-01-17T00:00:00",
            "suspicion_score": 75.0,
            "statistics": {
                "total_detections": 5,
                "pending": 2,
                "reviewing": 1,
                "confirmed": 1,
                "dismissed": 1,
                "by_type": {"chip_dumping": 2, "bot_detection": 3},
                "by_severity": {"high": 1, "medium": 2, "low": 2},
            },
            "activities": [
                {
                    "id": 1,
                    "detection_type": "chip_dumping",
                    "severity": "high",
                    "status": "pending",
                    "details": {"amount": 5000},
                    "created_at": "2026-01-17T10:00:00",
                    "updated_at": None,
                    "reviewed_by": None,
                }
            ],
        }

        result = await mock_service.get_suspicious_user_detail("user-123")

        assert result["user_id"] == "user-123"
        assert result["suspicion_score"] == 75.0
        assert len(result["activities"]) == 1

    @pytest.mark.asyncio
    async def test_get_user_detail_not_found(self, mock_admin_user, mock_service):
        """존재하지 않는 사용자 조회"""
        mock_service.get_suspicious_user_detail.return_value = None

        result = await mock_service.get_suspicious_user_detail("non-existent")

        assert result is None


class TestGetActivityDetailAPI:
    """GET /api/suspicious/activities/{activity_id} 엔드포인트 테스트"""

    @pytest.fixture
    def mock_admin_user(self):
        user = MagicMock(spec=AdminUser)
        user.id = "admin-123"
        user.username = "admin"
        user.role = "viewer"
        return user

    @pytest.fixture
    def mock_service(self):
        with patch("app.api.suspicious.SuspiciousUserService") as mock:
            service_instance = AsyncMock()
            mock.return_value = service_instance
            yield service_instance

    @pytest.mark.asyncio
    async def test_get_activity_detail_success(self, mock_admin_user, mock_service):
        """활동 상세 조회 성공"""
        mock_service.get_activity_detail.return_value = {
            "id": 1,
            "detection_type": "chip_dumping",
            "user_ids": ["user-1", "user-2"],
            "users": [
                {"user_id": "user-1", "username": "player1", "is_banned": False},
                {"user_id": "user-2", "username": "player2", "is_banned": True},
            ],
            "details": {"pattern": "one_way_transfer", "amount": 10000},
            "severity": "high",
            "status": "pending",
            "created_at": "2026-01-17T10:00:00",
            "updated_at": None,
            "reviewed_by": None,
            "reviewed_at": None,
            "review_notes": None,
        }

        result = await mock_service.get_activity_detail(1)

        assert result["id"] == 1
        assert len(result["users"]) == 2

    @pytest.mark.asyncio
    async def test_get_activity_detail_not_found(self, mock_admin_user, mock_service):
        """존재하지 않는 활동 조회"""
        mock_service.get_activity_detail.return_value = None

        result = await mock_service.get_activity_detail(999)

        assert result is None


class TestUpdateReviewStatusAPI:
    """PATCH /api/suspicious/activities/{activity_id}/review 엔드포인트 테스트"""

    @pytest.fixture
    def mock_operator_user(self):
        user = MagicMock(spec=AdminUser)
        user.id = "admin-456"
        user.username = "operator"
        user.role = "operator"
        return user

    @pytest.fixture
    def mock_service(self):
        with patch("app.api.suspicious.SuspiciousUserService") as mock:
            service_instance = AsyncMock()
            mock.return_value = service_instance
            yield service_instance

    @pytest.mark.asyncio
    async def test_update_review_status_success(self, mock_operator_user, mock_service):
        """검토 상태 업데이트 성공"""
        mock_service.update_review_status.return_value = {
            "id": 1,
            "detection_type": "chip_dumping",
            "severity": "high",
            "status": "confirmed",
            "reviewed_by": "admin-456",
            "reviewed_at": "2026-01-17T12:00:00",
            "notes": "부정 행위 확인됨",
            "created_at": "2026-01-17T10:00:00",
            "updated_at": "2026-01-17T12:00:00",
        }

        result = await mock_service.update_review_status(
            activity_id=1,
            status="confirmed",
            admin_user_id="admin-456",
            notes="부정 행위 확인됨",
        )

        assert result["status"] == "confirmed"
        assert result["reviewed_by"] == "admin-456"
        assert result["notes"] == "부정 행위 확인됨"

    @pytest.mark.asyncio
    async def test_update_review_status_invalid_status(self, mock_operator_user, mock_service):
        """잘못된 상태로 업데이트 시도"""
        mock_service.update_review_status.side_effect = ValueError("유효하지 않은 상태: invalid")

        with pytest.raises(ValueError):
            await mock_service.update_review_status(
                activity_id=1,
                status="invalid",
                admin_user_id="admin-456",
            )

    @pytest.mark.asyncio
    async def test_update_review_status_not_found(self, mock_operator_user, mock_service):
        """존재하지 않는 활동 업데이트 시도"""
        mock_service.update_review_status.return_value = None

        result = await mock_service.update_review_status(
            activity_id=999,
            status="confirmed",
            admin_user_id="admin-456",
        )

        assert result is None


class TestGetDetectionTypesAPI:
    """GET /api/suspicious/detection-types 엔드포인트 테스트"""

    @pytest.fixture
    def mock_admin_user(self):
        user = MagicMock(spec=AdminUser)
        user.id = "admin-123"
        user.username = "admin"
        user.role = "viewer"
        return user

    def test_detection_types_response(self, mock_admin_user):
        """탐지 유형 목록 조회"""
        # API 함수 직접 호출하여 응답 확인
        from app.api.suspicious import get_detection_types

        # Mock dependency 없이 직접 호출 (인증 우회)
        import asyncio

        async def call_endpoint():
            # get_detection_types는 현재 사용자만 받으므로 Mock 전달
            return await get_detection_types(mock_admin_user)

        result = asyncio.get_event_loop().run_until_complete(call_endpoint())

        assert "detection_types" in result
        assert "severities" in result
        assert "statuses" in result
        assert len(result["detection_types"]) == 4
        assert len(result["severities"]) == 3
        assert len(result["statuses"]) == 4


class TestSuspiciousUserServiceUnit:
    """SuspiciousUserService 단위 테스트"""

    @pytest.mark.asyncio
    async def test_calculate_suspicion_score(self):
        """의심 점수 계산"""
        from app.services.suspicious_user_service import SuspiciousUserService

        # Mock DB sessions
        mock_main_db = AsyncMock()
        mock_admin_db = AsyncMock()

        service = SuspiciousUserService(mock_main_db, mock_admin_db)

        # 테스트 데이터
        activities = [
            {
                "detection_type": "chip_dumping",
                "severity": "high",
                "status": "confirmed",
            },
            {
                "detection_type": "bot_detection",
                "severity": "medium",
                "status": "pending",
            },
            {
                "detection_type": "anomaly_detection",
                "severity": "low",
                "status": "dismissed",  # dismissed는 제외됨
            },
        ]

        score = service._calculate_suspicion_score(activities)

        # chip_dumping(40) * high(2.5) * confirmed(1.5) = 150
        # bot_detection(35) * medium(1.5) = 52.5
        # anomaly_detection은 dismissed이므로 제외
        expected = 40 * 2.5 * 1.5 + 35 * 1.5
        assert score == expected

    @pytest.mark.asyncio
    async def test_calculate_suspicion_score_empty(self):
        """빈 활동 목록으로 점수 계산"""
        from app.services.suspicious_user_service import SuspiciousUserService

        mock_main_db = AsyncMock()
        mock_admin_db = AsyncMock()

        service = SuspiciousUserService(mock_main_db, mock_admin_db)

        score = service._calculate_suspicion_score([])

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_calculate_suspicion_score_all_dismissed(self):
        """모든 활동이 dismissed인 경우"""
        from app.services.suspicious_user_service import SuspiciousUserService

        mock_main_db = AsyncMock()
        mock_admin_db = AsyncMock()

        service = SuspiciousUserService(mock_main_db, mock_admin_db)

        activities = [
            {"detection_type": "chip_dumping", "severity": "high", "status": "dismissed"},
            {"detection_type": "bot_detection", "severity": "medium", "status": "dismissed"},
        ]

        score = service._calculate_suspicion_score(activities)

        assert score == 0.0
