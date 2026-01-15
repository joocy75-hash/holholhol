# Design Document: Time Bank (타임 뱅크)

## Overview

Time Bank 기능은 플레이어가 턴 제한 시간이 부족할 때 추가 시간을 요청할 수 있는 기능입니다. 기존 `backend/app/game/poker_table.py`의 Player 클래스와 타이머 로직을 확장하여 구현합니다.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│   WebSocket      │────▶│   Action        │
│   Timer UI      │     │   Gateway        │     │   Handler       │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                         │
                                                         ▼
                                                 ┌─────────────────┐
                                                 │   PokerTable    │
                                                 │   (Extended)    │
                                                 └─────────────────┘
```

## Components and Interfaces

### 1. Player 클래스 확장

**파일**: `backend/app/game/poker_table.py`

```python
@dataclass
class Player:
    """Player at a poker table."""
    user_id: str
    username: str
    seat: int
    stack: int
    hole_cards: Optional[List[str]] = None
    current_bet: int = 0
    status: str = "active"
    total_bet_this_hand: int = 0
    is_bot: bool = False
    # Time Bank 추가
    time_bank_remaining: int = 3  # 남은 타임 뱅크 횟수
```

### 2. PokerTable 타임 뱅크 메서드

**파일**: `backend/app/game/poker_table.py`

```python
class PokerTable:
    # 설정 상수
    TIME_BANK_COUNT: int = 3  # 기본 타임 뱅크 횟수
    TIME_BANK_SECONDS: int = 30  # 타임 뱅크당 추가 시간
    
    def use_time_bank(self, seat: int) -> TimeBankResult:
        """Use time bank for the current player."""
        
    def reset_time_banks(self) -> None:
        """Reset all players' time banks at hand start."""
        
    def get_time_bank_remaining(self, seat: int) -> int:
        """Get remaining time bank count for a player."""
```

### 3. WebSocket 이벤트

**파일**: `backend/app/ws/events.py`

```python
class EventType(str, Enum):
    # 기존 이벤트들...
    TIME_BANK_REQUEST = "TIME_BANK_REQUEST"  # 클라이언트 → 서버
    TIME_BANK_USED = "TIME_BANK_USED"        # 서버 → 클라이언트 (브로드캐스트)
```

### 4. Action Handler 확장

**파일**: `backend/app/ws/handlers/action.py`

```python
class ActionHandler(BaseHandler):
    @property
    def handled_events(self) -> tuple[EventType, ...]:
        return (
            EventType.ACTION_REQUEST,
            EventType.START_GAME,
            EventType.TIME_BANK_REQUEST,  # 추가
        )
    
    async def _handle_time_bank(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope:
        """Handle TIME_BANK_REQUEST event."""
```

### 5. Frontend 컴포넌트

**파일**: `frontend/src/components/table/TimeBankButton.tsx`

```typescript
interface TimeBankButtonProps {
  remaining: number;
  isMyTurn: boolean;
  onUseTimeBank: () => void;
}
```

## Data Models

### TimeBankResult

```python
@dataclass
class TimeBankResult:
    success: bool
    remaining: int  # 남은 타임 뱅크 횟수
    added_seconds: int  # 추가된 시간
    new_deadline: datetime | None  # 새로운 턴 마감 시간
    error: str | None = None
```

### TIME_BANK_USED 이벤트 페이로드

```python
{
    "tableId": str,
    "seat": int,
    "userId": str,
    "remaining": int,  # 남은 횟수
    "addedSeconds": int,  # 추가된 시간
    "newDeadline": str,  # ISO 형식 새 마감 시간
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system.*

### Property 1: Time Bank Initialization

*For any* player seated at a table, their time_bank_remaining should be initialized to TIME_BANK_COUNT (default 3) when they sit down or when a new hand starts.

**Validates: Requirements 1.1, 1.2, 1.3**

### Property 2: Time Bank Usage Effect

*For any* valid time bank request (player's turn, remaining > 0), the turn deadline should increase by exactly TIME_BANK_SECONDS and the player's remaining count should decrease by exactly 1.

**Validates: Requirements 2.1, 2.2**

### Property 3: Time Bank Bounds

*For any* player, their time_bank_remaining should always be in range [0, TIME_BANK_COUNT].

**Validates: Requirements 1.2**

## Error Handling

| Error Code | Condition | HTTP Status |
|------------|-----------|-------------|
| NO_TIME_BANK | 타임 뱅크 횟수가 0 | 400 |
| NOT_YOUR_TURN | 현재 플레이어의 턴이 아님 | 400 |
| NO_ACTIVE_HAND | 진행 중인 핸드가 없음 | 400 |

## Testing Strategy

### Unit Tests
- `use_time_bank()` - 타임 뱅크 사용 로직
- `reset_time_banks()` - 초기화 로직
- 에러 케이스 (횟수 0, 턴 아님)

### Property-Based Tests (Hypothesis)
- Property 1: 초기화 시 올바른 횟수 부여
- Property 2: 사용 시 정확한 시간 추가 및 횟수 감소
- Property 3: 횟수가 항상 유효 범위 내

### Integration Tests
- WebSocket TIME_BANK_REQUEST → TIME_BANK_USED 브로드캐스트
