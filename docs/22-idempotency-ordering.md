# 멱등성 및 순서 보장 규칙

> 중복 요청 방지 및 이벤트 순서 보장 메커니즘

---

## 1. 개요

### 1.1 문제 상황

| 문제 | 원인 | 영향 |
|------|------|------|
| 중복 액션 | 네트워크 지연, 더블 클릭 | 잘못된 베팅, 의도치 않은 폴드 |
| 역순 도착 | 네트워크 지연, 패킷 재정렬 | UI 상태 불일치 |
| 누락 이벤트 | 연결 끊김, 패킷 손실 | 상태 동기화 실패 |

### 1.2 해결 전략

| 전략 | 메커니즘 |
|------|---------|
| 멱등성 | `requestId` 기반 중복 감지 |
| 순서 보장 | `stateVersion` 기반 순서 검증 |
| 복구 | `TABLE_SNAPSHOT` 기반 전체 동기화 |

---

## 2. 멱등성 (Idempotency)

### 2.1 requestId 규칙

모든 클라이언트 요청에 고유한 `requestId` 포함:

```json
{
  "type": "ACTION_REQUEST",
  "requestId": "client-abc-123-456",
  "payload": {
    "tableId": "table-1",
    "actionType": "raise",
    "amount": 100
  }
}
```

### 2.2 requestId 생성 규칙

```typescript
// 클라이언트 측 생성
const requestId = `${clientId}-${Date.now()}-${randomString(6)}`;

// 예시: "user123-1704067200000-a1b2c3"
```

### 2.3 서버 측 중복 감지

```python
# 중복 감지 키
idempotency_key = f"{table_id}:{user_id}:{request_id}"

# Redis에 저장 (TTL: 5분)
if redis.exists(idempotency_key):
    return cached_response
else:
    result = process_action()
    redis.setex(idempotency_key, 300, serialize(result))
    return result
```

### 2.4 중복 요청 응답

동일 `requestId`로 재요청 시 동일한 결과 반환:

```json
{
  "type": "ACTION_RESULT",
  "requestId": "client-abc-123-456",
  "payload": {
    "success": true,
    "cached": true,
    "action": {
      "type": "raise",
      "amount": 100
    }
  }
}
```

---

## 3. 순서 보장 (Ordering)

### 3.1 stateVersion 규칙

| 규칙 | 설명 |
|------|------|
| 단조 증가 | 버전은 항상 1씩 증가 |
| 테이블 단위 | 각 테이블별 독립적 버전 |
| 모든 변경 포함 | 액션, 타임아웃, 시스템 이벤트 모두 |

### 3.2 클라이언트 버전 검증

```typescript
function handleStateUpdate(update: TableStateUpdate) {
  const { stateVersion, previousVersion } = update;
  
  // 정상: 연속된 버전
  if (previousVersion === localVersion) {
    applyUpdate(update);
    localVersion = stateVersion;
    return;
  }
  
  // 이미 적용된 업데이트 (무시)
  if (stateVersion <= localVersion) {
    console.log('Ignoring outdated update');
    return;
  }
  
  // 버전 갭 발생 → 스냅샷 요청
  if (previousVersion > localVersion) {
    requestSnapshot();
    return;
  }
}
```

### 3.3 서버 측 버전 관리

```python
class TableStateManager:
    def __init__(self, table_id: str):
        self.table_id = table_id
        self._version = 0
        self._lock = asyncio.Lock()
    
    async def apply_transition(
        self, 
        transition: StateTransition
    ) -> TableState:
        async with self._lock:
            self._version += 1
            new_state = transition.apply(self._state)
            new_state = replace(
                new_state, 
                state_version=self._version
            )
            self._state = new_state
            return new_state
```

---

## 4. 상태 복구 (Recovery)

### 4.1 스냅샷 요청 조건

| 조건 | 트리거 |
|------|--------|
| 버전 갭 | `previousVersion > localVersion` |
| 재접속 | WebSocket 재연결 완료 |
| 명시적 요청 | 클라이언트 수동 동기화 |
| 에러 복구 | `STATE_STALE_VERSION` 에러 수신 |

### 4.2 스냅샷 요청

```json
{
  "type": "REQUEST_SNAPSHOT",
  "requestId": "snap-req-001",
  "payload": {
    "tableId": "table-123",
    "currentVersion": 10
  }
}
```

### 4.3 스냅샷 응답

```json
{
  "type": "TABLE_SNAPSHOT",
  "payload": {
    "tableId": "table-123",
    "stateVersion": 15,
    // ... 전체 테이블 상태
  }
}
```

---

## 5. 클라이언트 구현 가이드

### 5.1 요청 큐 관리

```typescript
class RequestQueue {
  private pending = new Map<string, PendingRequest>();
  private timeout = 10000; // 10초
  
  async send(request: Request): Promise<Response> {
    const requestId = generateRequestId();
    request.requestId = requestId;
    
    return new Promise((resolve, reject) => {
      this.pending.set(requestId, {
        resolve,
        reject,
        timer: setTimeout(() => {
          this.pending.delete(requestId);
          reject(new TimeoutError());
        }, this.timeout)
      });
      
      this.ws.send(JSON.stringify(request));
    });
  }
  
  handleResponse(response: Response) {
    const pending = this.pending.get(response.requestId);
    if (pending) {
      clearTimeout(pending.timer);
      this.pending.delete(response.requestId);
      pending.resolve(response);
    }
  }
}
```

### 5.2 낙관적 UI 업데이트

```typescript
async function handleAction(action: Action) {
  // 1. 낙관적 UI 업데이트
  const optimisticState = applyOptimisticUpdate(action);
  renderState(optimisticState);
  
  // 2. 서버 요청
  try {
    const result = await sendAction(action);
    
    // 3. 서버 응답으로 상태 확정
    if (result.success) {
      // 서버 상태로 동기화
      syncWithServerState(result.newState);
    } else {
      // 롤백
      rollbackOptimisticUpdate();
      showError(result.error);
    }
  } catch (error) {
    rollbackOptimisticUpdate();
    showError('Network error');
  }
}
```

### 5.3 중복 클릭 방지

```typescript
class ActionButton {
  private processing = false;
  
  async onClick(action: Action) {
    if (this.processing) return;
    
    this.processing = true;
    this.disable();
    
    try {
      await sendAction(action);
    } finally {
      this.processing = false;
      // 버튼 활성화는 서버 응답 후 턴 상태에 따라
    }
  }
}
```

---

## 6. 서버 구현 가이드

### 6.1 테이블별 처리 큐

```python
class TableProcessor:
    """테이블별 단일 처리 루프"""
    
    def __init__(self, table_id: str):
        self.table_id = table_id
        self.queue = asyncio.Queue()
        self.task = asyncio.create_task(self._process_loop())
    
    async def _process_loop(self):
        while True:
            request = await self.queue.get()
            try:
                await self._process_request(request)
            except Exception as e:
                logger.error(f"Error processing request: {e}")
            finally:
                self.queue.task_done()
    
    async def submit(self, request: ActionRequest):
        await self.queue.put(request)
```

### 6.2 멱등성 키 저장소

```python
class IdempotencyStore:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.ttl = 300  # 5분
    
    async def check_and_set(
        self, 
        key: str, 
        result: ActionResult
    ) -> ActionResult | None:
        """
        키가 존재하면 캐시된 결과 반환
        없으면 결과 저장 후 None 반환
        """
        cached = await self.redis.get(key)
        if cached:
            return deserialize(cached)
        
        await self.redis.setex(key, self.ttl, serialize(result))
        return None
```

---

## 7. 에지 케이스 처리

### 7.1 동시 액션 요청

같은 유저가 동시에 여러 액션 요청 시:

```python
# 첫 번째 요청만 처리, 나머지는 중복으로 처리
async def process_action(request: ActionRequest):
    lock_key = f"action_lock:{table_id}:{user_id}"
    
    if not await redis.set(lock_key, "1", nx=True, ex=5):
        raise ConcurrentActionError()
    
    try:
        return await _do_process(request)
    finally:
        await redis.delete(lock_key)
```

### 7.2 타임아웃 중 액션 도착

```python
async def handle_turn_timeout(table_id: str, position: int):
    # 타임아웃 처리 전 마지막 확인
    async with table_lock:
        if table.current_turn != position:
            return  # 이미 액션 처리됨
        
        # 자동 폴드 처리
        await process_auto_fold(table_id, position)
```

### 7.3 재접속 중 핸드 종료

```python
async def handle_reconnect(user_id: str, table_id: str):
    # 항상 최신 스냅샷 전송
    snapshot = await get_table_snapshot(table_id, user_id)
    
    # 핸드가 종료되었으면 결과도 함께 전송
    if snapshot.hand and snapshot.hand.phase == "finished":
        await send_hand_result(user_id, snapshot.hand.result)
    
    await send_snapshot(user_id, snapshot)
```

---

## 8. 모니터링

### 8.1 주요 메트릭

| 메트릭 | 설명 |
|--------|------|
| `idempotency_cache_hit_rate` | 중복 요청 비율 |
| `version_gap_count` | 버전 갭 발생 횟수 |
| `snapshot_request_rate` | 스냅샷 요청 비율 |
| `action_processing_time_p95` | 액션 처리 시간 |

### 8.2 알림 조건

| 조건 | 임계값 | 액션 |
|------|--------|------|
| 높은 중복 요청 | > 10% | 클라이언트 버그 조사 |
| 잦은 버전 갭 | > 5% | 네트워크/서버 점검 |
| 높은 스냅샷 요청 | > 20% | 성능 최적화 필요 |

---

## 관련 문서

- [20-realtime-protocol-v1.md](./20-realtime-protocol-v1.md) - 실시간 프로토콜
- [21-error-codes-v1.md](./21-error-codes-v1.md) - 에러 코드 명세
- [40-reconnect-recovery.md](./40-reconnect-recovery.md) - 재접속 복구 상세
