"""Live Bot management API for admin dashboard.

Provides endpoints to:
- Get bot system status
- Set target bot count (slider control)
- View active bot details
"""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.config import get_settings
from app.utils.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


class BotTargetRequest(BaseModel):
    """Request to set target bot count."""

    target_count: int = Field(ge=0, le=100, description="Target number of active bots (0-100)")


class BotStatusResponse(BaseModel):
    """Bot system status response."""

    enabled: bool
    running: bool
    target_count: int
    active_count: int
    total_count: int
    state_counts: dict[str, int]
    bots: list[dict]


class BotTargetResponse(BaseModel):
    """Response after setting target count."""

    success: bool
    old_target: int
    new_target: int
    current_active: int
    current_total: int


async def call_main_backend(
    method: str,
    path: str,
    json_data: Optional[dict] = None,
) -> dict:
    """Call the main backend API.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: API path (without base URL)
        json_data: Optional JSON body

    Returns:
        Response JSON

    Raises:
        HTTPException: If the request fails
    """
    url = f"{settings.main_api_url}/api/v1{path}"
    headers = {"X-API-Key": settings.main_api_key}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
            )

            if response.status_code >= 400:
                logger.error(
                    f"Main backend error: {response.status_code} - {response.text}"
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail=response.json() if response.text else "Backend error",
                )

            return response.json()

    except httpx.RequestError as e:
        logger.error(f"Failed to connect to main backend: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to connect to game server",
        )


@router.get(
    "/status",
    response_model=BotStatusResponse,
    summary="Get bot system status",
)
async def get_bot_status(
    _: dict = Depends(get_current_user),
) -> BotStatusResponse:
    """Get the current status of the live bot system.

    Returns:
        Bot system status including active count, state distribution, and bot list
    """
    result = await call_main_backend("GET", "/internal/admin/bots/status")
    return BotStatusResponse(**result)


@router.post(
    "/target",
    response_model=BotTargetResponse,
    summary="Set target bot count",
)
async def set_bot_target(
    request: BotTargetRequest,
    _: dict = Depends(get_current_user),
) -> BotTargetResponse:
    """Set the target number of active bots.

    The orchestrator will gradually adjust the bot count towards this target.

    Args:
        request: Target count (0-100)

    Returns:
        Result with old/new target and current counts
    """
    result = await call_main_backend(
        "POST",
        "/internal/admin/bots/target",
        json_data={"target_count": request.target_count},
    )
    return BotTargetResponse(**result)


@router.post(
    "/spawn",
    summary="Spawn a single bot immediately",
)
async def spawn_bot(
    _: dict = Depends(get_current_user),
) -> dict:
    """Spawn a single bot immediately (for testing).

    This bypasses the rate limiter.

    Returns:
        Result with spawned bot info
    """
    result = await call_main_backend("POST", "/internal/admin/bots/spawn")
    return result


@router.post(
    "/retire/{bot_id}",
    summary="Retire a specific bot",
)
async def retire_bot(
    bot_id: str,
    _: dict = Depends(get_current_user),
) -> dict:
    """Request a specific bot to retire gracefully.

    The bot will leave after completing its current hand.

    Args:
        bot_id: The bot's ID to retire

    Returns:
        Result with retirement status
    """
    result = await call_main_backend("POST", f"/internal/admin/bots/retire/{bot_id}")
    return result
