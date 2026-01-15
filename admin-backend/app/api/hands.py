from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()


class HandSummary(BaseModel):
    id: str
    room_id: str
    pot_size: float
    winner_id: str
    created_at: str


class PaginatedHands(BaseModel):
    items: list[HandSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class HandAction(BaseModel):
    player_id: str
    action: str
    amount: float | None
    timestamp: str


class HandDetail(BaseModel):
    id: str
    room_id: str
    players: list[dict]
    community_cards: list[str]
    actions: list[HandAction]
    pot_size: float
    winner_id: str
    created_at: str


@router.get("", response_model=PaginatedHands)
async def search_hands(
    hand_id: str | None = Query(None),
    user_id: str | None = Query(None),
    room_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Search hands"""
    # TODO: Implement actual hand search
    return PaginatedHands(
        items=[],
        total=0,
        page=page,
        page_size=page_size,
        total_pages=0,
    )


@router.get("/{hand_id}", response_model=HandDetail)
async def get_hand(hand_id: str):
    """Get hand details for replay"""
    # TODO: Implement actual hand retrieval
    return HandDetail(
        id=hand_id,
        room_id="room-1",
        players=[],
        community_cards=[],
        actions=[],
        pot_size=0,
        winner_id="",
        created_at="2026-01-15T00:00:00Z",
    )


@router.get("/{hand_id}/export")
async def export_hand(hand_id: str, format: str = Query("json", enum=["json", "text"])):
    """Export hand history"""
    # TODO: Implement actual hand export
    return {"hand_id": hand_id, "format": format, "data": {}}
