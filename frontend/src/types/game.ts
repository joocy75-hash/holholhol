// Card types
export type Suit = 'c' | 'd' | 'h' | 's'; // clubs, diamonds, hearts, spades
export type Rank = '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9' | 'T' | 'J' | 'Q' | 'K' | 'A';

export interface Card {
  rank: Rank;
  suit: Suit;
}

// Hand phases
export type HandPhase = 'preflop' | 'flop' | 'turn' | 'river' | 'showdown';

// Player status
export type PlayerStatus = 'active' | 'folded' | 'all_in' | 'sitting_out' | 'disconnected';

// Action types
export type ActionType = 'fold' | 'check' | 'call' | 'bet' | 'raise' | 'all_in';

// Seat state
export interface SeatState {
  position: number;
  player: {
    userId: string;
    nickname: string;
    avatarUrl?: string;
  } | null;
  stack: number;
  betAmount: number;
  status: PlayerStatus;
  lastAction?: {
    type: ActionType;
    amount?: number;
  };
  isDealer: boolean;
  isCurrentTurn: boolean;
  holeCards?: [Card, Card] | null;
}

// Valid action
export interface ValidAction {
  type: ActionType;
  minAmount?: number;
  maxAmount?: number;
}

// Hand state
export interface HandState {
  handId: string;
  phase: HandPhase;
  communityCards: Card[];
  pot: number;
  sidePots: Array<{
    amount: number;
    eligiblePositions: number[];
  }>;
  currentBet: number;
  minRaise: number;
  currentPosition: number | null;
  dealerPosition: number;
  turnDeadline: Date | null;
}

// Table config
export interface TableConfig {
  tableId: string;
  name: string;
  blinds: {
    small: number;
    big: number;
  };
  maxSeats: 2 | 6 | 9;
  buyIn: {
    min: number;
    max: number;
  };
}

// Full table state
export interface TableState {
  config: TableConfig;
  seats: SeatState[];
  hand: HandState | null;
  stateVersion: number;
}

// Room summary for lobby
export interface RoomSummary {
  id: string;
  name: string;
  blinds: string;
  maxSeats: number;
  playerCount: number;
  status: 'waiting' | 'playing' | 'full';
}

// Showdown result
export interface ShowdownResult {
  winners: Array<{
    position: number;
    nickname: string;
    holeCards: [Card, Card];
    handRank: string;
    handName: string;
    winAmount: number;
  }>;
  losers: Array<{
    position: number;
    nickname: string;
    holeCards: [Card, Card];
    handRank: string;
    handName: string;
  }>;
}

// Hand rank names (Korean)
export const HAND_RANK_NAMES: Record<string, string> = {
  'royal_flush': '로열 플러시',
  'straight_flush': '스트레이트 플러시',
  'four_of_a_kind': '포카드',
  'full_house': '풀하우스',
  'flush': '플러시',
  'straight': '스트레이트',
  'three_of_a_kind': '트리플',
  'two_pair': '투페어',
  'one_pair': '원페어',
  'high_card': '하이카드',
};
