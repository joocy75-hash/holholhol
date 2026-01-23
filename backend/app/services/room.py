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
        room_type: str = "cash",
        max_seats: int = 9,
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
            "room_type": room_type,
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
        # 중간 입장: 기본 상태는 sitting_out (BB 대기)
        seats[str(position)] = {
            "user_id": user_id,
            "nickname": user.nickname,
            "stack": buy_in,
            "status": "sitting_out",
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

    async def force_close_room(
        self,
        room_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """관리자에 의한 방 강제 종료.

        진행 중인 게임이 있어도 강제로 종료하고 모든 플레이어의 칩을 환불합니다.

        Args:
            room_id: Room ID
            reason: 강제 종료 사유

        Returns:
            환불 결과 정보
            {
                "room_id": str,
                "refunds": [{"user_id": str, "amount": int}, ...],
                "total_refunded": int,
                "players_affected": int,
            }

        Raises:
            RoomError: If force close fails
        """
        from app.game.manager import game_manager

        room = await self.get_room_with_tables(room_id)

        if not room:
            raise RoomError("ROOM_NOT_FOUND", "Room not found")

        if room.status == RoomStatus.CLOSED.value:
            raise RoomError("ROOM_ALREADY_CLOSED", "Room is already closed")

        table = room.tables[0] if room.tables else None
        if not table:
            raise RoomError("TABLE_NOT_FOUND", "Table not found")

        # GameManager에서 최신 스택 정보 가져오기
        game_table = game_manager.get_table(room_id)
        refunds = []
        total_refunded = 0

        # DB seats 정보
        seats = dict(table.seats) if table.seats else {}

        # GameManager 스택과 DB 동기화 후 환불
        if game_table:
            for seat, player in game_table.players.items():
                if player:
                    # GameManager의 최신 스택으로 업데이트
                    seat_str = str(seat)
                    if seat_str in seats:
                        seats[seat_str]["stack"] = player.stack

                    # 환불 처리
                    user = await self.db.get(User, player.user_id)
                    if user and player.stack > 0:
                        user.balance += player.stack
                        refunds.append({
                            "user_id": player.user_id,
                            "nickname": player.username,
                            "amount": player.stack,
                            "seat": seat,
                        })
                        total_refunded += player.stack

            # GameManager에서 테이블 제거
            game_manager.remove_table(room_id)
        else:
            # GameManager에 없으면 DB seats 기준으로 환불
            for pos, seat_data in seats.items():
                user_id = seat_data.get("user_id")
                stack = seat_data.get("stack", 0)
                if user_id and stack > 0:
                    user = await self.db.get(User, user_id)
                    if user:
                        user.balance += stack
                        refunds.append({
                            "user_id": user_id,
                            "nickname": seat_data.get("nickname", "Unknown"),
                            "amount": stack,
                            "seat": int(pos),
                        })
                        total_refunded += stack

        # DB 업데이트
        table.seats = {}
        attributes.flag_modified(table, "seats")
        table.status = "closed"

        room.status = RoomStatus.CLOSED.value
        room.current_players = 0

        return {
            "room_id": room_id,
            "room_name": room.name,
            "reason": reason,
            "refunds": refunds,
            "total_refunded": total_refunded,
            "players_affected": len(refunds),
        }

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
        # 중간 입장: 기본 상태는 sitting_out (BB 대기)
        seats[seat_key] = {
            "user_id": user_id,
            "nickname": user.nickname,
            "stack": buy_in,
            "status": "sitting_out",
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

    # =========================================================================
    # Waitlist Methods (Phase 4.1)
    # =========================================================================

    async def add_to_waitlist(
        self,
        room_id: str,
        user_id: str,
        buy_in: int,
    ) -> dict[str, Any]:
        """대기열에 사용자 추가.

        Args:
            room_id: 방 ID
            user_id: 사용자 ID
            buy_in: 바이인 금액

        Returns:
            대기열 정보 (position, joined_at 등)

        Raises:
            RoomError: 방을 찾을 수 없거나 유효하지 않은 경우
        """
        from app.utils.redis_client import get_redis_context

        # 방 검증
        room = await self.get_room_with_tables(room_id)

        if not room:
            raise RoomError("ROOM_NOT_FOUND", "Room not found")

        if room.status == RoomStatus.CLOSED.value:
            raise RoomError("ROOM_CLOSED", "Room is closed")

        # 바이인 범위 검증
        buy_in_min = room.config.get("buy_in_min", 400)
        buy_in_max = room.config.get("buy_in_max", 2000)
        if buy_in < buy_in_min or buy_in > buy_in_max:
            raise RoomError(
                "ROOM_INVALID_BUYIN",
                f"Buy-in must be between {buy_in_min} and {buy_in_max}",
                {"buy_in_min": buy_in_min, "buy_in_max": buy_in_max},
            )

        # 사용자 잔액 검증
        user = await self.db.get(User, user_id)
        if not user:
            raise RoomError("USER_NOT_FOUND", "User not found")

        if user.balance < buy_in:
            raise RoomError(
                "INSUFFICIENT_BALANCE",
                f"Insufficient balance. Required: {buy_in}, Available: {user.balance}",
                {"required": buy_in, "available": user.balance},
            )

        # 이미 착석 중인지 확인
        table = room.tables[0] if room.tables else None
        if table:
            seats = table.seats or {}
            for seat_data in seats.values():
                if seat_data.get("user_id") == user_id:
                    raise RoomError(
                        "ALREADY_SEATED",
                        "Already seated in this room",
                    )

        # Redis 대기열에 추가
        async with get_redis_context() as redis:
            from app.utils.redis_client import RedisService
            redis_service = RedisService(redis)
            result = await redis_service.add_to_waitlist(room_id, user_id, buy_in)

        return {
            "room_id": room_id,
            "user_id": user_id,
            "buy_in": buy_in,
            "position": result["position"],
            "joined_at": result["joined_at"],
            "already_waiting": result.get("already_waiting", False),
        }

    async def cancel_waitlist(
        self,
        room_id: str,
        user_id: str,
    ) -> bool:
        """대기열에서 사용자 제거.

        Args:
            room_id: 방 ID
            user_id: 사용자 ID

        Returns:
            제거 성공 여부
        """
        from app.utils.redis_client import get_redis_context

        async with get_redis_context() as redis:
            from app.utils.redis_client import RedisService
            redis_service = RedisService(redis)
            return await redis_service.remove_from_waitlist(room_id, user_id)

    async def get_waitlist(
        self,
        room_id: str,
    ) -> list[dict[str, Any]]:
        """대기열 목록 조회.

        Args:
            room_id: 방 ID

        Returns:
            대기 중인 사용자 목록
        """
        from app.utils.redis_client import get_redis_context

        async with get_redis_context() as redis:
            from app.utils.redis_client import RedisService
            redis_service = RedisService(redis)
            return await redis_service.get_waitlist(room_id)

    async def get_waitlist_position(
        self,
        room_id: str,
        user_id: str,
    ) -> int | None:
        """대기열에서 사용자의 위치 조회.

        Args:
            room_id: 방 ID
            user_id: 사용자 ID

        Returns:
            위치 (1부터 시작) 또는 None
        """
        from app.utils.redis_client import get_redis_context

        async with get_redis_context() as redis:
            from app.utils.redis_client import RedisService
            redis_service = RedisService(redis)
            return await redis_service.get_waitlist_position(room_id, user_id)

    async def process_waitlist(
        self,
        room_id: str,
    ) -> dict[str, Any] | None:
        """대기열에서 첫 번째 사용자를 착석시킴.

        자리가 비었을 때 호출되어 대기열 첫 번째 사용자를 자동 착석시킵니다.

        Args:
            room_id: 방 ID

        Returns:
            착석 결과 또는 None (대기열 비어있음)
        """
        from app.utils.redis_client import get_redis_context

        async with get_redis_context() as redis:
            from app.utils.redis_client import RedisService
            redis_service = RedisService(redis)

            # 첫 번째 대기자 조회
            first_waiter = await redis_service.get_first_in_waitlist(room_id)

            if not first_waiter:
                return None

            user_id = first_waiter["user_id"]
            buy_in = first_waiter["buy_in"]

            try:
                # 착석 시도
                result = await self.join_room(room_id, user_id, buy_in)

                # 성공하면 대기열에서 제거
                await redis_service.remove_from_waitlist(room_id, user_id)

                return {
                    "user_id": user_id,
                    "buy_in": buy_in,
                    "seat_result": result,
                    "success": True,
                }

            except RoomError as e:
                # 착석 실패 (잔액 부족 등) - 대기열에서 제거하고 다음 사람 시도
                if e.code in ("INSUFFICIENT_BALANCE", "USER_NOT_FOUND"):
                    await redis_service.remove_from_waitlist(room_id, user_id)
                    # 재귀적으로 다음 대기자 처리
                    return await self.process_waitlist(room_id)
                # 방이 아직 만석이면 None 반환
                elif e.code in ("ROOM_FULL", "TABLE_FULL"):
                    return None
                raise

    # =========================================================================
    # Admin Methods (어드민 전용)
    # =========================================================================

    async def list_rooms_admin(
        self,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        search: str | None = None,
        include_closed: bool = False,
    ) -> tuple[list[Room], int]:
        """어드민용 방 목록 조회 (closed 포함 가능).

        Args:
            page: 페이지 번호 (1부터 시작)
            page_size: 페이지 크기
            status: 상태 필터 (waiting, playing, closed)
            search: 방 이름 검색어
            include_closed: 종료된 방 포함 여부

        Returns:
            (방 목록, 전체 개수) 튜플
        """
        # Base query
        query = select(Room).options(selectinload(Room.owner))

        # 필터 조건
        conditions = []

        if status:
            conditions.append(Room.status == status)
        elif not include_closed:
            conditions.append(Room.status != RoomStatus.CLOSED.value)

        if search:
            conditions.append(Room.name.ilike(f"%{search}%"))

        for condition in conditions:
            query = query.where(condition)

        # 전체 개수 조회
        count_query = select(func.count()).select_from(Room)
        for condition in conditions:
            count_query = count_query.where(condition)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # 페이지네이션 및 정렬
        offset = (page - 1) * page_size
        query = query.order_by(Room.created_at.desc()).offset(offset).limit(page_size)

        result = await self.db.execute(query)
        rooms = list(result.scalars().all())

        return rooms, total

    async def create_room_admin(
        self,
        name: str,
        description: str | None = None,
        room_type: str = "cash",
        max_seats: int = 9,
        small_blind: int = 10,
        big_blind: int = 20,
        buy_in_min: int = 400,
        buy_in_max: int = 2000,
        turn_timeout: int = 30,
        is_private: bool = False,
        password: str | None = None,
    ) -> Room:
        """어드민에 의한 방 생성 (owner_id 없음).

        어드민이 생성한 방은 시스템 소유로 설정됩니다 (owner_id = None).

        Args:
            name: 방 이름
            description: 방 설명
            room_type: 방 타입 (cash/tournament)
            max_seats: 최대 좌석 수
            small_blind: 스몰 블라인드
            big_blind: 빅 블라인드
            buy_in_min: 최소 바이인
            buy_in_max: 최대 바이인
            turn_timeout: 턴 타임아웃
            is_private: 비공개 여부
            password: 비공개 방 비밀번호

        Returns:
            생성된 Room 객체

        Raises:
            RoomError: 생성 실패 시
        """
        # 비공개 방 비밀번호 검증
        if is_private and not password:
            raise RoomError("ROOM_PASSWORD_REQUIRED", "비공개 방은 비밀번호가 필요합니다")

        # 바이인 범위 검증
        if buy_in_max < buy_in_min:
            raise RoomError(
                "INVALID_BUYIN_RANGE",
                "최대 바이인은 최소 바이인보다 커야 합니다",
                {"buy_in_min": buy_in_min, "buy_in_max": buy_in_max},
            )

        # 블라인드 검증
        if big_blind < small_blind * 2:
            raise RoomError(
                "INVALID_BLIND_RANGE",
                "빅 블라인드는 스몰 블라인드의 2배 이상이어야 합니다",
                {"small_blind": small_blind, "big_blind": big_blind},
            )

        # 방 설정 생성
        config = {
            "room_type": room_type,
            "max_seats": max_seats,
            "small_blind": small_blind,
            "big_blind": big_blind,
            "buy_in_min": buy_in_min,
            "buy_in_max": buy_in_max,
            "turn_timeout": turn_timeout,
            "is_private": is_private,
            "password_hash": hash_password(password) if password else None,
        }

        # 방 생성 (owner_id = None)
        room = Room(
            name=name,
            description=description,
            owner_id=None,  # 시스템 소유
            config=config,
            status=RoomStatus.WAITING.value,
            current_players=0,
        )
        self.db.add(room)
        await self.db.flush()

        # 초기 테이블 생성
        table = Table(
            room_id=room.id,
            status="waiting",
            dealer_position=0,
            state_version=0,
            seats={},
        )
        self.db.add(table)

        return room

    async def update_room_admin(
        self,
        room_id: str,
        name: str | None = None,
        description: str | None = None,
        is_private: bool | None = None,
        password: str | None = None,
        small_blind: int | None = None,
        big_blind: int | None = None,
        buy_in_min: int | None = None,
        buy_in_max: int | None = None,
        turn_timeout: int | None = None,
        max_seats: int | None = None,
    ) -> Room:
        """어드민에 의한 방 설정 수정 (owner 권한 체크 없음).

        Args:
            room_id: 방 ID
            name: 새 방 이름
            description: 새 설명
            is_private: 비공개 여부
            password: 비공개 방 비밀번호
            small_blind: 스몰 블라인드
            big_blind: 빅 블라인드
            buy_in_min: 최소 바이인
            buy_in_max: 최대 바이인
            turn_timeout: 턴 타임아웃
            max_seats: 최대 좌석 수 (플레이어 없을 때만)

        Returns:
            수정된 Room 객체

        Raises:
            RoomError: 수정 실패 시
        """
        room = await self.get_room(room_id)

        if not room:
            raise RoomError("ROOM_NOT_FOUND", "방을 찾을 수 없습니다")

        if room.status == RoomStatus.CLOSED.value:
            raise RoomError("ROOM_ALREADY_CLOSED", "이미 종료된 방입니다")

        # 기본 정보 업데이트
        if name is not None:
            room.name = name

        if description is not None:
            room.description = description

        # 블라인드 업데이트
        if small_blind is not None:
            room.small_blind = small_blind

        if big_blind is not None:
            room.big_blind = big_blind

        # 좌석 수 변경 (플레이어 없을 때만)
        if max_seats is not None and max_seats != room.max_seats:
            if room.current_players > 0:
                raise RoomError(
                    "CANNOT_CHANGE_SEATS",
                    "플레이어가 있는 방의 좌석 수는 변경할 수 없습니다"
                )
            room.max_seats = max_seats

        # config 업데이트 (JSONB)
        config = room.config.copy()
        config_changed = False

        if is_private is not None:
            config["is_private"] = is_private
            if is_private and password:
                config["password_hash"] = hash_password(password)
            elif not is_private:
                config["password_hash"] = None
            config_changed = True

        if buy_in_min is not None:
            config["buy_in_min"] = buy_in_min
            config_changed = True

        if buy_in_max is not None:
            config["buy_in_max"] = buy_in_max
            config_changed = True

        if turn_timeout is not None:
            config["turn_timeout"] = turn_timeout
            config_changed = True

        if config_changed:
            room.config = config
            attributes.flag_modified(room, "config")

        return room

    async def close_room_admin(self, room_id: str) -> bool:
        """어드민에 의한 방 종료 (플레이어 없을 때만).

        플레이어가 있으면 force_close_room을 사용해야 합니다.

        Args:
            room_id: 방 ID

        Returns:
            성공 여부

        Raises:
            RoomError: 종료 실패 시 (플레이어가 있는 경우 등)
        """
        room = await self.get_room_with_tables(room_id)

        if not room:
            raise RoomError("ROOM_NOT_FOUND", "방을 찾을 수 없습니다")

        if room.status == RoomStatus.CLOSED.value:
            raise RoomError("ROOM_ALREADY_CLOSED", "이미 종료된 방입니다")

        # 플레이어 확인
        if room.current_players > 0:
            raise RoomError(
                "ROOM_HAS_PLAYERS",
                "플레이어가 있는 방은 강제 종료를 사용하세요",
                {"current_players": room.current_players},
            )

        # 방 종료
        room.status = RoomStatus.CLOSED.value

        # 테이블도 종료
        for table in room.tables:
            table.status = "closed"

        return True
