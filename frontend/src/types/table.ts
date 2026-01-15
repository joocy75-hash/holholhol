/**
 * Table Page Type Definitions
 *
 * Type definitions for the poker table page components and state.
 * Re-exports common types from websocket.ts for convenience.
 */

// Re-export common types from websocket.ts
export type {
  SeatInfo,
  TableConfig,
  GamePhase,
  PlayerStatus,
  ActionType,
  AvailableAction,
} from './websocket';

// =============================================================================
// Card Types
// =============================================================================

export interface Card {
  rank: string;
  suit: string;
}

// =============================================================================
// Player Types (for UI rendering)
// =============================================================================

export interface Player {
  id: string;
  username: string;
  chips: number;
  cards: Card[];
  bet: number;
  folded: boolean;
  isActive: boolean;
  seatIndex: number;
  hasCards?: boolean; // 카드를 받았는지 여부 (봇 카드 뒷면 표시용)
  isWinner?: boolean; // 승자 여부 (WIN 표시용)
  winAmount?: number; // 승리 금액
  winHandRank?: string; // 승리 족보 (예: "풀하우스", "스트레이트")
}

// =============================================================================
// Game State Types
// =============================================================================

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

// =============================================================================
// Action Types
// =============================================================================

export interface AllowedAction {
  type: string;
  amount?: number;
  minAmount?: number;
  maxAmount?: number;
}

export interface PlayerAction {
  type: string;
  amount?: number;
  timestamp: number;
}

// =============================================================================
// Showdown Types
// =============================================================================

export type ShowdownPhase = 'idle' | 'intro' | 'revealing' | 'winner_announced' | 'settling' | 'complete';

// =============================================================================
// Animation Types
// =============================================================================

export interface ChipAnimation {
  id: string;
  fromPosition: { top: string; left: string };
  toPosition: { top: string; left: string };
  amount: number;
  startTime: number;
}

export interface DealTarget {
  position: number;
  x: number;
  y: number;
}

// =============================================================================
// Side Pot Types
// =============================================================================

export interface SidePot {
  amount: number;
  eligiblePlayers: number[];
}
