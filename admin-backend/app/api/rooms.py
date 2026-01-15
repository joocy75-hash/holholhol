from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()


class RoomResponse(BaseModel):
    id: str
    name: str
    player_count: int
    max_players: int
    small_blind: int
    big_blind: int
    status: str
    created_at: str


class PaginatedRooms(BaseModel):
    items: list[RoomResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ForceCloseRequest(BaseModel):
    reason: str


class SystemMessageRequest(BaseModel):
    message: str


@router.get("", response_model=PaginatedRooms)
async def list_rooms(
    status: str | None = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List active rooms"""
    # TODO: Implement actual room listing
    return PaginatedRooms(
        items=[],
        total=0,
        page=page,
        page_size=page_size,
        total_pages=0,
    )


@router.get("/{room_id}", response_model=RoomResponse)
async def get_room(room_id: str):
    """Get room details"""
    # TODO: Implement actual room retrieval
    return RoomResponse(
        id=room_id,
        name="Test Room",
        player_count=4,
        max_players=9,
        small_blind=100,
        big_blind=200,
        status="active",
        created_at="2026-01-15T00:00:00Z",
    )


@router.post("/{room_id}/force-close")
async def force_close_room(room_id: str, request: ForceCloseRequest):
    """Force close a room"""
    # TODO: Implement actual room force close
    return {"message": f"Room {room_id} closed", "reason": request.reason}


@router.post("/{room_id}/message")
async def send_system_message(room_id: str, request: SystemMessageRequest):
    """Send system message to room"""
    # TODO: Implement actual message sending
    return {"message": "Message sent", "room_id": room_id}
