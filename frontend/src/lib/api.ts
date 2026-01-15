import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
  signup: (data: { email: string; password: string; nickname: string }) =>
    api.post('/api/v1/auth/register', data),

  login: (data: { email: string; password: string }) =>
    api.post('/api/v1/auth/login', data),

  logout: () => api.post('/api/v1/auth/logout'),

  me: () => api.get('/api/v1/users/me'),

  refresh: (refreshToken: string) =>
    api.post('/api/v1/auth/refresh', { refreshToken }),
};

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

export default api;
