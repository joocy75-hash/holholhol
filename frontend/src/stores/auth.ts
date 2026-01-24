import { create } from 'zustand';
import { authApi } from '@/lib/api';
import { extractErrorMessage } from '@/types/errors';

interface User {
  id: string;
  nickname: string;
  avatarUrl: string | null;
  balance: number;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  login: (username: string, password: string) => Promise<void>;
  signup: (
    username: string,
    email: string,
    password: string,
    nickname: string,
    partnerCode?: string,
    usdtWalletAddress?: string,
    usdtWalletType?: string
  ) => Promise<void>;
  logout: () => Promise<void>;
  fetchUser: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,

  login: async (username: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await authApi.login({ username, password });
      const { user, tokens } = response.data;

      localStorage.setItem('access_token', tokens.accessToken);
      localStorage.setItem('refresh_token', tokens.refreshToken);

      set({
        user,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (error: unknown) {
      set({
        error: extractErrorMessage(error, '로그인에 실패했습니다.'),
        isLoading: false,
      });
      throw error;
    }
  },

  signup: async (
    username: string,
    email: string,
    password: string,
    nickname: string,
    partnerCode?: string,
    usdtWalletAddress?: string,
    usdtWalletType?: string
  ) => {
    set({ isLoading: true, error: null });
    try {
      const response = await authApi.signup({
        username,
        email,
        password,
        nickname,
        partnerCode,
        usdtWalletAddress,
        usdtWalletType,
      });
      const { user, tokens } = response.data;

      localStorage.setItem('access_token', tokens.accessToken);
      localStorage.setItem('refresh_token', tokens.refreshToken);

      set({
        user,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (error: unknown) {
      set({
        error: extractErrorMessage(error, '회원가입에 실패했습니다.'),
        isLoading: false,
      });
      throw error;
    }
  },

  logout: async () => {
    try {
      await authApi.logout();
    } catch {
      // ignore logout errors
    }
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    set({ user: null, isAuthenticated: false });
  },

  fetchUser: async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      set({ isAuthenticated: false, user: null });
      return;
    }

    set({ isLoading: true });
    try {
      const response = await authApi.me();
      set({
        user: response.data,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (error: unknown) {
      // The axios interceptor handles token refresh automatically
      // Only clear tokens if the interceptor couldn't recover (already logged out)
      // Check if we still have a token - if interceptor cleared it, we're done
      const stillHasToken = localStorage.getItem('access_token');
      if (!stillHasToken) {
        set({
          user: null,
          isAuthenticated: false,
          isLoading: false,
        });
      } else {
        // For network errors or other issues, keep auth state
        set({ isLoading: false });
        console.error('fetchUser error:', extractErrorMessage(error));
      }
    }
  },

  clearError: () => set({ error: null }),
}));
