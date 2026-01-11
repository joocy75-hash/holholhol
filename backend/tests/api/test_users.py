"""Tests for user API endpoints."""

import pytest
from httpx import AsyncClient

from app.models.user import User


class TestGetCurrentUser:
    """Tests for GET /api/v1/users/me"""

    @pytest.mark.asyncio
    async def test_get_me_success(
        self, test_client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """Test successfully getting current user profile."""
        response = await test_client.get("/api/v1/users/me", headers=auth_headers)

        assert response.status_code == 200
        result = response.json()
        assert result["id"] == test_user.id
        assert result["email"] == test_user.email
        assert result["nickname"] == test_user.nickname
        assert "status" in result
        assert "totalHands" in result
        assert "totalWinnings" in result
        assert "createdAt" in result

    @pytest.mark.asyncio
    async def test_get_me_unauthorized(self, test_client: AsyncClient):
        """Test getting current user without authentication fails."""
        response = await test_client.get("/api/v1/users/me")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_me_invalid_token(
        self, test_client: AsyncClient, invalid_auth_headers: dict
    ):
        """Test getting current user with invalid token fails."""
        response = await test_client.get(
            "/api/v1/users/me", headers=invalid_auth_headers
        )

        assert response.status_code == 401


class TestUpdateProfile:
    """Tests for PATCH /api/v1/users/me"""

    @pytest.mark.asyncio
    async def test_update_nickname_success(
        self, test_client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """Test successfully updating nickname."""
        data = {"nickname": "newnickname"}

        response = await test_client.patch(
            "/api/v1/users/me",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["nickname"] == "newnickname"
        assert result["id"] == test_user.id

    @pytest.mark.asyncio
    async def test_update_avatar_success(
        self, test_client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """Test successfully updating avatar URL."""
        data = {"avatarUrl": "https://example.com/avatar.png"}

        response = await test_client.patch(
            "/api/v1/users/me",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["avatarUrl"] == "https://example.com/avatar.png"

    @pytest.mark.asyncio
    async def test_update_both_fields(
        self, test_client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """Test updating both nickname and avatar."""
        data = {
            "nickname": "updateduser",
            "avatarUrl": "https://example.com/new-avatar.png",
        }

        response = await test_client.patch(
            "/api/v1/users/me",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["nickname"] == "updateduser"
        assert result["avatarUrl"] == "https://example.com/new-avatar.png"

    @pytest.mark.asyncio
    async def test_update_duplicate_nickname(
        self,
        test_client: AsyncClient,
        test_user: User,
        test_user2: User,
        auth_headers: dict,
    ):
        """Test updating to existing nickname fails."""
        data = {"nickname": test_user2.nickname}

        response = await test_client.patch(
            "/api/v1/users/me",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 409
        result = response.json()
        assert "NICKNAME_EXISTS" in result["detail"]["error"]["code"]

    @pytest.mark.asyncio
    async def test_update_invalid_nickname(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """Test updating with invalid nickname fails."""
        data = {"nickname": "invalid@nickname!"}

        response = await test_client.patch(
            "/api/v1/users/me",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_nickname_too_short(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """Test updating with nickname too short fails."""
        data = {"nickname": "a"}

        response = await test_client.patch(
            "/api/v1/users/me",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_unauthorized(self, test_client: AsyncClient):
        """Test updating profile without authentication fails."""
        data = {"nickname": "newname"}

        response = await test_client.patch("/api/v1/users/me", json=data)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_empty_body(
        self, test_client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """Test updating with empty body succeeds (no changes)."""
        response = await test_client.patch(
            "/api/v1/users/me",
            json={},
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["nickname"] == test_user.nickname


class TestChangePassword:
    """Tests for POST /api/v1/users/me/password"""

    @pytest.mark.asyncio
    async def test_change_password_success(
        self, test_client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """Test successfully changing password."""
        data = {
            "currentPassword": "TestPass123",
            "newPassword": "NewSecure456",
        }

        response = await test_client.post(
            "/api/v1/users/me/password",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_change_password_wrong_current(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """Test changing password with wrong current password fails."""
        data = {
            "currentPassword": "WrongPassword123",
            "newPassword": "NewSecure456",
        }

        response = await test_client.post(
            "/api/v1/users/me/password",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 400
        result = response.json()
        assert "INVALID_PASSWORD" in result["detail"]["error"]["code"]

    @pytest.mark.asyncio
    async def test_change_password_weak_new(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """Test changing to weak password fails."""
        data = {
            "currentPassword": "TestPass123",
            "newPassword": "weak",  # Too short, no number
        }

        response = await test_client.post(
            "/api/v1/users/me/password",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_change_password_unauthorized(self, test_client: AsyncClient):
        """Test changing password without authentication fails."""
        data = {
            "currentPassword": "TestPass123",
            "newPassword": "NewSecure456",
        }

        response = await test_client.post("/api/v1/users/me/password", json=data)

        assert response.status_code == 401


class TestGetUserStats:
    """Tests for GET /api/v1/users/me/stats"""

    @pytest.mark.asyncio
    async def test_get_stats_success(
        self, test_client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """Test successfully getting user statistics."""
        response = await test_client.get(
            "/api/v1/users/me/stats",
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert "totalHands" in result
        assert "totalWinnings" in result
        assert "handsWon" in result
        assert "biggestPot" in result
        assert "vpip" in result
        assert "pfr" in result

    @pytest.mark.asyncio
    async def test_get_stats_unauthorized(self, test_client: AsyncClient):
        """Test getting stats without authentication fails."""
        response = await test_client.get("/api/v1/users/me/stats")

        assert response.status_code == 401


class TestDeactivateAccount:
    """Tests for DELETE /api/v1/users/me"""

    @pytest.mark.asyncio
    async def test_deactivate_success(
        self, test_client: AsyncClient, test_user: User, auth_headers: dict
    ):
        """Test successfully deactivating account."""
        response = await test_client.delete(
            "/api/v1/users/me",
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "deactivated" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_deactivate_unauthorized(self, test_client: AsyncClient):
        """Test deactivating account without authentication fails."""
        response = await test_client.delete("/api/v1/users/me")

        assert response.status_code == 401


class TestGetUserById:
    """Tests for GET /api/v1/users/{user_id}"""

    @pytest.mark.asyncio
    async def test_get_user_success(
        self, test_client: AsyncClient, test_user: User
    ):
        """Test getting user by ID successfully."""
        response = await test_client.get(f"/api/v1/users/{test_user.id}")

        assert response.status_code == 200
        result = response.json()
        assert result["id"] == test_user.id
        assert result["nickname"] == test_user.nickname
        # Email should be masked for public profiles
        assert "***" in result["email"]

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, test_client: AsyncClient):
        """Test getting non-existent user fails."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = await test_client.get(f"/api/v1/users/{fake_uuid}")

        assert response.status_code == 404
        result = response.json()
        assert result["detail"]["error"]["code"] == "USER_NOT_FOUND"


class TestUserAuthFlow:
    """Integration tests for user operations requiring authentication."""

    @pytest.mark.asyncio
    async def test_inactive_user_cannot_access(
        self, test_client: AsyncClient, inactive_user: User
    ):
        """Test that inactive users cannot access protected endpoints."""
        from app.utils.security import create_token_pair, generate_session_id

        # Create valid token for inactive user
        session_id = generate_session_id()
        tokens = create_token_pair(inactive_user.id, session_id)
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # Try to access protected endpoint
        response = await test_client.get("/api/v1/users/me", headers=headers)

        assert response.status_code == 403
        result = response.json()
        assert "INACTIVE" in result["detail"]["error"]["code"]

    @pytest.mark.asyncio
    async def test_full_user_profile_flow(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """Test complete user profile flow: get -> update -> verify."""
        # 1. Get current profile
        get_response = await test_client.get(
            "/api/v1/users/me", headers=auth_headers
        )
        assert get_response.status_code == 200
        original = get_response.json()

        # 2. Update profile
        update_data = {
            "nickname": "flowtest_user",
            "avatarUrl": "https://example.com/flow-avatar.png",
        }
        update_response = await test_client.patch(
            "/api/v1/users/me",
            json=update_data,
            headers=auth_headers,
        )
        assert update_response.status_code == 200

        # 3. Verify changes
        verify_response = await test_client.get(
            "/api/v1/users/me", headers=auth_headers
        )
        assert verify_response.status_code == 200
        updated = verify_response.json()

        assert updated["nickname"] == "flowtest_user"
        assert updated["avatarUrl"] == "https://example.com/flow-avatar.png"
        # Other fields should remain unchanged
        assert updated["id"] == original["id"]
        assert updated["email"] == original["email"]

    @pytest.mark.asyncio
    async def test_stats_remain_after_profile_update(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """Test that user stats are preserved after profile update."""
        # 1. Get initial stats
        stats_response = await test_client.get(
            "/api/v1/users/me/stats", headers=auth_headers
        )
        assert stats_response.status_code == 200
        initial_stats = stats_response.json()

        # 2. Update profile
        await test_client.patch(
            "/api/v1/users/me",
            json={"nickname": "stats_test_user"},
            headers=auth_headers,
        )

        # 3. Verify stats unchanged
        stats_response2 = await test_client.get(
            "/api/v1/users/me/stats", headers=auth_headers
        )
        assert stats_response2.status_code == 200
        new_stats = stats_response2.json()

        assert new_stats["totalHands"] == initial_stats["totalHands"]
        assert new_stats["totalWinnings"] == initial_stats["totalWinnings"]
