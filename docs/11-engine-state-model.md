# 엔진 상태 모델

> PokerKit 기반 게임 엔진의 상태 모델 정의

---

## 1. 상태 계층 구조

```
TableState (테이블 전체 상태)
├── TableConfig (테이블 설정)
├── HandState (현재 핸드 상태)
│   ├── Phase (게임 단계)
│   ├── Pot (팟 정보)
│   ├── CommunityCards (커뮤니티 카드)
│   └── PlayerHandStates[] (플레이어별 핸드 상태)
├── SeatStates[] (좌석 상태)
└── Metadata (버전, 타임스탬프 등)
```

---

## 2. 핵심 상태 모델

### 2.1 TableState

```python
@dataclass(frozen=True)
class TableState:
    """테이블 전체 상태 (불변)"""
    
    table_id: str
    config: TableConfig
    seats: tuple[SeatState, ...]
    hand: HandState | None  # 핸드 진행 중이 아니면 None
    dealer_position: int
    state_version: int
    updated_at: datetime
    
    def with_hand(self, hand: HandState) -> "TableState":
        """새 핸드 상태로 복사"""
        return replace(self, hand=hand, state_version=self.state_version + 1)
```

### 2.2 TableConfig

```python
@dataclass(frozen=True)
class TableConfig:
    """테이블 설정 (불변)"""
    
    max_seats: int  # 2-9
    small_blind: int
    big_blind: int
    min_buy_in: int
    max_buy_in: int
    turn_timeout_seconds: int = 30
    
    @property
    def ante(self) -> int:
        return 0  # 기본값, 향후 확장
```

### 2.3 SeatState

```python
@dataclass(frozen=True)
class SeatState:
    """좌석 상태"""
    
    position: int  # 0-based
    player: Player | None  # 비어있으면 None
    stack: int
    status: SeatStatus
    
class SeatStatus(Enum):
    EMPTY = "empty"
    WAITING = "waiting"      # 다음 핸드 대기
    ACTIVE = "active"        # 현재 핸드 참여 중
    SITTING_OUT = "sitting_out"
    DISCONNECTED = "disconnected"
```

### 2.4 Player

```python
@dataclass(frozen=True)
class Player:
    """플레이어 정보"""
    
    user_id: str
    nickname: str
    avatar_url: str | None = None
```

---

## 3. 핸드 상태 모델

### 3.1 HandState

```python
@dataclass(frozen=True)
class HandState:
    """핸드 상태"""
    
    hand_id: str
    hand_number: int
    phase: GamePhase
    community_cards: tuple[Card, ...]
    pot: PotState
    player_states: tuple[PlayerHandState, ...]
    current_turn: int | None  # 현재 턴 좌석 위치
    last_aggressor: int | None
    min_raise: int
    started_at: datetime
    
class GamePhase(Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    FINISHED = "finished"
```

### 3.2 PlayerHandState

```python
@dataclass(frozen=True)
class PlayerHandState:
    """플레이어의 핸드 내 상태"""
    
    position: int
    hole_cards: tuple[Card, Card] | None  # 폴드 시 None
    bet_amount: int  # 현재 라운드 베팅액
    total_bet: int   # 핸드 전체 베팅액
    status: PlayerHandStatus
    last_action: PlayerAction | None
    
class PlayerHandStatus(Enum):
    ACTIVE = "active"
    FOLDED = "folded"
    ALL_IN = "all_in"
```

### 3.3 PotState

```python
@dataclass(frozen=True)
class PotState:
    """팟 상태"""
    
    main_pot: int
    side_pots: tuple[SidePot, ...] = ()
    
    @property
    def total(self) -> int:
        return self.main_pot + sum(sp.amount for sp in self.side_pots)

@dataclass(frozen=True)
class SidePot:
    """사이드 팟"""
    
    amount: int
    eligible_positions: tuple[int, ...]
```

---

## 4. 카드 모델

### 4.1 Card

```python
@dataclass(frozen=True)
class Card:
    """카드"""
    
    rank: Rank
    suit: Suit
    
    def __str__(self) -> str:
        return f"{self.rank.symbol}{self.suit.symbol}"

class Rank(Enum):
    TWO = (2, "2")
    THREE = (3, "3")
    FOUR = (4, "4")
    FIVE = (5, "5")
    SIX = (6, "6")
    SEVEN = (7, "7")
    EIGHT = (8, "8")
    NINE = (9, "9")
    TEN = (10, "T")
    JACK = (11, "J")
    QUEEN = (12, "Q")
    KING = (13, "K")
    ACE = (14, "A")
    
    @property
    def value(self) -> int:
        return self.value[0]
    
    @property
    def symbol(self) -> str:
        return self.value[1]

class Suit(Enum):
    CLUBS = ("c", "♣")
    DIAMONDS = ("d", "♦")
    HEARTS = ("h", "♥")
    SPADES = ("s", "♠")
    
    @property
    def symbol(self) -> str:
        return self.value[0]
```

---

## 5. 액션 모델

### 5.1 ActionRequest

```python
@dataclass(frozen=True)
class ActionRequest:
    """클라이언트 액션 요청"""
    
    request_id: str
    action_type: ActionType
    amount: int | None = None  # raise/bet 시 필수

class ActionType(Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"
```

### 5.2 PlayerAction

```python
@dataclass(frozen=True)
class PlayerAction:
    """처리된 플레이어 액션"""
    
    position: int
    action_type: ActionType
    amount: int
    timestamp: datetime
```

### 5.3 ValidAction

```python
@dataclass(frozen=True)
class ValidAction:
    """유효한 액션 정보"""
    
    action_type: ActionType
    min_amount: int | None = None  # raise/bet 최소값
    max_amount: int | None = None  # raise/bet 최대값 (스택)
```

---

## 6. 결과 모델

### 6.1 HandResult

```python
@dataclass(frozen=True)
class HandResult:
    """핸드 결과"""
    
    hand_id: str
    winners: tuple[WinnerInfo, ...]
    showdown_hands: tuple[ShowdownHand, ...] | None
    
@dataclass(frozen=True)
class WinnerInfo:
    """승자 정보"""
    
    position: int
    amount: int
    pot_type: str  # "main" or "side_0", "side_1", ...

@dataclass(frozen=True)
class ShowdownHand:
    """쇼다운 핸드 정보"""
    
    position: int
    hole_cards: tuple[Card, Card]
    hand_rank: HandRank
    best_five: tuple[Card, ...]
```

### 6.2 HandRank

```python
class HandRank(Enum):
    HIGH_CARD = (1, "High Card")
    ONE_PAIR = (2, "One Pair")
    TWO_PAIR = (3, "Two Pair")
    THREE_OF_A_KIND = (4, "Three of a Kind")
    STRAIGHT = (5, "Straight")
    FLUSH = (6, "Flush")
    FULL_HOUSE = (7, "Full House")
    FOUR_OF_A_KIND = (8, "Four of a Kind")
    STRAIGHT_FLUSH = (9, "Straight Flush")
    ROYAL_FLUSH = (10, "Royal Flush")
```

---

## 7. 뷰 상태 모델

### 7.1 PlayerViewState

플레이어에게 전송되는 상태 (자신의 홀카드만 공개)

```python
@dataclass(frozen=True)
class PlayerViewState:
    """플레이어 시점 상태"""
    
    table_id: str
    config: TableConfig
    seats: tuple[SeatViewState, ...]
    hand: HandViewState | None
    my_position: int
    my_hole_cards: tuple[Card, Card] | None
    allowed_actions: tuple[ValidAction, ...]
    turn_deadline_at: datetime | None
    state_version: int
```

### 7.2 SpectatorViewState

관전자에게 전송되는 상태 (모든 홀카드 마스킹)

```python
@dataclass(frozen=True)
class SpectatorViewState:
    """관전자 시점 상태"""
    
    table_id: str
    config: TableConfig
    seats: tuple[SeatViewState, ...]
    hand: HandViewState | None
    state_version: int
    # hole_cards 없음
    # allowed_actions 없음
```

---

## 8. 직렬화 스키마

### 8.1 TableSnapshot JSON

```json
{
  "tableId": "table-123",
  "config": {
    "maxSeats": 6,
    "smallBlind": 10,
    "bigBlind": 20,
    "minBuyIn": 400,
    "maxBuyIn": 2000,
    "turnTimeoutSeconds": 30
  },
  "seats": [
    {
      "position": 0,
      "player": {
        "userId": "user-1",
        "nickname": "Player1",
        "avatarUrl": null
      },
      "stack": 1500,
      "status": "active"
    }
  ],
  "hand": {
    "handId": "hand-456",
    "handNumber": 1,
    "phase": "flop",
    "communityCards": ["Ah", "Kd", "Qc"],
    "pot": {
      "mainPot": 100,
      "sidePots": []
    },
    "currentTurn": 2,
    "minRaise": 40
  },
  "dealerPosition": 0,
  "stateVersion": 15,
  "updatedAt": "2026-01-11T10:30:00Z"
}
```

### 8.2 카드 직렬화

```
카드 형식: {Rank}{Suit}
예시: "Ah" (Ace of Hearts), "Tc" (Ten of Clubs)

Rank: 2-9, T, J, Q, K, A
Suit: c (clubs), d (diamonds), h (hearts), s (spades)
```

---

## 9. 상태 전이 규칙

### 9.1 Phase 전이

```
PREFLOP → FLOP → TURN → RIVER → SHOWDOWN → FINISHED
                                    ↓
                              (1명 남으면)
                                    ↓
                                FINISHED
```

### 9.2 전이 조건

| 현재 Phase | 전이 조건 | 다음 Phase |
|-----------|----------|-----------|
| PREFLOP | 모든 액션 완료 | FLOP |
| FLOP | 모든 액션 완료 | TURN |
| TURN | 모든 액션 완료 | RIVER |
| RIVER | 모든 액션 완료 | SHOWDOWN |
| SHOWDOWN | 결과 처리 완료 | FINISHED |
| Any | 1명 제외 모두 폴드 | FINISHED |

---

## 10. 불변성 보장

### 10.1 규칙

1. 모든 상태 클래스는 `frozen=True`
2. 컬렉션은 `tuple` 사용 (list 대신)
3. 상태 변경은 `replace()` 또는 새 인스턴스 생성

### 10.2 예시

```python
# 잘못된 방법 (금지)
state.hand.phase = GamePhase.FLOP

# 올바른 방법
new_hand = replace(state.hand, phase=GamePhase.FLOP)
new_state = replace(state, hand=new_hand, state_version=state.state_version + 1)
```

---

## 관련 문서

- [10-engine-architecture.md](./10-engine-architecture.md) - 엔진 아키텍처
- [ADR-0001-pokerkit-core.md](./ADR/ADR-0001-pokerkit-core.md) - PokerKit 채택 결정
- [20-realtime-protocol-v1.md](./20-realtime-protocol-v1.md) - 실시간 프로토콜
