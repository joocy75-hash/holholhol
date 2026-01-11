# 상태 일관성 규칙

> 클라이언트-서버 상태 동기화 메커니즘

---

## 1. 개요

### 1.1 일관성 보장 원칙

| 원칙 | 설명 |
|------|------|
| 서버 Authoritative | 서버 상태가 항상 정답 |
| 버전 기반 검증 | stateVersion으로 순서 보장 |
| 스냅샷 복구 | 불일치 시 전체 상태 재동기화 |

### 1.2 불일치 발생 원인

| 원인 | 빈도 | 영향 |
|------|------|------|
| 네트워크 지연 | 높음 | 일시적 불일치 |
| 패킷 손실 | 중간 | 이벤트 누락 |
| 역순 도착 | 낮음 | 상태 역전 |
| 클라이언트 버그 | 낮음 | 영구 불일치 |

---

## 2. 버전 관리

### 2.1 stateVersion 규칙

```python
class TableState:
    state_version: int  # 단조 증가
    
    def apply_transition(self, transition: Transition) -> "TableState":
        return replace(
            self,
            state_version=self.state_version + 1,
            **transition.changes
        )
```

### 2.2 버전 증가 이벤트

| 이벤트 | 버전 증가 |
|--------|----------|
| 플레이어 액션 | +1 |
| 타임아웃 폴드 | +1 |
| Phase 전환 | +1 |
| 핸드 종료 | +1 |
| 플레이어 입장/퇴장 | +1 |

### 2.3 클라이언트 버전 검증

```typescript
function handleStateUpdate(update: TableStateUpdate) {
  const { stateVersion, previousVersion } = update;
  
  // Case 1: 정상 - 연속된 버전
  if (previousVersion === localVersion) {
    applyUpdate(update);
    localVersion = stateVersion;
    return;
  }
  
  // Case 2: 중복 - 이미 적용된 업데이트
  if (stateVersion <= localVersion) {
    console.log('Ignoring duplicate update');
    return;
  }
  
  // Case 3: 갭 - 이벤트 누락
  if (previousVersion > localVersion) {
    console.log('Version gap detected, requesting snapshot');
    requestSnapshot();
    return;
  }
}
```

---

## 3. 스냅샷 동기화

### 3.1 스냅샷 요청 조건

| 조건 | 트리거 |
|------|--------|
| 버전 갭 | `previousVersion > localVersion` |
| 재접속 | WebSocket 재연결 |
| 명시적 요청 | 사용자 새로고침 |
| 에러 복구 | STATE_STALE_VERSION 에러 |

### 3.2 스냅샷 요청/응답

```typescript
// 요청
{
  type: "REQUEST_SNAPSHOT",
  payload: {
    tableId: "table-123",
    currentVersion: 10
  }
}

// 응답
{
  type: "TABLE_SNAPSHOT",
  payload: {
    tableId: "table-123",
    stateVersion: 15,
    // ... 전체 상태
  }
}
```

### 3.3 스냅샷 적용

```typescript
function applySnapshot(snapshot: TableSnapshot) {
  // 1. 로컬 상태 완전 교체
  tableState = snapshot;
  localVersion = snapshot.stateVersion;
  
  // 2. UI 전체 리렌더링
  renderTable(tableState);
  
  // 3. 진행 중인 요청 취소
  pendingRequests.clear();
  
  // 4. 액션 버튼 상태 업데이트
  updateActionButtons(tableState.allowedActions);
}
```

---

## 4. 낙관적 업데이트

### 4.1 낙관적 UI 패턴

```typescript
async function handleAction(action: Action) {
  // 1. 낙관적 업데이트 적용
  const optimisticState = applyOptimistic(action);
  renderTable(optimisticState);
  disableActionButtons();
  
  // 2. 서버 요청
  try {
    const result = await sendAction(action);
    
    if (result.success) {
      // 서버 상태로 확정
      // (TABLE_STATE_UPDATE 이벤트로 처리됨)
    } else {
      // 롤백
      rollbackOptimistic();
      showError(result.error);
    }
  } catch (error) {
    rollbackOptimistic();
    showError('Network error');
  }
}
```

### 4.2 롤백 처리

```typescript
class OptimisticUpdateManager {
  private originalState: TableState | null = null;
  
  apply(action: Action): TableState {
    this.originalState = tableState;
    return this.computeOptimistic(action);
  }
  
  rollback(): void {
    if (this.originalState) {
      tableState = this.originalState;
      renderTable(tableState);
      this.originalState = null;
    }
  }
  
  confirm(): void {
    this.originalState = null;
  }
}
```

---

## 5. 충돌 해결

### 5.1 충돌 시나리오

| 시나리오 | 해결 방식 |
|---------|----------|
| 동시 액션 | 서버 순서 우선 |
| 타임아웃 vs 액션 | 먼저 도착한 것 처리 |
| 중복 요청 | 멱등성 키로 중복 제거 |

### 5.2 서버 측 충돌 해결

```python
async def process_action(
    table_id: str,
    user_id: str,
    action: ActionRequest
) -> ActionResult:
    async with table_lock(table_id):
        table = await get_table(table_id)
        
        # 턴 검증
        if table.current_turn_user_id != user_id:
            return ActionResult(
                success=False,
                error_code="NOT_YOUR_TURN"
            )
        
        # 액션 처리
        new_state = table.apply_action(action)
        await save_table(new_state)
        
        return ActionResult(success=True)
```

---

## 6. 모니터링

### 6.1 일관성 메트릭

| 메트릭 | 설명 | 임계값 |
|--------|------|--------|
| `version_gap_rate` | 버전 갭 발생률 | < 5% |
| `snapshot_request_rate` | 스냅샷 요청률 | < 10% |
| `rollback_rate` | 롤백 발생률 | < 1% |
| `sync_latency_p95` | 동기화 지연 | < 500ms |

### 6.2 알림 조건

```yaml
alerts:
  - name: high_version_gap_rate
    condition: version_gap_rate > 0.1
    severity: warning
    
  - name: high_snapshot_rate
    condition: snapshot_request_rate > 0.2
    severity: critical
```

---

## 관련 문서

- [40-reconnect-recovery.md](./40-reconnect-recovery.md) - 재접속 복구
- [42-timer-turn-rules.md](./42-timer-turn-rules.md) - 타이머/턴 규칙
- [22-idempotency-ordering.md](./22-idempotency-ordering.md) - 멱등성/순서
