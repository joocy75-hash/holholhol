"""
봇용 핸드 강도 평가기
텍사스 홀덤 핸드 강도를 평가하여 봇 결정에 사용
"""

from typing import Optional
from collections import Counter
from dataclasses import dataclass
from enum import IntEnum


# 랭크 값 매핑 (2=2, ..., A=14)
RANK_VALUES = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
    "7": 7, "8": 8, "9": 9, "T": 10, "10": 10,
    "J": 11, "Q": 12, "K": 13, "A": 14,
}


class HandRank(IntEnum):
    """족보 랭크 (높을수록 강함)"""
    HIGH_CARD = 1
    ONE_PAIR = 2
    TWO_PAIR = 3
    THREE_OF_A_KIND = 4
    STRAIGHT = 5
    FLUSH = 6
    FULL_HOUSE = 7
    FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9
    ROYAL_FLUSH = 10


@dataclass
class HandStrength:
    """핸드 강도 결과"""
    rank: HandRank
    strength: float  # 0.0 ~ 1.0 (정규화된 강도)
    has_flush_draw: bool = False
    has_straight_draw: bool = False
    description: str = ""


def parse_card(card_str: str) -> tuple[str, str]:
    """카드 문자열 파싱 ("As" -> ("A", "s"))"""
    if len(card_str) == 2:
        return card_str[0].upper(), card_str[1].lower()
    elif len(card_str) == 3:  # "10s" 형식
        return "T", card_str[2].lower()
    return card_str[0].upper(), card_str[-1].lower()


def get_rank_value(rank: str) -> int:
    """랭크의 숫자 값 반환"""
    return RANK_VALUES.get(rank.upper(), 0)


# ============================================
# 프리플롭 핸드 강도 평가
# ============================================

# 프리플롭 핸드 티어 (1=최강, 8=최약)
PREFLOP_TIERS = {
    # 티어 1: 프리미엄 핸드
    ("A", "A"): 1, ("K", "K"): 1, ("Q", "Q"): 1, ("A", "K", "s"): 1,
    # 티어 2: 강한 핸드
    ("J", "J"): 2, ("A", "K", "o"): 2, ("A", "Q", "s"): 2, ("K", "Q", "s"): 2,
    # 티어 3: 좋은 핸드
    ("T", "T"): 3, ("A", "Q", "o"): 3, ("A", "J", "s"): 3, ("K", "J", "s"): 3,
    ("Q", "J", "s"): 3, ("A", "T", "s"): 3,
    # 티어 4: 플레이 가능
    ("9", "9"): 4, ("8", "8"): 4, ("A", "J", "o"): 4, ("K", "Q", "o"): 4,
    ("K", "T", "s"): 4, ("Q", "T", "s"): 4, ("J", "T", "s"): 4, ("A", "9", "s"): 4,
    # 티어 5: 포지션 의존
    ("7", "7"): 5, ("6", "6"): 5, ("5", "5"): 5, ("K", "J", "o"): 5,
    ("Q", "J", "o"): 5, ("J", "9", "s"): 5, ("T", "9", "s"): 5, ("9", "8", "s"): 5,
    # 티어 6: 스페큘레이티브
    ("4", "4"): 6, ("3", "3"): 6, ("2", "2"): 6, ("A", "x", "s"): 6,
    ("8", "7", "s"): 6, ("7", "6", "s"): 6, ("6", "5", "s"): 6, ("5", "4", "s"): 6,
}


def evaluate_preflop_strength(hole_cards: list[str]) -> float:
    """
    프리플롭 핸드 강도 평가 (0.0 ~ 1.0)

    Args:
        hole_cards: 홀카드 2장 ["As", "Kh"]

    Returns:
        0.0 (최약) ~ 1.0 (최강)
    """
    if not hole_cards or len(hole_cards) != 2:
        return 0.3  # 기본값

    r1, s1 = parse_card(hole_cards[0])
    r2, s2 = parse_card(hole_cards[1])

    suited = s1 == s2
    v1, v2 = get_rank_value(r1), get_rank_value(r2)

    # 높은 카드가 먼저 오도록 정렬
    if v1 < v2:
        r1, r2 = r2, r1
        v1, v2 = v2, v1

    # 포켓 페어
    if r1 == r2:
        # AA=1.0, KK=0.95, ..., 22=0.5
        return 0.5 + (v1 - 2) * 0.042

    # 프리미엄 핸드 체크
    key_suited = (r1, r2, "s") if suited else (r1, r2, "o")
    key_pair = (r1, r2)

    # 직접 매핑된 핸드 체크
    tier = PREFLOP_TIERS.get(key_suited) or PREFLOP_TIERS.get(key_pair)

    if tier:
        # 티어 1=0.95, 티어 6=0.45
        return 1.0 - (tier - 1) * 0.1

    # 수딧 Ax
    if r1 == "A" and suited:
        return 0.55

    # 커넥터 (연속 카드)
    gap = v1 - v2
    if gap == 1:  # 커넥터
        base = 0.35 + (v1 / 14) * 0.15
        return base + (0.1 if suited else 0)
    elif gap == 2:  # 1갭
        base = 0.3 + (v1 / 14) * 0.1
        return base + (0.08 if suited else 0)

    # 기타 핸드
    high_card_bonus = (v1 + v2) / 28 * 0.2
    suited_bonus = 0.05 if suited else 0

    return 0.2 + high_card_bonus + suited_bonus


# ============================================
# 포스트플롭 핸드 평가
# ============================================

def evaluate_postflop_strength(
    hole_cards: list[str],
    community_cards: list[str]
) -> HandStrength:
    """
    포스트플롭 핸드 강도 평가

    Args:
        hole_cards: 홀카드 2장
        community_cards: 커뮤니티 카드 3~5장

    Returns:
        HandStrength 객체
    """
    if not hole_cards or not community_cards:
        return HandStrength(
            rank=HandRank.HIGH_CARD,
            strength=0.2,
            description="No cards"
        )

    all_cards = hole_cards + community_cards
    parsed = [parse_card(c) for c in all_cards]

    # 랭크와 슈트 분리
    ranks = [p[0] for p in parsed]
    suits = [p[1] for p in parsed]
    values = [get_rank_value(r) for r in ranks]

    # 랭크별 카운트
    rank_counts = Counter(ranks)
    suit_counts = Counter(suits)

    # 드로우 체크
    has_flush_draw = max(suit_counts.values()) == 4
    has_straight_draw = _check_straight_draw(values)

    # 플러시 체크
    flush_suit = None
    for suit, count in suit_counts.items():
        if count >= 5:
            flush_suit = suit
            break

    # 스트레이트 체크
    straight_high = _find_straight(values)

    # 스트레이트 플러시 체크
    if flush_suit and straight_high:
        flush_values = [v for (r, s), v in zip(parsed, values) if s == flush_suit]
        sf_high = _find_straight(flush_values)
        if sf_high:
            if sf_high == 14:  # 로얄 플러시
                return HandStrength(
                    rank=HandRank.ROYAL_FLUSH,
                    strength=1.0,
                    description="로얄 플러시"
                )
            return HandStrength(
                rank=HandRank.STRAIGHT_FLUSH,
                strength=0.98,
                description=f"스트레이트 플러시 {sf_high} 하이"
            )

    # 포카드 체크
    quads = [r for r, c in rank_counts.items() if c >= 4]
    if quads:
        return HandStrength(
            rank=HandRank.FOUR_OF_A_KIND,
            strength=0.95 + get_rank_value(quads[0]) / 140,
            description=f"{quads[0]} 포카드"
        )

    # 트리플 및 페어 체크
    trips = [r for r, c in rank_counts.items() if c >= 3]
    pairs = [r for r, c in rank_counts.items() if c == 2]

    # 풀하우스 체크
    if trips and pairs:
        return HandStrength(
            rank=HandRank.FULL_HOUSE,
            strength=0.90 + get_rank_value(trips[0]) / 140,
            description=f"{trips[0]} 풀하우스"
        )
    if len(trips) >= 2:  # 트리플 2개 -> 풀하우스
        sorted_trips = sorted(trips, key=get_rank_value, reverse=True)
        return HandStrength(
            rank=HandRank.FULL_HOUSE,
            strength=0.90 + get_rank_value(sorted_trips[0]) / 140,
            description=f"{sorted_trips[0]} 풀하우스"
        )

    # 플러시 체크
    if flush_suit:
        flush_values = sorted(
            [v for (r, s), v in zip(parsed, values) if s == flush_suit],
            reverse=True
        )
        return HandStrength(
            rank=HandRank.FLUSH,
            strength=0.82 + flush_values[0] / 140,
            has_flush_draw=False,
            description=f"플러시 {flush_values[0]} 하이"
        )

    # 스트레이트 체크
    if straight_high:
        return HandStrength(
            rank=HandRank.STRAIGHT,
            strength=0.75 + straight_high / 140,
            has_flush_draw=has_flush_draw,
            has_straight_draw=False,
            description=f"스트레이트 {straight_high} 하이"
        )

    # 트리플 체크
    if trips:
        return HandStrength(
            rank=HandRank.THREE_OF_A_KIND,
            strength=0.65 + get_rank_value(trips[0]) / 140,
            has_flush_draw=has_flush_draw,
            has_straight_draw=has_straight_draw,
            description=f"{trips[0]} 트리플"
        )

    # 투페어 체크
    if len(pairs) >= 2:
        sorted_pairs = sorted(pairs, key=get_rank_value, reverse=True)
        strength = 0.50 + (get_rank_value(sorted_pairs[0]) + get_rank_value(sorted_pairs[1])) / 280
        return HandStrength(
            rank=HandRank.TWO_PAIR,
            strength=strength,
            has_flush_draw=has_flush_draw,
            has_straight_draw=has_straight_draw,
            description=f"{sorted_pairs[0]}-{sorted_pairs[1]} 투페어"
        )

    # 원페어 체크
    if pairs:
        pair_value = get_rank_value(pairs[0])
        # 탑 페어인지 확인 (커뮤니티 카드의 가장 높은 카드와 페어)
        community_values = [get_rank_value(parse_card(c)[0]) for c in community_cards]
        is_top_pair = pair_value >= max(community_values) if community_values else False

        base_strength = 0.35 + pair_value / 140
        if is_top_pair:
            base_strength += 0.1

        return HandStrength(
            rank=HandRank.ONE_PAIR,
            strength=base_strength,
            has_flush_draw=has_flush_draw,
            has_straight_draw=has_straight_draw,
            description=f"{pairs[0]} 원페어" + (" (탑 페어)" if is_top_pair else "")
        )

    # 하이카드
    sorted_values = sorted(values, reverse=True)
    return HandStrength(
        rank=HandRank.HIGH_CARD,
        strength=0.15 + sorted_values[0] / 140,
        has_flush_draw=has_flush_draw,
        has_straight_draw=has_straight_draw,
        description=f"{sorted_values[0]} 하이카드"
    )


def _find_straight(values: list[int]) -> Optional[int]:
    """스트레이트 찾기, 하이 카드 값 반환"""
    unique = sorted(set(values), reverse=True)

    # A-2-3-4-5 (휠) 처리를 위해 A를 1로도 추가
    if 14 in unique:
        unique.append(1)

    for i in range(len(unique) - 4):
        if unique[i] - unique[i + 4] == 4:
            return unique[i]

    return None


def _check_straight_draw(values: list[int]) -> bool:
    """오픈엔드 또는 거셧 스트레이트 드로우 체크"""
    unique = sorted(set(values))

    if 14 in unique:
        unique = [1] + unique

    # 4장 연속 (오픈엔드)
    for i in range(len(unique) - 3):
        if unique[i + 3] - unique[i] == 3:
            return True

    # 4장 중 1갭 (거셧)
    for i in range(len(unique) - 3):
        if unique[i + 3] - unique[i] == 4:
            # 중간에 정확히 1개 빠진 경우
            gaps = sum(1 for j in range(3) if unique[i + j + 1] - unique[i + j] > 1)
            if gaps == 1:
                return True

    return False


# ============================================
# 봇 결정용 통합 함수
# ============================================

def evaluate_hand_for_bot(
    hole_cards: list[str],
    community_cards: list[str],
    pot: int = 0,
    to_call: int = 0,
) -> dict:
    """
    봇 결정을 위한 핸드 평가

    Returns:
        {
            "strength": float (0.0~1.0),
            "rank": HandRank,
            "phase": "preflop" | "postflop",
            "has_draw": bool,
            "pot_odds": float,
            "recommendation": "fold" | "check" | "call" | "bet" | "raise"
        }
    """
    phase = "preflop" if not community_cards else "postflop"

    if phase == "preflop":
        strength = evaluate_preflop_strength(hole_cards)
        hand_rank = HandRank.HIGH_CARD
        has_draw = False
        description = "프리플롭"
    else:
        result = evaluate_postflop_strength(hole_cards, community_cards)
        strength = result.strength
        hand_rank = result.rank
        has_draw = result.has_flush_draw or result.has_straight_draw
        description = result.description

    # 팟 오즈 계산
    pot_odds = to_call / (pot + to_call) if (pot + to_call) > 0 else 0

    # 추천 액션 결정
    recommendation = _get_recommendation(strength, pot_odds, has_draw, to_call)

    return {
        "strength": strength,
        "rank": hand_rank,
        "phase": phase,
        "has_draw": has_draw,
        "pot_odds": pot_odds,
        "recommendation": recommendation,
        "description": description,
    }


def _get_recommendation(
    strength: float,
    pot_odds: float,
    has_draw: bool,
    to_call: int,
) -> str:
    """강도에 따른 추천 액션"""

    # 매우 강한 핸드 (0.75+): 레이즈/베팅
    if strength >= 0.75:
        return "raise"

    # 강한 핸드 (0.55+): 베팅/콜
    if strength >= 0.55:
        if to_call == 0:
            return "bet"
        return "call"

    # 중간 핸드 (0.40+): 체크/콜 (팟오즈 고려)
    if strength >= 0.40:
        if to_call == 0:
            return "check"
        # 드로우가 있으면 콜 확률 증가
        call_threshold = pot_odds + (0.15 if has_draw else 0)
        if strength >= call_threshold:
            return "call"
        return "fold"

    # 약한 핸드 + 드로우: 체크/콜 (좋은 팟오즈에서만)
    if has_draw and strength >= 0.30:
        if to_call == 0:
            return "check"
        if pot_odds <= 0.25:  # 4:1 이상의 팟오즈
            return "call"
        return "fold"

    # 매우 약한 핸드: 체크/폴드
    if to_call == 0:
        return "check"
    return "fold"
