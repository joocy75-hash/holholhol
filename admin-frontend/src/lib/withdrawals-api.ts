/**
 * Withdrawals API Client for crypto withdrawal management
 */
import { api } from './api';
import { useAuthStore } from '@/stores/authStore';

export interface WithdrawalListItem {
  id: string;
  userId: string;
  username: string;
  toAddress: string;
  amountUsdt: number;
  amountKrw: number;
  exchangeRate: number;
  networkFeeUsdt: number;
  networkFeeKrw: number;
  txHash: string | null;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'rejected';
  requestedAt: string;
  approvedBy: string | null;
  approvedAt: string | null;
  processedAt: string | null;
}

export interface WithdrawalDetail extends WithdrawalListItem {
  rejectionReason: string | null;
  createdAt: string;
  updatedAt: string;
  netAmountUsdt: number;
  netAmountKrw: number;
}

export interface PaginatedWithdrawals {
  items: WithdrawalListItem[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface WithdrawalStats {
  pendingCount: number;
  pendingAmountKrw: number;
  processingCount: number;
  todayCompletedCount: number;
  todayCompletedAmountKrw: number;
  todayRejectedCount: number;
  totalCompletedCount: number;
  totalCompletedAmountKrw: number;
}

function getToken(): string | undefined {
  return useAuthStore.getState().accessToken || undefined;
}

export interface WithdrawalSearchParams {
  status?: string;
  userId?: string;
  page?: number;
  pageSize?: number;
}

export interface WithdrawalApproveRequest {
  twoFactorCode: string;
  note?: string;
}

export interface WithdrawalRejectRequest {
  twoFactorCode: string;
  reason: string;
}

export const withdrawalsApi = {
  /**
   * List withdrawal requests with pagination and filtering
   */
  async listWithdrawals(params: WithdrawalSearchParams = {}): Promise<PaginatedWithdrawals> {
    const query = new URLSearchParams();
    if (params.status) query.append('status', params.status);
    if (params.userId) query.append('user_id', params.userId);
    query.append('page', String(params.page || 1));
    query.append('page_size', String(params.pageSize || 20));

    return api.get<PaginatedWithdrawals>(`/api/crypto/withdrawals?${query.toString()}`, { token: getToken() });
  },

  /**
   * Get detailed withdrawal information
   */
  async getWithdrawal(withdrawalId: string): Promise<WithdrawalDetail> {
    return api.get<WithdrawalDetail>(`/api/crypto/withdrawals/${withdrawalId}`, { token: getToken() });
  },

  /**
   * Get withdrawal statistics
   */
  async getStats(periodDays: number = 7): Promise<WithdrawalStats> {
    return api.get<WithdrawalStats>(`/api/crypto/withdrawals/stats?period_days=${periodDays}`, { token: getToken() });
  },

  /**
   * Get count of pending withdrawal requests
   */
  async getPendingCount(): Promise<{ count: number }> {
    return api.get<{ count: number }>('/api/crypto/withdrawals/pending/count', { token: getToken() });
  },

  /**
   * Approve a pending withdrawal request
   */
  async approveWithdrawal(withdrawalId: string, request: WithdrawalApproveRequest): Promise<{ message: string; withdrawal: WithdrawalDetail }> {
    return api.post<{ message: string; withdrawal: WithdrawalDetail }>(
      `/api/crypto/withdrawals/${withdrawalId}/approve`,
      request,
      { token: getToken() }
    );
  },

  /**
   * Reject a pending withdrawal request
   */
  async rejectWithdrawal(withdrawalId: string, request: WithdrawalRejectRequest): Promise<{ message: string; withdrawal: WithdrawalDetail }> {
    return api.post<{ message: string; withdrawal: WithdrawalDetail }>(
      `/api/crypto/withdrawals/${withdrawalId}/reject`,
      request,
      { token: getToken() }
    );
  },
};
