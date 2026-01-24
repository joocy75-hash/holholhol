import { api } from './api';
import { API_ROUTES } from './api-routes';
import type { AdminUser, LoginRequest, LoginResponse } from '@/types';

export interface TwoFactorVerifyRequest {
  code: string;
}

export interface TwoFactorSetupResponse {
  secret: string;
  qr_code: string;
}

export const authApi = {
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    // 로그인 API는 401 에러 시 "세션 만료" 처리를 건너뜀 (잘못된 자격증명을 의미)
    return api.post<LoginResponse>(API_ROUTES.AUTH.LOGIN, data, { skipAuthRefresh: true });
  },

  verify2FA: async (
    code: string,
    twoFactorToken: string
  ): Promise<LoginResponse> => {
    return api.post<LoginResponse>(
      API_ROUTES.AUTH.TWO_FA_VERIFY,
      { code },
      { token: twoFactorToken }
    );
  },

  setup2FA: async (token: string): Promise<TwoFactorSetupResponse> => {
    return api.post<TwoFactorSetupResponse>(API_ROUTES.AUTH.TWO_FA_SETUP, {}, { token });
  },

  enable2FA: async (code: string, token: string): Promise<void> => {
    return api.post(API_ROUTES.AUTH.TWO_FA_ENABLE, { code }, { token });
  },

  disable2FA: async (code: string, token: string): Promise<void> => {
    return api.post(API_ROUTES.AUTH.TWO_FA_DISABLE, { code }, { token });
  },

  logout: async (token: string): Promise<void> => {
    return api.post(API_ROUTES.AUTH.LOGOUT, {}, { token });
  },

  getCurrentUser: async (token: string): Promise<AdminUser> => {
    return api.get<AdminUser>(API_ROUTES.USERS.ME, { token });
  },

  refreshSession: async (token: string): Promise<void> => {
    return api.post(API_ROUTES.AUTH.REFRESH, {}, { token });
  },
};
