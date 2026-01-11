# 재접속 및 복구 규칙

> 연결 끊김 시 상태 복구 메커니즘

---

## 1. 개요

### 1.1 목표

- 연결 끊김 후 5초 내 재연결
- 재연결 후 즉시 플레이 재개 가능
- 핸드 진행 중 끊김 시 상태 100% 복구

### 1.2 시나리오

| 시나리오 | 복구 방식 |
|---------|----------|
| 일시적 네트워크 끊김 | 자동 재연결 + 스냅샷 |
| 브라우저 새로고침 | 세션 복구 + 스냅샷 |
| 앱 재시작 | 로그인 + 스냅샷 |
| 장시간 끊김 (> 60초) | 자동 폴드 후 복구 |

---

## 2. 재연결 프로토콜

### 2.1 클라이언트 재연결 흐름

```
1. 연결 끊김 감지
   └── onclose / onerror 이벤트

2. 재연결 시도 (Exponential Backoff)
   └── 1초 → 2초 → 4초 → 8초 → ... → 최대 30초

3. 재연결 성공
   └── 서버에 세션 정보 전송

4. 서버 응답
   └── CONNECTION_STATE (reconnecting)
   └── TABLE_SNAPSHOT (전체 상태)
   └── CONNECTION_STATE (recovered)

5. 클라이언트 상태 복구
   └── 로컬 상태를 서버 스냅샷으로 교체
   └── UI 업데이트
   └── 액션 버튼 활성화
```

### 2.2 재연결 파라미터

```typescript
const RECONNECT_CONFIG = {
  initialDelay: 1000,      // 1초
  maxDelay: 30000,         // 30초
  maxAttempts: 10,         // 최대 10회
  backoffMultiplier: 2,    // 지수 증가
  jitter: 0.1,             // 10% 랜덤 지터
};
```

### 2.3 재연결 구현

```typescript
class ReconnectManager {
  private attempts = 0;
  private delay = RECONNECT_CONFIG.initialDelay;
  
  async reconnect(): Promise<boolean> {
    while (this.attempts < RECONNECT_CONFIG.maxAttempts) {
      this.attempts++;
      
      try {
        await this.connect();
        this.reset();
        return true;
      } catch (error) {
        await this.wait(this.getDelay());
        this.delay = Math.min(
          this.delay * RECONNECT_CONFIG.backoffMultiplier,
          RECONNECT_CONFIG.maxDelay
        );
      }
    }
    
    return false;
  }
  
  private getDelay(): number {
    const jitter = this.delay * RECONNECT_CONFIG.jitter;
    return this.delay + (Math.random() * jitter * 2 - jitter);
  }
}
```

---

## 3. 서버 측 복구 처리

### 3.1 세션 복구

```python
async def handle_reconnect(
    websocket: WebSocket,
    session_id: str,
    user_id: str
) -> None:
    # 1. 세션 유효성 확인
    session = await session_store.get(session_id)
    if not session or session.user_id != user_id:
        raise AuthenticationError()
    
    # 2. 이전 연결 정리
    await connection_manager.close_previous(user_id)
    
    # 3. 새 연결 등록
    await connection_manager.register(websocket, user_id)
    
    # 4. 구독 채널 복구
    for table_id in session.subscribed_tables:
        await table_manager.resubscribe(user_id, table_id)
    
    # 5. 스냅샷 전송
    for table_id in session.subscribed_tables:
        snapshot = await get_table_snapshot(table_id, user_id)
        await send_event(websocket, "TABLE_SNAPSHOT", snapshot)
```

### 3.2 Grace Period

```python
RECONNECT_GRACE_PERIOD = 60  # 초

async def handle_disconnect(user_id: str, table_id: str):
    # 즉시 폴드하지 않고 대기
    await asyncio.sleep(RECONNECT_GRACE_PERIOD)
    
    # 재연결 확인
    if not await is_connected(user_id):
        # 자동 폴드 처리
        await auto_fold(table_id, user_id)
```

---

## 4. 클라이언트 UI 처리

### 4.1 연결 상태 표시

| 상태 | UI | 사용자 액션 |
|------|-----|-----------|
| Connected | 없음 | 정상 플레이 |
| Reconnecting | 상단 배너 "재연결 중..." | 대기 |
| Disconnected | 모달 "연결 끊김" | 재연결 버튼 |

### 4.2 재연결 중 UI

```typescript
function showReconnectingUI() {
  // 1. 배너 표시
  showBanner({
    type: 'warning',
    message: '재연결 중...',
    showSpinner: true
  });
  
  // 2. 액션 버튼 비활성화
  disableAllActions();
  
  // 3. 테이블 상태 유지 (낙관적)
  // 기존 UI 그대로 표시
}

function showDisconnectedUI() {
  // 1. 모달 표시
  showModal({
    title: '연결 끊김',
    message: '서버와의 연결이 끊어졌습니다.',
    actions: [
      { label: '재연결', onClick: reconnect },
      { label: '로비로', onClick: goToLobby }
    ]
  });
}
```

### 4.3 복구 완료 UI

```typescript
function showRecoveredUI() {
  // 1. 배너 숨김
  hideBanner();
  
  // 2. 성공 토스트
  showToast({
    type: 'success',
    message: '연결 복구됨'
  });
  
  // 3. 액션 버튼 활성화 (턴인 경우)
  if (isMyTurn) {
    enableActions(allowedActions);
  }
}
```

---

## 5. 핸드 진행 중 끊김 처리

### 5.1 내 턴에 끊김

```
1. 끊김 감지
2. 서버: 턴 타이머 계속 진행
3. 클라이언트: 재연결 시도
4. 재연결 성공 시:
   - 남은 시간 내 액션 가능
5. 재연결 실패 또는 타임아웃:
   - 자동 폴드
```

### 5.2 다른 플레이어 턴에 끊김

```
1. 끊김 감지
2. 클라이언트: 재연결 시도
3. 재연결 성공 시:
   - 스냅샷으로 현재 상태 동기화
   - 게임 진행 상황 확인
4. 재연결 실패:
   - 다음 내 턴까지 Grace Period
   - Grace Period 초과 시 자동 폴드
```

### 5.3 핸드 종료 후 끊김

```
1. 끊김 감지
2. 클라이언트: 재연결 시도
3. 재연결 성공 시:
   - 핸드 결과 확인
   - 다음 핸드 대기
```

---

## 6. 에지 케이스

### 6.1 재연결 중 핸드 종료

```python
async def send_snapshot(user_id: str, table_id: str):
    snapshot = await get_table_snapshot(table_id, user_id)
    
    # 핸드가 종료되었으면 결과도 함께 전송
    if snapshot.hand and snapshot.hand.phase == "finished":
        await send_event(user_id, "HAND_RESULT", snapshot.hand.result)
    
    await send_event(user_id, "TABLE_SNAPSHOT", snapshot)
```

### 6.2 재연결 중 새 핸드 시작

```python
# 스냅샷에 새 핸드 정보 포함
# 클라이언트는 스냅샷 기준으로 상태 복구
```

### 6.3 동시 재연결 (다중 탭)

```python
async def handle_reconnect(user_id: str, websocket: WebSocket):
    # 이전 연결 강제 종료
    await connection_manager.close_previous(user_id)
    
    # 새 연결만 유지
    await connection_manager.register(websocket, user_id)
```

---

## 7. 테스트 시나리오

### 7.1 필수 테스트

| 시나리오 | 예상 결과 |
|---------|----------|
| 내 턴에 끊김 → 5초 내 재연결 | 액션 가능 |
| 내 턴에 끊김 → 타임아웃 | 자동 폴드 |
| 다른 턴에 끊김 → 재연결 | 상태 동기화 |
| 핸드 종료 후 끊김 → 재연결 | 결과 확인 가능 |
| 60초 이상 끊김 | 자동 폴드 후 복구 |

### 7.2 테스트 방법

```typescript
// 네트워크 끊김 시뮬레이션
function simulateDisconnect(duration: number) {
  websocket.close();
  setTimeout(() => {
    reconnect();
  }, duration);
}
```

---

## 관련 문서

- [41-state-consistency.md](./41-state-consistency.md) - 상태 일관성
- [42-timer-turn-rules.md](./42-timer-turn-rules.md) - 타이머/턴 규칙
- [20-realtime-protocol-v1.md](./20-realtime-protocol-v1.md) - 실시간 프로토콜
