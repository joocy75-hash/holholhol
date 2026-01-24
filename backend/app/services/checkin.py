"""출석체크 서비스"""

from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.checkin import DailyCheckin, CHECKIN_REWARDS
from app.models.user import User


# KST 타임존 (UTC+9)
KST = timezone(timedelta(hours=9))


class CheckinError(Exception):
    """출석체크 에러"""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class CheckinService:
    """출석체크 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _get_kst_today(self) -> date:
        """현재 KST 날짜 반환"""
        return datetime.now(KST).date()

    async def get_user_streak(self, user_id: UUID) -> int:
        """유저의 현재 연속 출석 일수 계산"""
        today = self._get_kst_today()

        # 최근 출석 기록 조회 (최근 31일)
        result = await self.db.execute(
            select(DailyCheckin.checkin_date)
            .where(DailyCheckin.user_id == user_id)
            .where(DailyCheckin.checkin_date >= today - timedelta(days=31))
            .order_by(DailyCheckin.checkin_date.desc())
        )
        dates = [row[0] for row in result.fetchall()]

        if not dates:
            return 0

        # 연속 출석 계산
        streak = 0
        check_date = today

        # 오늘 출석했으면 오늘부터, 아니면 어제부터 계산
        if dates[0] != today:
            check_date = today - timedelta(days=1)

        for checkin_date in dates:
            if checkin_date == check_date:
                streak += 1
                check_date -= timedelta(days=1)
            elif checkin_date < check_date:
                break

        return streak

    async def can_checkin_today(self, user_id: UUID) -> bool:
        """오늘 출석체크 가능 여부"""
        today = self._get_kst_today()

        result = await self.db.execute(
            select(DailyCheckin)
            .where(DailyCheckin.user_id == user_id)
            .where(DailyCheckin.checkin_date == today)
        )
        return result.scalar_one_or_none() is None

    async def checkin(self, user_id: UUID) -> dict:
        """출석체크 수행"""
        today = self._get_kst_today()
        now = datetime.now(KST)

        # 이미 출석했는지 확인
        if not await self.can_checkin_today(user_id):
            raise CheckinError("ALREADY_CHECKED_IN", "오늘은 이미 출석체크를 완료했습니다")

        # 유저 조회
        user = await self.db.get(User, str(user_id))
        if not user:
            raise CheckinError("USER_NOT_FOUND", "유저를 찾을 수 없습니다")

        # 연속 출석 일수 계산
        current_streak = await self.get_user_streak(user_id)
        new_streak = current_streak + 1

        # 보상 계산
        reward = CHECKIN_REWARDS["daily"]
        reward_type = "daily"
        bonus_rewards = []

        # 연속 출석 보너스
        if new_streak == 7:
            bonus = CHECKIN_REWARDS["streak_7"]
            reward += bonus
            reward_type = "streak_7"
            bonus_rewards.append({"type": "7일 연속 출석", "amount": bonus})
        elif new_streak == 14:
            bonus = CHECKIN_REWARDS["streak_14"]
            reward += bonus
            reward_type = "streak_14"
            bonus_rewards.append({"type": "14일 연속 출석", "amount": bonus})
        elif new_streak == 30:
            bonus = CHECKIN_REWARDS["streak_30"]
            reward += bonus
            reward_type = "streak_30"
            bonus_rewards.append({"type": "30일 연속 출석", "amount": bonus})

        # 출석 기록 생성
        checkin = DailyCheckin(
            user_id=user_id,
            checkin_date=today,
            streak_days=new_streak,
            reward_amount=reward,
            reward_type=reward_type,
            checked_at=now,
        )
        self.db.add(checkin)

        # 보상 지급 (KRW 잔액에 추가)
        user.krw_balance += reward

        await self.db.commit()
        await self.db.refresh(checkin)

        return {
            "success": True,
            "checkin_date": today.isoformat(),
            "streak_days": new_streak,
            "reward_amount": reward,
            "reward_type": reward_type,
            "bonus_rewards": bonus_rewards,
            "new_balance": user.krw_balance,
        }

    async def get_checkin_status(self, user_id: UUID) -> dict:
        """유저의 출석체크 상태 조회"""
        today = self._get_kst_today()

        # 오늘 출석 여부
        can_checkin = await self.can_checkin_today(user_id)

        # 연속 출석 일수
        streak = await self.get_user_streak(user_id)

        # 이번 달 출석 기록
        first_day = today.replace(day=1)
        result = await self.db.execute(
            select(DailyCheckin)
            .where(DailyCheckin.user_id == user_id)
            .where(DailyCheckin.checkin_date >= first_day)
            .order_by(DailyCheckin.checkin_date)
        )
        monthly_checkins = result.scalars().all()

        # 다음 보너스까지 남은 일수
        next_bonus = None
        if streak < 7:
            next_bonus = {"days_remaining": 7 - streak, "bonus": CHECKIN_REWARDS["streak_7"]}
        elif streak < 14:
            next_bonus = {"days_remaining": 14 - streak, "bonus": CHECKIN_REWARDS["streak_14"]}
        elif streak < 30:
            next_bonus = {"days_remaining": 30 - streak, "bonus": CHECKIN_REWARDS["streak_30"]}

        return {
            "can_checkin": can_checkin,
            "streak_days": streak,
            "monthly_checkins": [
                {
                    "date": c.checkin_date.isoformat(),
                    "reward": c.reward_amount,
                    "reward_type": c.reward_type,
                }
                for c in monthly_checkins
            ],
            "next_bonus": next_bonus,
            "daily_reward": CHECKIN_REWARDS["daily"],
        }

    async def get_checkin_history(
        self,
        user_id: UUID,
        limit: int = 30,
    ) -> list[dict]:
        """출석체크 히스토리 조회"""
        result = await self.db.execute(
            select(DailyCheckin)
            .where(DailyCheckin.user_id == user_id)
            .order_by(DailyCheckin.checkin_date.desc())
            .limit(limit)
        )
        checkins = result.scalars().all()

        return [
            {
                "date": c.checkin_date.isoformat(),
                "streak_days": c.streak_days,
                "reward_amount": c.reward_amount,
                "reward_type": c.reward_type,
                "checked_at": c.checked_at.isoformat(),
            }
            for c in checkins
        ]
