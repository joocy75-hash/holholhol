from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()


class BanResponse(BaseModel):
    id: str
    user_id: str
    username: str
    ban_type: str
    reason: str
    expires_at: str | None
    created_by: str
    created_at: str


class PaginatedBans(BaseModel):
    items: list[BanResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CreateBanRequest(BaseModel):
    user_id: str
    ban_type: str  # temporary, permanent, chat_only
    reason: str
    duration_hours: int | None = None  # for temporary bans


@router.get("", response_model=PaginatedBans)
async def list_bans(
    status: str | None = Query(None, description="active or expired"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List bans"""
    # TODO: Implement actual ban listing
    return PaginatedBans(
        items=[],
        total=0,
        page=page,
        page_size=page_size,
        total_pages=0,
    )


@router.post("", response_model=BanResponse)
async def create_ban(request: CreateBanRequest):
    """Create a new ban"""
    # TODO: Implement actual ban creation
    return BanResponse(
        id="ban-1",
        user_id=request.user_id,
        username="test_user",
        ban_type=request.ban_type,
        reason=request.reason,
        expires_at=None,
        created_by="admin",
        created_at="2026-01-15T00:00:00Z",
    )


@router.delete("/{ban_id}")
async def lift_ban(ban_id: str):
    """Lift a ban"""
    # TODO: Implement actual ban lifting
    return {"message": f"Ban {ban_id} lifted"}
