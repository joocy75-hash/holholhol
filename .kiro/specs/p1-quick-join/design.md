# Design Document: Quick Join (빠른 입장)

## Overview

Quick Join 기능은 사용자가 복잡한 방 선택 과정 없이 자동으로 적합한 방에 배정되는 기능입니다. 기존 `backend/app/api/rooms.py`와 `backend/app/services/room.py`를 확장하여 구현합니다.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│   Quick Join     │────▶│   Room Service  │
│   Lobby Page    │     │   API Endpoint   │     │   (Extended)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                │                        │
                                ▼                        ▼
                        ┌──────────────────┐     ┌─────────────────┐
                        │   Room Matcher   │     │   Game Manager  │
                        │   (New Module)   │     │   (Existing)    │
                        └──────────────────┘     └─────────────────┘
```

## Components and Interfaces

### 1. Quick Join API Endpoint

**파일**: `backend/app/api/rooms.py` (기존 파일 확장)

```python
@router.post("/quick-join", response_model=QuickJoinResponse)
async def quick_join(
    current_user: CurrentUser,
    db: DbSession,
    request: QuickJoinRequest,  # Optional blind level filter
) -> QuickJoinResponse:
    """Quick join to an available room."""
```

**Request Schema**:
```python
class QuickJoinRequest(BaseModel):
    blind_level: str | None = None  # "low", "medium", "high" or specific "10/20"
```

**Response Schema**:
```python
class QuickJoinResponse(BaseModel):
    room_id: str
    table_id: str
    seat: int
    buy_in: int
    room_name: str
    blinds: str
```

### 2. Room Matcher Service

**파일**: `backend/app/services/room_matcher.py` (새 파일)

```python
class RoomMatcher:
    """Matches users to optimal rooms based on criteria."""
    
    async def find_best_room(
        self,
        user_id: str,
        user_balance: int,
        blind_level: str | None = None,
    ) -> Room | None:
        """Find the best available room for the user."""
    
    def _calculate_room_score(self, room: Room) -> int:
        """Calculate priority score for room selection."""
    
    def _get_available_seat(self, room: Room) -> int | None:
        """Find an available seat in the room."""
```

### 3. Extended Room Service

**파일**: `backend/app/services/room.py` (기존 파일 확장)

```python
class RoomService:
    # 기존 메서드들...
    
    async def find_available_rooms(
        self,
        min_buy_in_max: int,  # User must afford at least min_buy_in
        blind_level: str | None = None,
        exclude_user_id: str | None = None,
    ) -> list[Room]:
        """Find rooms where user can join."""
    
    async def quick_join_room(
        self,
        user_id: str,
        room_id: str,
        seat: int,
        buy_in: int,
    ) -> dict:
        """Join a room via quick join."""
```

### 4. Frontend Integration

**파일**: `frontend/src/app/lobby/page.tsx` (기존 파일 확장)

```typescript
// Quick Join 버튼 컴포넌트
const QuickJoinButton: React.FC = () => {
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();
  
  const handleQuickJoin = async () => {
    setIsLoading(true);
    try {
      const response = await api.post('/rooms/quick-join');
      router.push(`/table/${response.data.room_id}`);
    } catch (error) {
      // Error handling
    } finally {
      setIsLoading(false);
    }
  };
  
  return (
    <Button onClick={handleQuickJoin} disabled={isLoading}>
      {isLoading ? '입장 중...' : '빠른 입장'}
    </Button>
  );
};
```

## Data Models

### Room Selection Priority

```python
# 방 선택 우선순위 점수 계산
def calculate_room_score(room: Room) -> int:
    score = 0
    
    # 1. 게임 진행 중인 방 우선 (+100)
    if room.status == "playing":
        score += 100
    
    # 2. 플레이어 수가 많은 방 우선 (+10 * player_count)
    score += room.current_players * 10
    
    # 3. 빈 좌석이 적은 방 우선 (더 활발한 게임)
    empty_seats = room.max_seats - room.current_players
    score += (room.max_seats - empty_seats)
    
    return score
```

### Buy-in Calculation

```python
def calculate_default_buy_in(room: Room, user_balance: int) -> int:
    """Calculate default buy-in amount."""
    buy_in_min = room.config.get("buy_in_min", 400)
    buy_in_max = room.config.get("buy_in_max", 2000)
    
    # 기본값: 최대 바이인의 50%
    default_buy_in = buy_in_max // 2
    
    # 사용자 잔액이 기본값보다 적으면 잔액 전체 사용
    if user_balance < default_buy_in:
        default_buy_in = user_balance
    
    # 최소 바이인 체크
    if default_buy_in < buy_in_min:
        raise InsufficientBalanceError()
    
    return default_buy_in
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Room Filtering Correctness

*For any* user with balance B and any set of rooms, the filtered rooms returned by `find_available_rooms()` should only include rooms where `buy_in_min <= B`.

**Validates: Requirements 1.1, 2.3, 2.4**

### Property 2: Room Selection Priority

*For any* set of available rooms, the selected room should have the highest priority score according to the scoring algorithm (playing > waiting, more players > fewer players).

**Validates: Requirements 1.2, 2.1, 2.2**

### Property 3: Buy-in Calculation Correctness

*For any* room with buy_in_max M and user with balance B where B >= buy_in_min:
- If B >= M/2, then buy_in = M/2
- If buy_in_min <= B < M/2, then buy_in = B

**Validates: Requirements 3.1, 3.2**

### Property 4: Seat Assignment Validity

*For any* quick join operation, the assigned seat must be empty (no existing player) in the target room.

**Validates: Requirements 1.3**

## Error Handling

| Error Code | Condition | HTTP Status |
|------------|-----------|-------------|
| NO_AVAILABLE_ROOM | 입장 가능한 방이 없음 | 404 |
| INSUFFICIENT_BALANCE | 보유 칩이 최소 바이인 미달 | 400 |
| ROOM_FULL | 선택된 방이 이미 가득 참 (race condition) | 409 |
| ALREADY_SEATED | 사용자가 이미 다른 방에 참여 중 | 409 |

## Testing Strategy

### Unit Tests
- `RoomMatcher.find_best_room()` - 다양한 방 조합에서 올바른 방 선택
- `calculate_default_buy_in()` - 바이인 계산 로직
- `find_available_rooms()` - 필터링 로직

### Property-Based Tests (Hypothesis)
- Property 1: 필터링된 방은 모두 사용자 잔액으로 입장 가능
- Property 2: 선택된 방은 항상 최고 우선순위
- Property 3: 바이인 금액은 항상 유효 범위 내

### Integration Tests
- Quick Join API 전체 흐름
- 동시 접속 시 race condition 처리

### E2E Tests
- 로비에서 빠른 입장 버튼 클릭 → 테이블 페이지 이동
