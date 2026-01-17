"""
Dashboard API 테스트

Phase 5: 운영 도구 API 테스트
- CCU/DAU/MAU 통계
- 매출 현황
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from fastapi.testclient import TestClient


class TestDashboardAPI:
    """Dashboard API 테스트"""

    @pytest.fixture
    def mock_metrics_service(self):
        """Mock MetricsService"""
        with patch("app.api.dashboard.get_metrics_service") as mock:
            service = AsyncMock()
            mock.return_value = service
            yield service

    @pytest.fixture
    def mock_statistics_service(self):
        """Mock StatisticsService"""
        with patch("app.api.dashboard.StatisticsService") as mock:
            service = AsyncMock()
            mock.return_value = service
            yield service

    def test_get_ccu(self, client, mock_metrics_service, admin_token):
        """CCU 조회 테스트"""
        mock_metrics_service.get_ccu.return_value = 150

        response = client.get(
            "/api/dashboard/ccu",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "ccu" in data
        assert data["ccu"] == 150

    def test_get_dau(self, client, mock_metrics_service, admin_token):
        """DAU 조회 테스트"""
        mock_metrics_service.get_dau.return_value = 500

        response = client.get(
            "/api/dashboard/dau",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "dau" in data
        assert data["dau"] == 500

    def test_get_mau(self, client, mock_metrics_service, admin_token):
        """MAU 조회 테스트"""
        mock_metrics_service.get_mau.return_value = 2000

        response = client.get(
            "/api/dashboard/mau",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "mau" in data
        assert data["mau"] == 2000

    def test_get_mau_with_month(self, client, mock_metrics_service, admin_token):
        """특정 월 MAU 조회 테스트"""
        mock_metrics_service.get_mau.return_value = 1800

        response = client.get(
            "/api/dashboard/mau?month=2025-01",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["mau"] == 1800
        assert data["month"] == "2025-01"

    def test_get_mau_history(self, client, mock_metrics_service, admin_token):
        """MAU 히스토리 조회 테스트"""
        mock_metrics_service.get_mau_history.return_value = [
            {"month": "2025-01", "mau": 1500},
            {"month": "2024-12", "mau": 1400},
        ]

        response = client.get(
            "/api/dashboard/mau/history?months=2",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["month"] == "2025-01"

    def test_get_user_statistics_summary(self, client, mock_metrics_service, admin_token):
        """사용자 통계 요약 테스트"""
        mock_metrics_service.get_user_statistics_summary.return_value = {
            "ccu": 100,
            "dau": 500,
            "wau": 1500,
            "mau": 3000,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        response = client.get(
            "/api/dashboard/users/summary",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ccu"] == 100
        assert data["dau"] == 500
        assert data["wau"] == 1500
        assert data["mau"] == 3000

    def test_get_ccu_history(self, client, mock_metrics_service, admin_token):
        """CCU 히스토리 조회 테스트"""
        mock_metrics_service.get_ccu_history.return_value = [
            {"timestamp": "2025-01-17T10:00:00", "hour": "10:00", "ccu": 80},
            {"timestamp": "2025-01-17T11:00:00", "hour": "11:00", "ccu": 120},
        ]

        response = client.get(
            "/api/dashboard/ccu/history?hours=2",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_dau_history(self, client, mock_metrics_service, admin_token):
        """DAU 히스토리 조회 테스트"""
        mock_metrics_service.get_dau_history.return_value = [
            {"date": "2025-01-17", "dau": 500},
            {"date": "2025-01-16", "dau": 480},
        ]

        response = client.get(
            "/api/dashboard/dau/history?days=2",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


class TestRevenueAPI:
    """매출 API 테스트"""

    @pytest.fixture
    def mock_main_db(self):
        """Mock main database"""
        with patch("app.api.dashboard.get_main_db") as mock:
            db = AsyncMock()
            mock.return_value = db
            yield db

    @pytest.fixture
    def mock_statistics_service(self):
        """Mock StatisticsService"""
        with patch("app.api.dashboard.StatisticsService") as mock:
            service = MagicMock()
            mock.return_value = service
            yield service

    def test_get_revenue_summary(
        self, client, mock_statistics_service, mock_main_db, admin_token
    ):
        """매출 요약 조회 테스트"""
        mock_statistics_service.get_revenue_summary = AsyncMock(
            return_value={
                "total_rake": 50000.0,
                "total_hands": 10000,
                "unique_rooms": 50,
                "period": {"start": "2025-01-01", "end": "2025-01-17"},
            }
        )

        response = client.get(
            "/api/dashboard/revenue/summary?days=30",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_rake"] == 50000.0
        assert data["total_hands"] == 10000

    def test_get_daily_revenue(
        self, client, mock_statistics_service, mock_main_db, admin_token
    ):
        """일별 매출 조회 테스트"""
        mock_statistics_service.get_daily_revenue = AsyncMock(
            return_value=[
                {"date": "2025-01-17", "rake": 1500.0, "hands": 300},
                {"date": "2025-01-16", "rake": 1400.0, "hands": 280},
            ]
        )

        response = client.get(
            "/api/dashboard/revenue/daily?days=7",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_game_statistics(
        self, client, mock_statistics_service, mock_main_db, admin_token
    ):
        """게임 통계 조회 테스트"""
        mock_statistics_service.get_game_statistics = AsyncMock(
            return_value={
                "today": {"hands": 500, "rake": 2500.0, "rooms": 25},
                "total": {"hands": 100000, "rake": 500000.0},
            }
        )

        response = client.get(
            "/api/dashboard/game/statistics",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["today"]["hands"] == 500
        assert data["total"]["hands"] == 100000


class TestAuthorizationRequired:
    """인증 요구 테스트"""

    def test_ccu_without_auth(self, unauthenticated_client):
        """인증 없이 CCU 조회 시 401 또는 403"""
        response = unauthenticated_client.get("/api/dashboard/ccu")
        assert response.status_code in [401, 403]

    def test_mau_without_auth(self, unauthenticated_client):
        """인증 없이 MAU 조회 시 401 또는 403"""
        response = unauthenticated_client.get("/api/dashboard/mau")
        assert response.status_code in [401, 403]

    def test_revenue_without_auth(self, unauthenticated_client):
        """인증 없이 매출 조회 시 401 또는 403"""
        response = unauthenticated_client.get("/api/dashboard/revenue/summary")
        assert response.status_code in [401, 403]
