"""
Admin Backend 테스트 공통 Fixture
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.admin_user import AdminUser, AdminRole
from app.utils.dependencies import (
    get_current_user,
    require_viewer,
    require_operator,
    require_supervisor,
    require_admin,
)
from app.database import get_main_db, get_admin_db


@pytest.fixture
def admin_user():
    """Mock admin user for authentication"""
    user = MagicMock(spec=AdminUser)
    user.id = "admin-123"
    user.username = "admin"
    user.role = AdminRole.admin
    return user


@pytest.fixture
def viewer_user():
    """Mock viewer user for authentication"""
    user = MagicMock(spec=AdminUser)
    user.id = "viewer-123"
    user.username = "viewer"
    user.role = AdminRole.viewer
    return user


@pytest.fixture
def admin_token():
    """Mock JWT token for admin authentication"""
    return "mock-admin-jwt-token"


@pytest.fixture
def mock_main_db():
    """Mock main database session"""
    db = AsyncMock()
    return db


@pytest.fixture
def mock_admin_db():
    """Mock admin database session"""
    db = AsyncMock()
    return db


@pytest.fixture
def client(admin_user, mock_main_db, mock_admin_db):
    """Test client with mocked authentication and database"""

    # Override dependencies
    def override_get_current_user():
        return admin_user

    def override_require_viewer():
        return admin_user

    def override_require_operator():
        return admin_user

    def override_require_supervisor():
        return admin_user

    def override_require_admin():
        return admin_user

    async def override_get_main_db():
        yield mock_main_db

    async def override_get_admin_db():
        yield mock_admin_db

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[require_viewer] = override_require_viewer
    app.dependency_overrides[require_operator] = override_require_operator
    app.dependency_overrides[require_supervisor] = override_require_supervisor
    app.dependency_overrides[require_admin] = override_require_admin
    app.dependency_overrides[get_main_db] = override_get_main_db
    app.dependency_overrides[get_admin_db] = override_get_admin_db

    with TestClient(app) as test_client:
        yield test_client

    # Clear overrides after test
    app.dependency_overrides.clear()


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    with patch("app.services.metrics_service.get_redis_client") as mock:
        redis = AsyncMock()
        mock.return_value = redis
        yield redis


@pytest.fixture
def unauthenticated_client():
    """Test client without authentication (for 401 tests)"""
    # Clear any existing overrides
    app.dependency_overrides.clear()

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

    # Clear overrides after test
    app.dependency_overrides.clear()
