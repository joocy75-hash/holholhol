# Design Document: Table Page Refactoring

## Overview

`frontend/src/app/table/[id]/page.tsx` 파일이 4000줄 이상으로 비대해져 유지보수가 어려운 상황입니다. 이미 `frontend/src/components/table/` 폴더에 분리된 컴포넌트들이 존재하지만, page.tsx에서 이를 사용하지 않고 내부에 중복 정의하고 있습니다.

### 현재 문제점

1. **중복 컴포넌트**: page.tsx 내부에 정의된 컴포넌트들이 `components/table/`에 이미 존재
2. **거대한 단일 파일**: 4000줄 이상의 코드가 한 파일에 집중
3. **혼재된 관심사**: UI 렌더링, WebSocket 통신, 게임 상태 관리가 모두 한 곳에
4. **테스트 어려움**: 개별 로직을 단위 테스트하기 어려움

### 리팩토링 전략

**점진적 접근**: 한 번에 모든 것을 바꾸지 않고, 단계별로 안전하게 진행

1. **Phase 1**: 백업 생성 및 분리된 컴포넌트 import로 교체
2. **Phase 2**: WebSocket 핸들러를 커스텀 훅으로 분리
3. **Phase 3**: 게임 상태 관리를 커스텀 훅으로 분리
4. **Phase 4**: 최종 정리 및 검증

## Architecture

### 현재 구조

```
frontend/src/app/table/[id]/page.tsx (4000+ lines)
├── Interfaces (Card, SeatInfo, TableConfig, Player, GameState)
├── Utility Functions (parseCard, parseCards, isSameCard, isCardInBestFive)
├── Components (PlayingCard, FlippableCard, DealingAnimation, PlayerSeat, BettingChips, BuyInModal, DevAdminPanel)
├── Constants (SEAT_POSITIONS, CHIP_POSITIONS, POT_POSITION, ACTION_LABELS)
├── Custom Hooks (useAnimatedNumber)
└── TablePage Component
    ├── 50+ useState declarations
    ├── 20+ WebSocket event handlers
    ├── Multiple useCallback/useMemo
    └── Complex JSX rendering
```

### 목표 구조

```
frontend/src/app/table/[id]/page.tsx (~300 lines)
├── Import statements
├── TablePage Component
│   ├── Custom hooks usage
│   └── Clean JSX rendering

frontend/src/components/table/ (기존 컴포넌트 활용)
├── PlayerSeat.tsx ✓
├── BuyInModal.tsx ✓
├── BettingChips.tsx ✓
├── DealingAnimation.tsx ✓
├── DevAdminPanel.tsx ✓
├── PlayingCard.tsx ✓
├── CommunityCards.tsx ✓
├── PotDisplay.tsx ✓
├── GameInfo.tsx ✓
├── TimerDisplay.tsx ✓
├── ActionButtons.tsx ✓
└── index.ts ✓

frontend/src/hooks/table/ (새로 생성)
├── useTableWebSocket.ts (WebSocket 핸들러 분리)
├── useGameState.ts (게임 상태 관리)
├── useTableActions.ts (액션 핸들러)
└── index.ts
```

## Components and Interfaces

### 기존 분리된 컴포넌트 (재사용)

| 컴포넌트 | 파일 | 상태 |
|---------|------|------|
| PlayerSeat | `components/table/PlayerSeat.tsx` | ✓ 분리됨 |
| BuyInModal | `components/table/BuyInModal.tsx` | ✓ 분리됨 |
| BettingChips | `components/table/BettingChips.tsx` | ✓ 분리됨 |
| DealingAnimation | `components/table/DealingAnimation.tsx` | ✓ 분리됨 |
| DevAdminPanel | `components/table/DevAdminPanel.tsx` | ✓ 분리됨 |
| PlayingCard | `components/table/PlayingCard.tsx` | ✓ 분리됨 |
| CommunityCards | `components/table/CommunityCards.tsx` | ✓ 분리됨 |
| PotDisplay | `components/table/PotDisplay.tsx` | ✓ 분리됨 |
| ActionButtons | `components/table/ActionButtons.tsx` | ✓ 분리됨 |

### 새로 생성할 커스텀 훅

#### useTableWebSocket

WebSocket 연결 및 이벤트 핸들링을 담당하는 훅

```typescript
interface UseTableWebSocketOptions {
  tableId: string;
  userId?: string;
  onStateUpdate: (state: Partial<GameState>) => void;
  onSeatsUpdate: (seats: SeatInfo[]) => void;
  onError: (error: string) => void;
}

interface UseTableWebSocketReturn {
  isConnected: boolean;
  sendAction: (action: ActionRequest) => void;
  sendSeatRequest: (buyIn: number) => void;
  sendLeaveRequest: () => void;
  // ... 기타 액션
}
```

#### useGameState

게임 상태 관리를 담당하는 훅

```typescript
interface UseGameStateReturn {
  gameState: GameState | null;
  seats: SeatInfo[];
  myPosition: number | null;
  myHoleCards: Card[];
  currentTurnPosition: number | null;
  allowedActions: AllowedAction[];
  // ... 기타 상태
  
  // 상태 업데이트 함수
  updateGameState: (partial: Partial<GameState>) => void;
  updateSeats: (seats: SeatInfo[]) => void;
  resetForNewHand: () => void;
}
```

#### useTableActions

액션 핸들러를 담당하는 훅

```typescript
interface UseTableActionsReturn {
  handleFold: () => void;
  handleCheck: () => void;
  handleCall: () => void;
  handleRaise: (amount: number) => void;
  handleAllIn: () => void;
  handleAutoFold: () => void;
  isActionPending: boolean;
}
```

## Data Models

### 기존 인터페이스 (types 파일로 분리)

```typescript
// frontend/src/types/table.ts

export interface Card {
  rank: string;
  suit: string;
}

export interface SeatInfo {
  position: number;
  player: {
    userId: string;
    nickname: string;
    avatarUrl?: string;
  } | null;
  stack: number;
  status: 'empty' | 'active' | 'waiting' | 'folded' | 'sitting_out' | 'all_in';
  betAmount: number;
  totalBet: number;
}

export interface TableConfig {
  maxSeats: number;
  smallBlind: number;
  bigBlind: number;
  minBuyIn: number;
  maxBuyIn: number;
  turnTimeoutSeconds: number;
}

export interface Player {
  id: string;
  username: string;
  chips: number;
  cards: Card[];
  bet: number;
  folded: boolean;
  isActive: boolean;
  seatIndex: number;
  hasCards?: boolean;
  isWinner?: boolean;
  winAmount?: number;
  winHandRank?: string;
}

export interface GameState {
  tableId: string;
  players: Player[];
  communityCards: Card[];
  pot: number;
  currentPlayer: string | null;
  phase: 'waiting' | 'preflop' | 'flop' | 'turn' | 'river' | 'showdown';
  smallBlind: number;
  bigBlind: number;
  minRaise: number;
  currentBet: number;
}

export interface AllowedAction {
  type: string;
  amount?: number;
  minAmount?: number;
  maxAmount?: number;
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: 기능 동등성 (Functional Equivalence)

*For any* user interaction (joining table, taking action, leaving table), the refactored page SHALL produce identical server communication and UI state changes as the original implementation.

**Validates: Requirements 1.3, 4.1-4.7**

### Property 2: 상태 관리 일관성 (State Management Consistency)

*For any* WebSocket message or state update, the refactored hooks SHALL produce identical state changes as the original inline handlers, including proper handling of showdown animation blocking.

**Validates: Requirements 2.2, 3.2, 3.3, 3.4**

### Property 3: E2E 테스트 호환성 (E2E Test Compatibility)

*For any* existing E2E test case, the refactored page SHALL pass with identical behavior, ensuring backward compatibility.

**Validates: Requirements 6.4**

## Error Handling

### 롤백 전략

1. **백업 파일 생성**: 리팩토링 전 원본 파일을 `page.backup.tsx`로 복사
2. **단계별 검증**: 각 단계 완료 후 E2E 테스트 실행
3. **Git 커밋**: 각 단계를 별도 커밋으로 관리하여 필요시 revert 가능

### 에러 처리

- WebSocket 연결 실패 시 기존과 동일한 에러 메시지 표시
- 액션 실패 시 기존과 동일한 에러 처리 로직 유지
- 컴포넌트 에러 시 ErrorBoundary로 격리

## Testing Strategy

### 단위 테스트

- 새로 생성되는 커스텀 훅에 대한 단위 테스트
- 상태 업데이트 로직 검증

### 통합 테스트

- 기존 E2E 테스트 스위트 실행
- 모든 테스트가 통과해야 리팩토링 완료로 간주

### 수동 테스트 체크리스트

1. 테이블 입장 및 바이인
2. 카드 딜링 애니메이션
3. 액션 버튼 동작 (폴드, 체크, 콜, 레이즈, 올인)
4. 타이머 및 자동 폴드
5. 쇼다운 애니메이션
6. 칩 수집/분배 애니메이션
7. 재연결 처리

## Implementation Notes

### Phase 1: 컴포넌트 교체

1. 백업 파일 생성
2. 기존 분리된 컴포넌트 import
3. 인라인 컴포넌트 정의 제거
4. Props 호환성 확인 및 조정

### Phase 2: WebSocket 훅 분리

1. `useTableWebSocket` 훅 생성
2. 모든 WebSocket 이벤트 핸들러 이동
3. 상태 업데이트 콜백 연결
4. 기존 핸들러 코드 제거

### Phase 3: 게임 상태 훅 분리

1. `useGameState` 훅 생성
2. 모든 게임 관련 상태 이동
3. 상태 업데이트 함수 구현
4. 기존 상태 코드 제거

### Phase 4: 최종 정리

1. 불필요한 코드 제거
2. 타입 정리
3. 린트 에러 수정
4. 최종 테스트
