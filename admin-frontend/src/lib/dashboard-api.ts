/**
 * Dashboard API Client
 */
import { api } from './api';
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

function getToken(): string | undefined {
  return useAuthStore.getState().accessToken || undefined;
}

export const dashboardApi = {
  async getSummary(): Promise<DashboardSummary> {
    return api.get<DashboardSummary>('/api/dashboard/summary', { token: getToken() });
  },

  async getCCU(): Promise<{ ccu: number; timestamp: string }> {
    return api.get('/api/dashboard/ccu', { token: getToken() });
  },

  async getDAU(date?: string): Promise<{ dau: number; date: string }> {
    const params = date ? `?date=${date}` : '';
    return api.get(`/api/dashboard/dau${params}`, { token: getToken() });
  },

  async getCCUHistory(hours: number = 24): Promise<CCUHistoryItem[]> {
    return api.get<CCUHistoryItem[]>(`/api/dashboard/ccu/history?hours=${hours}`, { token: getToken() });
  },

  async getDAUHistory(days: number = 30): Promise<DAUHistoryItem[]> {
    return api.get<DAUHistoryItem[]>(`/api/dashboard/dau/history?days=${days}`, { token: getToken() });
  },

  async getRoomStats(): Promise<RoomStats> {
    return api.get<RoomStats>('/api/dashboard/rooms', { token: getToken() });
  },

  async getRoomDistribution(): Promise<RoomDistribution[]> {
    return api.get<RoomDistribution[]>('/api/dashboard/rooms/distribution', { token: getToken() });
  },

  async getServerHealth(): Promise<ServerHealth> {
    return api.get<ServerHealth>('/api/dashboard/server/health', { token: getToken() });
  },

  // Phase 5.2: MAU APIs
  async getMAU(month?: string): Promise<{ mau: number; month: string }> {
    const params = month ? `?month=${month}` : '';
    return api.get(`/api/dashboard/mau${params}`, { token: getToken() });
  },

  async getMAUHistory(months: number = 12): Promise<MAUHistoryItem[]> {
    return api.get<MAUHistoryItem[]>(`/api/dashboard/mau/history?months=${months}`, { token: getToken() });
  },

  async getUserStatisticsSummary(): Promise<UserStatisticsSummary> {
    return api.get<UserStatisticsSummary>('/api/dashboard/users/summary', { token: getToken() });
  },

  // Phase 5.3: Revenue APIs
  async getRevenueSummary(days: number = 30): Promise<RevenueSummary> {
    return api.get<RevenueSummary>(`/api/dashboard/revenue/summary?days=${days}`, { token: getToken() });
  },

  async getDailyRevenue(days: number = 30): Promise<DailyRevenue[]> {
    return api.get<DailyRevenue[]>(`/api/dashboard/revenue/daily?days=${days}`, { token: getToken() });
  },

  async getWeeklyRevenue(weeks: number = 12): Promise<DailyRevenue[]> {
    return api.get<DailyRevenue[]>(`/api/dashboard/revenue/weekly?weeks=${weeks}`, { token: getToken() });
  },

  async getMonthlyRevenue(months: number = 12): Promise<DailyRevenue[]> {
    return api.get<DailyRevenue[]>(`/api/dashboard/revenue/monthly?months=${months}`, { token: getToken() });
  },

  async getGameStatistics(): Promise<GameStatistics> {
    return api.get<GameStatistics>('/api/dashboard/game/statistics', { token: getToken() });
  },

  async getTopPlayersByRake(limit: number = 10): Promise<{ players: any[] }> {
    return api.get(`/api/dashboard/revenue/top-players?limit=${limit}`, { token: getToken() });
  },

  async getPlayerActivitySummary(): Promise<any> {
    return api.get('/api/dashboard/players/activity', { token: getToken() });
  },

  async getHourlyPlayerActivity(hours: number = 24): Promise<{ activity: any[] }> {
    return api.get(`/api/dashboard/players/hourly-activity?hours=${hours}`, { token: getToken() });
  },

  async getStakeLevelStatistics(): Promise<{ stake_levels: any[] }> {
    return api.get('/api/dashboard/stake-levels', { token: getToken() });
  },
};

// Legacy statisticsApi for backwards compatibility
export const statisticsApi = {
  async getRevenueSummary(startDate?: string, endDate?: string): Promise<RevenueSummary> {
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    const query = params.toString() ? `?${params.toString()}` : '';
    return api.get<RevenueSummary>(`/api/statistics/revenue/summary${query}`, { token: getToken() });
  },

  async getDailyRevenue(days: number = 30): Promise<DailyRevenue[]> {
    return api.get<DailyRevenue[]>(`/api/statistics/revenue/daily?days=${days}`, { token: getToken() });
  },

  async getWeeklyRevenue(weeks: number = 12): Promise<DailyRevenue[]> {
    return api.get<DailyRevenue[]>(`/api/statistics/revenue/weekly?weeks=${weeks}`, { token: getToken() });
  },

  async getMonthlyRevenue(months: number = 12): Promise<DailyRevenue[]> {
    return api.get<DailyRevenue[]>(`/api/statistics/revenue/monthly?months=${months}`, { token: getToken() });
  },

  async getGameStatistics(): Promise<GameStatistics> {
    return api.get<GameStatistics>('/api/statistics/game', { token: getToken() });
  },
};
