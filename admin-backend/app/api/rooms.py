"""Room Management API for Admin Dashboard.

Provides endpoints for managing game rooms including:
- Room listing and details
- Force closing rooms with chip refunds
- Sending system messages to rooms

**Phase 3.3**: 방 강제 종료 기능 구현
"""
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.config import get_settings
from app.database import get_main_db
from app.models.admin_user import AdminUser
from app.utils.dependencies import get_current_user, require_supervisor
from app.utils.permissions import Permission, has_permission

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()


# ============================================================================
# Request/Response Models
# ============================================================================


class RoomResponse(BaseModel):
    """방 정보 응답"""
    id: str
    name: str
    player_count: int
    max_players: int
    small_blind: int
    big_blind: int
    status: str
    created_at: str


class PaginatedRooms(BaseModel):
    """방 목록 페이지네이션 응답"""
    items: list[RoomResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ForceCloseRequest(BaseModel):
    """방 강제 종료 요청"""
    reason: str = Field(..., min_length=1, max_length=500, description="강제 종료 사유")


class RefundInfo(BaseModel):
    """환불 정보"""
    user_id: str
    nickname: str
    amount: int
    seat: int


class ForceCloseResponse(BaseModel):
    """방 강제 종료 응답"""
    success: bool
    room_id: str
    room_name: str
    reason: str
    refunds: list[RefundInfo]
    total_refunded: int
    players_affected: int


class SystemMessageRequest(BaseModel):
    """시스템 메시지 요청"""
    message: str = Field(..., min_length=1, max_length=1000)


class SystemMessageResponse(BaseModel):
    """시스템 메시지 응답"""
    success: bool
    room_id: str
    message: str


# ============================================================================
# Helper Functions
# ============================================================================


async def _call_game_backend(
    method: str,
    path: str,
    data: Optional[dict] = None,
) -> dict:
    """Game Backend API 호출.

    Args:
        method: HTTP 메서드 (GET, POST, etc.)
        path: API 경로 (/internal/admin/...)
        data: 요청 데이터 (POST 등에서 사용)

    Returns:
        API 응답 데이터

    Raises:
        HTTPException: API 호출 실패 시
    """
    url = f"{settings.main_api_url}{path}"
    headers = {"X-API-Key": settings.main_api_key}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method.upper() == "GET":
                response = await client.get(url, headers=headers)
            elif method.upper() == "POST":
                response = await client.post(url, json=data, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                logger.error("Game Backend API key authentication failed")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Game server authentication failed",
                )
            elif response.status_code == 404:
                error_detail = response.json().get("detail", {})
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=error_detail,
                )
            elif response.status_code == 400:
                error_detail = response.json().get("detail", {})
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_detail,
                )
            else:
                logger.error(f"Game Backend API error: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Game server error",
                )

    except httpx.TimeoutException:
        logger.error(f"Game Backend API timeout: {url}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Game server timeout",
        )
    except httpx.RequestError as e:
        logger.error(f"Game Backend API connection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Game server connection failed",
        )


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("", response_model=PaginatedRooms)
async def list_rooms(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AdminUser = Depends(get_current_user),
):
    """방 목록 조회.

    모든 관리자가 조회 가능합니다.
    """
    if not has_permission(current_user.role, Permission.VIEW_ROOMS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="VIEW_ROOMS 권한이 필요합니다",
        )

    # TODO: Main DB에서 방 목록 조회 구현
    # 현재는 빈 목록 반환
    return PaginatedRooms(
        items=[],
        total=0,
        page=page,
        page_size=page_size,
        total_pages=0,
    )


@router.get("/{room_id}", response_model=RoomResponse)
async def get_room(
    room_id: str,
    current_user: AdminUser = Depends(get_current_user),
):
    """방 상세 조회.

    모든 관리자가 조회 가능합니다.
    """
    if not has_permission(current_user.role, Permission.VIEW_ROOMS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="VIEW_ROOMS 권한이 필요합니다",
        )

    # TODO: Main DB에서 방 정보 조회 구현
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="방을 찾을 수 없습니다",
    )


@router.post("/{room_id}/force-close", response_model=ForceCloseResponse)
async def force_close_room(
    room_id: str,
    request: ForceCloseRequest,
    current_user: AdminUser = Depends(require_supervisor),
):
    """방 강제 종료.

    - 진행 중인 게임이 있어도 강제로 종료합니다.
    - 모든 플레이어의 칩을 환불합니다.
    - WebSocket으로 플레이어에게 알림을 보냅니다.

    **권한**: supervisor 이상만 사용 가능
    """
    if not has_permission(current_user.role, Permission.FORCE_CLOSE_ROOM):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="FORCE_CLOSE_ROOM 권한이 필요합니다",
        )

    logger.info(
        f"Admin {current_user.username} ({current_user.id}) "
        f"requesting force close for room {room_id}: {request.reason}"
    )

    # Game Backend API 호출
    result = await _call_game_backend(
        method="POST",
        path=f"/api/v1/internal/admin/rooms/{room_id}/force-close",
        data={
            "reason": request.reason,
            "admin_user_id": str(current_user.id),
        },
    )

    logger.info(
        f"Room {room_id} force closed by admin {current_user.username}: "
        f"{result.get('players_affected', 0)} players refunded "
        f"{result.get('total_refunded', 0)} chips"
    )

    return ForceCloseResponse(
        success=result.get("success", True),
        room_id=result.get("room_id", room_id),
        room_name=result.get("room_name", "Unknown"),
        reason=result.get("reason", request.reason),
        refunds=[RefundInfo(**r) for r in result.get("refunds", [])],
        total_refunded=result.get("total_refunded", 0),
        players_affected=result.get("players_affected", 0),
    )


@router.post("/{room_id}/message", response_model=SystemMessageResponse)
async def send_system_message(
    room_id: str,
    request: SystemMessageRequest,
    current_user: AdminUser = Depends(get_current_user),
):
    """방에 시스템 메시지 전송.

    **권한**: operator 이상만 사용 가능
    """
    if not has_permission(current_user.role, Permission.SEND_ROOM_MESSAGE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SEND_ROOM_MESSAGE 권한이 필요합니다",
        )

    # TODO: Game Backend에 시스템 메시지 전송 API 호출 구현
    logger.info(
        f"Admin {current_user.username} sending message to room {room_id}: {request.message}"
    )

    return SystemMessageResponse(
        success=True,
        room_id=room_id,
        message=request.message,
    )
