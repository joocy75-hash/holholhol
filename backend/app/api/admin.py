"""Internal Admin API endpoints for admin-backend integration.

These endpoints are protected by API key authentication and should only be
called from the admin-backend service.
"""
import json
import logging
import math
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.api.deps import DbSession, TraceId
from app.config import get_settings
from app.schemas.admin import (
    AdminCloseRoomResponse,
    AdminCreateRoomRequest,
    AdminRoomDetailResponse,
    AdminRoomListResponse,
    AdminRoomResponse,
    AdminSeatInfo,
    AdminUpdateRoomRequest,
    RakeConfigCreate,
    RakeConfigListResponse,
    RakeConfigResponse,
    RakeConfigUpdate,
)
from app.services.rake import RakeConfigService
from app.services.room import RoomError, RoomService
from app.ws.events import EventType

router = APIRouter(prefix="/internal/admin", tags=["Internal Admin"])
logger = logging.getLogger(__name__)
settings = get_settings()


def verify_api_key(x_api_key: str = Header(...)) -> bool:
    """Verify the API key from admin-backend."""
    if not settings.internal_api_key:
        logger.warning("INTERNAL_API_KEY not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal API key not configured",
        )

    if x_api_key != settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return True


# ============================================================================
# Request/Response Models
# ============================================================================


class ForceCloseRoomRequest(BaseModel):
    """방 강제 종료 요청"""
    reason: str
    admin_user_id: str


class RefundInfo(BaseModel):
    """환불 정보"""
    user_id: str
    nickname: str
    amount: int
    seat: int


class ForceCloseRoomResponse(BaseModel):
    """방 강제 종료 응답"""
    success: bool
    room_id: str
    room_name: str
    reason: str
    refunds: list[RefundInfo]
    total_refunded: int
    players_affected: int


# ============================================================================
# API Endpoints
# ============================================================================


@router.post(
    "/rooms/{room_id}/force-close",
    response_model=ForceCloseRoomResponse,
    responses={
        401: {"description": "Invalid API key"},
        404: {"description": "Room not found"},
        400: {"description": "Room already closed"},
    },
)
async def force_close_room(
    room_id: str,
    request: ForceCloseRoomRequest,
    db: DbSession,
    trace_id: TraceId,
    x_api_key: str = Header(...),
):
    """관리자에 의한 방 강제 종료.

    - 진행 중인 게임이 있어도 강제로 종료
    - 모든 플레이어의 칩을 환불
    - WebSocket으로 플레이어에게 알림

    이 API는 admin-backend에서만 호출해야 합니다.
    """
    verify_api_key(x_api_key)

    room_service = RoomService(db)

    try:
        result = await room_service.force_close_room(
            room_id=room_id,
            reason=request.reason,
        )

        await db.commit()

        # WebSocket으로 플레이어에게 알림
        await _broadcast_room_force_closed(
            room_id=room_id,
            reason=request.reason,
            refunds=result["refunds"],
        )

        # 감사 로그 기록 (P0-2: Triple logging)
        from app.services.audit import get_audit_service
        audit_service = get_audit_service()
        await audit_service.log_admin_action(
            action="admin.force_close_room",
            admin_user_id=request.admin_user_id,
            target_id=room_id,
            target_type="room",
            context={
                "reason": request.reason,
                "room_name": result["room_name"],
                "players_affected": result["players_affected"],
                "total_refunded": result["total_refunded"],
                "refunds": result["refunds"],
            },
            result="success",
        )

        logger.info(
            f"Room {room_id} force closed by admin {request.admin_user_id}: "
            f"{result['players_affected']} players refunded {result['total_refunded']} chips"
        )

        return ForceCloseRoomResponse(
            success=True,
            room_id=result["room_id"],
            room_name=result["room_name"],
            reason=result["reason"],
            refunds=[RefundInfo(**r) for r in result["refunds"]],
            total_refunded=result["total_refunded"],
            players_affected=result["players_affected"],
        )

    except RoomError as e:
        # 실패 케이스도 감사 로그 기록 (P0-2)
        try:
            from app.services.audit import get_audit_service
            audit_service = get_audit_service()
            await audit_service.log_admin_action(
                action="admin.force_close_room",
                admin_user_id=request.admin_user_id,
                target_id=room_id,
                target_type="room",
                context={
                    "reason": request.reason,
                    "error_code": e.code,
                    "error_message": e.message,
                },
                result="failure",
            )
        except Exception as audit_err:
            logger.error(f"Failed to log audit for force_close_room failure: {audit_err}")

        status_code = status.HTTP_400_BAD_REQUEST
        if "NOT_FOUND" in e.code:
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


async def _broadcast_room_force_closed(
    room_id: str,
    reason: str,
    refunds: list[dict],
) -> None:
    """WebSocket을 통해 방 강제 종료 알림을 브로드캐스트."""
    try:
        from app.utils.redis_client import get_redis_service

        redis_service = get_redis_service()
        if not redis_service or not redis_service.client:
            logger.warning("Redis not available for broadcast")
            return

        # 환불 정보를 사용자 ID별로 정리
        refunds_by_user = {
            r["user_id"]: {
                "nickname": r["nickname"],
                "amount": r["amount"],
            }
            for r in refunds
        }

        message = {
            "type": EventType.ROOM_FORCE_CLOSED.value,
            "ts": int(__import__("time").time() * 1000),
            "traceId": str(uuid4()),
            "payload": {
                "roomId": room_id,
                "reason": reason,
                "refunds": refunds_by_user,
            },
        }

        # Redis pub/sub으로 브로드캐스트
        await redis_service.client.publish(
            f"ws:pubsub:table:{room_id}",
            json.dumps({
                "source_instance": "admin-api",
                "exclude_connection": None,
                "message": message,
            }),
        )

        logger.info(f"Broadcast ROOM_FORCE_CLOSED to table:{room_id}")

    except Exception as e:
        logger.error(f"Failed to broadcast room force closed: {e}")


# ============================================================================
# Room CRUD Endpoints
# ============================================================================


def _build_room_response(room) -> AdminRoomResponse:
    """Room 객체를 AdminRoomResponse로 변환."""
    return AdminRoomResponse(
        id=str(room.id),
        name=room.name,
        description=room.description,
        player_count=room.current_players,
        max_players=room.max_seats,
        small_blind=room.small_blind,
        big_blind=room.big_blind,
        buy_in_min=room.config.get("buy_in_min", 400),
        buy_in_max=room.config.get("buy_in_max", 2000),
        status=room.status,
        is_private=room.config.get("is_private", False),
        room_type=room.config.get("room_type", "cash"),
        owner_id=str(room.owner_id) if room.owner_id else None,
        owner_nickname=room.owner.nickname if room.owner else None,
        created_at=room.created_at,
    )


def _build_room_detail_response(room, seats_info: list[AdminSeatInfo]) -> AdminRoomDetailResponse:
    """Room 객체를 AdminRoomDetailResponse로 변환."""
    return AdminRoomDetailResponse(
        id=str(room.id),
        name=room.name,
        description=room.description,
        player_count=room.current_players,
        max_players=room.max_seats,
        small_blind=room.small_blind,
        big_blind=room.big_blind,
        buy_in_min=room.config.get("buy_in_min", 400),
        buy_in_max=room.config.get("buy_in_max", 2000),
        turn_timeout=room.config.get("turn_timeout", 30),
        status=room.status,
        is_private=room.config.get("is_private", False),
        room_type=room.config.get("room_type", "cash"),
        owner_id=str(room.owner_id) if room.owner_id else None,
        owner_nickname=room.owner.nickname if room.owner else None,
        seats=seats_info,
        current_hand_id=None,  # TODO: GameManager에서 가져오기
        created_at=room.created_at,
        updated_at=room.updated_at,
    )


@router.get(
    "/rooms",
    response_model=AdminRoomListResponse,
    responses={401: {"description": "Invalid API key"}},
)
async def list_rooms_admin(
    db: DbSession,
    x_api_key: str = Header(...),
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    status_filter: str | None = Query(None, alias="status", description="상태 필터"),
    search: str | None = Query(None, description="방 이름 검색"),
    include_closed: bool = Query(False, description="종료된 방 포함"),
):
    """어드민용 방 목록 조회.

    - 필터링: 상태, 검색어
    - 페이지네이션 지원
    - 종료된 방 포함 옵션
    """
    verify_api_key(x_api_key)

    room_service = RoomService(db)
    rooms, total = await room_service.list_rooms_admin(
        page=page,
        page_size=page_size,
        status=status_filter,
        search=search,
        include_closed=include_closed,
    )

    return AdminRoomListResponse(
        items=[_build_room_response(room) for room in rooms],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get(
    "/rooms/{room_id}",
    response_model=AdminRoomDetailResponse,
    responses={
        401: {"description": "Invalid API key"},
        404: {"description": "Room not found"},
    },
)
async def get_room_admin(
    room_id: str,
    db: DbSession,
    x_api_key: str = Header(...),
):
    """어드민용 방 상세 조회.

    - 현재 착석자 정보 포함
    - 진행 중인 핸드 ID 포함 (있는 경우)
    """
    verify_api_key(x_api_key)

    room_service = RoomService(db)
    room = await room_service.get_room_with_tables(room_id)

    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="방을 찾을 수 없습니다",
        )

    # 좌석 정보 구성
    seats_info = []
    max_seats = room.max_seats
    table = room.tables[0] if room.tables else None
    seats_data = table.seats if table else {}

    for pos in range(max_seats):
        seat_data = seats_data.get(str(pos), {})
        if seat_data:
            seats_info.append(
                AdminSeatInfo(
                    position=pos,
                    user_id=seat_data.get("user_id"),
                    nickname=seat_data.get("nickname"),
                    stack=seat_data.get("stack", 0),
                    status=seat_data.get("status", "active"),
                    is_bot=seat_data.get("is_bot", False),
                )
            )
        else:
            seats_info.append(
                AdminSeatInfo(position=pos, status="empty")
            )

    return _build_room_detail_response(room, seats_info)


@router.post(
    "/rooms",
    response_model=AdminRoomDetailResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "Invalid API key"},
        400: {"description": "Invalid request"},
    },
)
async def create_room_admin(
    request: AdminCreateRoomRequest,
    db: DbSession,
    trace_id: TraceId,
    x_api_key: str = Header(...),
):
    """어드민에 의한 방 생성.

    - owner_id는 None (시스템 소유)
    - 모든 설정 가능
    """
    verify_api_key(x_api_key)

    room_service = RoomService(db)

    try:
        room = await room_service.create_room_admin(
            name=request.name,
            description=request.description,
            room_type=request.room_type,
            max_seats=request.max_seats,
            small_blind=request.small_blind,
            big_blind=request.big_blind,
            buy_in_min=request.buy_in_min,
            buy_in_max=request.buy_in_max,
            turn_timeout=request.turn_timeout,
            is_private=request.is_private,
            password=request.password,
        )
        await db.commit()
        await db.refresh(room)

        logger.info(f"Room {room.id} created by admin: {room.name}")

        # 빈 좌석 정보
        seats_info = [
            AdminSeatInfo(position=pos, status="empty")
            for pos in range(room.max_seats)
        ]

        return _build_room_detail_response(room, seats_info)

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


@router.patch(
    "/rooms/{room_id}",
    response_model=AdminRoomDetailResponse,
    responses={
        401: {"description": "Invalid API key"},
        404: {"description": "Room not found"},
        400: {"description": "Invalid request"},
    },
)
async def update_room_admin(
    room_id: str,
    request: AdminUpdateRoomRequest,
    db: DbSession,
    trace_id: TraceId,
    x_api_key: str = Header(...),
):
    """어드민에 의한 방 설정 수정.

    - owner 권한 체크 없음
    - 모든 설정 변경 가능 (좌석 수는 플레이어 없을 때만)
    """
    verify_api_key(x_api_key)

    room_service = RoomService(db)

    try:
        room = await room_service.update_room_admin(
            room_id=room_id,
            name=request.name,
            description=request.description,
            is_private=request.is_private,
            password=request.password,
            small_blind=request.small_blind,
            big_blind=request.big_blind,
            buy_in_min=request.buy_in_min,
            buy_in_max=request.buy_in_max,
            turn_timeout=request.turn_timeout,
            max_seats=request.max_seats,
        )
        await db.commit()

        # 방 다시 조회 (테이블 정보 포함)
        room = await room_service.get_room_with_tables(room_id)

        logger.info(f"Room {room_id} updated by admin")

        # 좌석 정보 구성
        seats_info = []
        max_seats = room.max_seats
        table = room.tables[0] if room.tables else None
        seats_data = table.seats if table else {}

        for pos in range(max_seats):
            seat_data = seats_data.get(str(pos), {})
            if seat_data:
                seats_info.append(
                    AdminSeatInfo(
                        position=pos,
                        user_id=seat_data.get("user_id"),
                        nickname=seat_data.get("nickname"),
                        stack=seat_data.get("stack", 0),
                        status=seat_data.get("status", "active"),
                        is_bot=seat_data.get("is_bot", False),
                    )
                )
            else:
                seats_info.append(
                    AdminSeatInfo(position=pos, status="empty")
                )

        return _build_room_detail_response(room, seats_info)

    except RoomError as e:
        status_code = status.HTTP_400_BAD_REQUEST
        if "NOT_FOUND" in e.code:
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


@router.delete(
    "/rooms/{room_id}",
    response_model=AdminCloseRoomResponse,
    responses={
        401: {"description": "Invalid API key"},
        404: {"description": "Room not found"},
        400: {"description": "Room has players (use force-close)"},
    },
)
async def delete_room_admin(
    room_id: str,
    db: DbSession,
    trace_id: TraceId,
    x_api_key: str = Header(...),
):
    """어드민에 의한 방 종료.

    - 플레이어가 없는 방만 종료 가능
    - 플레이어가 있으면 force-close 사용 필요
    """
    verify_api_key(x_api_key)

    room_service = RoomService(db)

    try:
        await room_service.close_room_admin(room_id)
        await db.commit()

        logger.info(f"Room {room_id} closed by admin")

        return AdminCloseRoomResponse(
            success=True,
            message="방이 종료되었습니다",
            room_id=room_id,
        )

    except RoomError as e:
        status_code = status.HTTP_400_BAD_REQUEST
        if "NOT_FOUND" in e.code:
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


# ============================================================================
# Rake Config Endpoints (P1-1)
# ============================================================================


def _build_rake_config_response(config) -> RakeConfigResponse:
    """RakeConfig 객체를 응답으로 변환."""
    return RakeConfigResponse(
        id=str(config.id),
        small_blind=config.small_blind,
        big_blind=config.big_blind,
        percentage=float(config.percentage),
        cap_bb=config.cap_bb,
        is_active=config.is_active,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.get(
    "/rake-configs",
    response_model=RakeConfigListResponse,
    responses={401: {"description": "Invalid API key"}},
)
async def list_rake_configs(
    db: DbSession,
    x_api_key: str = Header(...),
    include_inactive: bool = Query(False, alias="includeInactive", description="비활성 설정 포함"),
):
    """레이크 설정 목록 조회.

    블라인드 레벨별 레이크 설정을 조회합니다.
    """
    verify_api_key(x_api_key)

    service = RakeConfigService(db)
    configs = await service.list_configs(include_inactive=include_inactive)

    return RakeConfigListResponse(
        items=[_build_rake_config_response(c) for c in configs],
        total=len(configs),
    )


@router.get(
    "/rake-configs/{config_id}",
    response_model=RakeConfigResponse,
    responses={
        401: {"description": "Invalid API key"},
        404: {"description": "Config not found"},
    },
)
async def get_rake_config(
    config_id: str,
    db: DbSession,
    x_api_key: str = Header(...),
):
    """레이크 설정 상세 조회."""
    verify_api_key(x_api_key)

    service = RakeConfigService(db)
    config = await service.get_config(config_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="레이크 설정을 찾을 수 없습니다",
        )

    return _build_rake_config_response(config)


@router.post(
    "/rake-configs",
    response_model=RakeConfigResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "Invalid API key"},
        409: {"description": "Duplicate blind level"},
    },
)
async def create_rake_config(
    request: RakeConfigCreate,
    db: DbSession,
    x_api_key: str = Header(...),
):
    """레이크 설정 생성.

    새로운 블라인드 레벨에 대한 레이크 설정을 추가합니다.
    동일한 블라인드 레벨 설정이 이미 있으면 409 에러가 발생합니다.
    """
    verify_api_key(x_api_key)

    service = RakeConfigService(db)

    # 중복 체크
    existing = await service.get_config_by_blind_level(
        request.small_blind, request.big_blind
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"SB={request.small_blind}/BB={request.big_blind} 설정이 이미 존재합니다",
        )

    config = await service.create_config(
        small_blind=request.small_blind,
        big_blind=request.big_blind,
        percentage=request.percentage,
        cap_bb=request.cap_bb,
        is_active=request.is_active,
    )
    await db.commit()
    await db.refresh(config)

    logger.info(
        f"Rake config created: SB={config.small_blind} BB={config.big_blind} "
        f"{float(config.percentage)*100}% cap={config.cap_bb}BB"
    )

    return _build_rake_config_response(config)


@router.patch(
    "/rake-configs/{config_id}",
    response_model=RakeConfigResponse,
    responses={
        401: {"description": "Invalid API key"},
        404: {"description": "Config not found"},
    },
)
async def update_rake_config(
    config_id: str,
    request: RakeConfigUpdate,
    db: DbSession,
    x_api_key: str = Header(...),
):
    """레이크 설정 수정.

    퍼센트, 캡, 활성화 여부를 수정할 수 있습니다.
    블라인드 레벨은 수정할 수 없습니다 (삭제 후 재생성 필요).
    """
    verify_api_key(x_api_key)

    service = RakeConfigService(db)
    config = await service.get_config(config_id)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="레이크 설정을 찾을 수 없습니다",
        )

    config = await service.update_config(
        config_id=config_id,
        percentage=request.percentage,
        cap_bb=request.cap_bb,
        is_active=request.is_active,
    )
    await db.commit()

    logger.info(f"Rake config updated: {config_id}")

    return _build_rake_config_response(config)


@router.delete(
    "/rake-configs/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"description": "Invalid API key"},
        404: {"description": "Config not found"},
    },
)
async def delete_rake_config(
    config_id: str,
    db: DbSession,
    x_api_key: str = Header(...),
):
    """레이크 설정 삭제.

    설정을 삭제하면 해당 블라인드 레벨은 기본값(5%, 3BB)이 적용됩니다.
    """
    verify_api_key(x_api_key)

    service = RakeConfigService(db)
    deleted = await service.delete_config(config_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="레이크 설정을 찾을 수 없습니다",
        )

    await db.commit()
    logger.info(f"Rake config deleted: {config_id}")


# ============================================================================
# Live Bot Endpoints
# ============================================================================


class BotTargetRequest(BaseModel):
    """봇 목표 수 설정 요청."""

    target_count: int = Field(ge=0, le=100, description="목표 봇 수 (0-100)")


@router.get(
    "/bots/status",
    responses={401: {"description": "Invalid API key"}},
)
async def get_bot_status(
    x_api_key: str = Header(...),
):
    """봇 시스템 상태 조회.

    현재 봇 수, 상태별 분포, 개별 봇 정보를 반환합니다.
    """
    verify_api_key(x_api_key)

    from app.bot.orchestrator import get_bot_orchestrator

    orchestrator = get_bot_orchestrator()
    return orchestrator.get_status()


@router.post(
    "/bots/target",
    responses={401: {"description": "Invalid API key"}},
)
async def set_bot_target(
    request: BotTargetRequest,
    x_api_key: str = Header(...),
):
    """목표 봇 수 설정.

    오케스트레이터가 이 목표에 맞게 봇 수를 점진적으로 조절합니다.
    """
    verify_api_key(x_api_key)

    from app.bot.orchestrator import get_bot_orchestrator

    orchestrator = get_bot_orchestrator()
    result = await orchestrator.set_target_count(request.target_count)

    logger.info(
        f"Bot target count changed: {result['old_target']} -> {result['new_target']} "
        f"(current active: {result['current_active']})"
    )

    return result


@router.post(
    "/bots/spawn",
    responses={401: {"description": "Invalid API key"}},
)
async def spawn_bot(
    x_api_key: str = Header(...),
):
    """봇 하나 즉시 생성 (테스트용).

    Rate limiter를 무시하고 즉시 봇을 생성합니다.
    """
    verify_api_key(x_api_key)

    from app.bot.orchestrator import get_bot_orchestrator

    orchestrator = get_bot_orchestrator()

    # Lock 획득 후 spawn 시도
    async with orchestrator._lock:
        success = await orchestrator._spawn_bot()

    if success:
        return {
            "success": True,
            "message": "봇이 생성되었습니다",
            "active_count": orchestrator.active_bot_count,
        }
    else:
        return {
            "success": False,
            "message": "봇 생성 실패 (적합한 방이 없을 수 있음)",
            "active_count": orchestrator.active_bot_count,
        }


@router.post(
    "/bots/retire/{bot_id}",
    responses={
        401: {"description": "Invalid API key"},
        404: {"description": "Bot not found"},
    },
)
async def retire_bot(
    bot_id: str,
    x_api_key: str = Header(...),
):
    """특정 봇 은퇴 요청.

    봇이 현재 핸드를 완료한 후 테이블을 떠나게 합니다.
    """
    verify_api_key(x_api_key)

    from app.bot.orchestrator import get_bot_orchestrator

    orchestrator = get_bot_orchestrator()

    # Find and retire the bot
    session = orchestrator._sessions.get(bot_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"봇을 찾을 수 없습니다: {bot_id}",
        )

    session.request_retire()

    logger.info(f"Bot retire requested: {session.nickname} ({bot_id})")

    return {
        "success": True,
        "bot_id": bot_id,
        "nickname": session.nickname,
        "state": session.state.name,
        "message": "은퇴 요청이 등록되었습니다. 현재 핸드 완료 후 테이블을 떠납니다.",
    }


@router.delete(
    "/bots/all",
    responses={401: {"description": "Invalid API key"}},
)
async def force_remove_all_bots(
    x_api_key: str = Header(...),
):
    """모든 봇 즉시 삭제.

    게임 진행 상태와 관계없이 모든 봇을 즉시 테이블에서 제거합니다.
    target_count도 0으로 리셋됩니다.
    """
    verify_api_key(x_api_key)

    from app.bot.orchestrator import get_bot_orchestrator

    orchestrator = get_bot_orchestrator()
    result = await orchestrator.force_remove_all_bots()

    logger.info(f"Force removed all bots: {result['removed_count']} bots removed")

    return result
