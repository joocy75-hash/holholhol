/**
 * Table Page Custom Hooks
 *
 * page.tsx에서 분리된 커스텀 훅들을 export합니다.
 * - useTableActions: 플레이어 액션 핸들러 (fold, check, call, raise, all-in)
 * - useGameState: 게임 상태 관리 (seats, cards, pot, phase 등)
 * - useTableWebSocket: WebSocket 연결 및 이벤트 핸들링
 */

export { useTableActions } from './useTableActions';
export { useGameState } from './useGameState';
export { useTableWebSocket } from './useTableWebSocket';
