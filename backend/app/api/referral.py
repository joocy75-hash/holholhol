"""친구추천 API"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.utils.db import get_db
from app.services.referral import ReferralService, ReferralError

router = APIRouter(prefix="/referral", tags=["Referral"])


# ============================================================================
# Response Models
# ============================================================================


class ReferralCodeResponse(BaseModel):
    """추천 코드 응답"""
    referral_code: str
    referrer_reward: int
    referee_reward: int


class RecentReferral(BaseModel):
    nickname: str
    joined_at: str | None


class ReferralStatsResponse(BaseModel):
    """추천 통계 응답"""
    referral_code: str
    total_referrals: int
    total_rewards: int
    referrer_reward: int
    referee_reward: int
    recent_referrals: list[RecentReferral]


class ApplyReferralRequest(BaseModel):
    """추천 코드 적용 요청"""
    referral_code: str


class ApplyReferralResponse(BaseModel):
    """추천 코드 적용 응답"""
    success: bool
    referrer_nickname: str
    referee_reward: int


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("/code", response_model=ReferralCodeResponse)
async def get_my_referral_code(
    user: CurrentUser = None,
    db: AsyncSession = Depends(get_db),
):
    """내 추천 코드 조회

    - 코드가 없으면 자동 생성
    - 친구에게 공유하여 가입 시 사용하도록 안내
    """
    service = ReferralService(db)

    try:
        code = await service.get_or_create_referral_code(user.id)
        from app.models.referral import REFERRAL_REWARDS
        return ReferralCodeResponse(
            referral_code=code,
            referrer_reward=REFERRAL_REWARDS["referrer"],
            referee_reward=REFERRAL_REWARDS["referee"],
        )
    except ReferralError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/stats", response_model=ReferralStatsResponse)
async def get_referral_stats(
    user: CurrentUser = None,
    db: AsyncSession = Depends(get_db),
):
    """추천 통계 조회

    - 총 추천 수
    - 총 보상 금액
    - 최근 추천 목록
    """
    service = ReferralService(db)

    try:
        stats = await service.get_referral_stats(user.id)
        return ReferralStatsResponse(**stats)
    except ReferralError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.post("/apply", response_model=ApplyReferralResponse)
async def apply_referral_code(
    request: ApplyReferralRequest,
    user: CurrentUser = None,
    db: AsyncSession = Depends(get_db),
):
    """추천 코드 적용 (가입 후)

    - 가입 시 추천 코드를 입력하지 않았다면 나중에 적용 가능
    - 한 번만 적용 가능
    - 양방향 보상 지급 (추천인 + 피추천인)
    """
    service = ReferralService(db)

    try:
        result = await service.process_referral(
            new_user_id=user.id,
            referral_code=request.referral_code.strip().upper(),
        )
        return ApplyReferralResponse(
            success=True,
            referrer_nickname=result["referrer"]["nickname"],
            referee_reward=result["referee"]["reward"],
        )
    except ReferralError as e:
        raise HTTPException(status_code=400, detail=e.message)
