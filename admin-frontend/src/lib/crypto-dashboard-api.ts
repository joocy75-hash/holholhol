/**
 * Crypto Dashboard API Client
 * Phase 9: 암호화폐 통계 및 지갑 관리 API
 */
import { api } from './api';
import { useAuthStore } from '@/stores/authStore';

// ============================================================
// Types
// ============================================================

export interface CryptoSummaryStats {
  period_days: number;
  deposits: {
    total_count: number;
    total_usdt: number;
    total_krw: number;
    avg_usdt: number;
  };
  withdrawals: {
    total_count: number;
    total_usdt: number;
    total_krw: number;
    avg_usdt: number;
  };
  net_flow_usdt: number;
  net_flow_krw: number;
  today: {
    deposits_count: number;
    deposits_usdt: number;
    withdrawals_count: number;
    withdrawals_usdt: number;
    net_flow_usdt: number;
  };
  pending: {
    deposits_count: number;
    withdrawals_count: number;
    withdrawals_usdt: number;
  };
}

export interface DailyStat {
  date: string;
  deposits_count: number;
  deposits_usdt: number;
  deposits_krw: number;
  withdrawals_count: number;
  withdrawals_usdt: number;
  withdrawals_krw: number;
  net_flow_usdt: number;
  net_flow_krw: number;
}

export interface HourlyPattern {
  hour: number;
  deposits_count: number;
  deposits_usdt: number;
  withdrawals_count: number;
  withdrawals_usdt: number;
  total_transactions: number;
}

export interface TopUser {
  user_id: string;
  deposits_count: number;
  deposits_usdt: number;
  withdrawals_count: number;
  withdrawals_usdt: number;
  total_volume_usdt: number;
  net_flow_usdt: number;
}

export interface ExchangeRateHistory {
  rate: number;
  source: string;
  recorded_at: string;
}

export interface TrendAnalysis {
  analysis_period: {
    current: { start: string; end: string };
    previous: { start: string; end: string };
  };
  deposits: {
    current_count: number;
    previous_count: number;
    change_percent: number;
    current_usdt: number;
    previous_usdt: number;
    volume_change_percent: number;
  };
  withdrawals: {
    current_count: number;
    previous_count: number;
    change_percent: number;
    current_usdt: number;
    previous_usdt: number;
    volume_change_percent: number;
  };
  overall_trend: 'increasing' | 'stable' | 'decreasing';
  deposit_trend: 'increasing' | 'stable' | 'decreasing';
  withdrawal_trend: 'increasing' | 'stable' | 'decreasing';
}

export interface WalletBalance {
  address: string;
  balance_usdt: number;
  balance_krw: number;
  available_usdt: number;
  available_krw: number;
  pending_withdrawals_usdt: number;
  pending_withdrawals_krw: number;
  pending_withdrawals_count: number;
  exchange_rate: number;
  last_updated: string;
}

export interface WalletAlertStatus {
  is_low_balance: boolean;
  is_critical_balance: boolean;
  thresholds: {
    warning_usdt: number;
    critical_usdt: number;
    recovery_margin_usdt: number;
  };
  last_alerts: {
    warning: string | null;
    critical: string | null;
    recovery: string | null;
  };
  last_alerted_balance_usdt: number | null;
}

export interface AutomationStatus {
  executor_enabled: boolean;
  executor_running: boolean;
  executor_pending_count: number;
  executor_retry_queue_size: number;
  executor_auto_threshold_usdt: number;
  monitor_running: boolean;
  monitor_tracking_count: number;
  monitor_today_completed: number;
  hot_wallet_usdt: number;
}

// ============================================================
// API Client
// ============================================================

function getToken(): string | undefined {
  return useAuthStore.getState().accessToken || undefined;
}

export const cryptoDashboardApi = {
  // =========================================================
  // Statistics
  // =========================================================

  /**
   * 요약 통계 조회
   */
  async getSummaryStats(days: number = 30): Promise<CryptoSummaryStats> {
    return api.get<CryptoSummaryStats>(
      `/api/crypto/stats/summary/v2?days=${days}`,
      { token: getToken() }
    );
  },

  /**
   * 일별 통계 조회
   */
  async getDailyStats(days: number = 30): Promise<{ items: DailyStat[]; days: number }> {
    return api.get<{ items: DailyStat[]; days: number }>(
      `/api/crypto/stats/daily/v2?days=${days}`,
      { token: getToken() }
    );
  },

  /**
   * 시간대별 패턴 조회
   */
  async getHourlyPatterns(days: number = 7): Promise<{ items: HourlyPattern[]; analysis_days: number }> {
    return api.get<{ items: HourlyPattern[]; analysis_days: number }>(
      `/api/crypto/stats/hourly-patterns?days=${days}`,
      { token: getToken() }
    );
  },

  /**
   * 상위 사용자 조회
   */
  async getTopUsers(days: number = 30, limit: number = 10): Promise<{ items: TopUser[]; days: number; limit: number }> {
    return api.get<{ items: TopUser[]; days: number; limit: number }>(
      `/api/crypto/stats/top-users?days=${days}&limit=${limit}`,
      { token: getToken() }
    );
  },

  /**
   * 환율 히스토리 조회
   */
  async getExchangeRateHistory(hours: number = 24): Promise<{ items: ExchangeRateHistory[]; hours: number }> {
    return api.get<{ items: ExchangeRateHistory[]; hours: number }>(
      `/api/crypto/stats/exchange-rate-history?hours=${hours}`,
      { token: getToken() }
    );
  },

  /**
   * 트렌드 분석 조회
   */
  async getTrendAnalysis(days: number = 7): Promise<TrendAnalysis> {
    return api.get<TrendAnalysis>(
      `/api/crypto/stats/trend?days=${days}`,
      { token: getToken() }
    );
  },

  // =========================================================
  // Wallet
  // =========================================================

  /**
   * 지갑 잔액 조회
   */
  async getWalletBalance(): Promise<WalletBalance> {
    return api.get<WalletBalance>(
      '/api/crypto/wallet/balance',
      { token: getToken() }
    );
  },

  /**
   * 지갑 잔액 히스토리 조회
   */
  async getWalletBalanceHistory(hours: number = 24): Promise<{ items: any[] }> {
    return api.get<{ items: any[] }>(
      `/api/crypto/wallet/balance/history?hours=${hours}`,
      { token: getToken() }
    );
  },

  /**
   * 지갑 알림 상태 조회
   */
  async getWalletAlertStatus(): Promise<WalletAlertStatus> {
    return api.get<WalletAlertStatus>(
      '/api/crypto/wallet/alerts/status',
      { token: getToken() }
    );
  },

  /**
   * 지갑 알림 임계값 업데이트
   */
  async updateWalletAlertThresholds(thresholds: {
    warning_usdt?: number;
    critical_usdt?: number;
    recovery_margin_usdt?: number;
    cooldown_seconds?: number;
  }): Promise<{ message: string; thresholds: any }> {
    return api.put<{ message: string; thresholds: any }>(
      '/api/crypto/wallet/alerts/thresholds',
      thresholds,
      { token: getToken() }
    );
  },

  /**
   * 지갑 잔액 수동 체크
   */
  async forceWalletCheck(): Promise<{ message: string; balance: any; alert_status: WalletAlertStatus }> {
    return api.post<{ message: string; balance: any; alert_status: WalletAlertStatus }>(
      '/api/crypto/wallet/alerts/force-check',
      {},
      { token: getToken() }
    );
  },

  // =========================================================
  // Automation
  // =========================================================

  /**
   * 자동화 상태 조회
   */
  async getAutomationStatus(): Promise<AutomationStatus> {
    return api.get<AutomationStatus>(
      '/api/crypto/automation/status',
      { token: getToken() }
    );
  },
};
