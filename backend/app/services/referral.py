"""친구추천 서비스"""

import secrets
import string
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.referral import ReferralReward, REFERRAL_REWARDS


# KST 타임존 (UTC+9)
KST = timezone(timedelta(hours=9))


class ReferralError(Exception):
    """추천 관련 에러"""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def generate_referral_code(length: int = 8) -> str:
    """랜덤 추천 코드 생성 (영문+숫자)"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


class ReferralService:
    """친구추천 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_referral_code(self, user_id: UUID) -> str:
        """유저의 추천 코드 조회 또는 생성"""
        user = await self.db.get(User, str(user_id))
        if not user:
            raise ReferralError("USER_NOT_FOUND", "유저를 찾을 수 없습니다")

        if user.referral_code:
            return user.referral_code

        # 새 추천 코드 생성 (중복 체크)
        for _ in range(10):  # 최대 10번 시도
            code = generate_referral_code()
            existing = await self.db.execute(
                select(User).where(User.referral_code == code)
            )
            if not existing.scalar_one_or_none():
                user.referral_code = code
                await self.db.commit()
                return code

        raise ReferralError("CODE_GENERATION_FAILED", "추천 코드 생성에 실패했습니다")

    async def get_referrer_by_code(self, code: str) -> User | None:
        """추천 코드로 추천인 조회"""
        result = await self.db.execute(
            select(User).where(User.referral_code == code)
        )
        return result.scalar_one_or_none()

    async def process_referral(
        self,
        new_user_id: UUID,
        referral_code: str,
    ) -> dict:
        """신규 가입자의 추천 처리 및 보상 지급

        Args:
            new_user_id: 신규 가입자 ID
            referral_code: 추천 코드

        Returns:
            처리 결과 (추천인 보상, 피추천인 보상 정보)
        """
        now = datetime.now(KST)

        # 추천인 조회
        referrer = await self.get_referrer_by_code(referral_code)
        if not referrer:
            raise ReferralError("INVALID_CODE", "유효하지 않은 추천 코드입니다")

        # 자기 자신 추천 방지
        if str(referrer.id) == str(new_user_id):
            raise ReferralError("SELF_REFERRAL", "자신의 추천 코드는 사용할 수 없습니다")

        # 신규 가입자 조회
        new_user = await self.db.get(User, str(new_user_id))
        if not new_user:
            raise ReferralError("USER_NOT_FOUND", "유저를 찾을 수 없습니다")

        # 이미 추천 받았는지 확인
        if new_user.referred_by_user_id:
            raise ReferralError("ALREADY_REFERRED", "이미 추천을 받은 유저입니다")

        # 추천인 연결
        new_user.referred_by_user_id = referrer.id

        # 보상 지급
        referrer_reward = REFERRAL_REWARDS["referrer"]
        referee_reward = REFERRAL_REWARDS["referee"]

        # 추천인 보상
        referrer.krw_balance += referrer_reward
        referrer_reward_record = ReferralReward(
            user_id=referrer.id,
            referred_user_id=new_user.id,
            reward_type="referrer",
            reward_amount=referrer_reward,
            rewarded_at=now,
            note=f"친구 추천 보상 (피추천인: {new_user.nickname})",
        )
        self.db.add(referrer_reward_record)

        # 피추천인 보상
        new_user.krw_balance += referee_reward
        referee_reward_record = ReferralReward(
            user_id=new_user.id,
            referred_user_id=new_user.id,
            reward_type="referee",
            reward_amount=referee_reward,
            rewarded_at=now,
            note=f"가입 추천 보너스 (추천인: {referrer.nickname})",
        )
        self.db.add(referee_reward_record)

        await self.db.commit()

        return {
            "success": True,
            "referrer": {
                "id": str(referrer.id),
                "nickname": referrer.nickname,
                "reward": referrer_reward,
            },
            "referee": {
                "id": str(new_user.id),
                "reward": referee_reward,
            },
        }

    async def get_referral_stats(self, user_id: UUID) -> dict:
        """유저의 추천 통계 조회"""
        user = await self.db.get(User, str(user_id))
        if not user:
            raise ReferralError("USER_NOT_FOUND", "유저를 찾을 수 없습니다")

        # 추천 코드 (없으면 생성)
        referral_code = await self.get_or_create_referral_code(user_id)

        # 내가 추천한 유저 수
        result = await self.db.execute(
            select(func.count(User.id))
            .where(User.referred_by_user_id == str(user_id))
        )
        total_referrals = result.scalar() or 0

        # 추천 보상 총액
        result = await self.db.execute(
            select(func.coalesce(func.sum(ReferralReward.reward_amount), 0))
            .where(ReferralReward.user_id == str(user_id))
            .where(ReferralReward.reward_type == "referrer")
        )
        total_rewards = result.scalar() or 0

        # 최근 추천 목록
        result = await self.db.execute(
            select(User)
            .where(User.referred_by_user_id == str(user_id))
            .order_by(User.created_at.desc())
            .limit(10)
        )
        recent_referrals = result.scalars().all()

        return {
            "referral_code": referral_code,
            "total_referrals": total_referrals,
            "total_rewards": total_rewards,
            "referrer_reward": REFERRAL_REWARDS["referrer"],
            "referee_reward": REFERRAL_REWARDS["referee"],
            "recent_referrals": [
                {
                    "nickname": u.nickname,
                    "joined_at": u.created_at.isoformat() if u.created_at else None,
                }
                for u in recent_referrals
            ],
        }
