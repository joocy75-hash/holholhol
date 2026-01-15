"""Room management API endpoints."""

from math import ceil

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession, OptionalUser, TraceId
from app.game.manager import game_manager
from app.schemas import (
    CreateRoomRequest,
    ErrorResponse,
    JoinRoomRequest,
    JoinRoomResponse,
    PaginationMeta,
    QuickJoinRequest,
    QuickJoinResponse,
    RoomConfigResponse,
    RoomDetailResponse,
    RoomListResponse,
    RoomSummaryResponse,
    SuccessResponse,
    UpdateRoomRequest,
    UserBasicResponse,
)
from app.services.room import RoomError, RoomService

router = APIRouter(prefix="/rooms", tags=["Rooms"])


@router.get(
    "/my-seats",
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def get_my_seated_rooms(
    current_user: CurrentUser,
    db: DbSession,
):
    """Get rooms where the current user is seated.

    Returns a list of room IDs where the user is currently seated.
    Used by frontend to show "continue" buttons or auto-redirect.
    """
    room_service = RoomService(db)
    room_ids = await room_service.get_user_rooms(current_user.id)
    return {"rooms": room_ids}


@router.get(
    "",
    response_model=RoomListResponse,
)
async def list_rooms(
    db: DbSession,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize", description="Items per page"),
    status_filter: str | None = Query(default=None, alias="status", description="Filter by status"),
):
    """List all available rooms.

    Returns a paginated list of public rooms with their current status.
    """
    room_service = RoomService(db)

    rooms, total = await room_service.list_rooms(
        page=page,
        page_size=page_size,
        status=status_filter,
        include_private=True,  # Include private rooms in list (they won't show password)
    )

    total_pages = ceil(total / page_size) if total > 0 else 1

    return RoomListResponse(
        rooms=[
            RoomSummaryResponse(
                id=room.id,
                name=room.name,
                blinds=f"{room.small_blind}/{room.big_blind}",
                max_seats=room.max_seats,
                player_count=room.current_players,
                status=room.status,
                is_private=room.config.get("is_private", False),
                buy_in_min=room.config.get("buy_in_min", 400),
                buy_in_max=room.config.get("buy_in_max", 2000),
            )
            for room in rooms
        ],
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        ),
    )


@router.post(
    "/quick-join",
    response_model=QuickJoinResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Insufficient balance"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "No available room"},
        409: {"model": ErrorResponse, "description": "Already seated or room full"},
    },
)
async def quick_join(
    current_user: CurrentUser,
    db: DbSession,
    trace_id: TraceId,
    request_body: QuickJoinRequest | None = None,
):
    """Quick join to an available room.

    Automatically finds the best available room based on user's balance
    and optional blind level preference. Calculates optimal buy-in amount.
    """
    from app.services.room_matcher import RoomMatcher, calculate_default_buy_in
    from app.utils.errors import (
        NoAvailableRoomError,
        InsufficientBalanceError,
        RoomFullError,
        AlreadySeatedError,
    )

    room_service = RoomService(db)
    room_matcher = RoomMatcher(db)

    blind_level = request_body.blind_level if request_body else None

    try:
        # Check if user is already seated somewhere
        existing_rooms = await room_service.get_user_rooms(current_user.id)
        if existing_rooms:
            raise AlreadySeatedError(room_id=existing_rooms[0])

        # Find best room
        room = await room_matcher.find_best_room(
            user_id=current_user.id,
            user_balance=current_user.balance,
            blind_level=blind_level,
            exclude_room_ids=existing_rooms,
        )

        if not room:
            raise NoAvailableRoomError(blind_level=blind_level)

        # Find available seat
        seat = room_matcher.get_available_seat(room)
        if seat is None:
            raise RoomFullError(room_id=room.id)

        # Calculate buy-in
        buy_in_min = room.config.get("buy_in_min", 400)
        buy_in_max = room.config.get("buy_in_max", 2000)
        buy_in = calculate_default_buy_in(buy_in_min, buy_in_max, current_user.balance)

        # Join room
        result = await room_service.quick_join_room(
            user_id=current_user.id,
            room_id=room.id,
            seat=seat,
            buy_in=buy_in,
        )

        return QuickJoinResponse(
            success=True,
            room_id=room.id,
            table_id=result["table_id"],
            seat=result["position"],
            buy_in=buy_in,
            room_name=room.name,
            blinds=f"{room.small_blind}/{room.big_blind}",
        )

    except (NoAvailableRoomError, InsufficientBalanceError, RoomFullError, AlreadySeatedError) as e:
        status_code = status.HTTP_400_BAD_REQUEST
        if isinstance(e, NoAvailableRoomError):
            status_code = status.HTTP_404_NOT_FOUND
        elif isinstance(e, (RoomFullError, AlreadySeatedError)):
            status_code = status.HTTP_409_CONFLICT

        raise HTTPException(
            status_code=status_code,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": e.details,
                },
                "traceId": trace_id,
            },
        )

    except RoomError as e:
        status_code = status.HTTP_400_BAD_REQUEST
        if "NOT_FOUND" in e.code:
            status_code = status.HTTP_404_NOT_FOUND
        elif "FULL" in e.code or "ALREADY" in e.code:
            status_code = status.HTTP_409_CONFLICT

        raise HTTPException(
            status_code=status_code,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": e.details,
                },
                "traceId": trace_id,
            },
        )


@router.post(
    "",
    response_model=RoomDetailResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def create_room(
    request_body: CreateRoomRequest,
    current_user: CurrentUser,
    db: DbSession,
    trace_id: TraceId,
):
    """Create a new game room.

    Creates a room with the specified configuration.
    The authenticated user becomes the room owner.
    """
    room_service = RoomService(db)

    try:
        room = await room_service.create_room(
            owner_id=current_user.id,
            name=request_body.name,
            description=request_body.description,
            max_seats=request_body.max_seats,
            small_blind=request_body.small_blind,
            big_blind=request_body.big_blind,
            buy_in_min=request_body.buy_in_min,
            buy_in_max=request_body.buy_in_max,
            is_private=request_body.is_private,
            password=request_body.password,
        )

        return RoomDetailResponse(
            id=room.id,
            name=room.name,
            description=room.description,
            config=RoomConfigResponse(
                max_seats=room.max_seats,
                small_blind=room.small_blind,
                big_blind=room.big_blind,
                buy_in_min=room.config.get("buy_in_min", 400),
                buy_in_max=room.config.get("buy_in_max", 2000),
                turn_timeout=room.config.get("turn_timeout", 30),
                is_private=room.config.get("is_private", False),
            ),
            status=room.status,
            current_players=room.current_players,
            owner=UserBasicResponse(
                id=current_user.id,
                nickname=current_user.nickname,
                avatar_url=current_user.avatar_url,
                balance=current_user.balance,
            ),
            created_at=room.created_at,
            updated_at=room.updated_at,
        )

    except RoomError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": e.details,
                },
                "traceId": trace_id,
            },
        )


@router.get(
    "/{room_id}",
    response_model=RoomDetailResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Room not found"},
    },
)
async def get_room(
    room_id: str,
    db: DbSession,
    trace_id: TraceId,
):
    """Get room details by ID.

    Returns detailed information about a specific room.
    """
    room_service = RoomService(db)
    room = await room_service.get_room(room_id)

    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "ROOM_NOT_FOUND",
                    "message": "Room not found",
                    "details": {},
                },
                "traceId": trace_id,
            },
        )

    owner_response = None
    if room.owner:
        owner_response = UserBasicResponse(
            id=room.owner.id,
            nickname=room.owner.nickname,
            avatar_url=room.owner.avatar_url,
            balance=room.owner.balance,
        )

    return RoomDetailResponse(
        id=room.id,
        name=room.name,
        description=room.description,
        config=RoomConfigResponse(
            max_seats=room.max_seats,
            small_blind=room.small_blind,
            big_blind=room.big_blind,
            buy_in_min=room.config.get("buy_in_min", 400),
            buy_in_max=room.config.get("buy_in_max", 2000),
            turn_timeout=room.config.get("turn_timeout", 30),
            is_private=room.config.get("is_private", False),
        ),
        status=room.status,
        current_players=room.current_players,
        owner=owner_response,
        created_at=room.created_at,
        updated_at=room.updated_at,
    )


@router.post(
    "/{room_id}/join",
    response_model=JoinRoomResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid buy-in"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Invalid password"},
        404: {"model": ErrorResponse, "description": "Room not found"},
        409: {"model": ErrorResponse, "description": "Room full or already joined"},
    },
)
async def join_room(
    room_id: str,
    request_body: JoinRoomRequest,
    current_user: CurrentUser,
    db: DbSession,
    trace_id: TraceId,
):
    """Join a room.

    Joins the specified room with the provided buy-in amount.
    For private rooms, a password is required.
    """
    room_service = RoomService(db)

    try:
        result = await room_service.join_room(
            room_id=room_id,
            user_id=current_user.id,
            buy_in=request_body.buy_in,
            password=request_body.password,
        )

        return JoinRoomResponse(
            success=True,
            room_id=room_id,
            table_id=result["table_id"],
            position=result["position"],
            message=result["message"],
        )

    except RoomError as e:
        status_code = status.HTTP_400_BAD_REQUEST
        if "NOT_FOUND" in e.code:
            status_code = status.HTTP_404_NOT_FOUND
        elif "PASSWORD" in e.code:
            status_code = status.HTTP_403_FORBIDDEN
        elif "FULL" in e.code or "ALREADY" in e.code:
            status_code = status.HTTP_409_CONFLICT

        raise HTTPException(
            status_code=status_code,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": e.details,
                },
                "traceId": trace_id,
            },
        )


@router.post(
    "/{room_id}/leave",
    response_model=SuccessResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "Room not found or not seated"},
    },
)
async def leave_room(
    room_id: str,
    current_user: CurrentUser,
    db: DbSession,
    trace_id: TraceId,
):
    """Leave a room.

    Removes the authenticated user from the room.
    """
    room_service = RoomService(db)

    try:
        await room_service.leave_room(room_id=room_id, user_id=current_user.id)

        return SuccessResponse(
            success=True,
            message="Left room successfully",
        )

    except RoomError as e:
        status_code = status.HTTP_404_NOT_FOUND
        if "NOT_SEATED" in e.code:
            status_code = status.HTTP_404_NOT_FOUND

        raise HTTPException(
            status_code=status_code,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": e.details,
                },
                "traceId": trace_id,
            },
        )


@router.patch(
    "/{room_id}",
    response_model=RoomDetailResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Not room owner"},
        404: {"model": ErrorResponse, "description": "Room not found"},
    },
)
async def update_room(
    room_id: str,
    request_body: UpdateRoomRequest,
    current_user: CurrentUser,
    db: DbSession,
    trace_id: TraceId,
):
    """Update room settings.

    Only the room owner can update room settings.
    """
    room_service = RoomService(db)

    try:
        room = await room_service.update_room(
            room_id=room_id,
            owner_id=current_user.id,
            name=request_body.name,
            description=request_body.description,
            is_private=request_body.is_private,
            password=request_body.password,
        )

        # Reload to get owner relationship
        room = await room_service.get_room(room_id)

        owner_response = None
        if room and room.owner:
            owner_response = UserBasicResponse(
                id=room.owner.id,
                nickname=room.owner.nickname,
                avatar_url=room.owner.avatar_url,
                balance=room.owner.balance,
            )

        return RoomDetailResponse(
            id=room.id,
            name=room.name,
            description=room.description,
            config=RoomConfigResponse(
                max_seats=room.max_seats,
                small_blind=room.small_blind,
                big_blind=room.big_blind,
                buy_in_min=room.config.get("buy_in_min", 400),
                buy_in_max=room.config.get("buy_in_max", 2000),
                turn_timeout=room.config.get("turn_timeout", 30),
                is_private=room.config.get("is_private", False),
            ),
            status=room.status,
            current_players=room.current_players,
            owner=owner_response,
            created_at=room.created_at,
            updated_at=room.updated_at,
        )

    except RoomError as e:
        status_code = status.HTTP_400_BAD_REQUEST
        if "NOT_FOUND" in e.code:
            status_code = status.HTTP_404_NOT_FOUND
        elif "NOT_OWNER" in e.code:
            status_code = status.HTTP_403_FORBIDDEN

        raise HTTPException(
            status_code=status_code,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": e.details,
                },
                "traceId": trace_id,
            },
        )


@router.delete(
    "/{room_id}",
    response_model=SuccessResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Not room owner"},
        404: {"model": ErrorResponse, "description": "Room not found"},
    },
)
async def close_room(
    room_id: str,
    current_user: CurrentUser,
    db: DbSession,
    trace_id: TraceId,
):
    """Close a room.

    Only the room owner can close a room.
    Closing a room removes it from the active room list.
    """
    room_service = RoomService(db)

    try:
        await room_service.close_room(room_id=room_id, owner_id=current_user.id)

        return SuccessResponse(
            success=True,
            message="Room closed successfully",
        )

    except RoomError as e:
        status_code = status.HTTP_400_BAD_REQUEST
        if "NOT_FOUND" in e.code:
            status_code = status.HTTP_404_NOT_FOUND
        elif "NOT_OWNER" in e.code:
            status_code = status.HTTP_403_FORBIDDEN

        raise HTTPException(
            status_code=status_code,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": e.details,
                },
                "traceId": trace_id,
            },
        )


# ============================================
# 개발용 API (Dev/Admin)
# ============================================

@router.post(
    "/{room_id}/dev/reset",
    response_model=SuccessResponse,
    tags=["Dev"],
)
async def dev_reset_table(
    room_id: str,
    db: DbSession,
    trace_id: TraceId,
    current_user: OptionalUser = None,
):
    """[DEV] Reset table - remove all players/bots and reset game state.
    
    DEV 환경에서는 인증 없이도 접근 가능합니다.
    """
    from app.config import get_settings
    settings = get_settings()
    
    # 프로덕션 환경에서는 인증 필수
    if settings.app_env == "production" and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "AUTH_REQUIRED", "message": "Authentication required"}},
        )
    
    # 1. GameManager 리셋
    game_manager.reset_table(room_id)

    # 2. DB 업데이트 (seats 비우기, current_players 0으로)
    from sqlalchemy import select
    from sqlalchemy.orm import attributes
    from app.models import Room, Table

    result = await db.execute(select(Room).where(Room.id == room_id))
    room = result.scalar_one_or_none()

    if room:
        # Room의 current_players를 0으로
        room.current_players = 0

        # Table의 seats를 빈 객체로
        table_result = await db.execute(select(Table).where(Table.room_id == room_id))
        table = table_result.scalar_one_or_none()
        if table:
            table.seats = {}
            attributes.flag_modified(table, "seats")

        await db.commit()

    return SuccessResponse(
        success=True,
        message="테이블이 리셋되었습니다",
    )


@router.post(
    "/{room_id}/dev/remove-bots",
    response_model=SuccessResponse,
    tags=["Dev"],
)
async def dev_remove_bots(
    room_id: str,
    db: DbSession,
    trace_id: TraceId,
    current_user: OptionalUser = None,
):
    """[DEV] Remove all bots from the table.
    
    DEV 환경에서는 인증 없이도 접근 가능합니다.
    """
    from app.config import get_settings
    settings = get_settings()
    
    # 프로덕션 환경에서는 인증 필수
    if settings.app_env == "production" and not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "AUTH_REQUIRED", "message": "Authentication required"}},
        )
    
    # 1. GameManager에서 봇 제거
    removed = game_manager.remove_bots_from_table(room_id)

    # 2. DB에서도 봇 제거 (is_bot이 true인 좌석)
    from sqlalchemy import select
    from sqlalchemy.orm import attributes
    from app.models import Room, Table

    table_result = await db.execute(select(Table).where(Table.room_id == room_id))
    table = table_result.scalar_one_or_none()

    if table and table.seats:
        seats = dict(table.seats)
        # is_bot이 true인 좌석 제거
        seats_to_remove = [pos for pos, data in seats.items() if data.get("is_bot")]
        for pos in seats_to_remove:
            del seats[pos]

        table.seats = seats
        attributes.flag_modified(table, "seats")

        # Room의 current_players 업데이트
        room_result = await db.execute(select(Room).where(Room.id == room_id))
        room = room_result.scalar_one_or_none()
        if room:
            room.current_players = len(seats)

        await db.commit()

    return SuccessResponse(
        success=True,
        message=f"봇 {removed}개가 제거되었습니다",
    )
