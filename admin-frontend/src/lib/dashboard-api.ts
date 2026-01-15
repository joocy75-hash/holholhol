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
};

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
