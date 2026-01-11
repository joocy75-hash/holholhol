# 엔진 레이어 아키텍처

> PokerKit 기반 게임 엔진 레이어 설계 문서

---

## 1. 개요

### 1.1 목적

PokerKit 라이브러리를 래핑하여 웹서비스에 적합한 게임 엔진 레이어를 구축한다.

### 1.2 설계 원칙

| 원칙 | 설명 |
|------|------|
| **서버 Authoritative** | 모든 게임 판정은 서버에서만 수행 |
| **상태 불변성** | 상태 변경은 새 상태 객체 생성으로 처리 |
| **직렬화 가능** | 모든 상태는 JSON 직렬화/역직렬화 가능 |
| **버전 추적** | 모든 상태 변경에 단조 증가 버전 부여 |

---

## 2. 레이어 구조

```
┌─────────────────────────────────────────────────────────────┐
│                    Table Orchestrator                        │
│         (테이블 라이프사이클, 플레이어 관리, 브로드캐스트)       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Engine Layer                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ ActionProc  │  │ StateManager│  │ SnapshotSerializer  │  │
│  │ (액션 처리)  │  │ (상태 관리) │  │ (직렬화/역직렬화)    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    PokerKit Core                             │
│         (게임 규칙, 핸드 평가, 팟 계산)                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 컴포넌트 상세

### 3.1 PokerKitWrapper

PokerKit 라이브러리의 직접 의존성을 캡슐화한다.

```python
class PokerKitWrapper:
    """PokerKit 라이브러리 래퍼"""
    
    def create_game(self, config: GameConfig) -> PokerKitState:
        """새 게임 상태 생성"""
        pass
    
    def apply_action(
        self, 
        state: PokerKitState, 
        action: PlayerAction
    ) -> PokerKitState:
        """액션 적용 후 새 상태 반환"""
        pass
    
    def get_valid_actions(
        self, 
        state: PokerKitState, 
        player_index: int
    ) -> list[ValidAction]:
        """현재 플레이어의 유효한 액션 목록"""
        pass
    
    def evaluate_hand(
        self, 
        state: PokerKitState
    ) -> HandResult:
        """핸드 결과 평가 (쇼다운)"""
        pass
```

### 3.2 StateManager

게임 상태의 생성, 변환, 버전 관리를 담당한다.

```python
class StateManager:
    """게임 상태 관리자"""
    
    def __init__(self, wrapper: PokerKitWrapper):
        self._wrapper = wrapper
        self._version = 0
    
    def create_initial_state(
        self, 
        table_config: TableConfig,
        players: list[Player]
    ) -> TableState:
        """초기 테이블 상태 생성"""
        pass
    
    def transition(
        self, 
        current: TableState, 
        action: PlayerAction
    ) -> tuple[TableState, StateTransition]:
        """상태 전이 수행, 새 상태와 전이 정보 반환"""
        pass
    
    def get_player_view(
        self, 
        state: TableState, 
        player_id: str
    ) -> PlayerViewState:
        """특정 플레이어 시점의 상태 (홀카드 마스킹)"""
        pass
    
    def get_spectator_view(
        self, 
        state: TableState
    ) -> SpectatorViewState:
        """관전자 시점의 상태 (모든 홀카드 마스킹)"""
        pass
```

### 3.3 ActionProcessor

액션 검증 및 처리를 담당한다.

```python
class ActionProcessor:
    """액션 처리기"""
    
    def validate_action(
        self, 
        state: TableState, 
        player_id: str,
        action: ActionRequest
    ) -> ValidationResult:
        """액션 유효성 검증"""
        pass
    
    def process_action(
        self, 
        state: TableState,
        player_id: str,
        action: ActionRequest,
        request_id: str
    ) -> ActionResult:
        """액션 처리 및 결과 반환"""
        pass
```

### 3.4 SnapshotSerializer

상태의 직렬화/역직렬화를 담당한다.

```python
class SnapshotSerializer:
    """스냅샷 직렬화"""
    
    def serialize(self, state: TableState) -> dict:
        """상태를 JSON 직렬화 가능한 dict로 변환"""
        pass
    
    def deserialize(self, data: dict) -> TableState:
        """dict에서 상태 복원"""
        pass
    
    def create_snapshot(
        self, 
        state: TableState,
        view_type: ViewType
    ) -> TableSnapshot:
        """특정 뷰 타입의 스냅샷 생성"""
        pass
```

---

## 4. 데이터 흐름

### 4.1 액션 처리 흐름

```
1. Client → ACTION_REQUEST (requestId, action, amount?)
2. Orchestrator → ActionProcessor.validate_action()
3. ActionProcessor → StateManager.transition()
4. StateManager → PokerKitWrapper.apply_action()
5. PokerKitWrapper → 새 PokerKit 상태 반환
6. StateManager → TableState 생성 (version++)
7. Orchestrator → 브로드캐스트 (TABLE_STATE_UPDATE)
8. Client ← ACTION_RESULT + TABLE_STATE_UPDATE
```

### 4.2 재접속 흐름

```
1. Client → 재연결
2. Orchestrator → StateManager.get_player_view()
3. StateManager → SnapshotSerializer.create_snapshot()
4. Client ← TABLE_SNAPSHOT (전체 상태)
```

---

## 5. 상태 버전 관리

### 5.1 버전 정책

| 규칙 | 설명 |
|------|------|
| 단조 증가 | 버전은 항상 증가만 함 |
| 테이블 단위 | 각 테이블별 독립적 버전 |
| 모든 변경 포함 | 액션, 타임아웃, 시스템 이벤트 모두 버전 증가 |

### 5.2 버전 활용

```python
# 클라이언트 상태 검증
if client_version < server_version:
    # 클라이언트 상태가 오래됨 → 스냅샷 전송
    send_snapshot()
elif client_version > server_version:
    # 비정상 상태 → 에러 처리
    raise StaleStateError()
```

---

## 6. 에러 처리

### 6.1 엔진 레벨 에러

| 에러 | 설명 | 처리 |
|------|------|------|
| `InvalidActionError` | 유효하지 않은 액션 | ACTION_RESULT rejected |
| `NotYourTurnError` | 턴이 아닌 플레이어 액션 | ACTION_RESULT rejected |
| `InsufficientStackError` | 스택 부족 | ACTION_RESULT rejected |
| `GameStateError` | 게임 상태 오류 | 로깅 + 복구 시도 |

### 6.2 에러 응답 형식

```python
@dataclass
class ActionResult:
    success: bool
    request_id: str
    error_code: str | None = None
    error_message: str | None = None
    new_state_version: int | None = None
```

---

## 7. 확장 포인트

### 7.1 게임 변형 지원

```python
class GameVariant(Enum):
    TEXAS_HOLDEM = "texas_holdem"
    OMAHA = "omaha"  # 향후 지원
    STUD = "stud"    # 향후 지원

class PokerKitWrapper:
    def create_game(
        self, 
        config: GameConfig,
        variant: GameVariant = GameVariant.TEXAS_HOLDEM
    ) -> PokerKitState:
        pass
```

### 7.2 이벤트 훅

```python
class EngineEventHook(Protocol):
    def on_action_processed(
        self, 
        action: PlayerAction, 
        result: ActionResult
    ) -> None: ...
    
    def on_hand_completed(
        self, 
        result: HandResult
    ) -> None: ...
    
    def on_state_transition(
        self, 
        old_state: TableState, 
        new_state: TableState
    ) -> None: ...
```

---

## 8. 성능 고려사항

### 8.1 상태 복사 최적화

- 불변 상태 사용으로 안전한 공유 가능
- 필요시 copy-on-write 패턴 적용

### 8.2 직렬화 최적화

- 자주 사용되는 스냅샷 캐싱
- 델타 업데이트 지원 (향후)

---

## 관련 문서

- [11-engine-state-model.md](./11-engine-state-model.md) - 상태 모델 상세
- [ADR-0001-pokerkit-core.md](./ADR/ADR-0001-pokerkit-core.md) - PokerKit 채택 결정
- [20-realtime-protocol-v1.md](./20-realtime-protocol-v1.md) - 실시간 프로토콜
