"""Room management service."""

from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.room import Room, RoomStatus
from app.models.table import Table
from app.utils.security import hash_password, verify_password

settings = get_settings()


class RoomError(Exception):
    """Room operation error with code."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class RoomService:
    """Service for room management operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_room(
        self,
        owner_id: str,
        name: str,
        description: str | None = None,
        max_seats: int = 6,
        small_blind: int = 10,
        big_blind: int = 20,
        buy_in_min: int = 400,
        buy_in_max: int = 2000,
        turn_timeout: int = 30,
        is_private: bool = False,
        password: str | None = None,
    ) -> Room:
        """Create a new game room.

        Args:
            owner_id: User ID of room owner
            name: Room name
            description: Optional room description
            max_seats: Maximum seats (2-9)
            small_blind: Small blind amount
            big_blind: Big blind amount
            buy_in_min: Minimum buy-in
            buy_in_max: Maximum buy-in
            turn_timeout: Turn timeout in seconds
            is_private: Whether room requires password
            password: Room password (if private)

        Returns:
            Created Room object

        Raises:
            RoomError: If room creation fails
        """
        # Validate private room has password
        if is_private and not password:
            raise RoomError("ROOM_PASSWORD_REQUIRED", "Password required for private room")

        # Create room config
        config = {
            "max_seats": max_seats,
            "small_blind": small_blind,
            "big_blind": big_blind,
            "buy_in_min": buy_in_min,
            "buy_in_max": buy_in_max,
            "turn_timeout": turn_timeout,
            "is_private": is_private,
            "password_hash": hash_password(password) if password else None,
        }

        # Create room
        room = Room(
            name=name,
            description=description,
            owner_id=owner_id,
            config=config,
            status=RoomStatus.WAITING.value,
            current_players=0,
        )
        self.db.add(room)
        await self.db.flush()

        # Create initial table for the room
        table = Table(
            room_id=room.id,
            status="waiting",
            dealer_position=0,
            state_version=0,
            seats={},
        )
        self.db.add(table)

        return room

    async def get_room(self, room_id: str) -> Room | None:
        """Get room by ID with owner loaded.

        Args:
            room_id: Room ID

        Returns:
            Room object or None
        """
        result = await self.db.execute(
            select(Room)
            .options(selectinload(Room.owner))
            .where(Room.id == room_id)
        )
        return result.scalar_one_or_none()

    async def get_room_with_tables(self, room_id: str) -> Room | None:
        """Get room by ID with tables loaded.

        Args:
            room_id: Room ID

        Returns:
            Room object with tables or None
        """
        result = await self.db.execute(
            select(Room)
            .options(selectinload(Room.owner), selectinload(Room.tables))
            .where(Room.id == room_id)
        )
        return result.scalar_one_or_none()

    async def list_rooms(
        self,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        include_private: bool = True,
    ) -> tuple[list[Room], int]:
        """List rooms with pagination.

        Args:
            page: Page number (1-indexed)
            page_size: Items per page
            status: Optional status filter
            include_private: Include private rooms

        Returns:
            Tuple of (rooms list, total count)
        """
        # Base query
        query = select(Room).options(selectinload(Room.owner))

        # Apply filters
        conditions = [Room.status != RoomStatus.CLOSED.value]

        if status:
            conditions.append(Room.status == status)

        if not include_private:
            conditions.append(
                Room.config["is_private"].astext.cast(bool) == False  # noqa: E712
            )

        for condition in conditions:
            query = query.where(condition)

        # Count total
        count_query = select(func.count()).select_from(Room)
        for condition in conditions:
            count_query = count_query.where(condition)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        offset = (page - 1) * page_size
        query = query.order_by(Room.created_at.desc()).offset(offset).limit(page_size)

        result = await self.db.execute(query)
        rooms = list(result.scalars().all())

        return rooms, total

    async def join_room(
        self,
        room_id: str,
        user_id: str,
        buy_in: int,
        password: str | None = None,
    ) -> dict[str, Any]:
        """Join a room.

        Args:
            room_id: Room ID
            user_id: User ID
            buy_in: Buy-in amount
            password: Room password (if private)

        Returns:
            Dict with table_id and position

        Raises:
            RoomError: If join fails
        """
        # Get room
        room = await self.get_room_with_tables(room_id)

        if not room:
            raise RoomError("ROOM_NOT_FOUND", "Room not found")

        if room.status == RoomStatus.CLOSED.value:
            raise RoomError("ROOM_CLOSED", "Room is closed")

        # Verify password for private rooms
        if room.config.get("is_private"):
            if not password:
                raise RoomError("ROOM_PASSWORD_REQUIRED", "Password required")
            password_hash = room.config.get("password_hash")
            if not password_hash or not verify_password(password, password_hash):
                raise RoomError("ROOM_INVALID_PASSWORD", "Invalid password")

        # Validate buy-in
        buy_in_min = room.config.get("buy_in_min", 400)
        buy_in_max = room.config.get("buy_in_max", 2000)
        if buy_in < buy_in_min or buy_in > buy_in_max:
            raise RoomError(
                "ROOM_INVALID_BUYIN",
                f"Buy-in must be between {buy_in_min} and {buy_in_max}",
                {"buy_in_min": buy_in_min, "buy_in_max": buy_in_max},
            )

        # Check if room is full
        if room.is_full:
            raise RoomError("ROOM_FULL", "Room is full")

        # Find available table
        table = room.tables[0] if room.tables else None
        if not table:
            raise RoomError("ROOM_NO_TABLE", "No table available")

        # Find available seat
        seats = table.seats or {}
        max_seats = room.max_seats
        position = None

        for i in range(max_seats):
            if str(i) not in seats:
                position = i
                break

        if position is None:
            raise RoomError("TABLE_FULL", "No seats available")

        # Check if user already seated
        for seat_pos, seat_data in seats.items():
            if seat_data.get("user_id") == user_id:
                raise RoomError(
                    "ROOM_ALREADY_JOINED",
                    "Already seated in this room",
                    {"position": int(seat_pos)},
                )

        # Add player to seat
        seats[str(position)] = {
            "user_id": user_id,
            "stack": buy_in,
            "status": "waiting",
            "bet_amount": 0,
        }
        table.seats = seats
        room.current_players += 1

        # Update room status if enough players
        if room.current_players >= 2 and room.status == RoomStatus.WAITING.value:
            room.status = RoomStatus.PLAYING.value

        return {
            "table_id": table.id,
            "position": position,
            "message": f"Joined room at position {position}",
        }

    async def leave_room(self, room_id: str, user_id: str) -> bool:
        """Leave a room.

        Args:
            room_id: Room ID
            user_id: User ID

        Returns:
            True if left successfully

        Raises:
            RoomError: If leave fails
        """
        room = await self.get_room_with_tables(room_id)

        if not room:
            raise RoomError("ROOM_NOT_FOUND", "Room not found")

        # Find user's seat
        table = room.tables[0] if room.tables else None
        if not table:
            raise RoomError("TABLE_NOT_FOUND", "Table not found")

        seats = table.seats or {}
        user_position = None

        for pos, seat_data in seats.items():
            if seat_data.get("user_id") == user_id:
                user_position = pos
                break

        if user_position is None:
            raise RoomError("TABLE_NOT_SEATED", "Not seated in this room")

        # Remove player from seat
        del seats[user_position]
        table.seats = seats
        room.current_players = max(0, room.current_players - 1)

        # Update room status
        if room.current_players < 2 and room.status == RoomStatus.PLAYING.value:
            room.status = RoomStatus.WAITING.value

        return True

    async def update_room(
        self,
        room_id: str,
        owner_id: str,
        name: str | None = None,
        description: str | None = None,
        is_private: bool | None = None,
        password: str | None = None,
    ) -> Room:
        """Update room settings.

        Args:
            room_id: Room ID
            owner_id: Owner ID (for authorization)
            name: New room name
            description: New description
            is_private: New privacy setting
            password: New password

        Returns:
            Updated Room object

        Raises:
            RoomError: If update fails
        """
        room = await self.get_room(room_id)

        if not room:
            raise RoomError("ROOM_NOT_FOUND", "Room not found")

        if room.owner_id != owner_id:
            raise RoomError("ROOM_NOT_OWNER", "Only owner can update room")

        # Update fields
        if name is not None:
            room.name = name

        if description is not None:
            room.description = description

        if is_private is not None:
            config = room.config.copy()
            config["is_private"] = is_private
            if is_private and password:
                config["password_hash"] = hash_password(password)
            elif not is_private:
                config["password_hash"] = None
            room.config = config

        return room

    async def close_room(self, room_id: str, owner_id: str) -> bool:
        """Close a room.

        Args:
            room_id: Room ID
            owner_id: Owner ID (for authorization)

        Returns:
            True if closed successfully

        Raises:
            RoomError: If close fails
        """
        room = await self.get_room(room_id)

        if not room:
            raise RoomError("ROOM_NOT_FOUND", "Room not found")

        if room.owner_id != owner_id:
            raise RoomError("ROOM_NOT_OWNER", "Only owner can close room")

        room.status = RoomStatus.CLOSED.value
        return True
