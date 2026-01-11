"""Tests for room API endpoints."""

import pytest
from httpx import AsyncClient

from app.models.room import Room
from tests.api.conftest import make_room_data


class TestListRooms:
    """Tests for GET /api/v1/rooms"""

    @pytest.mark.asyncio
    async def test_list_rooms_empty(self, test_client: AsyncClient):
        """Test listing rooms when none exist."""
        response = await test_client.get("/api/v1/rooms")

        assert response.status_code == 200
        result = response.json()
        assert "rooms" in result
        assert "pagination" in result
        assert result["rooms"] == []
        assert result["pagination"]["totalItems"] == 0

    @pytest.mark.asyncio
    async def test_list_rooms_with_rooms(
        self, test_client: AsyncClient, test_room: Room
    ):
        """Test listing rooms with existing rooms."""
        response = await test_client.get("/api/v1/rooms")

        assert response.status_code == 200
        result = response.json()
        assert len(result["rooms"]) >= 1

        # Check room structure
        room = result["rooms"][0]
        assert "id" in room
        assert "name" in room
        assert "blinds" in room
        assert "maxSeats" in room
        assert "currentPlayers" in room
        assert "status" in room
        assert "isPrivate" in room

    @pytest.mark.asyncio
    async def test_list_rooms_pagination(
        self, test_client: AsyncClient, test_room: Room
    ):
        """Test room list pagination."""
        response = await test_client.get("/api/v1/rooms", params={"page": 1, "pageSize": 10})

        assert response.status_code == 200
        result = response.json()
        pagination = result["pagination"]
        assert pagination["page"] == 1
        assert pagination["pageSize"] == 10
        assert "totalItems" in pagination
        assert "totalPages" in pagination
        assert "hasNext" in pagination
        assert "hasPrev" in pagination

    @pytest.mark.asyncio
    async def test_list_rooms_filter_by_status(
        self, test_client: AsyncClient, test_room: Room
    ):
        """Test filtering rooms by status."""
        response = await test_client.get(
            "/api/v1/rooms", params={"status": "waiting"}
        )

        assert response.status_code == 200
        result = response.json()
        for room in result["rooms"]:
            assert room["status"] == "waiting"


class TestCreateRoom:
    """Tests for POST /api/v1/rooms"""

    @pytest.mark.asyncio
    async def test_create_room_success(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """Test successful room creation."""
        data = make_room_data(name="My Test Room")

        response = await test_client.post(
            "/api/v1/rooms",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 201
        result = response.json()
        assert result["name"] == "My Test Room"
        assert result["status"] == "waiting"
        assert result["config"]["maxSeats"] == 6
        assert result["config"]["smallBlind"] == 10
        assert result["config"]["bigBlind"] == 20
        assert result["config"]["isPrivate"] is False
        assert "owner" in result

    @pytest.mark.asyncio
    async def test_create_private_room(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """Test creating a private room with password."""
        data = make_room_data(
            name="Private Test Room",
            is_private=True,
            password="secretpass",
        )

        response = await test_client.post(
            "/api/v1/rooms",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 201
        result = response.json()
        assert result["config"]["isPrivate"] is True

    @pytest.mark.asyncio
    async def test_create_private_room_without_password(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """Test creating private room without password fails."""
        data = make_room_data(
            name="Private Room No Pass",
            is_private=True,
            # No password provided
        )

        response = await test_client.post(
            "/api/v1/rooms",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 400
        result = response.json()
        assert "ROOM_PASSWORD_REQUIRED" in result["detail"]["error"]["code"]

    @pytest.mark.asyncio
    async def test_create_room_unauthorized(self, test_client: AsyncClient):
        """Test creating room without authentication fails."""
        data = make_room_data()

        response = await test_client.post("/api/v1/rooms", json=data)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_room_invalid_blinds(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """Test creating room with invalid blinds fails."""
        data = make_room_data(
            small_blind=20,
            big_blind=10,  # BB less than 2x SB
        )

        response = await test_client.post(
            "/api/v1/rooms",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_room_invalid_buyin(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """Test creating room with invalid buy-in range fails."""
        data = make_room_data(
            buy_in_min=2000,
            buy_in_max=400,  # Max less than min
        )

        response = await test_client.post(
            "/api/v1/rooms",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_room_short_name(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """Test creating room with name too short fails."""
        data = make_room_data(name="A")  # Too short

        response = await test_client.post(
            "/api/v1/rooms",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 422


class TestGetRoom:
    """Tests for GET /api/v1/rooms/{room_id}"""

    @pytest.mark.asyncio
    async def test_get_room_success(
        self, test_client: AsyncClient, test_room: Room
    ):
        """Test getting room details successfully."""
        response = await test_client.get(f"/api/v1/rooms/{test_room.id}")

        assert response.status_code == 200
        result = response.json()
        assert result["id"] == test_room.id
        assert result["name"] == test_room.name
        assert "config" in result
        assert "owner" in result
        assert "createdAt" in result
        assert "updatedAt" in result

    @pytest.mark.asyncio
    async def test_get_room_not_found(self, test_client: AsyncClient):
        """Test getting non-existent room fails."""
        # Use a valid UUID format that doesn't exist
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = await test_client.get(f"/api/v1/rooms/{fake_uuid}")

        assert response.status_code == 404
        result = response.json()
        assert result["detail"]["error"]["code"] == "ROOM_NOT_FOUND"


class TestJoinRoom:
    """Tests for POST /api/v1/rooms/{room_id}/join"""

    @pytest.mark.asyncio
    async def test_join_room_success(
        self,
        test_client: AsyncClient,
        test_room: Room,
        auth_headers_user2: dict,
    ):
        """Test successfully joining a room."""
        data = {"buyIn": 500}

        response = await test_client.post(
            f"/api/v1/rooms/{test_room.id}/join",
            json=data,
            headers=auth_headers_user2,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["roomId"] == test_room.id
        assert "tableId" in result
        assert result["position"] is not None
        assert "message" in result

    @pytest.mark.asyncio
    async def test_join_room_unauthorized(
        self, test_client: AsyncClient, test_room: Room
    ):
        """Test joining room without authentication fails."""
        data = {"buyIn": 500}

        response = await test_client.post(
            f"/api/v1/rooms/{test_room.id}/join",
            json=data,
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_join_room_not_found(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """Test joining non-existent room fails."""
        data = {"buyIn": 500}
        fake_uuid = "00000000-0000-0000-0000-000000000000"

        response = await test_client.post(
            f"/api/v1/rooms/{fake_uuid}/join",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_join_room_buyin_too_low(
        self,
        test_client: AsyncClient,
        test_room: Room,
        auth_headers_user2: dict,
    ):
        """Test joining room with buy-in below minimum fails."""
        data = {"buyIn": 100}  # Below 400 min

        response = await test_client.post(
            f"/api/v1/rooms/{test_room.id}/join",
            json=data,
            headers=auth_headers_user2,
        )

        assert response.status_code == 400
        result = response.json()
        assert "BUYIN" in result["detail"]["error"]["code"]

    @pytest.mark.asyncio
    async def test_join_room_buyin_too_high(
        self,
        test_client: AsyncClient,
        test_room: Room,
        auth_headers_user2: dict,
    ):
        """Test joining room with buy-in above maximum fails."""
        data = {"buyIn": 10000}  # Above 2000 max

        response = await test_client.post(
            f"/api/v1/rooms/{test_room.id}/join",
            json=data,
            headers=auth_headers_user2,
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_join_private_room_success(
        self,
        test_client: AsyncClient,
        private_room: Room,
        auth_headers_user2: dict,
    ):
        """Test joining private room with correct password."""
        data = {"buyIn": 500, "password": "roompass"}

        response = await test_client.post(
            f"/api/v1/rooms/{private_room.id}/join",
            json=data,
            headers=auth_headers_user2,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_join_private_room_wrong_password(
        self,
        test_client: AsyncClient,
        private_room: Room,
        auth_headers_user2: dict,
    ):
        """Test joining private room with wrong password fails."""
        data = {"buyIn": 500, "password": "wrongpass"}

        response = await test_client.post(
            f"/api/v1/rooms/{private_room.id}/join",
            json=data,
            headers=auth_headers_user2,
        )

        assert response.status_code == 403
        result = response.json()
        assert "PASSWORD" in result["detail"]["error"]["code"]

    @pytest.mark.asyncio
    async def test_join_private_room_no_password(
        self,
        test_client: AsyncClient,
        private_room: Room,
        auth_headers_user2: dict,
    ):
        """Test joining private room without password fails."""
        data = {"buyIn": 500}

        response = await test_client.post(
            f"/api/v1/rooms/{private_room.id}/join",
            json=data,
            headers=auth_headers_user2,
        )

        assert response.status_code == 403


class TestUpdateRoom:
    """Tests for PATCH /api/v1/rooms/{room_id}"""

    @pytest.mark.asyncio
    async def test_update_room_success(
        self,
        test_client: AsyncClient,
        test_room: Room,
        auth_headers: dict,
    ):
        """Test successfully updating room settings."""
        data = {
            "name": "Updated Room Name",
            "description": "Updated description",
        }

        response = await test_client.patch(
            f"/api/v1/rooms/{test_room.id}",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["name"] == "Updated Room Name"
        assert result["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_update_room_unauthorized(
        self, test_client: AsyncClient, test_room: Room
    ):
        """Test updating room without authentication fails."""
        data = {"name": "New Name"}

        response = await test_client.patch(
            f"/api/v1/rooms/{test_room.id}",
            json=data,
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_room_not_owner(
        self,
        test_client: AsyncClient,
        test_room: Room,
        auth_headers_user2: dict,
    ):
        """Test updating room by non-owner fails."""
        data = {"name": "Hijacked Name"}

        response = await test_client.patch(
            f"/api/v1/rooms/{test_room.id}",
            json=data,
            headers=auth_headers_user2,
        )

        assert response.status_code == 403
        result = response.json()
        assert "NOT_OWNER" in result["detail"]["error"]["code"]

    @pytest.mark.asyncio
    async def test_update_room_not_found(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """Test updating non-existent room fails."""
        data = {"name": "New Name"}
        fake_uuid = "00000000-0000-0000-0000-000000000000"

        response = await test_client.patch(
            f"/api/v1/rooms/{fake_uuid}",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_room_make_private(
        self,
        test_client: AsyncClient,
        test_room: Room,
        auth_headers: dict,
    ):
        """Test making a room private."""
        data = {"isPrivate": True, "password": "newpassword"}

        response = await test_client.patch(
            f"/api/v1/rooms/{test_room.id}",
            json=data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["config"]["isPrivate"] is True


class TestDeleteRoom:
    """Tests for DELETE /api/v1/rooms/{room_id}"""

    @pytest.mark.asyncio
    async def test_close_room_success(
        self,
        test_client: AsyncClient,
        test_room: Room,
        auth_headers: dict,
    ):
        """Test successfully closing a room."""
        response = await test_client.delete(
            f"/api/v1/rooms/{test_room.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "closed" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_close_room_unauthorized(
        self, test_client: AsyncClient, test_room: Room
    ):
        """Test closing room without authentication fails."""
        response = await test_client.delete(f"/api/v1/rooms/{test_room.id}")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_close_room_not_owner(
        self,
        test_client: AsyncClient,
        test_room: Room,
        auth_headers_user2: dict,
    ):
        """Test closing room by non-owner fails."""
        response = await test_client.delete(
            f"/api/v1/rooms/{test_room.id}",
            headers=auth_headers_user2,
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_close_room_not_found(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """Test closing non-existent room fails."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = await test_client.delete(
            f"/api/v1/rooms/{fake_uuid}",
            headers=auth_headers,
        )

        assert response.status_code == 404


class TestLeaveRoom:
    """Tests for POST /api/v1/rooms/{room_id}/leave"""

    @pytest.mark.asyncio
    async def test_leave_room_not_seated(
        self,
        test_client: AsyncClient,
        test_room: Room,
        auth_headers_user2: dict,
    ):
        """Test leaving room when not seated fails."""
        response = await test_client.post(
            f"/api/v1/rooms/{test_room.id}/leave",
            headers=auth_headers_user2,
        )

        assert response.status_code == 404
        result = response.json()
        assert "NOT_SEATED" in result["detail"]["error"]["code"]

    @pytest.mark.asyncio
    async def test_leave_room_unauthorized(
        self, test_client: AsyncClient, test_room: Room
    ):
        """Test leaving room without authentication fails."""
        response = await test_client.post(f"/api/v1/rooms/{test_room.id}/leave")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_leave_room_not_found(
        self, test_client: AsyncClient, auth_headers: dict
    ):
        """Test leaving non-existent room fails."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = await test_client.post(
            f"/api/v1/rooms/{fake_uuid}/leave",
            headers=auth_headers,
        )

        assert response.status_code == 404


class TestRoomFlow:
    """Integration tests for room management flow."""

    @pytest.mark.asyncio
    async def test_full_room_flow(
        self,
        test_client: AsyncClient,
        auth_headers: dict,
        auth_headers_user2: dict,
    ):
        """Test complete room flow: create -> join -> leave -> close."""
        # 1. Create room
        create_data = make_room_data(name="Flow Test Room")
        create_response = await test_client.post(
            "/api/v1/rooms",
            json=create_data,
            headers=auth_headers,
        )
        assert create_response.status_code == 201
        room_id = create_response.json()["id"]

        # 2. Second user joins
        join_data = {"buyIn": 500}
        join_response = await test_client.post(
            f"/api/v1/rooms/{room_id}/join",
            json=join_data,
            headers=auth_headers_user2,
        )
        assert join_response.status_code == 200
        assert join_response.json()["success"] is True

        # 3. Second user leaves
        leave_response = await test_client.post(
            f"/api/v1/rooms/{room_id}/leave",
            headers=auth_headers_user2,
        )
        assert leave_response.status_code == 200

        # 4. Owner closes room
        close_response = await test_client.delete(
            f"/api/v1/rooms/{room_id}",
            headers=auth_headers,
        )
        assert close_response.status_code == 200

        # 5. Verify room is closed (should not appear in list)
        list_response = await test_client.get("/api/v1/rooms")
        rooms = list_response.json()["rooms"]
        room_ids = [r["id"] for r in rooms]
        assert room_id not in room_ids
