# 프론트엔드 연동 가이드

> 백엔드 API 및 WebSocket 연동을 위한 상세 가이드

---

## 목차

1. [환경 설정](#1-환경-설정)
2. [인증 시스템](#2-인증-시스템)
3. [REST API 연동](#3-rest-api-연동)
4. [WebSocket 연동](#4-websocket-연동)
5. [게임 상태 관리](#5-게임-상태-관리)
6. [에러 처리](#6-에러-처리)
7. [타입 정의](#7-타입-정의)

---

## 1. 환경 설정

### 1.1 API 엔드포인트

```typescript
// config.ts
export const API_CONFIG = {
  development: {
    REST_URL: 'http://localhost:8000/api/v1',
    WS_URL: 'ws://localhost:8000/ws',
  },
  production: {
    REST_URL: 'https://api.example.com/api/v1',
    WS_URL: 'wss://api.example.com/ws',
  },
};
```

### 1.2 Axios 설정

```typescript
// api/client.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: API_CONFIG[process.env.NODE_ENV].REST_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 요청 인터셉터 - 토큰 추가
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 응답 인터셉터 - 토큰 갱신
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const refreshToken = localStorage.getItem('refreshToken');
      if (refreshToken) {
        try {
          const { data } = await axios.post(
            `${API_CONFIG[process.env.NODE_ENV].REST_URL}/auth/refresh`,
            { refreshToken }
          );
          localStorage.setItem('accessToken', data.accessToken);
          localStorage.setItem('refreshToken', data.refreshToken);
          error.config.headers.Authorization = `Bearer ${data.accessToken}`;
          return apiClient(error.config);
        } catch {
          localStorage.clear();
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;
```

---

## 2. 인증 시스템

### 2.1 회원가입

```typescript
// api/auth.ts
interface RegisterRequest {
  email: string;
  password: string;  // 최소 8자, 문자+숫자 포함
  nickname: string;  // 2-50자, 영문/숫자/한글/언더스코어
}

interface AuthResponse {
  user: {
    id: string;
    nickname: string;
    avatarUrl: string | null;
    balance: number;
  };
  tokens: {
    accessToken: string;
    refreshToken: string;
    tokenType: string;
    expiresIn: number;
  };
}

export async function register(data: RegisterRequest): Promise<AuthResponse> {
  const response = await apiClient.post('/auth/register', data);
  return response.data;
}
```

### 2.2 로그인

```typescript
interface LoginRequest {
  email: string;
  password: string;
}

export async function login(data: LoginRequest): Promise<AuthResponse> {
  const response = await apiClient.post('/auth/login', data);
  return response.data;
}
```

### 2.3 토큰 갱신

```typescript
interface TokenResponse {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresIn: number;
}

export async function refreshTokens(refreshToken: string): Promise<TokenResponse> {
  const response = await apiClient.post('/auth/refresh', { refreshToken });
  return response.data;
}
```

### 2.4 2FA (선택적)

```typescript
// 2FA 설정
interface TwoFactorSetup {
  secret: string;
  qrCodeUri: string;
  backupCodes: string[];
}

export async function setup2FA(): Promise<TwoFactorSetup> {
  const response = await apiClient.post('/auth/2fa/setup');
  return response.data;
}

// 2FA 인증
export async function verify2FA(code: string): Promise<void> {
  await apiClient.post('/auth/2fa/verify', { code });
}

// 2FA 상태 확인
interface TwoFactorStatus {
  isEnabled: boolean;
  backupCodesRemaining: number;
  lastUsedAt: string | null;
}

export async function get2FAStatus(): Promise<TwoFactorStatus> {
  const response = await apiClient.get('/auth/2fa/status');
  return response.data;
}
```

---

## 3. REST API 연동

### 3.1 방 목록 조회

```typescript
// api/rooms.ts
interface Room {
  id: string;
  name: string;
  blinds: string;        // "10/20"
  maxSeats: number;
  playerCount: number;
  status: 'waiting' | 'playing' | 'full';
  isPrivate: boolean;
}

interface RoomListResponse {
  rooms: Room[];
  pagination: {
    page: number;
    pageSize: number;
    totalItems: number;
    totalPages: number;
  };
}

export async function getRooms(params?: {
  page?: number;
  pageSize?: number;
  status?: string;
}): Promise<RoomListResponse> {
  const response = await apiClient.get('/rooms', { params });
  return response.data;
}
```

### 3.2 방 생성

```typescript
interface CreateRoomRequest {
  name: string;
  description?: string;
  maxSeats: number;      // 2-9
  smallBlind: number;
  bigBlind: number;
  buyInMin: number;
  buyInMax: number;
  isPrivate: boolean;
  password?: string;     // isPrivate=true일 때 필수
}

interface RoomDetail {
  id: string;
  name: string;
  description: string | null;
  config: {
    maxSeats: number;
    smallBlind: number;
    bigBlind: number;
    buyInMin: number;
    buyInMax: number;
    turnTimeout: number;
    isPrivate: boolean;
  };
  status: string;
  currentPlayers: number;
  owner: {
    id: string;
    nickname: string;
    avatarUrl: string | null;
  } | null;
  createdAt: string;
  updatedAt: string;
}

export async function createRoom(data: CreateRoomRequest): Promise<RoomDetail> {
  const response = await apiClient.post('/rooms', data);
  return response.data;
}
```

### 3.3 방 입장

```typescript
interface JoinRoomRequest {
  password?: string;
  buyIn: number;
}

interface JoinRoomResponse {
  success: boolean;
  roomId: string;
  tableId: string;
  position: number | null;  // null이면 관전자
  message: string;
}

export async function joinRoom(
  roomId: string,
  data: JoinRoomRequest
): Promise<JoinRoomResponse> {
  const response = await apiClient.post(`/rooms/${roomId}/join`, data);
  return response.data;
}
```

### 3.4 사용자 프로필

```typescript
interface UserProfile {
  id: string;
  email: string;
  nickname: string;
  avatarUrl: string | null;
  status: string;
  balance: number;
  totalHands: number;
  totalWinnings: number;
  createdAt: string;
}

export async function getMyProfile(): Promise<UserProfile> {
  const response = await apiClient.get('/users/me');
  return response.data;
}

export async function updateProfile(data: {
  nickname?: string;
  avatarUrl?: string;
}): Promise<UserProfile> {
  const response = await apiClient.patch('/users/me', data);
  return response.data;
}
```

---

## 4. WebSocket 연동

### 4.1 연결 관리 클래스

```typescript
// ws/PokerWebSocket.ts
type MessageHandler = (message: any) => void;
type ConnectionHandler = (status: 'connected' | 'reconnecting' | 'disconnected') => void;

export class PokerWebSocket {
  private ws: WebSocket | null = null;
  private pingInterval: NodeJS.Timeout | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private messageHandlers: Map<string, MessageHandler[]> = new Map();
  private connectionHandler: ConnectionHandler | null = null;

  constructor(private wsUrl: string) {}

  // 연결
  connect(token: string): Promise<void> {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(`${this.wsUrl}?token=${token}`);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.startPing();
        this.connectionHandler?.('connected');
        resolve();
      };

      this.ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        this.handleMessage(message);
      };

      this.ws.onclose = () => {
        this.stopPing();
        this.connectionHandler?.('disconnected');
        this.attemptReconnect(token);
      };

      this.ws.onerror = (error) => {
        reject(error);
      };
    });
  }

  // 메시지 전송
  send(type: string, payload: any, requestId?: string): void {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket not connected');
      return;
    }

    const message = {
      type,
      ts: Date.now(),
      traceId: crypto.randomUUID(),
      requestId: requestId || crypto.randomUUID(),
      payload,
      version: 'v1',
    };

    this.ws.send(JSON.stringify(message));
  }

  // 이벤트 핸들러 등록
  on(eventType: string, handler: MessageHandler): void {
    const handlers = this.messageHandlers.get(eventType) || [];
    handlers.push(handler);
    this.messageHandlers.set(eventType, handlers);
  }

  // 이벤트 핸들러 제거
  off(eventType: string, handler: MessageHandler): void {
    const handlers = this.messageHandlers.get(eventType) || [];
    const index = handlers.indexOf(handler);
    if (index > -1) {
      handlers.splice(index, 1);
    }
  }

  // 연결 상태 핸들러
  onConnectionChange(handler: ConnectionHandler): void {
    this.connectionHandler = handler;
  }

  // 연결 종료
  disconnect(): void {
    this.stopPing();
    this.ws?.close();
    this.ws = null;
  }

  private handleMessage(message: any): void {
    const handlers = this.messageHandlers.get(message.type) || [];
    handlers.forEach((handler) => handler(message));

    // 전체 메시지 핸들러
    const allHandlers = this.messageHandlers.get('*') || [];
    allHandlers.forEach((handler) => handler(message));
  }

  private startPing(): void {
    this.pingInterval = setInterval(() => {
      this.send('PING', {});
    }, 15000);
  }

  private stopPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private async attemptReconnect(token: string): Promise<void> {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    this.connectionHandler?.('reconnecting');

    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    await new Promise((r) => setTimeout(r, delay));

    try {
      await this.connect(token);
    } catch {
      this.attemptReconnect(token);
    }
  }
}
```

### 4.2 사용 예시

```typescript
// hooks/usePokerSocket.ts
import { useEffect, useRef, useCallback } from 'react';
import { PokerWebSocket } from '../ws/PokerWebSocket';
import { useGameStore } from '../store/gameStore';

export function usePokerSocket() {
  const wsRef = useRef<PokerWebSocket | null>(null);
  const { setConnectionStatus, handleMessage } = useGameStore();

  useEffect(() => {
    const token = localStorage.getItem('accessToken');
    if (!token) return;

    const ws = new PokerWebSocket(API_CONFIG[process.env.NODE_ENV].WS_URL);
    wsRef.current = ws;

    // 연결 상태 핸들러
    ws.onConnectionChange(setConnectionStatus);

    // 메시지 핸들러 등록
    ws.on('*', handleMessage);

    // 연결
    ws.connect(token);

    return () => {
      ws.disconnect();
    };
  }, []);

  // 로비 구독
  const subscribeLobby = useCallback(() => {
    wsRef.current?.send('SUBSCRIBE_LOBBY', {});
  }, []);

  // 로비 구독 해제
  const unsubscribeLobby = useCallback(() => {
    wsRef.current?.send('UNSUBSCRIBE_LOBBY', {});
  }, []);

  // 테이블 구독
  const subscribeTable = useCallback((tableId: string, mode: 'player' | 'spectator' = 'player') => {
    wsRef.current?.send('SUBSCRIBE_TABLE', { tableId, mode });
  }, []);

  // 테이블 구독 해제
  const unsubscribeTable = useCallback((tableId: string) => {
    wsRef.current?.send('UNSUBSCRIBE_TABLE', { tableId });
  }, []);

  // 게임 액션
  const sendAction = useCallback((tableId: string, actionType: string, amount?: number) => {
    wsRef.current?.send('ACTION_REQUEST', { tableId, actionType, amount });
  }, []);

  // 채팅
  const sendChat = useCallback((tableId: string, message: string) => {
    wsRef.current?.send('CHAT_MESSAGE', { tableId, message });
  }, []);

  return {
    subscribeLobby,
    unsubscribeLobby,
    subscribeTable,
    unsubscribeTable,
    sendAction,
    sendChat,
  };
}
```

---

## 5. 게임 상태 관리

### 5.1 Zustand Store

```typescript
// store/gameStore.ts
import { create } from 'zustand';

interface Seat {
  position: number;
  player: {
    userId: string;
    nickname: string;
    avatarUrl: string | null;
  } | null;
  stack: number;
  betAmount: number;
  status: 'active' | 'folded' | 'all_in' | 'sitting_out' | 'disconnected';
  lastAction?: {
    type: string;
    amount?: number;
  };
}

interface Hand {
  handId: string;
  handNumber: number;
  phase: 'preflop' | 'flop' | 'turn' | 'river' | 'showdown';
  communityCards: string[];
  pot: {
    mainPot: number;
    sidePots: { amount: number; eligiblePlayers: number[] }[];
  };
  currentTurn: number;
  minRaise: number;
}

interface TableState {
  tableId: string;
  config: {
    maxSeats: number;
    smallBlind: number;
    bigBlind: number;
    minBuyIn: number;
    maxBuyIn: number;
    turnTimeoutSeconds: number;
  };
  seats: Seat[];
  hand: Hand | null;
  dealerPosition: number;
  myPosition: number | null;
  myHoleCards: string[] | null;
  stateVersion: number;
}

interface ValidAction {
  type: 'fold' | 'check' | 'call' | 'bet' | 'raise' | 'all_in';
  minAmount?: number;
  maxAmount?: number;
}

interface TurnPrompt {
  position: number;
  allowedActions: ValidAction[];
  turnDeadlineAt: string;
}

interface GameState {
  connectionStatus: 'connected' | 'reconnecting' | 'disconnected';
  lobby: Room[];
  currentTable: TableState | null;
  turnPrompt: TurnPrompt | null;
  
  setConnectionStatus: (status: 'connected' | 'reconnecting' | 'disconnected') => void;
  handleMessage: (message: any) => void;
}

export const useGameStore = create<GameState>((set, get) => ({
  connectionStatus: 'disconnected',
  lobby: [],
  currentTable: null,
  turnPrompt: null,

  setConnectionStatus: (status) => set({ connectionStatus: status }),

  handleMessage: (message) => {
    switch (message.type) {
      case 'CONNECTION_STATE':
        set({ connectionStatus: message.payload.state });
        break;

      case 'LOBBY_SNAPSHOT':
        set({ lobby: message.payload.rooms });
        break;

      case 'LOBBY_UPDATE':
        set((state) => ({
          lobby: applyLobbyUpdate(state.lobby, message.payload),
        }));
        break;

      case 'TABLE_SNAPSHOT':
        set({
          currentTable: message.payload,
          turnPrompt: null,
        });
        break;

      case 'TABLE_STATE_UPDATE':
        set((state) => ({
          currentTable: state.currentTable
            ? applyTableUpdate(state.currentTable, message.payload.changes)
            : null,
        }));
        break;

      case 'TURN_PROMPT':
        set({ turnPrompt: message.payload });
        break;

      case 'ACTION_RESULT':
        if (!message.payload.success) {
          // 에러 처리
          console.error('Action failed:', message.payload.errorMessage);
        }
        break;

      case 'SHOWDOWN_RESULT':
        // 쇼다운 결과 처리
        handleShowdown(message.payload);
        break;

      case 'HAND_RESULT':
        // 핸드 종료 처리
        set({ turnPrompt: null });
        break;

      case 'ERROR':
        handleError(message.payload);
        break;
    }
  },
}));

// 헬퍼 함수들
function applyLobbyUpdate(lobby: Room[], update: any): Room[] {
  // 로비 업데이트 적용 로직
  return lobby;
}

function applyTableUpdate(table: TableState, changes: any): TableState {
  return {
    ...table,
    ...changes,
    seats: changes.seats
      ? table.seats.map((seat) => {
          const update = changes.seats.find((s: any) => s.position === seat.position);
          return update ? { ...seat, ...update } : seat;
        })
      : table.seats,
    stateVersion: changes.stateVersion || table.stateVersion,
  };
}

function handleShowdown(payload: any) {
  // 쇼다운 애니메이션 등 처리
}

function handleError(payload: any) {
  // 에러 토스트 표시 등
}
```

---

## 6. 에러 처리

### 6.1 에러 코드 상수

```typescript
// constants/errorCodes.ts
export const ERROR_CODES = {
  // 인증
  AUTH_REQUIRED: 'AUTH_REQUIRED',
  AUTH_INVALID_TOKEN: 'AUTH_INVALID_TOKEN',
  AUTH_TOKEN_EXPIRED: 'AUTH_TOKEN_EXPIRED',
  AUTH_SESSION_EXPIRED: 'AUTH_SESSION_EXPIRED',

  // 방
  ROOM_NOT_FOUND: 'ROOM_NOT_FOUND',
  ROOM_FULL: 'ROOM_FULL',
  ROOM_CLOSED: 'ROOM_CLOSED',

  // 테이블
  TABLE_NOT_FOUND: 'TABLE_NOT_FOUND',
  TABLE_SEAT_TAKEN: 'TABLE_SEAT_TAKEN',
  TABLE_NOT_SEATED: 'TABLE_NOT_SEATED',

  // 액션
  ACTION_NOT_YOUR_TURN: 'ACTION_NOT_YOUR_TURN',
  ACTION_INVALID: 'ACTION_INVALID',
  ACTION_INVALID_AMOUNT: 'ACTION_INVALID_AMOUNT',
  ACTION_INSUFFICIENT_STACK: 'ACTION_INSUFFICIENT_STACK',
  ACTION_TIMEOUT: 'ACTION_TIMEOUT',

  // 상태
  STATE_STALE_VERSION: 'STATE_STALE_VERSION',

  // 레이트 리밋
  RATE_LIMIT_EXCEEDED: 'RATE_LIMIT_EXCEEDED',
} as const;
```

### 6.2 에러 핸들러

```typescript
// utils/errorHandler.ts
import { toast } from 'your-toast-library';

interface ErrorPayload {
  errorCode: string;
  errorMessage: string;
  details?: Record<string, any>;
}

export function handleApiError(error: any): void {
  const errorData = error.response?.data?.error as ErrorPayload | undefined;
  
  if (!errorData) {
    toast.error('네트워크 오류가 발생했습니다.');
    return;
  }

  switch (errorData.errorCode) {
    case ERROR_CODES.AUTH_TOKEN_EXPIRED:
    case ERROR_CODES.AUTH_SESSION_EXPIRED:
      // 토큰 갱신 시도는 인터셉터에서 처리
      break;

    case ERROR_CODES.ROOM_FULL:
      toast.error('방이 가득 찼습니다. 다른 방을 선택해주세요.');
      break;

    case ERROR_CODES.ACTION_INVALID_AMOUNT:
      const { minAmount, maxAmount } = errorData.details || {};
      toast.error(`금액은 ${minAmount}~${maxAmount} 사이여야 합니다.`);
      break;

    case ERROR_CODES.RATE_LIMIT_EXCEEDED:
      const { retryAfterSeconds } = errorData.details || {};
      toast.error(`요청이 너무 많습니다. ${retryAfterSeconds}초 후 다시 시도해주세요.`);
      break;

    default:
      toast.error(errorData.errorMessage);
  }
}

export function handleWebSocketError(payload: ErrorPayload): void {
  switch (payload.errorCode) {
    case ERROR_CODES.STATE_STALE_VERSION:
      // 스냅샷 재요청
      // wsClient.send('SUBSCRIBE_TABLE', { tableId, mode: 'player' });
      break;

    case ERROR_CODES.ACTION_NOT_YOUR_TURN:
      toast.warning('아직 당신의 차례가 아닙니다.');
      break;

    case ERROR_CODES.ACTION_TIMEOUT:
      toast.info('시간 초과로 자동 폴드되었습니다.');
      break;

    default:
      toast.error(payload.errorMessage);
  }
}
```

---

## 7. 타입 정의

### 7.1 전체 타입 파일

```typescript
// types/index.ts

// ============ Auth ============
export interface User {
  id: string;
  nickname: string;
  avatarUrl: string | null;
  balance: number;
}

export interface Tokens {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresIn: number;
}

// ============ Room ============
export interface Room {
  id: string;
  name: string;
  blinds: string;
  maxSeats: number;
  playerCount: number;
  status: 'waiting' | 'playing' | 'full';
  isPrivate: boolean;
}

export interface RoomConfig {
  maxSeats: number;
  smallBlind: number;
  bigBlind: number;
  buyInMin: number;
  buyInMax: number;
  turnTimeout: number;
  isPrivate: boolean;
}

// ============ Table ============
export interface Player {
  userId: string;
  nickname: string;
  avatarUrl: string | null;
}

export interface Seat {
  position: number;
  player: Player | null;
  stack: number;
  betAmount: number;
  status: 'active' | 'folded' | 'all_in' | 'sitting_out' | 'disconnected';
  lastAction?: {
    type: string;
    amount?: number;
  };
}

export interface Pot {
  mainPot: number;
  sidePots: {
    amount: number;
    eligiblePlayers: number[];
  }[];
}

export interface Hand {
  handId: string;
  handNumber: number;
  phase: 'preflop' | 'flop' | 'turn' | 'river' | 'showdown';
  communityCards: string[];
  pot: Pot;
  currentTurn: number;
  minRaise: number;
}

export interface TableState {
  tableId: string;
  config: RoomConfig;
  seats: Seat[];
  hand: Hand | null;
  dealerPosition: number;
  myPosition: number | null;
  myHoleCards: string[] | null;
  stateVersion: number;
  updatedAt: string;
}

// ============ Actions ============
export type ActionType = 'fold' | 'check' | 'call' | 'bet' | 'raise' | 'all_in';

export interface ValidAction {
  type: ActionType;
  minAmount?: number;
  maxAmount?: number;
  amount?: number;  // all_in의 경우
}

export interface TurnPrompt {
  tableId: string;
  position: number;
  allowedActions: ValidAction[];
  turnDeadlineAt: string;
  stateVersion: number;
}

// ============ WebSocket Messages ============
export interface MessageEnvelope<T = any> {
  type: string;
  ts: number;
  traceId: string;
  requestId?: string;
  payload: T;
  version: string;
}

export interface ErrorPayload {
  errorCode: string;
  errorMessage: string;
  details?: Record<string, any>;
}

// ============ Showdown ============
export interface ShowdownHand {
  position: number;
  holeCards: string[];
  handRank: string;
  handDescription: string;
}

export interface Winner {
  position: number;
  amount: number;
  potType: 'main' | 'side';
}

export interface ShowdownResult {
  tableId: string;
  handId: string;
  showdownHands: ShowdownHand[];
  winners: Winner[];
  stateVersion: number;
}
```

---

## 부록: 카드 표기법

카드는 2자리 문자열로 표현됩니다:
- 첫 번째 문자: 랭크 (2-9, T, J, Q, K, A)
- 두 번째 문자: 수트 (c=클럽, d=다이아, h=하트, s=스페이드)

예시:
- `As` = 스페이드 에이스
- `Kh` = 하트 킹
- `Td` = 다이아 10
- `2c` = 클럽 2

```typescript
// utils/card.ts
export function parseCard(card: string): { rank: string; suit: string } {
  return {
    rank: card[0],
    suit: card[1],
  };
}

export function getSuitSymbol(suit: string): string {
  const symbols: Record<string, string> = {
    c: '♣',
    d: '♦',
    h: '♥',
    s: '♠',
  };
  return symbols[suit] || suit;
}

export function getSuitColor(suit: string): 'red' | 'black' {
  return suit === 'h' || suit === 'd' ? 'red' : 'black';
}
```
