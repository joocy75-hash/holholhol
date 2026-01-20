# 테스트 플랜

> MVP 릴리즈를 위한 테스트 전략 및 체크리스트

---

## 1. 테스트 전략

### 1.1 테스트 피라미드

```
        ┌─────────┐
        │  E2E    │  10%
        ├─────────┤
        │ 통합    │  30%
        ├─────────┤
        │ 유닛    │  60%
        └─────────┘
```

### 1.2 커버리지 목표

| 영역 | 목표 | 우선순위 |
|------|------|---------|
| 게임 엔진 | 90%+ | P0 |
| API 핸들러 | 80%+ | P1 |
| WebSocket | 70%+ | P1 |
| UI 컴포넌트 | 70%+ | P2 |

---

## 2. 유닛 테스트

### 2.1 게임 엔진 테스트

```python
# tests/unit/engine/test_actions.py

class TestFoldAction:
    def test_fold_removes_player_from_hand(self):
        """폴드 시 플레이어가 핸드에서 제외된다"""
        pass
    
    def test_fold_preserves_stack(self):
        """폴드 시 스택은 유지된다"""
        pass
    
    def test_fold_not_allowed_when_not_turn(self):
        """턴이 아닐 때 폴드 불가"""
        pass

class TestRaiseAction:
    def test_raise_increases_pot(self):
        """레이즈 시 팟이 증가한다"""
        pass
    
    def test_raise_below_minimum_rejected(self):
        """최소 레이즈 미만은 거부된다"""
        pass
    
    def test_raise_above_stack_rejected(self):
        """스택 초과 레이즈는 거부된다"""
        pass

class TestShowdown:
    def test_best_hand_wins(self):
        """가장 좋은 핸드가 승리한다"""
        pass
    
    def test_split_pot_on_tie(self):
        """동점 시 팟을 나눈다"""
        pass
    
    def test_side_pot_distribution(self):
        """사이드 팟이 올바르게 분배된다"""
        pass
```

### 2.2 상태 모델 테스트

```python
# tests/unit/engine/test_state.py

class TestTableState:
    def test_state_is_immutable(self):
        """상태는 불변이다"""
        pass
    
    def test_version_increments_on_change(self):
        """변경 시 버전이 증가한다"""
        pass
    
    def test_snapshot_serialization(self):
        """스냅샷 직렬화/역직렬화가 정확하다"""
        pass
```

---

## 3. 통합 테스트

### 3.1 API 통합 테스트

```python
# tests/integration/test_api.py

class TestRoomAPI:
    async def test_create_room(self, client):
        """방 생성 API"""
        response = await client.post("/api/rooms", json={
            "name": "Test Room",
            "blinds": {"small": 10, "big": 20},
            "maxSeats": 6
        })
        assert response.status_code == 201
    
    async def test_join_room(self, client, room_id):
        """방 입장 API"""
        pass
    
    async def test_join_full_room_rejected(self, client, full_room_id):
        """가득 찬 방 입장 거부"""
        pass
```

### 3.2 WebSocket 통합 테스트

```python
# tests/integration/test_websocket.py

class TestWebSocketConnection:
    async def test_connect_with_valid_token(self, ws_client):
        """유효한 토큰으로 연결"""
        pass
    
    async def test_connect_with_invalid_token_rejected(self, ws_client):
        """유효하지 않은 토큰 거부"""
        pass
    
    async def test_heartbeat(self, ws_client):
        """하트비트 동작"""
        pass

class TestTableSubscription:
    async def test_subscribe_table(self, ws_client, table_id):
        """테이블 구독"""
        pass
    
    async def test_receive_snapshot_on_subscribe(self, ws_client, table_id):
        """구독 시 스냅샷 수신"""
        pass
    
    async def test_receive_updates(self, ws_client, table_id):
        """상태 업데이트 수신"""
        pass
```

---

## 4. E2E 테스트

### 4.1 핵심 시나리오

```typescript
// tests/e2e/game-flow.spec.ts

describe('Game Flow', () => {
  it('방 생성 → 입장 → 착석 → 핸드 시작', async () => {
    // 1. 로그인
    await login(player1);
    
    // 2. 방 생성
    const room = await createRoom({ blinds: '10/20', maxSeats: 6 });
    
    // 3. 입장
    await joinRoom(room.id, { buyIn: 1000 });
    
    // 4. 착석
    await takeSeat(0);
    
    // 5. 다른 플레이어 입장
    await login(player2);
    await joinRoom(room.id, { buyIn: 1000 });
    await takeSeat(1);
    
    // 6. 핸드 시작 확인
    await expect(page.locator('.hand-phase')).toHaveText('Preflop');
  });
  
  it('2~6명 턴 이동 정상', async () => {
    // 턴 순서 검증
  });
  
  it('콜/레이즈/폴드 기본 액션', async () => {
    // 각 액션 동작 검증
  });
  
  it('불가능 액션 거부', async () => {
    // 유효하지 않은 액션 거부 검증
  });
  
  it('핸드 종료/쇼다운 결과 브로드캐스트', async () => {
    // 쇼다운 결과 표시 검증
  });
});
```

### 4.2 재접속 시나리오

```typescript
// tests/e2e/reconnect.spec.ts

describe('Reconnect', () => {
  it('핸드 중 끊김 → 복구 → 상태 일치', async () => {
    // 1. 게임 진행 중
    await startHand();
    
    // 2. 연결 끊김 시뮬레이션
    await simulateDisconnect();
    
    // 3. 재연결
    await waitForReconnect();
    
    // 4. 상태 일치 확인
    await expect(page.locator('.pot')).toHaveText('$100');
    await expect(page.locator('.my-cards')).toBeVisible();
  });
});
```

### 4.3 중복 클릭 시나리오

```typescript
// tests/e2e/idempotency.spec.ts

describe('Idempotency', () => {
  it('동일 requestId 재전송 → 결과 1회 반영', async () => {
    // 1. 레이즈 버튼 더블 클릭
    await page.locator('.raise-btn').dblclick();
    
    // 2. 팟 증가 1회만 확인
    await expect(page.locator('.pot')).toHaveText('$120');
  });
});
```

### 4.4 관전 시나리오

```typescript
// tests/e2e/spectate.spec.ts

describe('Spectate', () => {
  it('테이블 스냅샷/업데이트 정상 수신', async () => {
    // 1. 관전 모드로 입장
    await spectateTable(tableId);
    
    // 2. 스냅샷 수신 확인
    await expect(page.locator('.table')).toBeVisible();
    
    // 3. 홀카드 숨김 확인
    await expect(page.locator('.hole-cards')).not.toBeVisible();
    
    // 4. 업데이트 수신 확인
    await waitForStateUpdate();
    await expect(page.locator('.pot')).toHaveText('$100');
  });
});
```

---

## 5. MVP 릴리즈 체크리스트

### 5.1 필수 통과 시나리오 (2026-01-12 업데이트)

```markdown
## 백엔드 테스트 현황
[x] 단위 테스트 179개 통과
[x] 서비스 테스트 (Rake, VIP) 통과
[ ] 통합 테스트 - pydantic config 경고 수정 필요

## E2E 시나리오
[ ] 방 생성 → 입장 → 착석 → 핸드 시작
[ ] 2~6명 턴 이동 정상
[ ] 콜/레이즈/폴드 기본 액션, 불가능 액션 거부
[ ] 핸드 종료/쇼다운 결과 브로드캐스트
[ ] 재접속: 핸드 중 끊김 → 복구 → 상태 일치
[ ] 중복 클릭: 동일 requestId 재전송 → 결과 1회 반영
[ ] 관전: 테이블 스냅샷/업데이트 정상 수신
```

### 5.2 품질 게이트

| 항목 | 기준 |
|------|------|
| 유닛 테스트 | 100% 통과 |
| 통합 테스트 | 100% 통과 |
| E2E 테스트 | 100% 통과 |
| 커버리지 | 엔진 90%+, API 80%+ |
| 린트 | 에러 0개 |
| 타입 체크 | 에러 0개 |

---

## 6. 테스트 실행

### 6.1 로컬 실행

```bash
# 백엔드 테스트
cd backend
pytest                          # 전체 테스트
pytest tests/unit/              # 유닛 테스트만
pytest --cov=app --cov-report=html  # 커버리지 포함

# 프론트엔드 테스트
cd frontend
pnpm test                       # 유닛 테스트
pnpm test:e2e                   # E2E 테스트
```

### 6.2 CI 실행

```yaml
# .github/workflows/test.yml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Backend tests
        run: |
          cd backend
          pytest --cov=app --cov-fail-under=80
      
      - name: Frontend tests
        run: |
          cd frontend
          pnpm test
          pnpm test:e2e
```

---

## 관련 문서

- [51-observability.md](./51-observability.md) - 관측성 설계
- [52-deploy-staging.md](./52-deploy-staging.md) - 배포 가이드
- [03-dev-workflow.md](./03-dev-workflow.md) - 개발 워크플로
