"""Room management service."""

from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import attributes, selectinload

from app.config import get_settings
from app.models.room import Room, RoomStatus
from app.models.table import Table
from app.models.user import User
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

        # Validate buy-in range
        buy_in_min = room.config.get("buy_in_min", 400)
        buy_in_max = room.config.get("buy_in_max", 2000)
        if buy_in < buy_in_min or buy_in > buy_in_max:
            raise RoomError(
                "ROOM_INVALID_BUYIN",
                f"Buy-in must be between {buy_in_min} and {buy_in_max}",
                {"buy_in_min": buy_in_min, "buy_in_max": buy_in_max},
            )

        # Check if room is full (before any balance operations)
        if room.is_full:
            raise RoomError("ROOM_FULL", "Room is full")

        # Find available table
        table = room.tables[0] if room.tables else None
        if not table:
            raise RoomError("ROOM_NO_TABLE", "No table available")

        # Get seats and check if user already seated (before balance deduction)
        seats = table.seats or {}
        for seat_pos, seat_data in seats.items():
            if seat_data.get("user_id") == user_id:
                # Already seated - return success with current position
                # This handles the case where user refreshed/lost connection
                return {
                    "table_id": table.id,
                    "position": int(seat_pos),
                    "stack": seat_data.get("stack", 0),
                    "message": f"Already seated at position {seat_pos}",
                    "already_seated": True,
                }

        # Find available seat (before balance deduction)
        max_seats = room.max_seats
        position = None

        for i in range(max_seats):
            if str(i) not in seats:
                position = i
                break

        if position is None:
            raise RoomError("TABLE_FULL", "No seats available")

        # Now verify user and balance (after all room validations pass)
        user = await self.db.get(User, user_id)
        if not user:
            raise RoomError("USER_NOT_FOUND", "User not found")

        if user.balance < buy_in:
            raise RoomError(
                "INSUFFICIENT_BALANCE",
                f"Insufficient balance. Required: {buy_in}, Available: {user.balance}",
                {"required": buy_in, "available": user.balance},
            )

        # Deduct buy-in from user balance (LAST, after all validations pass)
        user.balance -= buy_in

        # Add player to seat
        seats[str(position)] = {
            "user_id": user_id,
            "nickname": user.nickname,
            "stack": buy_in,
            "status": "active",
            "bet_amount": 0,
        }
        table.seats = seats
        # Mark JSON field as modified so SQLAlchemy detects the change
        attributes.flag_modified(table, "seats")
        room.current_players += 1

        # Update room status if enough players
        if room.current_players >= 2 and room.status == RoomStatus.WAITING.value:
            room.status = RoomStatus.PLAYING.value

        return {
            "table_id": table.id,
            "position": position,
            "stack": buy_in,
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

        # Return stack to user's balance
        seat_data = seats[user_position]
        stack = seat_data.get("stack", 0)
        if stack > 0:
            user = await self.db.get(User, user_id)
            if user:
                user.balance += stack

        # Remove player from seat
        del seats[user_position]
        table.seats = seats
        # Mark JSON field as modified so SQLAlchemy detects the change
        attributes.flag_modified(table, "seats")
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

    async def get_user_rooms(self, user_id: str) -> list[str]:
        """Get all room IDs where the user is seated.

        Args:
            user_id: User ID

        Returns:
            List of room IDs where user is seated
        """
        # Query all non-closed rooms with tables
        result = await self.db.execute(
            select(Room)
            .options(selectinload(Room.tables))
            .where(Room.status != RoomStatus.CLOSED.value)
        )
        rooms = result.scalars().all()

        user_room_ids = []
        for room in rooms:
            for table in room.tables:
                seats = table.seats or {}
                for seat_data in seats.values():
                    if seat_data.get("user_id") == user_id:
                        user_room_ids.append(room.id)
                        break

        return user_room_ids

    async def leave_all_rooms(self, user_id: str) -> int:
        """Leave all rooms where the user is seated.

        Used when WebSocket connection closes to cleanup user state.

        Args:
            user_id: User ID

        Returns:
            Number of rooms left
        """
        room_ids = await self.get_user_rooms(user_id)
        left_count = 0

        for room_id in room_ids:
            try:
                await self.leave_room(room_id, user_id)
                left_count += 1
            except RoomError:
                # Ignore errors (room might have been closed, etc.)
                pass

        return left_count

    # =========================================================================
    # Quick Join Methods
    # =========================================================================

    async def find_available_rooms(
        self,
        user_balance: int,
        blind_level: str | None = None,
        exclude_user_id: str | None = None,
    ) -> list[Room]:
        """Find rooms where user can join based on balance.

        Args:
            user_balance: User's current balance
            blind_level: Optional blind level filter ('low', 'medium', 'high', or '10/20')
            exclude_user_id: User ID to exclude rooms they're already in

        Returns:
            List of available rooms sorted by priority
        """
        from app.services.room_matcher import RoomMatcher, calculate_room_score

        # Get rooms user is already in
        exclude_room_ids = []
        if exclude_user_id:
            exclude_room_ids = await self.get_user_rooms(exclude_user_id)

        # Query available rooms
        query = select(Room).options(
            selectinload(Room.tables)
        ).where(
            Room.status.in_([RoomStatus.WAITING.value, RoomStatus.PLAYING.value]),
            Room.current_players < Room.max_seats,
        )

        if exclude_room_ids:
            query = query.where(Room.id.notin_(exclude_room_ids))

        result = await self.db.execute(query)
        rooms = list(result.scalars().all())

        # Filter by user balance (must afford min buy-in)
        affordable_rooms = [
            room for room in rooms
            if room.config.get("buy_in_min", 400) <= user_balance
        ]

        # Filter by blind level if specified
        if blind_level and affordable_rooms:
            matcher = RoomMatcher(self.db)
            affordable_rooms = matcher._filter_by_blind_level(affordable_rooms, blind_level)

        # Sort by priority score
        affordable_rooms.sort(key=lambda r: calculate_room_score(r), reverse=True)

        return affordable_rooms

    async def quick_join_room(
        self,
        user_id: str,
        room_id: str,
        seat: int,
        buy_in: int,
    ) -> dict[str, Any]:
        """Join a room via quick join.

        Similar to join_room but with pre-selected seat and buy-in.

        Args:
            user_id: User ID
            room_id: Room ID
            seat: Pre-selected seat number
            buy_in: Pre-calculated buy-in amount

        Returns:
            Dict with table_id, position, stack

        Raises:
            RoomError: If join fails
        """
        # Get room with tables
        room = await self.get_room_with_tables(room_id)

        if not room:
            raise RoomError("ROOM_NOT_FOUND", "Room not found")

        if room.status == RoomStatus.CLOSED.value:
            raise RoomError("ROOM_CLOSED", "Room is closed")

        # Check if room is full
        if room.is_full:
            raise RoomError("ROOM_FULL", "Room is full")

        # Find table
        table = room.tables[0] if room.tables else None
        if not table:
            raise RoomError("ROOM_NO_TABLE", "No table available")

        # Check if seat is available
        seats = table.seats or {}
        seat_key = str(seat)

        if seat_key in seats and seats[seat_key] is not None:
            # Seat taken - find another available seat
            max_seats = room.max_seats
            seat = None
            for i in range(max_seats):
                if str(i) not in seats or seats[str(i)] is None:
                    seat = i
                    seat_key = str(i)
                    break

            if seat is None:
                raise RoomError("TABLE_FULL", "No seats available")

        # Check if user already seated
        for pos, seat_data in seats.items():
            if seat_data and seat_data.get("user_id") == user_id:
                return {
                    "table_id": table.id,
                    "position": int(pos),
                    "stack": seat_data.get("stack", 0),
                    "message": f"Already seated at position {pos}",
                    "already_seated": True,
                }

        # Verify user and balance
        user = await self.db.get(User, user_id)
        if not user:
            raise RoomError("USER_NOT_FOUND", "User not found")

        if user.balance < buy_in:
            raise RoomError(
                "INSUFFICIENT_BALANCE",
                f"Insufficient balance. Required: {buy_in}, Available: {user.balance}",
                {"required": buy_in, "available": user.balance},
            )

        # Deduct buy-in from user balance
        user.balance -= buy_in

        # Add player to seat
        seats[seat_key] = {
            "user_id": user_id,
            "nickname": user.nickname,
            "stack": buy_in,
            "status": "active",
            "bet_amount": 0,
        }
        table.seats = seats
        attributes.flag_modified(table, "seats")
        room.current_players += 1

        # Update room status if enough players
        if room.current_players >= 2 and room.status == RoomStatus.WAITING.value:
            room.status = RoomStatus.PLAYING.value

        return {
            "table_id": table.id,
            "position": seat,
            "stack": buy_in,
            "message": f"Quick joined room at position {seat}",
        }
