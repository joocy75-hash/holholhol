import { api } from './api';
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
    return api.post<LoginResponse>('/api/auth/login', data);
  },

  verify2FA: async (
    code: string,
    twoFactorToken: string
  ): Promise<LoginResponse> => {
    return api.post<LoginResponse>(
      '/api/auth/2fa/verify',
      { code },
      { token: twoFactorToken }
    );
  },

  setup2FA: async (token: string): Promise<TwoFactorSetupResponse> => {
    return api.post<TwoFactorSetupResponse>('/api/auth/2fa/setup', {}, { token });
  },

  enable2FA: async (code: string, token: string): Promise<void> => {
    return api.post('/api/auth/2fa/enable', { code }, { token });
  },

  disable2FA: async (code: string, token: string): Promise<void> => {
    return api.post('/api/auth/2fa/disable', { code }, { token });
  },

  logout: async (token: string): Promise<void> => {
    return api.post('/api/auth/logout', {}, { token });
  },

  getCurrentUser: async (token: string): Promise<AdminUser> => {
    return api.get<AdminUser>('/api/auth/me', { token });
  },

  refreshSession: async (token: string): Promise<void> => {
    return api.post('/api/auth/refresh', {}, { token });
  },
};
