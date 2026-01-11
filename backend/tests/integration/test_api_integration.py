"""API Integration Tests - Full game flow through REST API.

Tests the complete user journey:
1. Registration & Login
2. Room creation & management
3. Joining & leaving rooms
4. Seat management
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from .conftest import create_room, join_room, leave_room, register_user, login_user


# =============================================================================
# Authentication Flow Tests
# =============================================================================


class TestAuthenticationFlow:
    """Test complete authentication flows."""

    @pytest.mark.asyncio
    async def test_register_login_flow(self, integration_client: AsyncClient):
        """Test: Register new user → Login → Access protected endpoint."""
        # 1. Register
        register_response = await integration_client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@test.com",
                "password": "NewUserPass123",
                "nickname": "NewUser",
            },
        )
        assert register_response.status_code == 201
        register_data = register_response.json()["data"]
        assert "accessToken" in register_data
        assert "refreshToken" in register_data

        # 2. Login with new credentials
        login_response = await integration_client.post(
            "/api/v1/auth/login",
            json={
                "email": "newuser@test.com",
                "password": "NewUserPass123",
            },
        )
        assert login_response.status_code == 200
        login_data = login_response.json()["data"]
        access_token = login_data["accessToken"]

        # 3. Access protected endpoint (get current user)
        me_response = await integration_client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert me_response.status_code == 200
        user_data = me_response.json()["data"]
        assert user_data["email"] == "newuser@test.com"
        assert user_data["nickname"] == "NewUser"

    @pytest.mark.asyncio
    async def test_invalid_credentials_rejected(self, integration_client: AsyncClient):
        """Test: Invalid login credentials are rejected."""
        response = await integration_client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@test.com",
                "password": "WrongPass123",
            },
        )
        assert response.status_code in [401, 404]

    @pytest.mark.asyncio
    async def test_protected_endpoint_requires_auth(
        self, integration_client: AsyncClient
    ):
        """Test: Protected endpoints require authentication."""
        response = await integration_client.get("/api/v1/users/me")
        assert response.status_code == 401


# =============================================================================
# Room Management Tests
# =============================================================================


class TestRoomManagement:
    """Test room creation and management flows."""

    @pytest.mark.asyncio
    async def test_create_room_success(
        self,
        integration_client: AsyncClient,
        player1: dict,
    ):
        """Test: Authenticated user can create a room."""
        response = await integration_client.post(
            "/api/v1/rooms",
            json={
                "name": "Test Poker Room",
                "description": "A test room",
                "maxSeats": 6,
                "smallBlind": 10,
                "bigBlind": 20,
                "buyInMin": 400,
                "buyInMax": 2000,
                "isPrivate": False,
            },
            headers=player1["headers"],
        )

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["name"] == "Test Poker Room"
        assert data["config"]["maxSeats"] == 6
        assert data["config"]["smallBlind"] == 10
        assert data["config"]["bigBlind"] == 20

    @pytest.mark.asyncio
    async def test_create_private_room(
        self,
        integration_client: AsyncClient,
        player1: dict,
    ):
        """Test: Create private room with password."""
        response = await integration_client.post(
            "/api/v1/rooms",
            json={
                "name": "Private Room",
                "maxSeats": 4,
                "smallBlind": 25,
                "bigBlind": 50,
                "buyInMin": 1000,
                "buyInMax": 5000,
                "isPrivate": True,
                "password": "secret123",
            },
            headers=player1["headers"],
        )

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["config"]["isPrivate"] is True

    @pytest.mark.asyncio
    async def test_list_rooms(
        self,
        integration_client: AsyncClient,
        player1: dict,
    ):
        """Test: List available rooms."""
        # Create some rooms
        await create_room(integration_client, player1["headers"], name="Room 1")
        await create_room(integration_client, player1["headers"], name="Room 2")

        # List rooms
        response = await integration_client.get("/api/v1/rooms")
        assert response.status_code == 200

        data = response.json()["data"]
        assert "items" in data
        assert len(data["items"]) >= 2

    @pytest.mark.asyncio
    async def test_get_room_details(
        self,
        integration_client: AsyncClient,
        player1: dict,
    ):
        """Test: Get room details by ID."""
        # Create room
        room = await create_room(integration_client, player1["headers"])
        room_id = room["id"]

        # Get room details
        response = await integration_client.get(
            f"/api/v1/rooms/{room_id}",
            headers=player1["headers"],
        )
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["id"] == room_id


# =============================================================================
# Room Join/Leave Flow Tests
# =============================================================================


class TestRoomJoinLeaveFlow:
    """Test room join and leave operations."""

    @pytest.mark.asyncio
    async def test_join_room_success(
        self,
        integration_client: AsyncClient,
        player1: dict,
        player2: dict,
    ):
        """Test: Player can join a room with valid buy-in."""
        # Player1 creates room
        room = await create_room(integration_client, player1["headers"])
        room_id = room["id"]

        # Player2 joins room
        response = await integration_client.post(
            f"/api/v1/rooms/{room_id}/join",
            json={"buyIn": 1000},
            headers=player2["headers"],
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_join_room_invalid_buyin_rejected(
        self,
        integration_client: AsyncClient,
        player1: dict,
        player2: dict,
    ):
        """Test: Buy-in below minimum is rejected."""
        room = await create_room(
            integration_client,
            player1["headers"],
            small_blind=10,
            big_blind=20,
        )
        room_id = room["id"]

        # Try to join with buy-in below minimum (400)
        response = await integration_client.post(
            f"/api/v1/rooms/{room_id}/join",
            json={"buyIn": 100},  # Below minimum
            headers=player2["headers"],
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_join_private_room_requires_password(
        self,
        integration_client: AsyncClient,
        player1: dict,
        player2: dict,
    ):
        """Test: Private room requires correct password."""
        # Create private room
        response = await integration_client.post(
            "/api/v1/rooms",
            json={
                "name": "Secret Room",
                "maxSeats": 6,
                "smallBlind": 10,
                "bigBlind": 20,
                "buyInMin": 400,
                "buyInMax": 2000,
                "isPrivate": True,
                "password": "secret123",
            },
            headers=player1["headers"],
        )
        room_id = response.json()["data"]["id"]

        # Try to join without password
        no_pass_response = await integration_client.post(
            f"/api/v1/rooms/{room_id}/join",
            json={"buyIn": 1000},
            headers=player2["headers"],
        )
        assert no_pass_response.status_code in [400, 403]

        # Try with wrong password
        wrong_pass_response = await integration_client.post(
            f"/api/v1/rooms/{room_id}/join",
            json={"buyIn": 1000, "password": "wrongpass"},
            headers=player2["headers"],
        )
        assert wrong_pass_response.status_code in [400, 403]

        # Join with correct password
        correct_pass_response = await integration_client.post(
            f"/api/v1/rooms/{room_id}/join",
            json={"buyIn": 1000, "password": "secret123"},
            headers=player2["headers"],
        )
        assert correct_pass_response.status_code == 200

    @pytest.mark.asyncio
    async def test_leave_room(
        self,
        integration_client: AsyncClient,
        player1: dict,
        player2: dict,
    ):
        """Test: Player can leave a room."""
        room = await create_room(integration_client, player1["headers"])
        room_id = room["id"]

        # Join
        await join_room(integration_client, player2["headers"], room_id, 1000)

        # Leave
        response = await integration_client.post(
            f"/api/v1/rooms/{room_id}/leave",
            headers=player2["headers"],
        )

        # 200 OK or 404 (already left) are acceptable
        assert response.status_code in [200, 404]


# =============================================================================
# Multi-Player Room Flow Tests
# =============================================================================


class TestMultiPlayerFlow:
    """Test multi-player room scenarios."""

    @pytest.mark.asyncio
    async def test_multiple_players_join(
        self,
        integration_client: AsyncClient,
        player1: dict,
        player2: dict,
        player3: dict,
    ):
        """Test: Multiple players can join the same room."""
        room = await create_room(
            integration_client,
            player1["headers"],
            max_seats=6,
        )
        room_id = room["id"]

        # Player2 joins
        join_response2 = await integration_client.post(
            f"/api/v1/rooms/{room_id}/join",
            json={"buyIn": 1000},
            headers=player2["headers"],
        )
        assert join_response2.status_code == 200

        # Player3 joins
        join_response3 = await integration_client.post(
            f"/api/v1/rooms/{room_id}/join",
            json={"buyIn": 1500},
            headers=player3["headers"],
        )
        assert join_response3.status_code == 200

        # Verify room state
        room_response = await integration_client.get(
            f"/api/v1/rooms/{room_id}",
            headers=player1["headers"],
        )
        assert room_response.status_code == 200
        # Room should show players

    @pytest.mark.asyncio
    async def test_room_owner_can_close_room(
        self,
        integration_client: AsyncClient,
        player1: dict,
    ):
        """Test: Room owner can close the room."""
        room = await create_room(integration_client, player1["headers"])
        room_id = room["id"]

        # Owner closes room
        response = await integration_client.delete(
            f"/api/v1/rooms/{room_id}",
            headers=player1["headers"],
        )
        assert response.status_code == 200

        # Room should be gone or closed
        get_response = await integration_client.get(
            f"/api/v1/rooms/{room_id}",
            headers=player1["headers"],
        )
        # 404 or shows closed status
        assert get_response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_non_owner_cannot_close_room(
        self,
        integration_client: AsyncClient,
        player1: dict,
        player2: dict,
    ):
        """Test: Non-owner cannot close room."""
        room = await create_room(integration_client, player1["headers"])
        room_id = room["id"]

        # Player2 tries to close
        response = await integration_client.delete(
            f"/api/v1/rooms/{room_id}",
            headers=player2["headers"],
        )
        assert response.status_code == 403


# =============================================================================
# User Profile Tests
# =============================================================================


class TestUserProfile:
    """Test user profile operations."""

    @pytest.mark.asyncio
    async def test_get_current_user(
        self,
        integration_client: AsyncClient,
        player1: dict,
    ):
        """Test: Get current user profile."""
        response = await integration_client.get(
            "/api/v1/users/me",
            headers=player1["headers"],
        )
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["email"] == "player1@test.com"
        assert data["nickname"] == "Player1"

    @pytest.mark.asyncio
    async def test_update_profile(
        self,
        integration_client: AsyncClient,
        player1: dict,
    ):
        """Test: Update user profile."""
        response = await integration_client.patch(
            "/api/v1/users/me",
            json={"nickname": "UpdatedPlayer1"},
            headers=player1["headers"],
        )
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["nickname"] == "UpdatedPlayer1"

    @pytest.mark.asyncio
    async def test_get_user_stats(
        self,
        integration_client: AsyncClient,
        player1: dict,
    ):
        """Test: Get user statistics."""
        response = await integration_client.get(
            "/api/v1/users/me/stats",
            headers=player1["headers"],
        )
        assert response.status_code == 200

        data = response.json()["data"]
        assert "totalHands" in data
        assert "totalWinnings" in data


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Test API error handling."""

    @pytest.mark.asyncio
    async def test_room_not_found(
        self,
        integration_client: AsyncClient,
        player1: dict,
    ):
        """Test: Non-existent room returns 404."""
        response = await integration_client.get(
            "/api/v1/rooms/nonexistent-room-id",
            headers=player1["headers"],
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_room_data_rejected(
        self,
        integration_client: AsyncClient,
        player1: dict,
    ):
        """Test: Invalid room data is rejected."""
        response = await integration_client.post(
            "/api/v1/rooms",
            json={
                "name": "",  # Empty name
                "maxSeats": 0,  # Invalid
                "smallBlind": -10,  # Invalid
                "bigBlind": 20,
                "buyInMin": 400,
                "buyInMax": 2000,
                "isPrivate": False,
            },
            headers=player1["headers"],
        )
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_duplicate_email_rejected(
        self,
        integration_client: AsyncClient,
    ):
        """Test: Duplicate email registration is rejected."""
        # First registration
        await integration_client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplicate@test.com",
                "password": "DupePass123",
                "nickname": "DupeUser1",
            },
        )

        # Second registration with same email
        response = await integration_client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplicate@test.com",
                "password": "DupePass123",
                "nickname": "DupeUser2",
            },
        )
        assert response.status_code in [400, 409]  # Conflict or Bad Request
