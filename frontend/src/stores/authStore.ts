import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { UserBasicResponse, LoginRequest, RegisterRequest } from '@/types/api';
import { authApi, userApi } from '@/lib/api/endpoints';
import { tokenManager } from '@/lib/api/client';

interface AuthState {
  user: UserBasicResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (credentials: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  fetchUser: () => Promise<void>;
  clearError: () => void;
  setUser: (user: UserBasicResponse | null) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, _get) => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (credentials) => {
        set({ isLoading: true, error: null });
        try {
          const response = await authApi.login(credentials);
          tokenManager.setTokens(response.accessToken, response.refreshToken);

          // Fetch user info
          const user = await userApi.getMe();
          set({ user, isAuthenticated: true, isLoading: false });
        } catch (error) {
          const message = error instanceof Error ? error.message : '로그인에 실패했습니다';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      register: async (data) => {
        set({ isLoading: true, error: null });
        try {
          const response = await authApi.register(data);
          tokenManager.setTokens(response.accessToken, response.refreshToken);

          // Fetch user info
          const user = await userApi.getMe();
          set({ user, isAuthenticated: true, isLoading: false });
        } catch (error) {
          const message = error instanceof Error ? error.message : '회원가입에 실패했습니다';
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      logout: async () => {
        try {
          await authApi.logout();
        } catch {
          // Ignore logout API errors
        } finally {
          tokenManager.clearTokens();
          set({ user: null, isAuthenticated: false });
        }
      },

      fetchUser: async () => {
        const token = tokenManager.getAccessToken();
        if (!token) {
          set({ user: null, isAuthenticated: false });
          return;
        }

        set({ isLoading: true });
        try {
          const user = await userApi.getMe();
          set({ user, isAuthenticated: true, isLoading: false });
        } catch {
          // Token invalid, clear auth
          tokenManager.clearTokens();
          set({ user: null, isAuthenticated: false, isLoading: false });
        }
      },

      clearError: () => set({ error: null }),

      setUser: (user) => set({ user, isAuthenticated: !!user }),
    }),
    {
      name: 'holdem-auth',
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
