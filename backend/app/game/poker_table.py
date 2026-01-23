"""Memory-based PokerTable implementation.

Based on poker project's poker_table.py with modifications for holdem project.
Key difference: State is managed in memory, no DB serialization.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
from datetime import datetime, timezone, timedelta
import asyncio
import logging

from pokerkit import Automation, NoLimitTexasHoldem, State

from app.game.types import (
    ActionResult,
    AvailableActions,
    HandResult,
    HandStartResult,
    PlayerState,
    TableState,
)
from app.utils.errors import (
    GameError,
    InvalidActionError,
    NotYourTurnError,
    NoActiveHandError,
    InvalidAmountError,
)

logger = logging.getLogger(__name__)


class GamePhase(Enum):
    """Game phase within a hand."""
    WAITING = "waiting"
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"


# 테이블 기준 시계방향 좌석 순서 (9인 테이블)
# 시각적 배치 (플레이어 시점에서 화면):
#       7          8       (top row)
#    5                6    (upper row)
#    3                4    (mid row)
#    1                2    (lower row)
#          0               (bottom/player)
#
# 포커 시계방향 = 딜러 왼쪽으로 진행 (테이블 위에서 내려다볼 때 시계방향)
# 0에서 시작해서 왼쪽으로: 0 → 1 → 3 → 5 → 7 → 8 → 6 → 4 → 2 → 0
CLOCKWISE_SEAT_ORDER_9 = [0, 1, 3, 5, 7, 8, 6, 4, 2]

# 6인 테이블 시계방향 좌석 순서
# 시각적 배치:
#        5         (top center)
#    3       4     (upper row)
#    1       2     (lower row)
#        0         (bottom/player)
#
# 0에서 시작해서 왼쪽으로: 0 → 1 → 3 → 5 → 4 → 2 → 0
CLOCKWISE_SEAT_ORDER_6 = [0, 1, 3, 5, 4, 2]

# 하위호환용 별칭 (기존 코드 지원)
CLOCKWISE_SEAT_ORDER = CLOCKWISE_SEAT_ORDER_9
SEAT_TO_CLOCKWISE_INDEX = {seat: idx for idx, seat in enumerate(CLOCKWISE_SEAT_ORDER)}


def get_clockwise_order(max_players: int) -> list[int]:
    """Get clockwise seat order for table size."""
    return CLOCKWISE_SEAT_ORDER_6 if max_players == 6 else CLOCKWISE_SEAT_ORDER_9


def get_seat_to_clockwise_index(max_players: int) -> dict[int, int]:
    """Get seat to clockwise index mapping for table size."""
    order = get_clockwise_order(max_players)
    return {seat: idx for idx, seat in enumerate(order)}


def card_to_str(card) -> str:
    """Convert PokerKit card to string like 'Ah', 'Ks'."""
    return repr(card)


@dataclass
class Player:
    """Player at a poker table."""
    user_id: str
    username: str
    seat: int
    stack: int
    hole_cards: Optional[List[str]] = None
    current_bet: int = 0
    status: str = "active"  # active, folded, all_in, sitting_out
    total_bet_this_hand: int = 0
    is_bot: bool = False
    is_cards_revealed: bool = False  # 카드 오픈 상태 (클라이언트에서 카드를 열었는지)


@dataclass
class PokerTable:
    """Texas Hold'em poker table with memory-based state management.

    This class wraps PokerKit and manages the game state entirely in memory.
    No serialization to DB is needed during gameplay.
    """
    room_id: str
    name: str
    small_blind: int
    big_blind: int
    min_buy_in: int
    max_buy_in: int
    max_players: int = 9

    players: Dict[int, Optional[Player]] = field(default_factory=dict)
    dealer_seat: int = -1
    hand_number: int = 0
    phase: GamePhase = GamePhase.WAITING
    pot: int = 0
    community_cards: List[str] = field(default_factory=list)
    current_player_seat: Optional[int] = None
    current_bet: int = 0  # Current bet to call

    _state: Optional[State] = field(default=None, repr=False)
    _seat_to_index: Dict[int, int] = field(default_factory=dict)
    _index_to_seat: Dict[int, int] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # Hand history tracking
    _hand_start_time: Optional[datetime] = field(default=None, repr=False)
    _hand_actions: List[Dict] = field(default_factory=list)
    _hand_starting_stacks: Dict[int, int] = field(default_factory=dict)
    _saw_flop: bool = field(default=False)
    _is_preflop_first_turn: bool = field(default=True)  # UTG 첫 턴 여부 (20초 부여용)

    # Turn timer tracking
    _turn_started_at: Optional[datetime] = field(default=None, repr=False)

    # Under-raise tracking (WSOP 규칙)
    # 마지막 풀 레이즈 금액 (레이즈 차액, 예: 100→300이면 200)
    _last_full_raise: int = field(default=0)
    # 마지막 풀 레이즈 이후 행동한 플레이어 (좌석 번호 집합)
    # 이 플레이어들은 언더 레이즈 발생 시 리레이즈 불가
    _players_acted_on_full_raise: set = field(default_factory=set)
    # 현재 언더 레이즈 상태인지 (마지막 레이즈가 언더 레이즈였는지)
    _is_under_raise_active: bool = field(default=False)

    def __post_init__(self):
        for i in range(self.max_players):
            if i not in self.players:
                self.players[i] = None

    def seat_player(self, seat: int, player: Player) -> bool:
        """Seat a player at the table."""
        if seat < 0 or seat >= self.max_players:
            return False
        if self.players[seat] is not None:
            return False
        if player.stack < self.min_buy_in or player.stack > self.max_buy_in:
            return False

        # Check if player is already seated at another seat
        for existing_seat, existing_player in self.players.items():
            if existing_player and existing_player.user_id == player.user_id:
                return False

        # 중간 입장: 기본값은 sitting_out (BB 대기)
        # 플레이어가 "바로 참여"를 선택하면 sit_in() 호출
        player.status = "sitting_out"

        self.players[seat] = player
        return True

    def remove_player(self, seat: int) -> Optional[Player]:
        """Remove a player from the table."""
        player = self.players.get(seat)
        self.players[seat] = None
        return player

    def sit_out(self, seat: int) -> bool:
        """Mark a player as sitting out.
        
        The player remains at the table but won't be dealt into new hands.
        If currently in a hand, they will auto-fold when their turn comes.
        
        Args:
            seat: The seat number of the player
            
        Returns:
            True if successful, False if player not found or already sitting out
        """
        player = self.players.get(seat)
        if player is None:
            return False
        if player.status == "sitting_out":
            return False
        
        # If in a hand and not folded, mark for auto-fold (handled by action handler)
        # For now, just mark as sitting_out
        player.status = "sitting_out"
        logger.info(f"Player {player.username} (seat {seat}) is now sitting out")
        return True

    def sit_in(self, seat: int) -> bool:
        """Mark a player as active again.
        
        The player will be dealt into the next hand.
        
        Args:
            seat: The seat number of the player
            
        Returns:
            True if successful, False if player not found or not sitting out
        """
        player = self.players.get(seat)
        if player is None:
            return False
        if player.status != "sitting_out":
            return False
        
        player.status = "active"
        logger.info(f"Player {player.username} (seat {seat}) is now active")
        return True

    def is_sitting_out(self, seat: int) -> bool:
        """Check if a player is sitting out.
        
        Args:
            seat: The seat number to check
            
        Returns:
            True if player is sitting out, False otherwise
        """
        player = self.players.get(seat)
        if player is None:
            return False
        return player.status == "sitting_out"

    def get_seated_players(self) -> List[Tuple[int, Player]]:
        """Get list of (seat, player) for seated players."""
        return [(seat, p) for seat, p in self.players.items()
                if p is not None and p.status != "sitting_out"]

    def get_all_seated_players(self) -> List[Tuple[int, Player]]:
        """Get list of (seat, player) for ALL seated players including sitting_out."""
        return [(seat, p) for seat, p in self.players.items() if p is not None]

    def get_all_seated_players_clockwise(self) -> List[Tuple[int, Player]]:
        """Get all seated players (including sitting_out) in clockwise order."""
        seated = self.get_all_seated_players()
        seat_to_idx = get_seat_to_clockwise_index(self.max_players)
        seated.sort(key=lambda x: seat_to_idx.get(x[0], x[0]))
        return seated

    def get_active_players(self) -> List[Player]:
        """Get players eligible to play (not sitting out)."""
        return [p for _, p in self.get_seated_players()]

    def get_seated_players_clockwise(self) -> List[Tuple[int, Player]]:
        """Get list of (seat, player) sorted in clockwise order around the table."""
        seated = self.get_seated_players()
        # 테이블 크기에 맞는 시계방향 순서로 정렬
        seat_to_idx = get_seat_to_clockwise_index(self.max_players)
        seated.sort(key=lambda x: seat_to_idx.get(x[0], x[0]))
        return seated

    def get_next_clockwise_seat(self, current_seat: int, occupied_seats: List[int]) -> int:
        """Get next occupied seat in clockwise order."""
        clockwise_order = get_clockwise_order(self.max_players)
        seat_to_idx = get_seat_to_clockwise_index(self.max_players)

        if current_seat not in occupied_seats:
            # current_seat이 점유되지 않은 경우, 첫 번째 점유된 좌석 반환
            for seat in clockwise_order:
                if seat in occupied_seats:
                    return seat
            return current_seat

        # current_seat의 시계방향 인덱스 찾기
        current_idx = seat_to_idx.get(current_seat, 0)

        # 다음 점유된 좌석 찾기 (시계방향으로)
        for i in range(1, len(clockwise_order)):
            next_idx = (current_idx + i) % len(clockwise_order)
            next_seat = clockwise_order[next_idx]
            if next_seat in occupied_seats:
                return next_seat

        return current_seat  # 본인만 있는 경우

    def get_players_in_hand(self) -> List[Player]:
        """Get players still in current hand."""
        return [p for p in self.get_active_players()
                if p.status in ("active", "all_in")]

    def can_start_hand(self) -> bool:
        """Check if a new hand can be started."""
        return len(self.get_active_players()) >= 2 and self.phase == GamePhase.WAITING

    def try_activate_bb_waiter_for_next_hand(self) -> List[int]:
        """다음 핸드 시작 전에 BB 위치 대기자를 활성화합니다.

        can_start_hand() 호출 전에 이 메서드를 호출하여, sitting_out 플레이어가
        BB 위치에 있다면 미리 활성화합니다. 이렇게 하면 active 플레이어가 1명뿐이어도
        BB 대기자를 활성화하여 게임을 시작할 수 있습니다.

        Returns:
            활성화된 좌석 번호 리스트
        """
        if self.phase != GamePhase.WAITING:
            return []

        # 모든 착석 플레이어 (sitting_out 포함)
        all_seated = self.get_all_seated_players_clockwise()
        all_seats = [s for s, _ in all_seated]

        if len(all_seats) < 2:
            return []

        # 다음 딜러 위치 계산 (active 플레이어 기준)
        active_seated = self.get_seated_players_clockwise()
        active_seats = [s for s, _ in active_seated]

        if not active_seats:
            # active 플레이어가 없으면, 모든 플레이어 중 첫 번째를 딜러로 가정
            next_dealer = all_seats[0]
        elif self.dealer_seat == -1 or self.dealer_seat not in active_seats:
            # 첫 핸드 또는 딜러가 활성 좌석에 없으면
            next_dealer = active_seats[0]
        else:
            # 시계방향으로 다음 활성 플레이어
            next_dealer = self.get_next_clockwise_seat(self.dealer_seat, active_seats)

        # BB 위치 계산 (모든 플레이어 기준, 다음 딜러 기준)
        if len(all_seats) == 2:
            # 헤즈업: 딜러가 아닌 쪽이 BB
            bb_seat = self.get_next_clockwise_seat(next_dealer, all_seats)
        else:
            # 3인+: 딜러 → SB → BB
            sb_seat = self.get_next_clockwise_seat(next_dealer, all_seats)
            bb_seat = self.get_next_clockwise_seat(sb_seat, all_seats)

        activated = []

        # BB 위치에 sitting_out 플레이어가 있으면 활성화
        player = self.players.get(bb_seat)
        if player and player.status == "sitting_out":
            player.status = "active"
            activated.append(bb_seat)
            logger.info(
                f"[PRE_HAND_ACTIVATE] BB 위치 도달 예정으로 자동 활성화: "
                f"seat={bb_seat}, user={player.username}, next_dealer={next_dealer}"
            )

        return activated

    def _activate_bb_waiters(self) -> List[int]:
        """BB 위치의 sitting_out 플레이어를 자동 활성화합니다.

        "BB 대기" 옵션을 선택한 플레이어가 BB 위치에 도달하면
        자동으로 active 상태로 전환하여 게임에 참여시킵니다.

        Returns:
            활성화된 좌석 번호 리스트
        """
        activated = []

        # 모든 플레이어 (sitting_out 포함) 시계방향 순서로 가져옴
        all_seated = self.get_all_seated_players_clockwise()
        all_seats = [s for s, _ in all_seated]

        if len(all_seats) < 2 or self.dealer_seat is None:
            return activated

        # BB 위치 계산 (모든 플레이어 기준)
        if len(all_seats) == 2:
            # 헤즈업: 딜러가 아닌 쪽이 BB
            bb_seat = self.get_next_clockwise_seat(self.dealer_seat, all_seats)
        else:
            # 3인+: 딜러 → SB → BB
            sb_seat = self.get_next_clockwise_seat(self.dealer_seat, all_seats)
            bb_seat = self.get_next_clockwise_seat(sb_seat, all_seats)

        # BB 위치에 sitting_out 플레이어가 있으면 활성화
        player = self.players.get(bb_seat)
        if player and player.status == "sitting_out":
            player.status = "active"
            activated.append(bb_seat)
            logger.info(
                f"[AUTO_SIT_IN] BB 위치 도달로 자동 활성화: "
                f"seat={bb_seat}, user={player.username}"
            )

        return activated

    def _is_heads_up(self) -> bool:
        """헤즈업(2인) 게임인지 확인합니다.

        Returns:
            정확히 2명의 active 플레이어가 있으면 True, 아니면 False
        """
        active_count = len(self.get_active_players())
        return active_count == 2

    def get_blind_seats(self) -> tuple[int | None, int | None]:
        """SB와 BB 좌석 번호를 반환합니다.

        Returns:
            (sb_seat, bb_seat) 튜플. 플레이어가 부족하면 (None, None).

        포커 규칙:
        - 헤즈업(2인): 딜러=SB, 상대=BB
        - 3인 이상: 딜러 시계방향 다음=SB, 그 다음=BB
        """
        seated = self.get_seated_players_clockwise()
        seats_in_order = [s for s, _ in seated]

        if len(seats_in_order) < 2 or self.dealer_seat not in seats_in_order:
            return None, None

        if self._is_heads_up():
            # 헤즈업: 딜러가 SB, 상대가 BB
            sb_seat = self.dealer_seat
            bb_seat = self.get_next_clockwise_seat(self.dealer_seat, seats_in_order)
        else:
            # 3명 이상: 딜러 다음이 SB, 그 다음이 BB
            sb_seat = self.get_next_clockwise_seat(self.dealer_seat, seats_in_order)
            bb_seat = self.get_next_clockwise_seat(sb_seat, seats_in_order)

        return sb_seat, bb_seat

    def start_new_hand(self) -> HandStartResult:
        """Start a new hand."""
        if not self.can_start_hand():
            return {"success": False, "error": "Need at least 2 players to start"}

        # 즉시 phase 변경 - 동시 시작 방지
        self.phase = GamePhase.PREFLOP

        # 먼저 딜러 이동 (플레이어 순서 결정 전에 필요)
        self._move_dealer()

        # BB 위치 대기자 자동 활성화 (get_seated_players_clockwise 전에 호출)
        auto_activated = self._activate_bb_waiters()

        # 시계방향 순서로 플레이어 정렬 (auto_activated된 플레이어 포함)
        seated = self.get_seated_players_clockwise()

        # PokerKit은 [SB, BB, ..., BTN] 순서를 기대함
        # 딜러(BTN)를 마지막으로 이동하여 SB부터 시작하는 순서로 재정렬
        if len(seated) >= 2:
            # 딜러 위치 찾기
            dealer_idx = None
            for i, (seat, _) in enumerate(seated):
                if seat == self.dealer_seat:
                    dealer_idx = i
                    break

            if dealer_idx is not None:
                # PokerKit 블라인드 할당 규칙:
                # - 헤즈업: Player 0=BB, Player 1=SB (SB가 먼저 액션)
                # - 3명+: Player 0=SB, Player 1=BB, ..., Player N-1=BTN

                if len(seated) == 2:
                    # 헤즈업: [상대(BB), 딜러(SB)] 순서로 전달
                    # 딜러=SB, 상대=BB (표준 헤즈업 규칙)
                    other_idx = 1 - dealer_idx
                    seated = [seated[other_idx], seated[dealer_idx]]
                else:
                    # 3명 이상: 딜러 다음(SB)부터 시작하여 딜러(BTN)로 끝남
                    # [SB, BB, UTG, ..., BTN]
                    seated = seated[dealer_idx + 1:] + seated[:dealer_idx + 1]

        # Initialize hand tracking
        self._hand_start_time = datetime.now(timezone.utc)
        self._hand_actions = []
        self._hand_starting_stacks = {seat: p.stack for seat, p in seated}
        self._saw_flop = False
        self._is_preflop_first_turn = True  # UTG 첫 턴에 20초 부여

        # P0-3: 칩 무결성 스냅샷 캡처
        try:
            from app.services.chip_integrity import get_chip_integrity_service
            chip_service = get_chip_integrity_service()
            chip_service.capture_hand_start(
                table_id=self.room_id,
                hand_number=self.hand_number + 1,  # 아직 증가 전
                player_stacks=self._hand_starting_stacks,
            )
        except Exception as e:
            logger.warning(f"[CHIP_INTEGRITY] 스냅샷 캡처 실패 (게임은 계속): {e}")

        # Build mapping between seat numbers and PokerKit player indices
        self._seat_to_index = {seat: idx for idx, (seat, _) in enumerate(seated)}
        self._index_to_seat = {idx: seat for seat, idx in self._seat_to_index.items()}

        stacks = [p.stack for _, p in seated]

        # Create PokerKit state
        self._state = NoLimitTexasHoldem.create_state(
            automations=(
                Automation.ANTE_POSTING,
                Automation.BET_COLLECTION,
                Automation.BLIND_OR_STRADDLE_POSTING,
                Automation.BOARD_DEALING,
                Automation.CARD_BURNING,
                Automation.HOLE_CARDS_SHOWING_OR_MUCKING,
                Automation.HAND_KILLING,
                Automation.CHIPS_PUSHING,
                Automation.CHIPS_PULLING,
            ),
            ante_trimming_status=True,
            raw_antes=0,
            raw_blinds_or_straddles=(self.small_blind, self.big_blind),
            min_bet=self.big_blind,
            raw_starting_stacks=stacks,
            player_count=len(seated),
        )

        self.hand_number += 1
        self.community_cards = []
        self.current_bet = self.big_blind

        # Initialize under-raise tracking
        # Preflop: BB가 첫 번째 "베팅"이므로 BB 금액이 초기 레이즈 기준
        self._last_full_raise = self.big_blind
        self._players_acted_on_full_raise = set()
        self._is_under_raise_active = False

        # Reset player states
        for _, player in seated:
            player.status = "active"
            player.current_bet = 0
            player.hole_cards = None
            player.total_bet_this_hand = 0
            player.is_cards_revealed = False

        # Deal hole cards
        self._deal_hole_cards()

        # Update phase and current player
        self._update_phase()
        self._update_current_player()
        self._update_pot()

        # Set initial blinds as current bets
        self._sync_bets_from_state()

        return {
            "success": True,
            "hand_number": self.hand_number,
            "dealer": self.dealer_seat,
            "auto_activated": auto_activated,  # BB 위치 도달로 자동 활성화된 좌석
        }

    def process_action(self, user_id: str, action: str, amount: int = 0) -> ActionResult:
        """Process a player action."""
        if not self._state or self.phase == GamePhase.WAITING:
            return {"success": False, "error": "No active hand"}

        # Find player
        player = None
        player_seat = None
        for seat, p in self.players.items():
            if p and p.user_id == user_id:
                player = p
                player_seat = seat
                break

        if not player:
            return {"success": False, "error": "Player not found"}

        if player_seat != self.current_player_seat:
            return {"success": False, "error": "Not your turn"}

        player_index = self._seat_to_index.get(player_seat)
        if player_index is None:
            return {"success": False, "error": "Player not in hand"}

        # Normalize action name
        action = action.lower()

        try:
            if action == "fold":
                # Check if fold is valid
                if not self._state.can_fold():
                    # 체크가 가능한 상황에서 fold 요청 → 에러 반환 (자동 변환하지 않음)
                    if self._state.can_check_or_call():
                        call_amount = self._state.checking_or_calling_amount or 0
                        if call_amount == 0:
                            return {"success": False, "error": "Cannot fold - you can check for free", "should_refresh": True}
                        else:
                            return {"success": False, "error": "Cannot fold", "should_refresh": True}
                    else:
                        return {"success": False, "error": "Cannot fold"}
                else:
                    self._state.fold()
                    player.status = "folded"

            elif action == "check":
                if not self._state.can_check_or_call():
                    return {"success": False, "error": "Cannot check"}
                call_amount = self._state.checking_or_calling_amount or 0
                if call_amount > 0:
                    return {"success": False, "error": "Cannot check, must call"}
                self._state.check_or_call()
                # 체크한 플레이어는 풀 레이즈에 대해 행동한 것으로 간주
                self._players_acted_on_full_raise.add(player_seat)

            elif action == "call":
                if not self._state.can_check_or_call():
                    return {"success": False, "error": "Cannot call"}
                call_amount = self._state.checking_or_calling_amount or 0
                self._state.check_or_call()
                # If call amount is 0, it's actually a check
                if call_amount == 0:
                    action = "check"
                amount = call_amount
                # 콜한 플레이어는 풀 레이즈에 대해 행동한 것으로 간주
                self._players_acted_on_full_raise.add(player_seat)

            elif action in ("bet", "raise"):
                if amount <= 0:
                    return {"success": False, "error": "Invalid amount"}
                # Validate amount is within allowed range
                min_raise = self._state.min_completion_betting_or_raising_to_amount
                max_raise = self._state.max_completion_betting_or_raising_to_amount
                if min_raise is not None and amount < min_raise:
                    return {"success": False, "error": f"최소 베팅/레이즈 금액은 {min_raise}입니다"}
                if max_raise is not None and amount > max_raise:
                    return {"success": False, "error": f"최대 베팅/레이즈 금액은 {max_raise}입니다 (스택 초과)"}
                if not self._state.can_complete_bet_or_raise_to(amount):
                    return {"success": False, "error": f"Cannot bet/raise to {amount}"}

                # 언더 레이즈 추적: 레이즈 금액 계산
                raise_amount = amount - self.current_bet
                if raise_amount >= self._last_full_raise:
                    # 풀 레이즈: 새로운 레이즈 기준 설정
                    self._last_full_raise = raise_amount
                    self._players_acted_on_full_raise = set()
                    self._is_under_raise_active = False
                else:
                    # 언더 레이즈: 이전에 행동한 플레이어들은 리레이즈 불가
                    self._is_under_raise_active = True
                    logger.info(f"[UNDER_RAISE] seat={player_seat}, raise={raise_amount}, min_full={self._last_full_raise}")

                self._state.complete_bet_or_raise_to(amount)

            elif action == "all_in":
                max_raise = self._state.max_completion_betting_or_raising_to_amount
                if max_raise is not None:
                    # 올인이 레이즈인 경우 - 언더 레이즈 체크
                    raise_amount = max_raise - self.current_bet
                    if raise_amount >= self._last_full_raise:
                        # 풀 레이즈
                        self._last_full_raise = raise_amount
                        self._players_acted_on_full_raise = set()
                        self._is_under_raise_active = False
                    else:
                        # 언더 레이즈 (올인)
                        self._is_under_raise_active = True
                        logger.info(f"[UNDER_RAISE_ALLIN] seat={player_seat}, raise={raise_amount}, min_full={self._last_full_raise}")

                    self._state.complete_bet_or_raise_to(max_raise)
                    amount = max_raise
                elif self._state.can_check_or_call():
                    # 올인이 콜인 경우
                    amount = self._state.checking_or_calling_amount or 0
                    self._state.check_or_call()
                    self._players_acted_on_full_raise.add(player_seat)
                else:
                    return {"success": False, "error": "Cannot go all-in"}
                player.status = "all_in"

            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except GameError as e:
            # GameError는 이미 구조화된 에러
            logger.warning(f"[GAME_ERROR] {e.code}: {e.message}")
            return {"success": False, "error": e.message, "errorCode": e.code}
        except Exception as e:
            # PokerKit 예외를 사용자 친화적 메시지로 변환
            error_msg = str(e)
            logger.error(f"[POKER_ERROR] {type(e).__name__}: {error_msg}")
            # 일반적인 PokerKit 에러 메시지 변환
            if "cannot" in error_msg.lower():
                return {"success": False, "error": "해당 액션을 수행할 수 없습니다"}
            return {"success": False, "error": error_msg}

        # Track action for hand history
        self._hand_actions.append({
            "seat": player_seat,
            "user_id": user_id,
            "action": action,
            "amount": amount,
            "phase": self.phase.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Sync state after action
        self._sync_bets_from_state()
        self._update_pot()

        # Check for phase transitions
        old_phase = self.phase
        self._check_phase_transition()

        # 페이즈 전환 시 언더 레이즈 상태 초기화
        if old_phase != self.phase:
            self._reset_under_raise_state()

        # Track if we saw flop
        if self.phase == GamePhase.FLOP and not self._saw_flop:
            self._saw_flop = True

        # Check if hand is complete
        hand_complete = False
        hand_result = None

        if self._state.status is False:
            hand_complete = True
            hand_result = self._complete_hand()

        # Update current player
        if not hand_complete:
            self._update_current_player()

        # 플레이어 상태 수집 (스택, 베팅 금액)
        players_state = []
        for seat, p in self.players.items():
            if p:
                players_state.append({
                    "position": seat,
                    "stack": p.stack,
                    "bet": p.current_bet,
                    "totalBet": p.total_bet_this_hand,  # 핸드 전체 누적 베팅
                    "status": p.status,
                })

        return {
            "success": True,
            "action": action,
            "amount": amount,
            "seat": player_seat,
            "pot": self.pot,
            "phase": self.phase.value,
            "phase_changed": old_phase != self.phase,
            "new_community_cards": self.community_cards if old_phase != self.phase else [],
            "hand_complete": hand_complete,
            "hand_result": hand_result,
            "players": players_state,  # 실시간 플레이어 상태
            "currentBet": self.current_bet,  # 현재 콜해야 할 금액
            "currentPlayer": self.current_player_seat,  # 현재 턴
        }

    def get_available_actions(self, user_id: str) -> AvailableActions:
        """Get available actions for a player."""
        if not self._state or self.phase == GamePhase.WAITING:
            return {"actions": []}

        player_seat = None
        player = None
        for seat, p in self.players.items():
            if p and p.user_id == user_id:
                player_seat = seat
                player = p
                break

        if player_seat != self.current_player_seat or not player:
            return {"actions": []}

        actions = []

        # Check if can check or must call
        call_amount = self.current_bet - player.current_bet
        if call_amount <= 0:
            # Can check - no fold option needed
            actions.append("check")
        else:
            # Must call or fold
            actions.append("fold")
            actions.append("call")

        # Check if can raise
        # WSOP 규칙: 언더 레이즈 발생 시, 이미 행동한 플레이어는 리레이즈 불가
        can_reraise = True
        if self._is_under_raise_active and player_seat in self._players_acted_on_full_raise:
            can_reraise = False
            logger.debug(f"[UNDER_RAISE_BLOCK] seat={player_seat}는 이미 행동했으므로 리레이즈 불가")

        if can_reraise and self._state.can_complete_bet_or_raise_to():
            min_raise = self._state.min_completion_betting_or_raising_to_amount
            max_raise = player.stack + player.current_bet

            if min_raise and max_raise >= min_raise:
                actions.append("raise" if call_amount > 0 else "bet")
                return {
                    "actions": actions,
                    "call_amount": max(0, call_amount),
                    "min_raise": min_raise,
                    "max_raise": max_raise,
                }

        return {
            "actions": actions,
            "call_amount": max(0, call_amount) if "call" in actions else 0,
        }

    def get_state_for_player(self, user_id: str) -> Dict[str, Any]:
        """Get game state from a specific player's perspective."""
        state = self._get_base_state()

        # Find player's position
        my_position = None
        for player_data in state["players"]:
            if player_data and player_data["userId"] == user_id:
                my_position = player_data["seat"]
                # Show hole cards for requesting player
                seat = player_data["seat"]
                actual_player = self.players.get(seat)
                if actual_player:
                    player_data["holeCards"] = actual_player.hole_cards
            elif player_data:
                player_data["holeCards"] = None  # Hide others' cards

        # Add available actions if it's this player's turn
        available_actions = []
        if state.get("currentTurn") is not None:
            current_seat = state["currentTurn"]
            current_player = self.players.get(current_seat)
            if current_player and current_player.user_id == user_id:
                actions_data = self.get_available_actions(user_id)
                for action in actions_data.get("actions", []):
                    action_dict = {"type": action}
                    if action == "call":
                        action_dict["minAmount"] = actions_data.get("call_amount", 0)
                        action_dict["maxAmount"] = actions_data.get("call_amount", 0)
                    elif action in ("bet", "raise"):
                        action_dict["minAmount"] = actions_data.get("min_raise", 0)
                        action_dict["maxAmount"] = actions_data.get("max_raise", 0)
                    available_actions.append(action_dict)

        state["myPosition"] = my_position
        state["allowedActions"] = available_actions

        return state

    def _get_base_state(self) -> Dict[str, Any]:
        """Get base game state."""
        players_data = []
        for seat in range(self.max_players):
            player = self.players.get(seat)
            if player:
                players_data.append({
                    "seat": seat,
                    "position": seat,
                    "userId": player.user_id,
                    "username": player.username,
                    "stack": player.stack,
                    "bet": player.current_bet,
                    "totalBet": player.total_bet_this_hand,  # 핸드 전체 누적 베팅
                    "status": player.status,
                    "isBot": player.is_bot,
                    "isCurrent": seat == self.current_player_seat,
                    "isDealer": seat == self.dealer_seat,
                })
            else:
                players_data.append(None)

        # Calculate SB and BB seats
        sb_seat, bb_seat = self.get_blind_seats()

        return {
            "tableId": self.room_id,
            "roomId": self.room_id,
            "tableName": self.name,
            "handNumber": self.hand_number,
            "phase": self.phase.value,
            "pot": self.pot,
            "communityCards": self.community_cards,
            "currentTurn": self.current_player_seat,
            "currentBet": self.current_bet,
            "dealer": self.dealer_seat,
            "smallBlindSeat": sb_seat,
            "bigBlindSeat": bb_seat,
            "smallBlind": self.small_blind,
            "bigBlind": self.big_blind,
            "players": players_data,
            "seats": {str(i): players_data[i] for i in range(self.max_players)},
        }

    def _move_dealer(self):
        """Move dealer button to next active player (clockwise)."""
        seated = self.get_seated_players_clockwise()
        seats = [s for s, _ in seated]

        if not seats:
            return

        if self.dealer_seat == -1 or self.dealer_seat not in seats:
            # 첫 핸드: 시계방향 순서상 첫 번째 좌석이 딜러
            self.dealer_seat = seats[0]
        else:
            # 다음 핸드: 시계방향으로 다음 플레이어에게 딜러 이동
            self.dealer_seat = self.get_next_clockwise_seat(self.dealer_seat, seats)

    def _deal_hole_cards(self):
        """Deal hole cards to players."""
        if not self._state:
            return

        # Deal hole cards (2 per player)
        num_players = len(self._seat_to_index)
        for _ in range(2 * num_players):
            if self._state.can_deal_hole():
                self._state.deal_hole()

        # Extract cards and assign to players
        for seat, idx in self._seat_to_index.items():
            player = self.players.get(seat)
            if player and self._state.hole_cards:
                cards = self._state.hole_cards[idx]
                if cards:
                    player.hole_cards = [card_to_str(c) for c in cards]

    def _check_phase_transition(self):
        """Check and handle phase transitions."""
        if not self._state:
            return
        self._update_phase()

    def _update_phase(self):
        """Update phase based on state."""
        if not self._state:
            return

        board_count = len(self._state.board_cards) if self._state.board_cards else 0

        if board_count == 0:
            self.phase = GamePhase.PREFLOP
        elif board_count == 3:
            self.phase = GamePhase.FLOP
        elif board_count == 4:
            self.phase = GamePhase.TURN
        elif board_count >= 5:
            self.phase = GamePhase.RIVER

        # Update community cards
        if self._state.board_cards:
            self.community_cards = [card_to_str(c[0]) for c in self._state.board_cards if c]

    def _reset_under_raise_state(self):
        """새 베팅 라운드 시작 시 언더 레이즈 상태 초기화.

        각 스트릿(Flop, Turn, River) 시작 시 호출됨.
        Postflop에서는 첫 베팅이 오픈 베팅이므로 big_blind를 기준으로 사용.
        """
        self._last_full_raise = self.big_blind
        self._players_acted_on_full_raise = set()
        self._is_under_raise_active = False
        logger.debug(f"[UNDER_RAISE_RESET] phase={self.phase.value}, last_full_raise={self._last_full_raise}")

    def _rebuild_index_mappings(self):
        """Rebuild seat-to-index mappings from current active players.

        페이즈 전환 후 매핑이 손실된 경우 복구용.
        """
        if not self._state:
            logger.warning("[REBUILD_MAPPINGS] No state available")
            return

        # 현재 핸드에 참여 중인 플레이어 (active 또는 all_in)
        active_players = [(seat, p) for seat, p in self.players.items()
                          if p and p.status in ("active", "all_in")]
        # 테이블 크기에 맞는 시계방향 인덱스 사용
        seat_to_idx = get_seat_to_clockwise_index(self.max_players)
        active_players.sort(key=lambda x: seat_to_idx.get(x[0], x[0]))

        self._seat_to_index = {seat: idx for idx, (seat, _) in enumerate(active_players)}
        self._index_to_seat = {idx: seat for seat, idx in self._seat_to_index.items()}

        logger.info(f"[REBUILD_MAPPINGS] Rebuilt mappings: seat_to_index={self._seat_to_index}, index_to_seat={self._index_to_seat}")

    def _update_current_player(self):
        """Update current player from state."""
        if not self._state:
            self.current_player_seat = None
            logger.debug("[UPDATE_PLAYER] No state available, setting current_player_seat=None")
            return

        if self._state.actor_index is not None:
            seat = self._index_to_seat.get(self._state.actor_index)
            if seat is None and self._index_to_seat:
                # 매핑이 존재하지만 actor_index에 대한 좌석이 없음
                logger.warning(f"[UPDATE_PLAYER] No mapping for actor_index={self._state.actor_index}, "
                             f"existing mappings: {self._index_to_seat}")
                # 매핑 재구성 시도
                self._rebuild_index_mappings()
                seat = self._index_to_seat.get(self._state.actor_index)

            self.current_player_seat = seat
            logger.debug(f"[UPDATE_PLAYER] Set current_player_seat={seat} from actor_index={self._state.actor_index}")
        else:
            self.current_player_seat = None
            logger.debug("[UPDATE_PLAYER] actor_index is None, setting current_player_seat=None")

    def _update_pot(self):
        """Update pot from state."""
        if self._state:
            collected = sum(pot.amount for pot in self._state.pots) if self._state.pots else 0
            current_bets = sum(self._state.bets) if self._state.bets else 0
            self.pot = collected + current_bets

    def _sync_bets_from_state(self):
        """Sync player bets and stacks from PokerKit state."""
        if not self._state:
            return

        for seat, idx in self._seat_to_index.items():
            player = self.players.get(seat)
            if player and idx < len(self._state.stacks):
                player.stack = self._state.stacks[idx]
                if self._state.bets and idx < len(self._state.bets):
                    new_bet = self._state.bets[idx]
                    # 베팅 금액이 증가한 경우에만 total_bet_this_hand에 누적
                    bet_increase = new_bet - player.current_bet
                    if bet_increase > 0:
                        player.total_bet_this_hand += bet_increase
                    player.current_bet = new_bet

        # Update current bet to call
        if self._state.bets:
            self.current_bet = max(self._state.bets)

    def _complete_hand(self) -> HandResult:
        """Complete the hand and determine winners."""
        if not self._state:
            return {"winners": [], "showdown": [], "pot": 0, "communityCards": [], "eliminatedPlayers": []}

        self.phase = GamePhase.SHOWDOWN
        self._sync_bets_from_state()

        winners = []
        showdown_cards = []

        # 최종 스택을 먼저 동기화
        final_stacks = {}
        for seat, idx in self._seat_to_index.items():
            player = self.players.get(seat)
            if not player:
                continue

            if idx < len(self._state.stacks):
                final_stack = self._state.stacks[idx]
                player.stack = final_stack
                final_stacks[seat] = final_stack

        # 먼저 active/all_in 플레이어 수 계산 (폴드하지 않은 플레이어)
        # 2명 이상일 때만 실제 쇼다운 (카드 공개)
        # 1명만 남으면 폴드-아웃 승리 (카드 공개 없음)
        active_player_count = sum(
            1 for seat in self._seat_to_index
            if (p := self.players.get(seat)) and p.status in ("active", "all_in")
        )
        is_actual_showdown = active_player_count >= 2

        # 승리액 및 팟 계산
        # PokerKit이 칩을 이미 분배했으므로 시작/최종 스택 차이로 계산
        total_pot = 0  # 총 팟 = 손실 합계 = 이익 합계
        for seat, idx in self._seat_to_index.items():
            player = self.players.get(seat)
            if not player:
                continue

            starting_stack = self._hand_starting_stacks.get(seat, 0)
            final_stack = final_stacks.get(seat, 0)
            net_gain = final_stack - starting_stack

            # 순이익이 양수인 경우 승자
            if net_gain > 0:
                total_pot += net_gain  # 승자의 이익 합계 = 패자의 손실 합계 = 팟
                winners.append({
                    "seat": seat,
                    "position": seat,
                    "userId": player.user_id,
                    "amount": net_gain,  # 실제 순이익 (최종 스택 - 시작 스택)
                })

            # 실제 쇼다운(2명 이상)일 때만 카드 공개
            # 폴드-아웃 승리(1명만 남음)는 카드 공개 안함
            if is_actual_showdown and player.status in ("active", "all_in") and player.hole_cards:
                showdown_cards.append({
                    "seat": seat,
                    "position": seat,
                    "holeCards": player.hole_cards,
                })

        # 팟이 계산되지 않은 경우 (모두 폴드 등) 손실 합계로 계산
        if total_pot == 0:
            for seat in self._seat_to_index:
                starting_stack = self._hand_starting_stacks.get(seat, 0)
                final_stack = final_stacks.get(seat, 0)
                loss = starting_stack - final_stack
                if loss > 0:
                    total_pot += loss

        # Fallback: 승자가 없는 경우 (모두 폴드 등)
        if not winners:
            for seat, idx in self._seat_to_index.items():
                player = self.players.get(seat)
                if player and player.status in ("active", "all_in"):
                    winners.append({
                        "seat": seat,
                        "position": seat,
                        "userId": player.user_id,
                        "amount": total_pot,  # total_pot 사용
                    })
                    break

        # 환불 (Uncalled Bet) 계산
        # 조건: 1명만 남음 (모두 폴드), 승자의 베팅 > 다른 플레이어 최대 베팅
        refund_info = None
        if not is_actual_showdown and len(winners) == 1:
            winner_seat = winners[0]["seat"]
            bets = {}
            for seat in self._seat_to_index:
                player = self.players.get(seat)
                if player:
                    bets[seat] = player.total_bet_this_hand

            winner_bet = bets.get(winner_seat, 0)
            other_bets = [b for s, b in bets.items() if s != winner_seat]
            other_max_bet = max(other_bets) if other_bets else 0

            refund_amount = winner_bet - other_max_bet
            if refund_amount > 0:
                winner_player = self.players.get(winner_seat)
                refund_info = {
                    "seat": winner_seat,
                    "userId": winner_player.user_id if winner_player else "",
                    "amount": refund_amount,
                }
                logger.info(f"[REFUND] seat={winner_seat}, amount={refund_amount} "
                          f"(winner_bet={winner_bet}, other_max={other_max_bet})")

        # P0-3: 칩 무결성 검증
        try:
            from app.services.chip_integrity import get_chip_integrity_service
            chip_service = get_chip_integrity_service()
            validation_result = chip_service.validate_hand_completion(
                table_id=self.room_id,
                final_stacks=final_stacks,
                rake_collected=0,  # 레이크 수집 시 이 값 업데이트 필요
            )
            if not validation_result.is_valid:
                logger.error(
                    f"[CHIP_INTEGRITY] 칩 무결성 검증 실패: {validation_result.error}"
                )
                # TODO: 알림 발송 및 관리자 개입 요청
        except Exception as e:
            logger.warning(f"[CHIP_INTEGRITY] 검증 중 예외 (게임은 계속): {e}")

        # HAND_RESULT 반환 데이터 (초기화 전에 저장)
        result_community_cards = self.community_cards.copy()
        seat_to_index_copy = dict(self._seat_to_index)

        # Reset for next hand - 완전 초기화
        self.phase = GamePhase.WAITING
        self._state = None
        self.current_player_seat = None
        self.current_bet = 0
        self.pot = 0
        self.community_cards = []  # 커뮤니티 카드 초기화

        # 스택이 0인 플레이어 추적 (리바이 모달용)
        zero_stack_players = []

        for seat in seat_to_index_copy:
            player = self.players.get(seat)
            if player:
                player.current_bet = 0
                player.total_bet_this_hand = 0
                player.hole_cards = None

                # stack이 0이면 sitting_out으로 전환
                if player.stack == 0:
                    player.status = "sitting_out"
                    zero_stack_players.append({
                        "seat": seat,
                        "userId": player.user_id,
                    })
                elif player.status != "sitting_out":
                    player.status = "active"

        # 매핑 변수도 초기화
        self._seat_to_index = {}
        self._index_to_seat = {}
        self._hand_actions = []
        self._hand_starting_stacks = {}
        self._hand_start_time = None
        self._saw_flop = False
        self._is_preflop_first_turn = True

        # 언더 레이즈 상태 초기화
        self._last_full_raise = 0
        self._players_acted_on_full_raise = set()
        self._is_under_raise_active = False

        return {
            "winners": winners,
            "showdown": showdown_cards,
            "pot": total_pot,  # 계산된 총 팟 반환
            "communityCards": result_community_cards,  # 초기화 전 값 반환
            "zeroStackPlayers": zero_stack_players,  # 스택 0인 플레이어 (리바이 모달용)
            "refund": refund_info,  # 환불 정보 (Uncalled bet 반환)
        }
