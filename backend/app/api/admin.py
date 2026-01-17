"""Internal Admin API endpoints for admin-backend integration.

These endpoints are protected by API key authentication and should only be
called from the admin-backend service.
"""
import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel
from redis.asyncio import Redis

from app.api.deps import DbSession, TraceId
from app.config import get_settings
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
