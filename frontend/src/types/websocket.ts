import type { Card, HandPhase, SeatState, ValidAction, ShowdownResult } from './game';

// WebSocket event types (matching backend)
export const WSEventType = {
  // System events
  CONNECTION_STATE: 'CONNECTION_STATE',
  PING: 'PING',
  PONG: 'PONG',
  ERROR: 'ERROR',

  // Lobby events
  SUBSCRIBE_LOBBY: 'SUBSCRIBE_LOBBY',
  UNSUBSCRIBE_LOBBY: 'UNSUBSCRIBE_LOBBY',
  LOBBY_SNAPSHOT: 'LOBBY_SNAPSHOT',
  LOBBY_UPDATE: 'LOBBY_UPDATE',
  ROOM_CREATE_REQUEST: 'ROOM_CREATE_REQUEST',
  ROOM_CREATE_RESULT: 'ROOM_CREATE_RESULT',

  // Table events
  SUBSCRIBE_TABLE: 'SUBSCRIBE_TABLE',
  UNSUBSCRIBE_TABLE: 'UNSUBSCRIBE_TABLE',
  TABLE_SNAPSHOT: 'TABLE_SNAPSHOT',
  TABLE_STATE_UPDATE: 'TABLE_STATE_UPDATE',
  SEAT_REQUEST: 'SEAT_REQUEST',
  SEAT_RESULT: 'SEAT_RESULT',
  LEAVE_TABLE: 'LEAVE_TABLE',

  // Action events
  TURN_PROMPT: 'TURN_PROMPT',
  ACTION_REQUEST: 'ACTION_REQUEST',
  ACTION_RESULT: 'ACTION_RESULT',
  SHOWDOWN_RESULT: 'SHOWDOWN_RESULT',

  // Chat events
  CHAT_MESSAGE: 'CHAT_MESSAGE',
  CHAT_BROADCAST: 'CHAT_BROADCAST',
} as const;

export type WSEventType = typeof WSEventType[keyof typeof WSEventType];

// Message envelope
export interface WSMessage<T = unknown> {
  type: WSEventType;
  ts: number;
  traceId: string;
  requestId?: string;
  payload: T;
  version: number;
}

// Connection state payload
export interface ConnectionStatePayload {
  state: 'connected' | 'reconnecting' | 'disconnected';
  userId?: string;
  sessionId?: string;
}

// Lobby payloads
export interface LobbyRoom {
  id: string;
  name: string;
  blinds: string;
  maxSeats: number;
  playerCount: number;
  status: 'waiting' | 'playing' | 'full';
}

export interface LobbySnapshotPayload {
  rooms: LobbyRoom[];
  stateVersion: number;
}

export interface LobbyUpdatePayload {
  type: 'add' | 'update' | 'remove';
  room?: LobbyRoom;
  roomId?: string;
  stateVersion: number;
}

export interface RoomCreateRequestPayload {
  name: string;
  smallBlind: number;
  bigBlind: number;
  maxSeats: 2 | 6 | 9;
  minBuyIn: number;
  maxBuyIn: number;
}

export interface RoomCreateResultPayload {
  success: boolean;
  roomId?: string;
  errorCode?: string;
  errorMessage?: string;
}

// Table payloads
export interface SubscribeTablePayload {
  tableId: string;
  mode: 'player' | 'spectator';
}

export interface TableSnapshotPayload {
  tableId: string;
  config: {
    name: string;
    smallBlind: number;
    bigBlind: number;
    maxSeats: number;
    minBuyIn: number;
    maxBuyIn: number;
  };
  seats: SeatState[];
  hand: {
    handId: string;
    phase: HandPhase;
    communityCards: Card[];
    pot: number;
    sidePots: Array<{ amount: number; eligiblePositions: number[] }>;
    currentBet: number;
    minRaise: number;
    currentPosition: number | null;
    dealerPosition: number;
    turnDeadline: string | null;
  } | null;
  myPosition: number | null;
  myHoleCards: [Card, Card] | null;
  stateVersion: number;
}

export interface TableStateUpdatePayload {
  tableId: string;
  changes: Partial<TableSnapshotPayload>;
  stateVersion: number;
}

export interface SeatRequestPayload {
  tableId: string;
  position: number;
  buyInAmount: number;
}

export interface SeatResultPayload {
  success: boolean;
  position?: number;
  errorCode?: string;
  errorMessage?: string;
}

// Action payloads
export interface TurnPromptPayload {
  tableId: string;
  position: number;
  allowedActions: ValidAction[];
  deadline: string;
  currentBet: number;
  myBet: number;
  myStack: number;
  pot: number;
  minRaise: number;
}

export interface ActionRequestPayload {
  tableId: string;
  actionType: 'fold' | 'check' | 'call' | 'bet' | 'raise' | 'all_in';
  amount?: number;
}

export interface ActionResultPayload {
  success: boolean;
  action?: {
    type: string;
    amount?: number;
    position: number;
  };
  errorCode?: string;
  errorMessage?: string;
}

export interface ShowdownResultPayload extends ShowdownResult {
  tableId: string;
  handId: string;
  nextHandDelay: number;
}

// Chat payloads
export interface ChatMessagePayload {
  tableId: string;
  message: string;
}

export interface ChatBroadcastPayload {
  tableId: string;
  senderId: string;
  senderNickname: string;
  message: string;
  timestamp: string;
  type: 'user' | 'system';
}

// Error payload
export interface ErrorPayload {
  errorCode: string;
  message: string;
  details?: Record<string, unknown>;
}
