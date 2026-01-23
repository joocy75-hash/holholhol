import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const ADMIN_API_BASE_URL = process.env.NEXT_PUBLIC_ADMIN_API_URL || 'http://localhost:8001';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for adding auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Track if we're currently refreshing to prevent infinite loops
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token!);
    }
  });
  failedQueue = [];
};

// Response interceptor for handling errors and token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // If error is 401 and we haven't tried refreshing yet
    if (error.response?.status === 401 && !originalRequest._retry) {
      // Skip refresh for auth endpoints to prevent loops
      if (originalRequest.url?.includes('/auth/login') ||
          originalRequest.url?.includes('/auth/register') ||
          originalRequest.url?.includes('/auth/refresh')) {
        return Promise.reject(error);
      }

      if (isRefreshing) {
        // Wait for the refresh to complete
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return api(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = localStorage.getItem('refresh_token');

      if (!refreshToken) {
        // No refresh token, logout immediately
        localStorage.removeItem('access_token');
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        // Try to refresh the token
        const response = await axios.post(
          `${API_BASE_URL}/api/v1/auth/refresh`,
          { refreshToken: refreshToken }  // camelCase for backend
        );

        const { accessToken, refreshToken: newRefreshToken } = response.data.tokens || response.data;

        localStorage.setItem('access_token', accessToken);
        if (newRefreshToken) {
          localStorage.setItem('refresh_token', newRefreshToken);
        }

        api.defaults.headers.common.Authorization = `Bearer ${accessToken}`;
        originalRequest.headers.Authorization = `Bearer ${accessToken}`;

        processQueue(null, accessToken);
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        // Refresh failed, logout
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

// Auth API
export const authApi = {
  signup: (data: { email: string; password: string; nickname: string; partnerCode?: string }) =>
    api.post('/api/v1/auth/register', data),

  login: (data: { email: string; password: string }) =>
    api.post('/api/v1/auth/login', data),

  logout: () => api.post('/api/v1/auth/logout'),

  me: () => api.get('/api/v1/users/me'),

  refresh: (refreshToken: string) =>
    api.post('/api/v1/auth/refresh', { refreshToken }),
};

// Waitlist API Types
export interface WaitlistEntry {
  user_id: string;
  buy_in: number;
  joined_at: string;
  position: number;
}

export interface WaitlistResponse {
  room_id: string;
  waitlist: WaitlistEntry[];
  count: number;
  my_position: number | null;
}

export interface WaitlistJoinResponse {
  success: boolean;
  room_id: string;
  position: number;
  joined_at: string;
  already_waiting: boolean;
  message: string;
}

// Rooms API
export const tablesApi = {
  list: () => api.get('/api/v1/rooms'),

  get: (tableId: string) => api.get(`/api/v1/rooms/${tableId}`),

  join: (tableId: string, buyIn: number, password?: string) =>
    api.post(`/api/v1/rooms/${tableId}/join`, { buyIn, password }),

  leave: (tableId: string) => api.post(`/api/v1/rooms/${tableId}/leave`),

  // Get rooms where current user is seated
  mySeats: () => api.get<{ rooms: string[] }>('/api/v1/rooms/my-seats'),

  // Quick join to an available room
  quickJoin: (blindLevel?: string) =>
    api.post<QuickJoinResponse>('/api/v1/rooms/quick-join',
      blindLevel ? { blindLevel } : {}
    ),

  // Waitlist API
  joinWaitlist: (roomId: string, buyIn: number) =>
    api.post<WaitlistJoinResponse>(`/api/v1/rooms/${roomId}/waitlist`, { buy_in: buyIn }),

  cancelWaitlist: (roomId: string) =>
    api.delete(`/api/v1/rooms/${roomId}/waitlist`),

  getWaitlist: (roomId: string) =>
    api.get<WaitlistResponse>(`/api/v1/rooms/${roomId}/waitlist`),
};

// Quick Join Response Type
export interface QuickJoinResponse {
  success: boolean;
  roomId: string;
  tableId: string;
  seat: number;
  buyIn: number;
  roomName: string;
  blinds: string;
}

// Wallet API
export const walletApi = {
  balance: () => api.get('/wallet/balance'),

  deposit: (amount: number, currency: string = 'KRW') =>
    api.post('/wallet/deposit', { amount, currency }),

  withdraw: (amount: number, currency: string = 'KRW') =>
    api.post('/wallet/withdraw', { amount, currency }),

  transactions: () => api.get('/wallet/transactions'),
};

// Bot API
export interface BotConfig {
  strategy: 'random' | 'calculated';
  nickname?: string;
  buyIn: number;
  aggression?: number;
  tightness?: number;
}

export interface BotInfo {
  botId: string;
  nickname: string;
  strategy: string;
  position: number | null;
  stack: number;
  status: string;
  handsPlayed: number;
}

export const botsApi = {
  // Get available strategies
  getStrategies: () => api.get('/api/v1/bots/strategies'),

  // Add a bot to a room
  addBot: (roomId: string, config?: Partial<BotConfig>) =>
    api.post('/api/v1/bots/add', { roomId, config: config || {} }),

  // Add multiple bots at once
  addMultipleBots: (roomId: string, count: number, strategy: string = 'calculated', buyIn: number = 1000) =>
    api.post('/api/v1/bots/add-multiple', { roomId, count, strategy, buyIn }),

  // Remove a bot from a room
  removeBot: (roomId: string, botId: string) =>
    api.delete('/api/v1/bots/remove', { data: { roomId, botId } }),

  // Get all bots in a room
  getRoomBots: (roomId: string) =>
    api.get<{ roomId: string; bots: BotInfo[]; totalCount: number }>(
      `/api/v1/bots/room/${roomId}`
    ),

  // Get all bots across all rooms
  getAllBots: () =>
    api.get<{ bots: BotInfo[]; totalCount: number }>('/api/v1/bots/all'),

  // Clear all bots from a room
  clearRoomBots: (roomId: string) =>
    api.delete(`/api/v1/bots/room/${roomId}`),

  // Clear all bots from all rooms
  clearAllBots: () =>
    api.delete('/api/v1/bots/all'),
};

// Admin API instance (for deposit)
export const adminApi = axios.create({
  baseURL: ADMIN_API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Deposit API Types (snake_case - 백엔드 응답 형식)
export interface DepositRequestCreate {
  requested_krw: number;
  telegram_id?: number;
}

export interface DepositRequestResponse {
  id: string;
  user_id: string;
  telegram_id: number | null;
  requested_krw: number;
  calculated_usdt: string;
  exchange_rate: string;
  memo: string;
  qr_data: string;
  status: 'pending' | 'confirmed' | 'expired' | 'cancelled';
  expires_at: string;
  remaining_seconds: number;
  created_at: string;
  confirmed_at: string | null;
  tx_hash: string | null;
}

export interface DepositStatusResponse {
  id: string;
  status: 'pending' | 'confirmed' | 'expired' | 'cancelled';
  remaining_seconds: number;
  is_expired: boolean;
  confirmed_at: string | null;
  tx_hash: string | null;
}

export interface ExchangeRateResponse {
  usdt_krw: string;
  timestamp: string;
}

// Users API Types
export interface UserProfile {
  id: string;
  email: string;
  nickname: string;
  avatar_url: string | null;
  balance: number;
  total_hands: number;
  total_winnings: number;
  created_at: string;
}

export interface UserStats {
  total_hands: number;
  hands_won: number;
  vpip: number;
  pfr: number;
  biggest_pot: number;
  win_rate: number;
}

// 상세 통계 타입
export interface DetailedStats {
  total_hands: number;
  total_winnings: number;
  hands_won: number;
  biggest_pot: number;
  vpip: number;
  pfr: number;
  three_bet: number;
  af: number;
  agg_freq: number;
  wtsd: number;
  wsd: number;
  win_rate: number;
  bb_per_100: number;
  play_style: {
    style: string;  // TAG, LAG, Nit, Calling Station, unknown
    description: string;
    emoji: string;
    characteristics?: string[];
  };
}

// VIP 상태 타입
export interface VIPStatusResponse {
  level: string;
  display_name: string;
  rakeback_pct: number;
  total_rake_paid: number;
  next_level: string | null;
  rake_to_next: number;
  progress_pct: number;
}

export interface UpdateProfileRequest {
  nickname?: string;
  avatar_url?: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

// Users API
export const usersApi = {
  getProfile: () => api.get<UserProfile>('/api/v1/users/me'),

  updateProfile: (data: UpdateProfileRequest) =>
    api.patch<UserProfile>('/api/v1/users/me', {
      nickname: data.nickname,
      avatarUrl: data.avatar_url,
    }),

  getStats: () => api.get<UserStats>('/api/v1/users/me/stats'),

  getDetailedStats: () => api.get<DetailedStats>('/api/v1/users/me/stats/detailed'),

  getVIPStatus: () => api.get<VIPStatusResponse>('/api/v1/users/me/vip-status'),

  changePassword: (data: ChangePasswordRequest) =>
    api.post('/api/v1/users/me/password', data),
};

// History API Types
export interface HandHistory {
  hand_id: string;
  table_id: string;
  hand_number: number;
  started_at: string;
  ended_at: string;
  pot_size: number;
  community_cards: string[];
  user_hole_cards: string[];
  user_bet_amount: number;
  user_won_amount: number;
  user_final_action: string;
  net_result: number;
}

export interface WalletTransaction {
  id: string;
  tx_type: 'crypto_deposit' | 'crypto_withdrawal' | 'buy_in' | 'cash_out' | 'win' | 'lose' | 'rake' | 'rakeback' | 'admin_adjust' | 'bonus';
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
  krw_amount: number;
  krw_balance_after: number;
  crypto_type: string | null;
  crypto_amount: string | null;
  crypto_tx_hash: string | null;
  description: string | null;
  created_at: string;
}

// History API
export const historyApi = {
  getGameHistory: (limit = 50, offset = 0) =>
    api.get<HandHistory[]>(`/api/v1/hands/history`, { params: { limit, offset } }),

  getTransactions: (txType?: string, limit = 50, offset = 0) =>
    api.get<WalletTransaction[]>('/wallet/transactions', {
      params: { tx_type: txType, limit, offset },
    }),
};

// 2FA API Types
export interface TwoFactorSetupResponse {
  secret: string;
  qr_code: string;
  backup_codes: string[];
}

export interface TwoFactorStatusResponse {
  is_enabled: boolean;
  backup_codes_remaining: number;
}

// 2FA API
export const twoFactorApi = {
  setup: () => api.post<TwoFactorSetupResponse>('/api/v1/auth/2fa/setup'),

  verify: (code: string) => api.post('/api/v1/auth/2fa/verify', { code }),

  status: () => api.get<TwoFactorStatusResponse>('/api/v1/auth/2fa/status'),

  disable: (code: string) => api.delete('/api/v1/auth/2fa', { data: { code } }),
};

// Deposit API
export const depositApi = {
  // 환율 조회
  getRate: () => adminApi.get<ExchangeRateResponse>('/api/ton/deposit/rate'),

  // 입금 요청 생성
  createRequest: (data: DepositRequestCreate) =>
    adminApi.post<DepositRequestResponse>('/api/ton/deposit/request', data),

  // 상태 확인 (폴링용)
  getStatus: (requestId: string) =>
    adminApi.get<DepositStatusResponse>(`/api/ton/deposit/status/${requestId}`),

  // 상세 조회 (QR 포함)
  getRequest: (requestId: string) =>
    adminApi.get<DepositRequestResponse>(`/api/ton/deposit/request/${requestId}`),
};

// Withdraw API Types
export interface WithdrawRequest {
  krw_amount: number;
  crypto_type: string;
  crypto_address: string;
}

export interface WithdrawResponse {
  transaction_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
  krw_amount: number;
  crypto_type: string;
  crypto_amount: string;
  crypto_address: string;
  estimated_arrival: string;
}

// Withdraw API
export const withdrawApi = {
  // 환전 요청
  request: (data: WithdrawRequest) =>
    api.post<WithdrawResponse>('/wallet/withdraw', data),

  // 환전 취소
  cancel: (transactionId: string) =>
    api.post<{ status: string; transaction_id: string }>(
      `/wallet/withdraw/${transactionId}/cancel`
    ),
};

// Announcements API (유저용 활성 공지 조회 - admin-backend에서 직접 조회)
export interface ActiveAnnouncement {
  id: string;
  title: string;
  content: string;
  announcement_type: 'notice' | 'event' | 'maintenance' | 'urgent';
  priority: 'low' | 'normal' | 'high' | 'critical';
  target: string;
  target_room_id: string | null;
  start_time: string | null;
  end_time: string | null;
  created_at: string | null;
}

export interface AnnouncementListResponse {
  items: ActiveAnnouncement[];
  total: number;
}

export const announcementsApi = {
  // 활성 공지 목록 조회 (admin-backend public 엔드포인트 사용)
  getActive: (limit: number = 10) =>
    adminApi.get<AnnouncementListResponse>('/api/public/announcements/active', {
      params: { limit },
    }),
};

export default api;
