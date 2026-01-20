/**
 * Multi-Approval API Client
 * Phase 10: 다중 승인 시스템 API
 */
import { api } from './api';
import { useAuthStore } from '@/stores/authStore';

// ============================================================
// Types
// ============================================================

export interface ApprovalPolicy {
  id: string;
  name: string;
  description: string | null;
  min_amount_usdt: number;
  max_amount_usdt: number | null;
  required_approvals: number;
  expiry_minutes: number;
  priority: number;
  is_active: boolean;
}

export interface ApprovalRecord {
  admin_name: string;
  action: 'approve' | 'reject';
  note: string | null;
  created_at: string;
}

export interface ApprovalRequest {
  id: string;
  withdrawal_id: string;
  user_id: string;
  amount_usdt: number;
  amount_krw: number;
  to_address: string;
  status: 'pending' | 'partially_approved' | 'approved' | 'rejected' | 'expired';
  required_approvals: number;
  current_approvals: number;
  expires_at: string;
  created_at: string;
  approval_records: ApprovalRecord[];
}

export interface ApprovalStatusDetail {
  id: string;
  withdrawal_id: string;
  status: string;
  required_approvals: number;
  current_approvals: number;
  remaining_approvals: number;
  is_fully_approved: boolean;
  is_expired: boolean;
  expires_at: string;
  approval_records: ApprovalRecord[];
}

export interface ApprovalStats {
  pending_count: number;
  today_approved: number;
  today_rejected: number;
}

export interface VipLimit {
  vip_level: number;
  name: string;
  per_transaction_usdt: number;
  daily_usdt: number;
  monthly_usdt: number;
  min_withdrawal_usdt: number;
}

export interface UserLimitStatus {
  user_id: string;
  vip_level: number;
  limits: {
    per_transaction_usdt: number;
    daily_usdt: number;
    monthly_usdt: number;
    min_withdrawal_usdt: number;
  };
  usage: {
    daily_used_usdt: number;
    daily_remaining_usdt: number;
    daily_usage_percent: number;
    monthly_used_usdt: number;
    monthly_remaining_usdt: number;
    monthly_usage_percent: number;
    pending_usdt: number;
  };
}

// ============================================================
// API Client
// ============================================================

function getToken(): string | undefined {
  return useAuthStore.getState().accessToken || undefined;
}

export const multiApprovalApi = {
  // =========================================================
  // Approval Policies
  // =========================================================

  /**
   * 승인 정책 목록 조회
   */
  async listPolicies(): Promise<{ items: ApprovalPolicy[] }> {
    return api.get<{ items: ApprovalPolicy[] }>(
      '/api/crypto/approvals/policies',
      { token: getToken() }
    );
  },

  /**
   * 승인 정책 생성
   */
  async createPolicy(policy: {
    name: string;
    description?: string;
    min_amount_usdt: number;
    max_amount_usdt?: number;
    required_approvals: number;
    expiry_minutes?: number;
    priority?: number;
  }): Promise<{ message: string; policy: { id: string; name: string } }> {
    return api.post<{ message: string; policy: { id: string; name: string } }>(
      '/api/crypto/approvals/policies',
      policy,
      { token: getToken() }
    );
  },

  /**
   * 승인 정책 업데이트
   */
  async updatePolicy(
    policyId: string,
    updates: Partial<Omit<ApprovalPolicy, 'id'>>
  ): Promise<{ message: string; policy: { id: string; name: string; is_active: boolean } }> {
    return api.put<{ message: string; policy: { id: string; name: string; is_active: boolean } }>(
      `/api/crypto/approvals/policies/${policyId}`,
      updates,
      { token: getToken() }
    );
  },

  // =========================================================
  // Approval Requests
  // =========================================================

  /**
   * 대기 중인 승인 요청 목록
   */
  async listPendingRequests(limit: number = 50): Promise<{ items: ApprovalRequest[]; total: number }> {
    return api.get<{ items: ApprovalRequest[]; total: number }>(
      `/api/crypto/approvals/pending?limit=${limit}`,
      { token: getToken() }
    );
  },

  /**
   * 승인 요청 상세 조회
   */
  async getRequestStatus(requestId: string): Promise<ApprovalStatusDetail> {
    return api.get<ApprovalStatusDetail>(
      `/api/crypto/approvals/${requestId}`,
      { token: getToken() }
    );
  },

  /**
   * 승인 처리
   */
  async approve(
    requestId: string,
    note?: string
  ): Promise<{
    message: string;
    status: string;
    current_approvals: number;
    required_approvals: number;
    is_fully_approved: boolean;
  }> {
    return api.post<{
      message: string;
      status: string;
      current_approvals: number;
      required_approvals: number;
      is_fully_approved: boolean;
    }>(
      `/api/crypto/approvals/${requestId}/approve`,
      { note },
      { token: getToken() }
    );
  },

  /**
   * 거부 처리
   */
  async reject(
    requestId: string,
    reason: string
  ): Promise<{ message: string; status: string }> {
    return api.post<{ message: string; status: string }>(
      `/api/crypto/approvals/${requestId}/reject`,
      { reason },
      { token: getToken() }
    );
  },

  /**
   * 승인 통계
   */
  async getStats(): Promise<ApprovalStats> {
    return api.get<ApprovalStats>(
      '/api/crypto/approvals/stats',
      { token: getToken() }
    );
  },

  // =========================================================
  // Withdrawal Limits
  // =========================================================

  /**
   * VIP 등급별 한도 목록
   */
  async listVipLimits(): Promise<{ items: VipLimit[] }> {
    return api.get<{ items: VipLimit[] }>(
      '/api/crypto/limits/vip-levels',
      { token: getToken() }
    );
  },

  /**
   * 사용자 한도 현황
   */
  async getUserLimitStatus(userId: string, vipLevel: number = 0): Promise<UserLimitStatus> {
    return api.get<UserLimitStatus>(
      `/api/crypto/limits/user/${userId}?vip_level=${vipLevel}`,
      { token: getToken() }
    );
  },

  /**
   * 한도 사전 확인
   */
  async checkLimit(
    userId: string,
    amountUsdt: number,
    vipLevel: number = 0
  ): Promise<{
    allowed: boolean;
    vip_level: number;
    amount_usdt: number;
    daily_used: number;
    daily_limit: number;
    daily_remaining: number;
    monthly_used: number;
    monthly_limit: number;
  }> {
    return api.post<{
      allowed: boolean;
      vip_level: number;
      amount_usdt: number;
      daily_used: number;
      daily_limit: number;
      daily_remaining: number;
      monthly_used: number;
      monthly_limit: number;
    }>(
      `/api/crypto/limits/check?user_id=${userId}&amount_usdt=${amountUsdt}&vip_level=${vipLevel}`,
      {},
      { token: getToken() }
    );
  },

  // =========================================================
  // Telegram
  // =========================================================

  /**
   * Telegram 설정 상태
   */
  async getTelegramStatus(): Promise<{
    configured: boolean;
    bot_token_set: boolean;
    chat_id_set: boolean;
  }> {
    return api.get<{
      configured: boolean;
      bot_token_set: boolean;
      chat_id_set: boolean;
    }>(
      '/api/crypto/telegram/status',
      { token: getToken() }
    );
  },

  /**
   * Telegram 테스트 알림
   */
  async sendTelegramTest(
    title: string,
    message: string,
    level: 'info' | 'warning' | 'critical' = 'info'
  ): Promise<{ message: string; success: boolean }> {
    return api.post<{ message: string; success: boolean }>(
      '/api/crypto/telegram/test',
      { title, message, level },
      { token: getToken() }
    );
  },
};
