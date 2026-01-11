# 타이머 및 턴 규칙

> 턴 타이머, 타임아웃 처리, 턴 전환 규칙

---

## 1. 타이머 설정

### 1.1 기본 설정

| 항목 | 기본값 | 범위 |
|------|--------|------|
| 턴 타임아웃 | 30초 | 15-60초 |
| 타임뱅크 | 30초 | 0-60초 |
| 핸드 간 대기 | 5초 | 3-10초 |
| 쇼다운 표시 | 3초 | 2-5초 |

### 1.2 테이블별 설정

```python
@dataclass
class TableConfig:
    turn_timeout_seconds: int = 30
    time_bank_seconds: int = 30
    hand_delay_seconds: int = 5
    showdown_delay_seconds: int = 3
```

---

## 2. 턴 타이머 동작

### 2.1 타이머 시작

```python
async def start_turn_timer(
    table_id: str,
    position: int,
    timeout: int
) -> None:
    deadline = datetime.utcnow() + timedelta(seconds=timeout)
    
    # 클라이언트에 턴 알림
    await broadcast_event(table_id, "TURN_PROMPT", {
        "position": position,
        "turnDeadlineAt": deadline.isoformat(),
        "allowedActions": get_allowed_actions(table_id, position)
    })
    
    # 타임아웃 스케줄링
    await schedule_timeout(table_id, position, deadline)
```

### 2.2 타이머 취소

```python
async def cancel_turn_timer(table_id: str, position: int) -> None:
    await cancel_scheduled_timeout(table_id, position)
```

### 2.3 타임아웃 처리

```python
async def handle_turn_timeout(table_id: str, position: int) -> None:
    async with table_lock(table_id):
        table = await get_table(table_id)
        
        # 이미 턴이 지났으면 무시
        if table.current_turn != position:
            return
        
        # 타임뱅크 확인
        player = table.get_player_at(position)
        if player.time_bank > 0:
            await use_time_bank(table_id, position)
            return
        
        # 자동 폴드/체크
        if can_check(table, position):
            await process_action(table_id, position, "check")
        else:
            await process_action(table_id, position, "fold")
        
        # 타임아웃 알림
        await broadcast_event(table_id, "ACTION_TIMEOUT", {
            "position": position,
            "action": "fold" if not can_check(table, position) else "check"
        })
```

---

## 3. 타임뱅크

### 3.1 타임뱅크 사용

```python
async def use_time_bank(table_id: str, position: int) -> None:
    table = await get_table(table_id)
    player = table.get_player_at(position)
    
    # 타임뱅크 시간 추가
    additional_time = min(player.time_bank, 30)
    player.time_bank -= additional_time
    
    # 새 타이머 시작
    new_deadline = datetime.utcnow() + timedelta(seconds=additional_time)
    
    await broadcast_event(table_id, "TIME_BANK_USED", {
        "position": position,
        "additionalSeconds": additional_time,
        "remainingTimeBank": player.time_bank,
        "newDeadline": new_deadline.isoformat()
    })
    
    await schedule_timeout(table_id, position, new_deadline)
```

### 3.2 타임뱅크 충전

```python
# 핸드 시작 시 타임뱅크 충전 (선택적)
async def recharge_time_bank(table_id: str) -> None:
    table = await get_table(table_id)
    
    for seat in table.seats:
        if seat.player:
            seat.player.time_bank = min(
                seat.player.time_bank + 10,  # 핸드당 10초 충전
                table.config.time_bank_seconds  # 최대값
            )
```

---

## 4. 턴 전환 규칙

### 4.1 턴 순서

```
딜러 버튼 기준 시계 방향

Preflop: SB → BB → UTG → ... → BTN
Postflop: SB → BB → ... → BTN (폴드 제외)
```

### 4.2 턴 전환 조건

| 조건 | 다음 턴 |
|------|---------|
| 액션 완료 | 다음 활성 플레이어 |
| 폴드 | 다음 활성 플레이어 |
| 올인 | 다음 활성 플레이어 |
| 라운드 종료 | Phase 전환 후 첫 플레이어 |

### 4.3 턴 전환 구현

```python
def get_next_turn(table: TableState) -> int | None:
    current = table.current_turn
    active_positions = [
        seat.position for seat in table.seats
        if seat.player and seat.status == "active"
    ]
    
    if len(active_positions) <= 1:
        return None  # 핸드 종료
    
    # 다음 활성 플레이어 찾기
    for i in range(1, len(table.seats)):
        next_pos = (current + i) % len(table.seats)
        if next_pos in active_positions:
            return next_pos
    
    return None
```

---

## 5. 라운드 종료 조건

### 5.1 베팅 라운드 종료

```python
def is_betting_round_complete(table: TableState) -> bool:
    active_players = [
        seat for seat in table.seats
        if seat.player and seat.status == "active"
    ]
    
    # 1명만 남으면 종료
    if len(active_players) <= 1:
        return True
    
    # 모든 활성 플레이어가 동일 금액 베팅
    bet_amounts = set(p.bet_amount for p in active_players)
    if len(bet_amounts) > 1:
        return False
    
    # 모든 플레이어가 액션 완료
    return all(p.has_acted for p in active_players)
```

### 5.2 Phase 전환

```python
async def transition_phase(table_id: str) -> None:
    table = await get_table(table_id)
    
    phase_order = ["preflop", "flop", "turn", "river", "showdown"]
    current_index = phase_order.index(table.hand.phase)
    
    if current_index < len(phase_order) - 1:
        new_phase = phase_order[current_index + 1]
        
        # 커뮤니티 카드 추가
        if new_phase == "flop":
            cards = deal_cards(3)
        elif new_phase in ["turn", "river"]:
            cards = deal_cards(1)
        else:
            cards = []
        
        # 상태 업데이트
        await update_table(table_id, {
            "phase": new_phase,
            "community_cards": table.hand.community_cards + cards,
            "current_turn": get_first_to_act(table)
        })
        
        # 새 턴 타이머 시작
        await start_turn_timer(
            table_id,
            get_first_to_act(table),
            table.config.turn_timeout_seconds
        )
```

---

## 6. 클라이언트 타이머 동기화

### 6.1 서버 시간 동기화

```typescript
class TimerSync {
  private serverOffset = 0;
  
  async sync(): Promise<void> {
    const clientTime = Date.now();
    const response = await fetch('/api/time');
    const serverTime = response.serverTime;
    const roundTrip = Date.now() - clientTime;
    
    this.serverOffset = serverTime - clientTime - (roundTrip / 2);
  }
  
  getServerTime(): number {
    return Date.now() + this.serverOffset;
  }
}
```

### 6.2 타이머 표시

```typescript
function TurnTimer({ deadline }: { deadline: Date }) {
  const [remaining, setRemaining] = useState(0);
  
  useEffect(() => {
    const interval = setInterval(() => {
      const now = timerSync.getServerTime();
      const remaining = Math.max(0, deadline.getTime() - now);
      setRemaining(Math.ceil(remaining / 1000));
      
      if (remaining <= 0) {
        clearInterval(interval);
      }
    }, 100);
    
    return () => clearInterval(interval);
  }, [deadline]);
  
  return (
    <div className={getTimerClass(remaining)}>
      ⏱️ {formatTime(remaining)}
    </div>
  );
}

function getTimerClass(seconds: number): string {
  if (seconds <= 5) return 'timer-critical';
  if (seconds <= 10) return 'timer-warning';
  return 'timer-normal';
}
```

---

## 7. 에지 케이스

### 7.1 동시 타임아웃과 액션

```python
async def process_action_with_timeout_check(
    table_id: str,
    position: int,
    action: Action
) -> ActionResult:
    async with table_lock(table_id):
        table = await get_table(table_id)
        
        # 타임아웃 확인
        if table.turn_deadline < datetime.utcnow():
            return ActionResult(
                success=False,
                error_code="ACTION_TIMEOUT"
            )
        
        # 액션 처리
        return await process_action(table_id, position, action)
```

### 7.2 모든 플레이어 올인

```python
def check_all_in_runout(table: TableState) -> bool:
    active_players = [
        seat for seat in table.seats
        if seat.player and seat.status in ["active", "all_in"]
    ]
    
    # 2명 이상 남고, 모두 올인이면 런아웃
    active_not_allin = [p for p in active_players if p.status == "active"]
    return len(active_players) >= 2 and len(active_not_allin) <= 1
```

---

## 관련 문서

- [40-reconnect-recovery.md](./40-reconnect-recovery.md) - 재접속 복구
- [41-state-consistency.md](./41-state-consistency.md) - 상태 일관성
- [11-engine-state-model.md](./11-engine-state-model.md) - 상태 모델
