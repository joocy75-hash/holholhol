"""Tests for AuthService.

Tests for authentication operations: register, login, token refresh, logout.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.user import UserStatus
from app.services.auth import AuthError, AuthService


class TestAuthServiceRegister:
    """Tests for user registration."""

    @pytest.fixture
    def auth_service(self):
        """Create AuthService with mocked session."""
        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        return AuthService(mock_session)

    @pytest.mark.asyncio
    async def test_register_success(self, auth_service):
        """Should register new user successfully."""
        # Mock no existing user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        auth_service.db.execute = AsyncMock(return_value=mock_result)

        result = await auth_service.register(
            email="test@example.com",
            password="SecurePass123!",
            nickname="TestUser",
        )

        assert "user" in result
        assert "tokens" in result
        assert result["user"]["nickname"] == "TestUser"
        assert "access_token" in result["tokens"]
        assert "refresh_token" in result["tokens"]

    @pytest.mark.asyncio
    async def test_register_email_exists(self, auth_service):
        """Should reject registration with existing email."""
        # Mock existing user found on first query (email check)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()
        auth_service.db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(AuthError) as exc_info:
            await auth_service.register(
                email="existing@example.com",
                password="SecurePass123!",
                nickname="NewUser",
            )

        assert exc_info.value.code == "AUTH_EMAIL_EXISTS"

    @pytest.mark.asyncio
    async def test_register_nickname_exists(self, auth_service):
        """Should reject registration with existing nickname."""
        # First call (email check) returns None, second call (nickname check) returns user
        call_count = 0

        def mock_execute_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.scalar_one_or_none.return_value = None
            else:
                mock_result.scalar_one_or_none.return_value = MagicMock()
            return mock_result

        auth_service.db.execute = AsyncMock(side_effect=mock_execute_side_effect)

        with pytest.raises(AuthError) as exc_info:
            await auth_service.register(
                email="new@example.com",
                password="SecurePass123!",
                nickname="ExistingNick",
            )

        assert exc_info.value.code == "AUTH_NICKNAME_EXISTS"


class TestAuthServiceLogin:
    """Tests for user login."""

    @pytest.fixture
    def auth_service(self):
        """Create AuthService with mocked session."""
        mock_session = MagicMock()
        mock_session.add = MagicMock()
        return AuthService(mock_session)

    @pytest.mark.asyncio
    async def test_login_success(self, auth_service):
        """Should login with valid credentials."""
        from app.utils.security import hash_password

        mock_user = MagicMock()
        mock_user.id = "user-123"
        mock_user.email = "test@example.com"
        mock_user.password_hash = hash_password("CorrectPassword123!")
        mock_user.nickname = "TestUser"
        mock_user.avatar_url = None
        mock_user.balance = 100000
        mock_user.status = UserStatus.ACTIVE.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        auth_service.db.execute = AsyncMock(return_value=mock_result)

        result = await auth_service.login(
            email="test@example.com",
            password="CorrectPassword123!",
        )

        assert "user" in result
        assert "tokens" in result
        assert result["user"]["id"] == "user-123"

    @pytest.mark.asyncio
    async def test_login_invalid_email(self, auth_service):
        """Should reject login with invalid email."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        auth_service.db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(AuthError) as exc_info:
            await auth_service.login(
                email="nonexistent@example.com",
                password="AnyPassword123!",
            )

        assert exc_info.value.code == "AUTH_INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, auth_service):
        """Should reject login with wrong password."""
        from app.utils.security import hash_password

        mock_user = MagicMock()
        mock_user.password_hash = hash_password("CorrectPassword123!")
        mock_user.status = UserStatus.ACTIVE.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        auth_service.db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(AuthError) as exc_info:
            await auth_service.login(
                email="test@example.com",
                password="WrongPassword123!",
            )

        assert exc_info.value.code == "AUTH_INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_login_inactive_account(self, auth_service):
        """Should reject login for inactive account."""
        from app.utils.security import hash_password

        mock_user = MagicMock()
        mock_user.password_hash = hash_password("CorrectPassword123!")
        mock_user.status = UserStatus.SUSPENDED.value

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        auth_service.db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(AuthError) as exc_info:
            await auth_service.login(
                email="test@example.com",
                password="CorrectPassword123!",
            )

        assert exc_info.value.code == "AUTH_ACCOUNT_INACTIVE"


class TestAuthServiceTokenRefresh:
    """Tests for token refresh."""

    @pytest.fixture
    def auth_service(self):
        """Create AuthService with mocked session."""
        mock_session = MagicMock()
        return AuthService(mock_session)

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, auth_service):
        """Should reject invalid refresh token."""
        with patch("app.services.auth.verify_refresh_token", return_value=None):
            with pytest.raises(AuthError) as exc_info:
                await auth_service.refresh_tokens("invalid_token")

            assert exc_info.value.code == "AUTH_INVALID_TOKEN"

    @pytest.mark.asyncio
    async def test_refresh_missing_user_id(self, auth_service):
        """Should reject token without user ID."""
        with patch("app.services.auth.verify_refresh_token", return_value={}):
            with pytest.raises(AuthError) as exc_info:
                await auth_service.refresh_tokens("token_without_sub")

            assert exc_info.value.code == "AUTH_INVALID_TOKEN"

    @pytest.mark.asyncio
    async def test_refresh_session_not_found(self, auth_service):
        """Should reject when session not found."""
        with patch(
            "app.services.auth.verify_refresh_token",
            return_value={"sub": "user-123"},
        ):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            auth_service.db.execute = AsyncMock(return_value=mock_result)

            with pytest.raises(AuthError) as exc_info:
                await auth_service.refresh_tokens("valid_token")

            assert exc_info.value.code == "AUTH_SESSION_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_refresh_session_expired(self, auth_service):
        """Should reject expired session."""
        with patch(
            "app.services.auth.verify_refresh_token",
            return_value={"sub": "user-123"},
        ):
            mock_session = MagicMock()
            mock_session.expires_at = datetime.now(timezone.utc) - timedelta(days=1)

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_session
            auth_service.db.execute = AsyncMock(return_value=mock_result)

            with pytest.raises(AuthError) as exc_info:
                await auth_service.refresh_tokens("expired_token")

            assert exc_info.value.code == "AUTH_SESSION_EXPIRED"


class TestAuthServiceLogout:
    """Tests for user logout."""

    @pytest.fixture
    def auth_service(self):
        """Create AuthService with mocked session."""
        mock_session = MagicMock()
        mock_session.delete = AsyncMock()
        return AuthService(mock_session)

    @pytest.mark.asyncio
    async def test_logout_specific_session(self, auth_service):
        """Should logout specific session with refresh token."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_session
        auth_service.db.execute = AsyncMock(return_value=mock_result)

        result = await auth_service.logout(
            user_id="user-123",
            refresh_token="specific_token",
        )

        assert result is True
        auth_service.db.delete.assert_called_once_with(mock_session)

    @pytest.mark.asyncio
    async def test_logout_all_sessions(self, auth_service):
        """Should logout all sessions without refresh token."""
        mock_sessions = [MagicMock(), MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_sessions
        auth_service.db.execute = AsyncMock(return_value=mock_result)

        result = await auth_service.logout(user_id="user-123")

        assert result is True
        assert auth_service.db.delete.call_count == 2


class TestAuthServiceUserQueries:
    """Tests for user query methods."""

    @pytest.fixture
    def auth_service(self):
        """Create AuthService with mocked session."""
        mock_session = MagicMock()
        return AuthService(mock_session)

    @pytest.mark.asyncio
    async def test_get_user_by_id_found(self, auth_service):
        """Should return user when found."""
        mock_user = MagicMock()
        mock_user.id = "user-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        auth_service.db.execute = AsyncMock(return_value=mock_result)

        user = await auth_service.get_user_by_id("user-123")

        assert user is not None
        assert user.id == "user-123"

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, auth_service):
        """Should return None when user not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        auth_service.db.execute = AsyncMock(return_value=mock_result)

        user = await auth_service.get_user_by_id("nonexistent")

        assert user is None

    @pytest.mark.asyncio
    async def test_validate_session_active(self, auth_service):
        """Should return True for active session."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_session
        auth_service.db.execute = AsyncMock(return_value=mock_result)

        is_valid = await auth_service.validate_session("user-123")

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_session_no_session(self, auth_service):
        """Should return False when no active session."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        auth_service.db.execute = AsyncMock(return_value=mock_result)

        is_valid = await auth_service.validate_session("user-123")

        assert is_valid is False
