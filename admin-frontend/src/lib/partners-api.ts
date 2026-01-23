/**
 * Partners API Client
 */
import { api } from './api';
import { useAuthStore } from '@/stores/authStore';

// =============================================================================
// Enums
// =============================================================================

export enum CommissionType {
  RAKEBACK = 'rakeback',
  REVSHARE = 'revshare',
  TURNOVER = 'turnover',
}

export enum PartnerStatus {
  ACTIVE = 'active',
  SUSPENDED = 'suspended',
  TERMINATED = 'terminated',
}

export enum SettlementPeriod {
  DAILY = 'daily',
  WEEKLY = 'weekly',
  MONTHLY = 'monthly',
}

export enum SettlementStatus {
  PENDING = 'pending',
  APPROVED = 'approved',
  REJECTED = 'rejected',
  PAID = 'paid',
}

// =============================================================================
// Interfaces
// =============================================================================

export interface Partner {
  id: string;
  userId: string;
  partnerCode: string;
  name: string;
  contactInfo: string | null;
  notes: string | null;
  commissionType: CommissionType;
  commissionRate: number;
  status: PartnerStatus;
  totalReferrals: number;
  totalCommissionEarned: number;
  currentMonthCommission: number;
  createdAt: string;
  updatedAt: string;
}

export interface PaginatedPartners {
  items: Partner[];
  total: number;
  page: number;
  pageSize: number;
}

export interface Referral {
  id: string;
  nickname: string;
  email: string;
  totalRakePaidKrw: number;
  totalBetAmountKrw: number;
  totalNetProfitKrw: number;
  createdAt: string;
}

export interface PaginatedReferrals {
  items: Referral[];
  total: number;
  page: number;
  pageSize: number;
}

export interface SettlementDetailItem {
  userId: string;
  nickname: string;
  amount: number;
}

export interface Settlement {
  id: string;
  partnerId: string;
  partnerName?: string;
  partnerCode?: string;
  periodType: SettlementPeriod;
  periodStart: string;
  periodEnd: string;
  commissionType: CommissionType;
  commissionRate: number;
  baseAmount: number;
  commissionAmount: number;
  status: SettlementStatus;
  approvedAt: string | null;
  paidAt: string | null;
  rejectionReason: string | null;
  detail: SettlementDetailItem[] | null;
  createdAt: string;
}

export interface PaginatedSettlements {
  items: Settlement[];
  total: number;
  page: number;
  pageSize: number;
}

// =============================================================================
// Request Interfaces
// =============================================================================

export interface CreatePartnerData {
  userId: string;
  partnerCode: string;
  name: string;
  contactInfo?: string;
  notes?: string;
  commissionType?: CommissionType;
  commissionRate?: number;
}

export interface UpdatePartnerData {
  name?: string;
  contactInfo?: string;
  commissionType?: CommissionType;
  commissionRate?: number;
  status?: PartnerStatus;
}

export interface GenerateSettlementData {
  periodType: SettlementPeriod;
  periodStart: string;
  periodEnd: string;
  partnerIds?: string[];
}

export interface UpdateSettlementData {
  status: SettlementStatus;
  rejectionReason?: string;
}

// =============================================================================
// Search Params
// =============================================================================

export interface PartnerSearchParams {
  search?: string;
  status?: PartnerStatus;
  page?: number;
  pageSize?: number;
}

export interface SettlementSearchParams {
  partnerId?: string;
  status?: SettlementStatus;
  periodType?: SettlementPeriod;
  page?: number;
  pageSize?: number;
}

// =============================================================================
// Helper
// =============================================================================

function getToken(): string | undefined {
  return useAuthStore.getState().accessToken || undefined;
}

// =============================================================================
// API Client
// =============================================================================

export const partnersApi = {
  // -------------------------------------------------------------------------
  // Partner CRUD
  // -------------------------------------------------------------------------

  async listPartners(params: PartnerSearchParams = {}): Promise<PaginatedPartners> {
    const query = new URLSearchParams();
    if (params.search) query.append('search', params.search);
    if (params.status) query.append('status', params.status);
    query.append('page', String(params.page || 1));
    query.append('page_size', String(params.pageSize || 20));

    return api.get<PaginatedPartners>(`/api/partners?${query.toString()}`, { token: getToken() });
  },

  async getPartner(partnerId: string): Promise<Partner> {
    return api.get<Partner>(`/api/partners/${partnerId}`, { token: getToken() });
  },

  async createPartner(data: CreatePartnerData): Promise<Partner> {
    const payload = {
      user_id: data.userId,
      partner_code: data.partnerCode,
      name: data.name,
      contact_info: data.contactInfo,
      notes: data.notes,
      commission_type: data.commissionType || CommissionType.RAKEBACK,
      commission_rate: data.commissionRate || 0.30,
    };
    return api.post<Partner>('/api/partners', payload, { token: getToken() });
  },

  async updatePartner(partnerId: string, data: UpdatePartnerData): Promise<Partner> {
    const payload: Record<string, unknown> = {};
    if (data.name !== undefined) payload.name = data.name;
    if (data.contactInfo !== undefined) payload.contact_info = data.contactInfo;
    if (data.commissionType !== undefined) payload.commission_type = data.commissionType;
    if (data.commissionRate !== undefined) payload.commission_rate = data.commissionRate;
    if (data.status !== undefined) payload.status = data.status;

    return api.patch<Partner>(`/api/partners/${partnerId}`, payload, { token: getToken() });
  },

  async deletePartner(partnerId: string): Promise<void> {
    await api.delete(`/api/partners/${partnerId}`, { token: getToken() });
  },

  async regenerateCode(partnerId: string): Promise<{ partnerCode: string }> {
    return api.post<{ partnerCode: string }>(`/api/partners/${partnerId}/regenerate-code`, {}, { token: getToken() });
  },

  // -------------------------------------------------------------------------
  // Referrals
  // -------------------------------------------------------------------------

  async getPartnerReferrals(
    partnerId: string,
    page: number = 1,
    pageSize: number = 20
  ): Promise<PaginatedReferrals> {
    const query = new URLSearchParams();
    query.append('page', String(page));
    query.append('page_size', String(pageSize));

    return api.get<PaginatedReferrals>(`/api/partners/${partnerId}/referrals?${query.toString()}`, { token: getToken() });
  },

  // -------------------------------------------------------------------------
  // Settlements
  // -------------------------------------------------------------------------

  async listSettlements(params: SettlementSearchParams = {}): Promise<PaginatedSettlements> {
    const query = new URLSearchParams();
    if (params.partnerId) query.append('partner_id', params.partnerId);
    if (params.status) query.append('status', params.status);
    if (params.periodType) query.append('period_type', params.periodType);
    query.append('page', String(params.page || 1));
    query.append('page_size', String(params.pageSize || 20));

    return api.get<PaginatedSettlements>(`/api/partners/settlements?${query.toString()}`, { token: getToken() });
  },

  async getPartnerSettlements(
    partnerId: string,
    params: SettlementSearchParams = {}
  ): Promise<PaginatedSettlements> {
    const query = new URLSearchParams();
    if (params.status) query.append('status', params.status);
    if (params.periodType) query.append('period_type', params.periodType);
    query.append('page', String(params.page || 1));
    query.append('page_size', String(params.pageSize || 20));

    return api.get<PaginatedSettlements>(`/api/partners/${partnerId}/settlements?${query.toString()}`, { token: getToken() });
  },

  async generateSettlements(data: GenerateSettlementData): Promise<Settlement[]> {
    const payload = {
      period_type: data.periodType,
      period_start: data.periodStart,
      period_end: data.periodEnd,
      partner_ids: data.partnerIds,
    };
    return api.post<Settlement[]>('/api/partners/settlements/generate', payload, { token: getToken() });
  },

  async updateSettlement(settlementId: string, data: UpdateSettlementData): Promise<Settlement> {
    const payload = {
      status: data.status,
      rejection_reason: data.rejectionReason,
    };
    return api.patch<Settlement>(`/api/partners/settlements/${settlementId}`, payload, { token: getToken() });
  },

  async paySettlement(settlementId: string): Promise<Settlement> {
    return api.post<Settlement>(`/api/partners/settlements/${settlementId}/pay`, {}, { token: getToken() });
  },
};
