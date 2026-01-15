/**
 * Users API Client
 */
import { api } from './api';
import { useAuthStore } from '@/stores/authStore';

export interface User {
  id: string;
  username: string;
  email: string;
  balance: number;
  createdAt: string | null;
  lastLogin: string | null;
  isBanned: boolean;
}

export interface UserDetail extends User {
  banReason: string | null;
  banExpiresAt: string | null;
}

export interface PaginatedUsers {
  items: User[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface Transaction {
  id: string;
  type: string;
  amount: number;
  balanceBefore: number;
  balanceAfter: number;
  description: string | null;
  createdAt: string | null;
}

export interface LoginHistory {
  id: string;
  ipAddress: string | null;
  userAgent: string | null;
  success: boolean;
  createdAt: string | null;
}

export interface HandHistory {
  id: string;
  handId: string;
  roomId: string | null;
  position: number | null;
  cards: string | null;
  betAmount: number;
  wonAmount: number;
  potSize: number;
  createdAt: string | null;
}

function getToken(): string | undefined {
  return useAuthStore.getState().accessToken || undefined;
}

export interface SearchParams {
  search?: string;
  isBanned?: boolean;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
  page?: number;
  pageSize?: number;
}

export const usersApi = {
  async listUsers(params: SearchParams = {}): Promise<PaginatedUsers> {
    const query = new URLSearchParams();
    if (params.search) query.append('search', params.search);
    if (params.isBanned !== undefined) query.append('is_banned', String(params.isBanned));
    if (params.sortBy) query.append('sort_by', params.sortBy);
    if (params.sortOrder) query.append('sort_order', params.sortOrder);
    query.append('page', String(params.page || 1));
    query.append('page_size', String(params.pageSize || 20));
    
    return api.get<PaginatedUsers>(`/api/users?${query.toString()}`, { token: getToken() });
  },

  async getUser(userId: string): Promise<UserDetail> {
    return api.get<UserDetail>(`/api/users/${userId}`, { token: getToken() });
  },

  async getUserTransactions(
    userId: string,
    page: number = 1,
    pageSize: number = 20,
    txType?: string
  ): Promise<{ items: Transaction[]; total: number; page: number; pageSize: number }> {
    const query = new URLSearchParams();
    query.append('page', String(page));
    query.append('page_size', String(pageSize));
    if (txType) query.append('tx_type', txType);
    
    return api.get(`/api/users/${userId}/transactions?${query.toString()}`, { token: getToken() });
  },

  async getUserLoginHistory(
    userId: string,
    page: number = 1,
    pageSize: number = 20
  ): Promise<{ items: LoginHistory[]; total: number; page: number; pageSize: number }> {
    const query = new URLSearchParams();
    query.append('page', String(page));
    query.append('page_size', String(pageSize));
    
    return api.get(`/api/users/${userId}/login-history?${query.toString()}`, { token: getToken() });
  },

  async getUserHands(
    userId: string,
    page: number = 1,
    pageSize: number = 20
  ): Promise<{ items: HandHistory[]; total: number; page: number; pageSize: number }> {
    const query = new URLSearchParams();
    query.append('page', String(page));
    query.append('page_size', String(pageSize));
    
    return api.get(`/api/users/${userId}/hands?${query.toString()}`, { token: getToken() });
  },
};
