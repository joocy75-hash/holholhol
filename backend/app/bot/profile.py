"""Bot profile generator.

Generates realistic bot profiles including nicknames and behavioral parameters.
"""

import random
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Literal

from app.config import get_settings


# Nickname pools for variety
KOREAN_NICKNAMES = [
    # 포커 관련
    "포커왕", "럭키스타", "에이스킹", "올인맨", "블러퍼",
    "레이즈마스터", "콜러킹", "폴드맨", "리버신", "플롭프로",
    # 일반적인
    "하늘별", "바다물결", "산들바람", "달빛소나타", "햇살",
    "구름타기", "무지개", "은하수", "별똥별", "오로라",
    # 게임 스타일
    "공격수", "수비수", "신중파", "도박사", "계산기",
    "직감러", "데이터맨", "확률왕", "심리전", "포커페이스",
    # 동물
    "호랑이", "독수리", "상어", "늑대", "여우",
    # 숫자 조합용
    "럭키", "프로", "마스터", "킹", "에이스",
]

ENGLISH_NICKNAMES = [
    # Poker related
    "PokerKing", "LuckyAce", "AllInPro", "Bluffer", "RaiseKing",
    "CallMaster", "FoldExpert", "RiverRat", "FlopHero", "NutHunter",
    # General
    "StarLight", "MoonRise", "SunShine", "RainBow", "Thunder",
    "Galaxy", "Phoenix", "Dragon", "Shadow", "Ghost",
    # Style
    "Aggressive", "Passive", "Tight", "Loose", "Balanced",
    "Calculator", "Reader", "Grinder", "Shark", "Fish",
    # Short
    "Ace", "King", "Queen", "Jack", "Ten",
    "Pro", "Noob", "Guru", "Boss", "Chief",
]

MIXED_PREFIXES = [
    # Korean first names
    "김", "이", "박", "최", "정", "강", "조", "윤", "장", "임",
    "한", "오", "서", "신", "권", "황", "안", "송", "유", "홍",
]

MIXED_SUFFIXES_EN = [
    "poker", "ace", "king", "pro", "star", "luck", "win",
    "bet", "call", "raise", "all", "chip", "card", "hand",
]


StrategyType = Literal[
    "tight_aggressive",
    "loose_aggressive",
    "tight_passive",
    "loose_passive",
    "balanced",
]

# Strategy distribution for bot assignment
STRATEGY_DISTRIBUTION: list[tuple[StrategyType, float]] = [
    ("tight_aggressive", 0.25),   # TAG: 25%
    ("loose_aggressive", 0.20),   # LAG: 20%
    ("tight_passive", 0.20),      # Tight-Passive: 20%
    ("loose_passive", 0.15),      # Loose-Passive: 15%
    ("balanced", 0.20),           # Balanced: 20%
]


@dataclass
class BotProfile:
    """Bot profile with nickname and behavioral parameters."""

    bot_id: str
    nickname: str
    strategy: StrategyType

    # Session parameters
    session_duration: timedelta
    rest_duration: timedelta

    # Behavioral parameters
    vpip: float  # Voluntarily Put money In Pot %
    pfr: float   # Pre-Flop Raise %
    aggression_factor: float  # Bet+Raise / Call ratio

    # Personality traits
    rebuy_tendency: float  # How likely to rebuy when low
    leave_on_win_tendency: float  # How likely to leave after big win
    tilt_factor: float  # How much losses affect play (higher = more tilt)

    @property
    def user_id(self) -> str:
        """User ID for the bot (livebot_ prefix)."""
        return f"livebot_{self.bot_id}"


def generate_nickname() -> str:
    """Generate a random nickname without numbers.

    Creates varied nicknames in different styles:
    - Pure Korean (e.g., "포커왕")
    - Pure English (e.g., "PokerKing")
    - Mixed (e.g., "김poker", "Lucky민수", "에이스_Kim")
    """
    style = random.choices(
        ["korean", "english", "mixed"],
        weights=[0.4, 0.3, 0.3],
        k=1,
    )[0]

    if style == "korean":
        nickname = random.choice(KOREAN_NICKNAMES)

    elif style == "english":
        nickname = random.choice(ENGLISH_NICKNAMES)

    else:  # mixed
        mix_type = random.choice(["kr_en", "en_kr", "underscore"])
        if mix_type == "kr_en":
            # Korean prefix + English suffix (e.g., "김poker")
            nickname = random.choice(MIXED_PREFIXES) + random.choice(MIXED_SUFFIXES_EN)
        elif mix_type == "en_kr":
            # English prefix + Korean (e.g., "Lucky민수")
            prefix = random.choice(["Lucky", "Pro", "Ace", "King", "Star"])
            suffix = random.choice(["민수", "영희", "철수", "지영", "준호", "수진"])
            nickname = prefix + suffix
        else:
            # Underscore style (e.g., "에이스_Kim")
            nickname = random.choice(KOREAN_NICKNAMES) + "_" + random.choice(["Kim", "Lee", "Park", "Choi"])

    return nickname[:15]  # Limit to 15 characters


def select_strategy() -> StrategyType:
    """Select a strategy based on distribution weights."""
    strategies, weights = zip(*STRATEGY_DISTRIBUTION)
    return random.choices(strategies, weights=weights, k=1)[0]


def get_strategy_parameters(strategy: StrategyType) -> dict:
    """Get behavioral parameters for a strategy.

    Returns:
        dict with vpip, pfr, and aggression_factor
    """
    params = {
        "tight_aggressive": {
            "vpip": (0.20, 0.25),  # Range for randomization
            "pfr": (0.16, 0.20),
            "aggression_factor": (2.5, 3.5),
        },
        "loose_aggressive": {
            "vpip": (0.30, 0.40),
            "pfr": (0.25, 0.32),
            "aggression_factor": (3.0, 4.5),
        },
        "tight_passive": {
            "vpip": (0.15, 0.20),
            "pfr": (0.06, 0.10),
            "aggression_factor": (0.8, 1.5),
        },
        "loose_passive": {
            "vpip": (0.35, 0.45),
            "pfr": (0.10, 0.15),
            "aggression_factor": (0.5, 1.2),
        },
        "balanced": {
            "vpip": (0.25, 0.30),
            "pfr": (0.18, 0.22),
            "aggression_factor": (1.5, 2.5),
        },
    }

    p = params[strategy]
    return {
        "vpip": random.uniform(*p["vpip"]),
        "pfr": random.uniform(*p["pfr"]),
        "aggression_factor": random.uniform(*p["aggression_factor"]),
    }


def create_bot_profile(bot_id: str) -> BotProfile:
    """Create a new bot profile with random characteristics.

    Args:
        bot_id: Unique identifier for the bot

    Returns:
        BotProfile with all behavioral parameters
    """
    settings = get_settings()

    # Generate nickname and strategy
    nickname = generate_nickname()
    strategy = select_strategy()

    # Get strategy parameters
    params = get_strategy_parameters(strategy)

    # Session duration (with some randomness)
    session_minutes = random.randint(
        settings.livebot_session_min_minutes,
        settings.livebot_session_max_minutes,
    )
    session_duration = timedelta(minutes=session_minutes)

    # Rest duration
    rest_minutes = random.randint(
        settings.livebot_rest_min_minutes,
        settings.livebot_rest_max_minutes,
    )
    rest_duration = timedelta(minutes=rest_minutes)

    # Personality traits (add some individual variation)
    rebuy_tendency = settings.livebot_rebuy_chance + random.uniform(-0.15, 0.15)
    rebuy_tendency = max(0.3, min(0.9, rebuy_tendency))  # Clamp to 0.3-0.9

    leave_on_win_tendency = settings.livebot_leave_after_big_win_chance + random.uniform(-0.05, 0.10)
    leave_on_win_tendency = max(0.05, min(0.30, leave_on_win_tendency))  # Clamp to 0.05-0.30

    tilt_factor = random.uniform(0.0, 1.0)  # 0 = no tilt, 1 = high tilt

    return BotProfile(
        bot_id=bot_id,
        nickname=nickname,
        strategy=strategy,
        session_duration=session_duration,
        rest_duration=rest_duration,
        vpip=params["vpip"],
        pfr=params["pfr"],
        aggression_factor=params["aggression_factor"],
        rebuy_tendency=rebuy_tendency,
        leave_on_win_tendency=leave_on_win_tendency,
        tilt_factor=tilt_factor,
    )
