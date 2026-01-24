/**
 * Partner Portal API
 *
 * 파트너 전용 API 클라이언트입니다.
 */

import { api } from './api';
import { API_ROUTES } from './api-routes';
import type {
  PartnerLoginRequest,
  PartnerLoginResponse,
  PartnerInfo,
  PartnerReferral,
  PartnerSettlement,
  PartnerOverviewStats,
  PartnerDailyStatsResponse,
  PartnerMonthlyStatsResponse,
} from '@/types';

export interface PartnerReferralListResponse {
  items: PartnerReferral[];
  total: number;
  page: number;
  pageSize: number;
}

export interface PartnerSettlementListResponse {
  items: PartnerSettlement[];
  total: number;
  page: number;
  pageSize: number;
}

export const partnerPortalApi = {
  /**
   * 파트너 로그인
   */
  login: async (data: PartnerLoginRequest): Promise<PartnerLoginResponse> => {
    return api.post<PartnerLoginResponse>(API_ROUTES.PARTNER.LOGIN, data);
  },

  /**
   * 내 파트너 정보 조회
   */
  getMyInfo: async (token: string): Promise<PartnerInfo> => {
    return api.get<PartnerInfo>(API_ROUTES.PARTNER.ME, { token });
  },

  /**
   * 추천 회원 목록 조회
   */
  getReferrals: async (
    token: string,
    params?: { page?: number; pageSize?: number; search?: string }
  ): Promise<PartnerReferralListResponse> => {
    const queryParams = new URLSearchParams();
    if (params?.page) queryParams.set('page', params.page.toString());
    if (params?.pageSize) queryParams.set('page_size', params.pageSize.toString());
    if (params?.search) queryParams.set('search', params.search);

    const url = queryParams.toString()
      ? `${API_ROUTES.PARTNER.REFERRALS}?${queryParams.toString()}`
      : API_ROUTES.PARTNER.REFERRALS;

    return api.get<PartnerReferralListResponse>(url, { token });
  },

  /**
   * 정산 내역 조회
   */
  getSettlements: async (
    token: string,
    params?: { page?: number; pageSize?: number; status?: string }
  ): Promise<PartnerSettlementListResponse> => {
    const queryParams = new URLSearchParams();
    if (params?.page) queryParams.set('page', params.page.toString());
    if (params?.pageSize) queryParams.set('page_size', params.pageSize.toString());
    if (params?.status) queryParams.set('status', params.status);

    const url = queryParams.toString()
      ? `${API_ROUTES.PARTNER.SETTLEMENTS}?${queryParams.toString()}`
      : API_ROUTES.PARTNER.SETTLEMENTS;

    return api.get<PartnerSettlementListResponse>(url, { token });
  },

  /**
   * 통계 개요 조회
   */
  getStatsOverview: async (token: string): Promise<PartnerOverviewStats> => {
    return api.get<PartnerOverviewStats>(API_ROUTES.PARTNER.STATS_OVERVIEW, { token });
  },

  /**
   * 일별 통계 조회
   * @returns 백엔드 응답 { items: [...], periodStart, periodEnd }
   */
  getDailyStats: async (
    token: string,
    days: number = 30
  ): Promise<PartnerDailyStatsResponse> => {
    return api.get<PartnerDailyStatsResponse>(
      `${API_ROUTES.PARTNER.STATS_DAILY}?days=${days}`,
      { token }
    );
  },

  /**
   * 월별 통계 조회
   * @returns 백엔드 응답 { items: [...], periodStart, periodEnd }
   */
  getMonthlyStats: async (
    token: string,
    months: number = 12
  ): Promise<PartnerMonthlyStatsResponse> => {
    return api.get<PartnerMonthlyStatsResponse>(
      `${API_ROUTES.PARTNER.STATS_MONTHLY}?months=${months}`,
      { token }
    );
  },
};
