/**
 * Dashboard API Client
 */
import { api } from './api';
import { API_ROUTES } from './api-routes';
import { useAuthStore } from '@/stores/authStore';

export interface ServerHealth {
  cpu: number;
  memory: number;
  latency: number;
  status: 'healthy' | 'warning' | 'critical' | 'unknown';
}

export interface DashboardSummary {
  ccu: number;
  dau: number;
  activeRooms: number;
  totalPlayers: number;
  serverHealth: ServerHealth;
}

export interface CCUHistoryItem {
  timestamp: string;
  hour: string;
  ccu: number;
}

export interface DAUHistoryItem {
  date: string;
  dau: number;
}

export interface MAUHistoryItem {
  month: string;
  mau: number;
}

export interface UserStatisticsSummary {
  ccu: number;
  dau: number;
  wau: number;
  mau: number;
  timestamp: string;
}

export interface RoomStats {
  activeRooms: number;
  totalPlayers: number;
  avgPlayersPerRoom: number;
}

export interface RoomDistribution {
  type: string;
  count: number;
}

export interface RevenueSummary {
  totalRake: number;
  totalHands: number;
  uniqueRooms: number;
  period: {
    start: string;
    end: string;
  };
}

export interface DailyRevenue {
  date: string;
  rake: number;
  hands: number;
}

export interface GameStatistics {
  today: {
    hands: number;
    rake: number;
    rooms: number;
  };
  total: {
    hands: number;
    rake: number;
  };
}

export interface ExchangeRateResponse {
  rate: number;
  source: string;
  timestamp: string;
}

// Event Statistics Types
export interface CheckinStats {
  today_checkins: number;
  total_checkins: number;
  total_rewards_paid: number;
  streak_7_count: number;
  streak_14_count: number;
  streak_30_count: number;
}

export interface ReferralStats {
  total_referrals: number;
  total_rewards_paid: number;
  today_referrals: number;
  recent_referrals: Array<{
    referrer: string;
    referee: string;
    reward: number;
    date: string | null;
  }>;
}

function getToken(): string | undefined {
  return useAuthStore.getState().accessToken || undefined;
}

export const dashboardApi = {
  async getSummary(): Promise<DashboardSummary> {
    return api.get<DashboardSummary>(API_ROUTES.DASHBOARD.SUMMARY, { token: getToken() });
  },

  async getCCU(): Promise<{ ccu: number; timestamp: string }> {
    return api.get(API_ROUTES.DASHBOARD.CCU, { token: getToken() });
  },

  async getDAU(date?: string): Promise<{ dau: number; date: string }> {
    const params = date ? `?date=${date}` : '';
    return api.get(`${API_ROUTES.DASHBOARD.DAU}${params}`, { token: getToken() });
  },

  async getCCUHistory(hours: number = 24): Promise<CCUHistoryItem[]> {
    return api.get<CCUHistoryItem[]>(`${API_ROUTES.DASHBOARD.CCU_HISTORY}?hours=${hours}`, { token: getToken() });
  },

  async getDAUHistory(days: number = 30): Promise<DAUHistoryItem[]> {
    return api.get<DAUHistoryItem[]>(`${API_ROUTES.DASHBOARD.DAU_HISTORY}?days=${days}`, { token: getToken() });
  },

  async getRoomStats(): Promise<RoomStats> {
    return api.get<RoomStats>(API_ROUTES.DASHBOARD.ROOMS, { token: getToken() });
  },

  async getRoomDistribution(): Promise<RoomDistribution[]> {
    return api.get<RoomDistribution[]>(API_ROUTES.DASHBOARD.ROOMS_DISTRIBUTION, { token: getToken() });
  },

  async getServerHealth(): Promise<ServerHealth> {
    return api.get<ServerHealth>(API_ROUTES.DASHBOARD.SERVER_HEALTH, { token: getToken() });
  },

  // Phase 5.2: MAU APIs
  async getMAU(month?: string): Promise<{ mau: number; month: string }> {
    const params = month ? `?month=${month}` : '';
    return api.get(`${API_ROUTES.DASHBOARD.MAU}${params}`, { token: getToken() });
  },

  async getMAUHistory(months: number = 12): Promise<MAUHistoryItem[]> {
    return api.get<MAUHistoryItem[]>(`${API_ROUTES.DASHBOARD.MAU_HISTORY}?months=${months}`, { token: getToken() });
  },

  async getUserStatisticsSummary(): Promise<UserStatisticsSummary> {
    return api.get<UserStatisticsSummary>(API_ROUTES.DASHBOARD.USERS_SUMMARY, { token: getToken() });
  },

  // Phase 5.3: Revenue APIs
  async getRevenueSummary(days: number = 30): Promise<RevenueSummary> {
    return api.get<RevenueSummary>(`${API_ROUTES.DASHBOARD.REVENUE_SUMMARY}?days=${days}`, { token: getToken() });
  },

  async getDailyRevenue(days: number = 30): Promise<DailyRevenue[]> {
    return api.get<DailyRevenue[]>(`${API_ROUTES.DASHBOARD.REVENUE_DAILY}?days=${days}`, { token: getToken() });
  },

  async getWeeklyRevenue(weeks: number = 12): Promise<DailyRevenue[]> {
    return api.get<DailyRevenue[]>(`${API_ROUTES.DASHBOARD.REVENUE_WEEKLY}?weeks=${weeks}`, { token: getToken() });
  },

  async getMonthlyRevenue(months: number = 12): Promise<DailyRevenue[]> {
    return api.get<DailyRevenue[]>(`${API_ROUTES.DASHBOARD.REVENUE_MONTHLY}?months=${months}`, { token: getToken() });
  },

  async getGameStatistics(): Promise<GameStatistics> {
    return api.get<GameStatistics>(API_ROUTES.DASHBOARD.GAME_STATISTICS, { token: getToken() });
  },

  async getTopPlayersByRake(limit: number = 10): Promise<{ players: unknown[] }> {
    return api.get(`${API_ROUTES.DASHBOARD.REVENUE_TOP_PLAYERS}?limit=${limit}`, { token: getToken() });
  },

  async getPlayerActivitySummary(): Promise<unknown> {
    return api.get(API_ROUTES.DASHBOARD.PLAYERS_ACTIVITY, { token: getToken() });
  },

  async getHourlyPlayerActivity(hours: number = 24): Promise<{ activity: unknown[] }> {
    return api.get(`${API_ROUTES.DASHBOARD.PLAYERS_HOURLY_ACTIVITY}?hours=${hours}`, { token: getToken() });
  },

  async getStakeLevelStatistics(): Promise<{ stake_levels: unknown[] }> {
    return api.get(API_ROUTES.DASHBOARD.STAKE_LEVELS, { token: getToken() });
  },

  // Exchange Rate API
  async getExchangeRate(): Promise<ExchangeRateResponse> {
    return api.get<ExchangeRateResponse>(API_ROUTES.CRYPTO.EXCHANGE_RATE, { token: getToken() });
  },

  // Event Statistics APIs
  async getCheckinStats(): Promise<CheckinStats> {
    return api.get<CheckinStats>('/api/dashboard/events/checkin/stats', { token: getToken() });
  },

  async getReferralStats(): Promise<ReferralStats> {
    return api.get<ReferralStats>('/api/dashboard/events/referral/stats', { token: getToken() });
  },
};

// Legacy statisticsApi for backwards compatibility
export const statisticsApi = {
  async getRevenueSummary(startDate?: string, endDate?: string): Promise<RevenueSummary> {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    const query = params.toString() ? `?${params.toString()}` : '';
    return api.get<RevenueSummary>(`${API_ROUTES.STATISTICS.REVENUE_SUMMARY}${query}`, { token: getToken() });
  },

  async getDailyRevenue(days: number = 30): Promise<DailyRevenue[]> {
    return api.get<DailyRevenue[]>(`${API_ROUTES.STATISTICS.REVENUE_DAILY}?days=${days}`, { token: getToken() });
  },

  async getWeeklyRevenue(weeks: number = 12): Promise<DailyRevenue[]> {
    return api.get<DailyRevenue[]>(`${API_ROUTES.STATISTICS.REVENUE_WEEKLY}?weeks=${weeks}`, { token: getToken() });
  },

  async getMonthlyRevenue(months: number = 12): Promise<DailyRevenue[]> {
    return api.get<DailyRevenue[]>(`${API_ROUTES.STATISTICS.REVENUE_MONTHLY}?months=${months}`, { token: getToken() });
  },

  async getGameStatistics(): Promise<GameStatistics> {
    return api.get<GameStatistics>(API_ROUTES.STATISTICS.GAME, { token: getToken() });
  },
};
