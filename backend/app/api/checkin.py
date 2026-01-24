"""출석체크 API"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.utils.db import get_db
from app.services.checkin import CheckinService, CheckinError

router = APIRouter(prefix="/checkin", tags=["Checkin"])


# ============================================================================
# Response Models
# ============================================================================


class BonusReward(BaseModel):
    type: str
    amount: int


class CheckinResponse(BaseModel):
    """출석체크 결과"""
    success: bool
    checkin_date: str
    streak_days: int
    reward_amount: int
    reward_type: str
    bonus_rewards: list[BonusReward]
    new_balance: int


class NextBonus(BaseModel):
    days_remaining: int
    bonus: int


class MonthlyCheckin(BaseModel):
    date: str
    reward: int
    reward_type: str


class CheckinStatusResponse(BaseModel):
    """출석체크 상태"""
    can_checkin: bool
    streak_days: int
    monthly_checkins: list[MonthlyCheckin]
    next_bonus: NextBonus | None
    daily_reward: int


class CheckinHistoryItem(BaseModel):
    date: str
    streak_days: int
    reward_amount: int
    reward_type: str
    checked_at: str


class CheckinHistoryResponse(BaseModel):
    items: list[CheckinHistoryItem]


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("", response_model=CheckinResponse)
async def do_checkin(
    user: CurrentUser = None,
    db: AsyncSession = Depends(get_db),
):
    """출석체크 수행

    - 하루 1회만 가능 (KST 기준)
    - 연속 출석 보너스: 7일(500), 14일(1000), 30일(3000)
    - 기본 보상: 100 KRW
    """
    service = CheckinService(db)

    try:
        result = await service.checkin(user.id)
        return CheckinResponse(**result)
    except CheckinError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/status", response_model=CheckinStatusResponse)
async def get_checkin_status(
    user: CurrentUser = None,
    db: AsyncSession = Depends(get_db),
):
    """출석체크 상태 조회

    - 오늘 출석 가능 여부
    - 현재 연속 출석 일수
    - 이번 달 출석 기록
    - 다음 보너스까지 남은 일수
    """
    service = CheckinService(db)
    result = await service.get_checkin_status(user.id)
    return CheckinStatusResponse(**result)


@router.get("/history", response_model=CheckinHistoryResponse)
async def get_checkin_history(
    limit: int = 30,
    user: CurrentUser = None,
    db: AsyncSession = Depends(get_db),
):
    """출석체크 히스토리 조회"""
    service = CheckinService(db)
    items = await service.get_checkin_history(user.id, limit)
    return CheckinHistoryResponse(items=items)
