/**
 * WebSocket Type Definitions
 *
 * Type-safe definitions for WebSocket events and payloads.
 * Mirrors backend/app/ws/events.py and backend/app/game/types.py
 */

// =============================================================================
// Event Types (mirrors backend EventType enum)
// =============================================================================

export enum EventType {
  // System events
  PING = 'PING',
  PONG = 'PONG',
  CONNECTION_STATE = 'CONNECTION_STATE',
  ERROR = 'ERROR',
  RECOVERY_REQUEST = 'RECOVERY_REQUEST',
  RECOVERY_RESPONSE = 'RECOVERY_RESPONSE',
  ANNOUNCEMENT = 'ANNOUNCEMENT',

  // Lobby events
  SUBSCRIBE_LOBBY = 'SUBSCRIBE_LOBBY',
  UNSUBSCRIBE_LOBBY = 'UNSUBSCRIBE_LOBBY',
  LOBBY_SNAPSHOT = 'LOBBY_SNAPSHOT',
  LOBBY_UPDATE = 'LOBBY_UPDATE',
  ROOM_CREATE_REQUEST = 'ROOM_CREATE_REQUEST',
  ROOM_CREATE_RESULT = 'ROOM_CREATE_RESULT',
  ROOM_JOIN_REQUEST = 'ROOM_JOIN_REQUEST',
  ROOM_JOIN_RESULT = 'ROOM_JOIN_RESULT',

  // Table events
  SUBSCRIBE_TABLE = 'SUBSCRIBE_TABLE',
  UNSUBSCRIBE_TABLE = 'UNSUBSCRIBE_TABLE',
  TABLE_SNAPSHOT = 'TABLE_SNAPSHOT',
  TABLE_STATE_UPDATE = 'TABLE_STATE_UPDATE',
  TURN_PROMPT = 'TURN_PROMPT',
  SEAT_REQUEST = 'SEAT_REQUEST',
  SEAT_RESULT = 'SEAT_RESULT',
  LEAVE_REQUEST = 'LEAVE_REQUEST',
  LEAVE_RESULT = 'LEAVE_RESULT',
  ADD_BOT_REQUEST = 'ADD_BOT_REQUEST',
  ADD_BOT_RESULT = 'ADD_BOT_RESULT',
  START_BOT_LOOP_REQUEST = 'START_BOT_LOOP_REQUEST',
  START_BOT_LOOP_RESULT = 'START_BOT_LOOP_RESULT',
  SIT_OUT_REQUEST = 'SIT_OUT_REQUEST',
  SIT_IN_REQUEST = 'SIT_IN_REQUEST',
  PLAYER_SIT_OUT = 'PLAYER_SIT_OUT',
  PLAYER_SIT_IN = 'PLAYER_SIT_IN',

  // Hand events
  START_GAME = 'START_GAME',
  GAME_STARTING = 'GAME_STARTING',
  HAND_START = 'HAND_START',
  HAND_STARTED = 'HAND_STARTED',
  COMMUNITY_CARDS = 'COMMUNITY_CARDS',

  // Action events
  ACTION_REQUEST = 'ACTION_REQUEST',
  ACTION_RESULT = 'ACTION_RESULT',
  SHOWDOWN_RESULT = 'SHOWDOWN_RESULT',
  HAND_RESULT = 'HAND_RESULT',
  TURN_CHANGED = 'TURN_CHANGED',
  STACK_ZERO = 'STACK_ZERO',  // 스택 0 시 리바이 모달용
  REBUY = 'REBUY',  // 리바이 요청

  // Timer events
  TIMEOUT_FOLD = 'TIMEOUT_FOLD',

  // Time Bank events
  TIME_BANK_REQUEST = 'TIME_BANK_REQUEST',
  TIME_BANK_USED = 'TIME_BANK_USED',

  // Chat events
  CHAT_MESSAGE = 'CHAT_MESSAGE',
  CHAT_HISTORY = 'CHAT_HISTORY',
}

// =============================================================================
// Player Types
// =============================================================================

export type PlayerStatus = 'active' | 'folded' | 'all_in' | 'sitting_out' | 'waiting' | 'empty';

export interface PlayerInfo {
  userId: string;
  nickname: string;
  stack: number;
  bet: number;
  status: PlayerStatus;
  holeCards?: string[] | null;
  isBot: boolean;
  isCurrent: boolean;
  isDealer: boolean;
}

export interface SeatInfo {
  position: number;
  player: {
    userId: string;
    nickname: string;
    avatarUrl?: string;
  } | null;
  stack: number;
  status: PlayerStatus;
  betAmount: number;
  totalBet: number;
  isDealer?: boolean;
  isCurrent?: boolean;
  isCardsRevealed?: boolean;
  timeBankRemaining?: number;  // 타임 뱅크 남은 횟수
}

// =============================================================================
// Action Types
// =============================================================================

export type ActionType = 'fold' | 'check' | 'call' | 'raise' | 'bet' | 'all_in';

export interface AvailableAction {
  type: ActionType;
  amount?: number;
  minAmount?: number;
  maxAmount?: number;
}

// =============================================================================
// Hand Result Types
// =============================================================================

export interface Winner {
  seat: number;
  position: number;
  userId: string;
  amount: number;
  handRank?: string;
  bestFive?: string[];
}

export interface ShowdownHand {
  seat: number;
  position: number;
  holeCards: string[];
  handRank?: string;
  bestFive?: string[];
}

export interface EliminatedPlayer {
  seat: number;
  userId: string;
  nickname: string;
}

// =============================================================================
// Server → Client Payloads
// =============================================================================

export interface ConnectionStatePayload {
  state: 'connected' | 'disconnected';
  userId?: string;
  nickname?: string;
}

export interface ErrorPayload {
  errorCode: string;
  errorMessage: string;
  details?: Record<string, unknown>;
}

/** 핸드 내 액션 기록 (중간 입장 동기화용) */
export interface ActionHistoryItem {
  seat: number;
  action: string;
  amount: number;
  phase: string;
}

/** 턴 타이머 정보 (중간 입장 동기화용) */
export interface TurnInfo {
  currentSeat: number;
  startedAt: string;
  deadlineAt: string;
  remainingSeconds: number;
  extraSeconds: number;
}

/** 핸드 정보 (진행 중인 핸드가 있을 때) */
export interface HandInfo {
  handNumber: number;
  phase: GamePhase;
  pot: number;
  communityCards: string[];
  currentTurn: number | null;
  currentBet: number;
  actionHistory?: ActionHistoryItem[];  // 중간 입장 동기화용
}

export interface TableSnapshotPayload {
  tableId: string;
  roomId: string;
  tableName?: string;
  config?: TableConfig;
  seats: SeatInfo[];
  hand?: HandInfo | null;
  dealerPosition: number;
  myPosition?: number | null;
  myHoleCards?: string[] | null;
  allowedActions?: AvailableAction[] | null;
  turnInfo?: TurnInfo | null;  // 중간 입장 시 턴 타이머 동기화용
  stateVersion?: number;
  updatedAt?: string | null;
  isStateRestore?: boolean;  // 상태 복원 플래그 (새로고침/재접속 구분용)
  // Legacy fields (for backwards compatibility)
  handNumber?: number;
  phase?: GamePhase;
  pot?: number;
  communityCards?: string[];
  currentTurn?: number | null;
  currentBet?: number;
  dealer?: number;
  smallBlindSeat?: number | null;
  bigBlindSeat?: number | null;
  smallBlind?: number;
  bigBlind?: number;
  players?: (PlayerInfo | null)[];
}

export interface TableConfig {
  maxSeats: number;
  smallBlind: number;
  bigBlind: number;
  minBuyIn: number;
  maxBuyIn: number;
  turnTimeoutSeconds: number;
}

export type GamePhase = 'waiting' | 'preflop' | 'flop' | 'turn' | 'river' | 'showdown';

export interface TableStateUpdatePayload {
  changes: Partial<{
    phase: GamePhase;
    pot: number;
    communityCards: string[];
    currentTurn: number | null;
    currentBet: number;
    dealer: number;
    players: (PlayerInfo | null)[];
    seats: Record<string, SeatInfo>;
    updateType: string;
    playerActions: Record<string, { type: string; amount?: number; timestamp: number }>;
  }>;
}

export interface TurnPromptPayload {
  seat: number;
  position: number;
  userId: string;
  allowedActions: AvailableAction[];
  turnStartTime: number;
  turnTime: number;
  callAmount?: number;
  minRaise?: number;
  maxRaise?: number;
}

export interface TurnChangedPayload {
  seat: number;
  position: number;
  userId: string;
  turnStartTime: number;
  turnTime: number;
}

export interface SeatResultPayload {
  success: boolean;
  seat?: number;
  errorMessage?: string;
}

export interface LeaveResultPayload {
  success: boolean;
  errorMessage?: string;
}

export interface AddBotResultPayload {
  success: boolean;
  botId?: string;
  seat?: number;
  errorMessage?: string;
}

export interface StartBotLoopResultPayload {
  success: boolean;
  botsAdded?: number;
  gameStarted?: boolean;
  errorMessage?: string;
}

export interface GameStartingPayload {
  countdownSeconds: number;
}

export interface HandStartedPayload {
  handNumber: number;
  dealer: number;
  smallBlindSeat: number;
  bigBlindSeat: number;
  players: {
    seat: number;
    position: number;
    userId: string;
    stack: number;
    holeCards?: string[];
  }[];
}

export interface CommunityCardsPayload {
  cards: string[];
  phase: GamePhase;
}

export interface ActionResultPayload {
  success: boolean;
  action?: string;
  amount?: number;
  seat?: number;
  pot?: number;
  phase?: GamePhase;
  phaseChanged?: boolean;
  newCommunityCards?: string[];
  handComplete?: boolean;
  handResult?: HandResultPayload | null;
  players?: PlayerInfo[];
  currentBet?: number;
  currentPlayer?: number | null;
  errorMessage?: string;
  shouldRefresh?: boolean;
}

export interface HandResultPayload {
  winners: Winner[];
  showdown: ShowdownHand[];
  pot: number;
  communityCards: string[];
  eliminatedPlayers: EliminatedPlayer[];
}

export interface StackZeroPayload {
  tableId: string;
  seat: number;
  options: string[];
}

export interface TimeoutFoldPayload {
  seat: number;
  userId: string;
  action: 'fold' | 'check';
}

// =============================================================================
// Time Bank Types
// =============================================================================

export interface TimeBankRequestPayload {
  tableId: string;
}

export interface TimeBankUsedPayload {
  success: boolean;
  tableId: string;
  seat?: number;
  remaining?: number;
  addedSeconds?: number;
  newDeadline?: string | null;
  errorCode?: string;
  errorMessage?: string;
}

// =============================================================================
// Announcement Types
// =============================================================================

export type AnnouncementType = 'notice' | 'event' | 'maintenance' | 'urgent';
export type AnnouncementPriority = 'low' | 'normal' | 'high' | 'critical';
export type AnnouncementTarget = 'all' | 'vip' | 'specific_room';

export interface AnnouncementPayload {
  id: string;
  title: string;
  content: string;
  type: AnnouncementType;
  priority: AnnouncementPriority;
  target: AnnouncementTarget;
  targetRoomId?: string | null;
}

// =============================================================================
// Client → Server Payloads
// =============================================================================

export interface SubscribeTablePayload {
  tableId: string;
}

export interface UnsubscribeTablePayload {
  tableId: string;
}

export interface SeatRequestPayload {
  tableId: string;
  buyInAmount: number;
  preferredSeat?: number;
}

export interface LeaveRequestPayload {
  tableId: string;
}

export interface StartGamePayload {
  tableId: string;
}

export interface ActionRequestPayload {
  tableId: string;
  actionType: ActionType;
  amount?: number;
}

export interface AddBotRequestPayload {
  tableId: string;
  buyIn: number;
}

export interface StartBotLoopRequestPayload {
  tableId: string;
  botCount: number;
  buyIn?: number;
}

// =============================================================================
// WebSocket Message Types
// =============================================================================

export interface WebSocketMessage<T = unknown> {
  type: EventType | string;
  payload: T;
}

// =============================================================================
// Event Handler Types
// =============================================================================

export type EventHandler<T = unknown> = (data: T) => void;

export interface TypedEventHandlers {
  [EventType.CONNECTION_STATE]: EventHandler<ConnectionStatePayload>;
  [EventType.ERROR]: EventHandler<ErrorPayload>;
  [EventType.TABLE_SNAPSHOT]: EventHandler<TableSnapshotPayload>;
  [EventType.TABLE_STATE_UPDATE]: EventHandler<TableStateUpdatePayload>;
  [EventType.TURN_PROMPT]: EventHandler<TurnPromptPayload>;
  [EventType.TURN_CHANGED]: EventHandler<TurnChangedPayload>;
  [EventType.SEAT_RESULT]: EventHandler<SeatResultPayload>;
  [EventType.LEAVE_RESULT]: EventHandler<LeaveResultPayload>;
  [EventType.ADD_BOT_RESULT]: EventHandler<AddBotResultPayload>;
  [EventType.START_BOT_LOOP_RESULT]: EventHandler<StartBotLoopResultPayload>;
  [EventType.GAME_STARTING]: EventHandler<GameStartingPayload>;
  [EventType.HAND_STARTED]: EventHandler<HandStartedPayload>;
  [EventType.COMMUNITY_CARDS]: EventHandler<CommunityCardsPayload>;
  [EventType.ACTION_RESULT]: EventHandler<ActionResultPayload>;
  [EventType.HAND_RESULT]: EventHandler<HandResultPayload>;
  [EventType.STACK_ZERO]: EventHandler<StackZeroPayload>;
  [EventType.TIMEOUT_FOLD]: EventHandler<TimeoutFoldPayload>;
  [EventType.TIME_BANK_USED]: EventHandler<TimeBankUsedPayload>;
  [EventType.ANNOUNCEMENT]: EventHandler<AnnouncementPayload>;
}

// =============================================================================
// Utility Types
// =============================================================================

/** Extract payload type for a given event */
export type PayloadFor<E extends keyof TypedEventHandlers> =
  TypedEventHandlers[E] extends EventHandler<infer P> ? P : never;
