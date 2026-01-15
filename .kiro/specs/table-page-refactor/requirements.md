# Requirements Document

## Introduction

테이블 페이지(`frontend/src/app/table/[id]/page.tsx`)가 4000줄 이상으로 비대해져 유지보수가 어려운 상황입니다. 이미 `frontend/src/components/table/` 폴더에 분리된 컴포넌트들이 존재하지만, page.tsx에서 이를 사용하지 않고 내부에 중복 정의하고 있습니다. 이 리팩토링은 기존 기능을 100% 유지하면서 코드를 정리하는 것을 목표로 합니다.

## Glossary

- **Table_Page**: 포커 테이블 화면을 렌더링하는 Next.js 페이지 컴포넌트 (`frontend/src/app/table/[id]/page.tsx`)
- **Table_Components**: `frontend/src/components/table/` 폴더에 분리된 재사용 가능한 컴포넌트들
- **Inline_Component**: page.tsx 내부에 직접 정의된 컴포넌트
- **WebSocket_Handler**: 서버와의 실시간 통신을 처리하는 이벤트 핸들러 함수들
- **Game_State**: 포커 게임의 현재 상태 (플레이어, 카드, 팟, 턴 등)

## Requirements

### Requirement 1: 중복 컴포넌트 제거

**User Story:** As a developer, I want to remove duplicate component definitions from page.tsx, so that the codebase is easier to maintain and has a single source of truth.

#### Acceptance Criteria

1. WHEN the Table_Page is loaded, THE System SHALL use components from Table_Components instead of Inline_Components
2. THE System SHALL remove all Inline_Component definitions that have equivalent implementations in Table_Components
3. WHEN removing Inline_Components, THE System SHALL ensure all props and functionality are preserved
4. IF an Inline_Component has additional features not in Table_Components, THEN THE System SHALL update Table_Components to include those features before removal

### Requirement 2: WebSocket 핸들러 분리

**User Story:** As a developer, I want WebSocket event handlers to be organized in a separate module, so that the page component focuses on rendering logic.

#### Acceptance Criteria

1. THE System SHALL extract WebSocket event handlers into a custom hook (`useTableWebSocket`)
2. WHEN extracting handlers, THE System SHALL maintain all existing event subscriptions and state updates
3. THE System SHALL ensure the custom hook returns all necessary state and callbacks for the page component
4. WHEN the Table_Page mounts, THE System SHALL establish WebSocket connection through the custom hook

### Requirement 3: 게임 상태 관리 분리

**User Story:** As a developer, I want game state management to be centralized, so that state updates are predictable and testable.

#### Acceptance Criteria

1. THE System SHALL extract game state management into a custom hook (`useGameState`)
2. WHEN game state changes, THE System SHALL update all dependent UI components correctly
3. THE System SHALL preserve all existing state transitions (waiting → preflop → flop → turn → river → showdown)
4. IF showdown animation is in progress, THEN THE System SHALL queue incoming state updates as before

### Requirement 4: 기능 동등성 보장

**User Story:** As a user, I want the refactored table page to work exactly the same as before, so that my gaming experience is not affected.

#### Acceptance Criteria

1. WHEN a player joins a table, THE System SHALL display the buy-in modal and process seat assignment
2. WHEN cards are dealt, THE System SHALL show dealing animation from center to each player
3. WHEN it is my turn, THE System SHALL display action buttons (fold, check, call, raise) with correct amounts
4. WHEN a player takes an action, THE System SHALL display the action label and update chips
5. WHEN showdown occurs, THE System SHALL reveal cards sequentially and announce winners
6. WHEN the timer expires, THE System SHALL auto-fold or auto-check based on allowed actions
7. THE System SHALL maintain all existing sound effects and visual animations

### Requirement 5: 코드 품질 개선

**User Story:** As a developer, I want the refactored code to follow best practices, so that future development is easier.

#### Acceptance Criteria

1. THE System SHALL reduce page.tsx to under 500 lines
2. THE System SHALL ensure all extracted modules have proper TypeScript types
3. THE System SHALL remove all eslint-disable comments where possible
4. WHEN extracting code, THE System SHALL add JSDoc comments for complex functions
5. THE System SHALL ensure no circular dependencies between modules

### Requirement 6: 점진적 리팩토링

**User Story:** As a developer, I want to refactor incrementally, so that I can verify each change works correctly before proceeding.

#### Acceptance Criteria

1. THE System SHALL refactor one component at a time
2. AFTER each component refactor, THE System SHALL verify the table page still functions correctly
3. IF a refactor introduces a bug, THEN THE System SHALL be able to revert to the previous working state
4. THE System SHALL maintain backward compatibility with existing E2E tests
