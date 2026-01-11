"""Tests for authentication API endpoints."""

import pytest
from httpx import AsyncClient

from app.models.user import User
from tests.api.conftest import make_login_data, make_register_data


class TestRegister:
    """Tests for POST /api/v1/auth/register"""

    @pytest.mark.asyncio
    async def test_register_success(self, test_client: AsyncClient):
        """Test successful user registration."""
        data = make_register_data()

        response = await test_client.post("/api/v1/auth/register", json=data)

        assert response.status_code == 201
        result = response.json()
        assert "user" in result
        assert "tokens" in result
        assert result["user"]["nickname"] == data["nickname"]
        assert "accessToken" in result["tokens"]
        assert "refreshToken" in result["tokens"]
        assert result["tokens"]["tokenType"] == "Bearer"
        assert "expiresIn" in result["tokens"]

    @pytest.mark.asyncio
    async def test_register_duplicate_email(
        self, test_client: AsyncClient, test_user: User
    ):
        """Test registration with existing email fails."""
        data = make_register_data(
            email=test_user.email,
            nickname="different_user",
        )

        response = await test_client.post("/api/v1/auth/register", json=data)

        assert response.status_code == 409
        result = response.json()
        assert "detail" in result
        assert result["detail"]["error"]["code"] == "AUTH_EMAIL_EXISTS"

    @pytest.mark.asyncio
    async def test_register_duplicate_nickname(
        self, test_client: AsyncClient, test_user: User
    ):
        """Test registration with existing nickname fails."""
        data = make_register_data(
            email="different@example.com",
            nickname=test_user.nickname,
        )

        response = await test_client.post("/api/v1/auth/register", json=data)

        assert response.status_code == 409
        result = response.json()
        assert result["detail"]["error"]["code"] == "AUTH_NICKNAME_EXISTS"

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, test_client: AsyncClient):
        """Test registration with invalid email fails."""
        data = make_register_data(email="invalid-email")

        response = await test_client.post("/api/v1/auth/register", json=data)

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_register_weak_password_no_number(self, test_client: AsyncClient):
        """Test registration with password without number fails."""
        data = make_register_data(password="OnlyLetters")

        response = await test_client.post("/api/v1/auth/register", json=data)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_weak_password_no_letter(self, test_client: AsyncClient):
        """Test registration with password without letter fails."""
        data = make_register_data(password="12345678")

        response = await test_client.post("/api/v1/auth/register", json=data)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_short_password(self, test_client: AsyncClient):
        """Test registration with password too short fails."""
        data = make_register_data(password="Ab1")

        response = await test_client.post("/api/v1/auth/register", json=data)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_invalid_nickname(self, test_client: AsyncClient):
        """Test registration with invalid nickname fails."""
        data = make_register_data(nickname="invalid@nickname!")

        response = await test_client.post("/api/v1/auth/register", json=data)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_short_nickname(self, test_client: AsyncClient):
        """Test registration with nickname too short fails."""
        data = make_register_data(nickname="a")

        response = await test_client.post("/api/v1/auth/register", json=data)

        assert response.status_code == 422


class TestLogin:
    """Tests for POST /api/v1/auth/login"""

    @pytest.mark.asyncio
    async def test_login_success(self, test_client: AsyncClient, test_user: User):
        """Test successful login."""
        data = make_login_data(email=test_user.email)

        response = await test_client.post("/api/v1/auth/login", json=data)

        assert response.status_code == 200
        result = response.json()
        assert "user" in result
        assert "tokens" in result
        assert result["user"]["id"] == test_user.id
        assert result["user"]["nickname"] == test_user.nickname
        assert "accessToken" in result["tokens"]
        assert "refreshToken" in result["tokens"]

    @pytest.mark.asyncio
    async def test_login_invalid_email(self, test_client: AsyncClient):
        """Test login with non-existent email fails."""
        data = make_login_data(email="nonexistent@example.com")

        response = await test_client.post("/api/v1/auth/login", json=data)

        assert response.status_code == 401
        result = response.json()
        assert result["detail"]["error"]["code"] == "AUTH_INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_login_wrong_password(
        self, test_client: AsyncClient, test_user: User
    ):
        """Test login with wrong password fails."""
        data = make_login_data(email=test_user.email, password="WrongPass123")

        response = await test_client.post("/api/v1/auth/login", json=data)

        assert response.status_code == 401
        result = response.json()
        assert result["detail"]["error"]["code"] == "AUTH_INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_login_inactive_account(
        self, test_client: AsyncClient, inactive_user: User
    ):
        """Test login with inactive account fails."""
        data = make_login_data(email=inactive_user.email)

        response = await test_client.post("/api/v1/auth/login", json=data)

        assert response.status_code == 403
        result = response.json()
        assert "INACTIVE" in result["detail"]["error"]["code"]


class TestRefreshToken:
    """Tests for POST /api/v1/auth/refresh"""

    @pytest.mark.asyncio
    async def test_refresh_token_success(
        self, test_client: AsyncClient, test_user: User
    ):
        """Test successful token refresh."""
        # First login to get tokens
        login_data = make_login_data(email=test_user.email)
        login_response = await test_client.post("/api/v1/auth/login", json=login_data)
        tokens = login_response.json()["tokens"]

        # Use refresh token
        refresh_data = {"refreshToken": tokens["refreshToken"]}
        response = await test_client.post("/api/v1/auth/refresh", json=refresh_data)

        assert response.status_code == 200
        result = response.json()
        assert "accessToken" in result
        assert "refreshToken" in result
        # New tokens should be different
        assert result["accessToken"] != tokens["accessToken"]
        assert result["refreshToken"] != tokens["refreshToken"]

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, test_client: AsyncClient):
        """Test refresh with invalid token fails."""
        refresh_data = {"refreshToken": "invalid-refresh-token"}

        response = await test_client.post("/api/v1/auth/refresh", json=refresh_data)

        assert response.status_code == 401
        result = response.json()
        assert "AUTH_INVALID_TOKEN" in result["detail"]["error"]["code"]

    @pytest.mark.asyncio
    async def test_refresh_token_missing(self, test_client: AsyncClient):
        """Test refresh without token fails."""
        response = await test_client.post("/api/v1/auth/refresh", json={})

        assert response.status_code == 422  # Validation error


class TestLogout:
    """Tests for POST /api/v1/auth/logout"""

    @pytest.mark.asyncio
    async def test_logout_success(
        self, test_client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """Test successful logout."""
        response = await test_client.post(
            "/api/v1/auth/logout",
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "message" in result

    @pytest.mark.asyncio
    async def test_logout_with_refresh_token(
        self, test_client: AsyncClient, test_user: User
    ):
        """Test logout with specific refresh token."""
        # Login to get tokens
        login_data = make_login_data(email=test_user.email)
        login_response = await test_client.post("/api/v1/auth/login", json=login_data)
        tokens = login_response.json()["tokens"]

        auth_headers = {"Authorization": f"Bearer {tokens['accessToken']}"}
        response = await test_client.post(
            "/api/v1/auth/logout",
            headers=auth_headers,
            params={"refresh_token": tokens["refreshToken"]},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_logout_unauthorized(self, test_client: AsyncClient):
        """Test logout without authentication fails."""
        response = await test_client.post("/api/v1/auth/logout")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_invalid_token(
        self, test_client: AsyncClient, invalid_auth_headers: dict
    ):
        """Test logout with invalid token fails."""
        response = await test_client.post(
            "/api/v1/auth/logout",
            headers=invalid_auth_headers,
        )

        assert response.status_code == 401


class TestAuthenticationFlow:
    """Integration tests for full authentication flow."""

    @pytest.mark.asyncio
    async def test_full_auth_flow(self, test_client: AsyncClient):
        """Test complete auth flow: register -> login -> refresh -> logout."""
        # 1. Register
        register_data = make_register_data(
            email="flowtest@example.com",
            password="FlowTest123",
            nickname="flowuser",
        )
        register_response = await test_client.post(
            "/api/v1/auth/register", json=register_data
        )
        assert register_response.status_code == 201
        register_result = register_response.json()
        user_id = register_result["user"]["id"]

        # 2. Login
        login_data = make_login_data(
            email="flowtest@example.com",
            password="FlowTest123",
        )
        login_response = await test_client.post("/api/v1/auth/login", json=login_data)
        assert login_response.status_code == 200
        tokens = login_response.json()["tokens"]

        # 3. Refresh tokens
        refresh_data = {"refreshToken": tokens["refreshToken"]}
        refresh_response = await test_client.post(
            "/api/v1/auth/refresh", json=refresh_data
        )
        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json()

        # 4. Logout
        auth_headers = {"Authorization": f"Bearer {new_tokens['accessToken']}"}
        logout_response = await test_client.post(
            "/api/v1/auth/logout", headers=auth_headers
        )
        assert logout_response.status_code == 200

    @pytest.mark.asyncio
    async def test_token_reuse_after_refresh(
        self, test_client: AsyncClient, test_user: User
    ):
        """Test that old refresh token can still be used (depends on implementation)."""
        # Login to get tokens
        login_data = make_login_data(email=test_user.email)
        login_response = await test_client.post("/api/v1/auth/login", json=login_data)
        tokens = login_response.json()["tokens"]

        # First refresh
        refresh_data = {"refreshToken": tokens["refreshToken"]}
        first_refresh = await test_client.post(
            "/api/v1/auth/refresh", json=refresh_data
        )
        assert first_refresh.status_code == 200

        # Try using the old token again - may fail depending on implementation
        second_refresh = await test_client.post(
            "/api/v1/auth/refresh", json=refresh_data
        )
        # This might be 401 if old token is invalidated, or 200 if not
        # The test documents the current behavior
        assert second_refresh.status_code in [200, 401]
