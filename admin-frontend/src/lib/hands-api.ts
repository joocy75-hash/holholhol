/**
 * Hands API Client - 핸드 히스토리 및 리플레이 API
 */
import { api } from './api';
import { useAuthStore } from '@/stores/authStore';

// ============================================================================
// Types
// ============================================================================

export interface HandSummary {
  id: string;
  tableId: string;
  tableName: string | null;
  handNumber: number;
  potSize: number;
  playerCount: number;
  startedAt: string | null;
  endedAt: string | null;
}

export interface PaginatedHands {
  items: HandSummary[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface TimelineAction {
  seqNo: number;
  eventType: string;
  playerId: string | null;
  playerSeat: number | null;
  playerNickname: string | null;
  amount: number | null;
  cards: string[] | null;
  timestamp: string | null;
  phase: string | null;
}

export interface ParticipantInfo {
  userId: string;
  nickname: string | null;
  seat: number;
  holeCards: string[] | null;
  betAmount: number;
  wonAmount: number;
  finalAction: string;
  netResult: number;
}

export interface InitialState {
  dealerPosition: number | null;
  smallBlind: number;
  bigBlind: number;
  players: Array<{
    seat: number;
    userId: string;
    stack: number;
  }>;
}

export interface HandResult {
  potTotal: number;
  communityCards: string[];
  winners: Array<{
    userId: string;
    amount: number;
    seat: number;
  }>;
}

export interface HandDetail {
  id: string;
  tableId: string;
  tableName: string | null;
  handNumber: number;
  startedAt: string | null;
  endedAt: string | null;
  initialState: InitialState | null;
  result: HandResult | null;
  participants: ParticipantInfo[];
  timeline: TimelineAction[];
  potSize: number;
  communityCards: string[];
}

export interface HandExport {
  handId: string;
  format: string;
  data: {
    handId?: string;
    participants?: unknown[];
    events?: unknown[];
    text?: string;
  };
}

export interface SearchHandsParams {
  handId?: string;
  userId?: string;
  tableId?: string;
  page?: number;
  pageSize?: number;
}

// ============================================================================
// API Functions
// ============================================================================

function getToken(): string | undefined {
  return useAuthStore.getState().accessToken || undefined;
}

export const handsApi = {
  /**
   * 핸드 검색/목록 조회
   */
  async searchHands(params: SearchHandsParams = {}): Promise<PaginatedHands> {
    const query = new URLSearchParams();
    if (params.handId) query.append('hand_id', params.handId);
    if (params.userId) query.append('user_id', params.userId);
    if (params.tableId) query.append('table_id', params.tableId);
    query.append('page', String(params.page || 1));
    query.append('page_size', String(params.pageSize || 20));

    return api.get<PaginatedHands>(`/api/hands?${query.toString()}`, { token: getToken() });
  },

  /**
   * 핸드 상세 조회 (리플레이용)
   */
  async getHandDetail(handId: string): Promise<HandDetail> {
    return api.get<HandDetail>(`/api/hands/${handId}`, { token: getToken() });
  },

  /**
   * 핸드 내보내기
   */
  async exportHand(handId: string, format: 'json' | 'text' = 'json'): Promise<HandExport> {
    return api.get<HandExport>(`/api/hands/${handId}/export?format=${format}`, { token: getToken() });
  },
};
