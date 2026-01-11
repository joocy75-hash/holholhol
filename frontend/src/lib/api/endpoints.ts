import apiClient from './client';
import type {
  LoginRequest,
  RegisterRequest,
  AuthResponse,
  RefreshTokenRequest,
  UserBasicResponse,
  UserProfileResponse,
  UpdateProfileRequest,
  CreateRoomRequest,
  RoomResponse,
  RoomListResponse,
  JoinRoomRequest,
  PaginationParams,
} from '@/types/api';

// Auth endpoints
export const authApi = {
  login: async (data: LoginRequest): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>('/auth/login', data);
    return response.data;
  },

  register: async (data: RegisterRequest): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>('/auth/register', data);
    return response.data;
  },

  refresh: async (data: RefreshTokenRequest): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>('/auth/refresh', data);
    return response.data;
  },

  logout: async (): Promise<void> => {
    await apiClient.post('/auth/logout');
  },
};

// User endpoints
export const userApi = {
  getMe: async (): Promise<UserBasicResponse> => {
    const response = await apiClient.get<UserBasicResponse>('/users/me');
    return response.data;
  },

  getProfile: async (): Promise<UserProfileResponse> => {
    const response = await apiClient.get<UserProfileResponse>('/users/me/profile');
    return response.data;
  },

  updateProfile: async (data: UpdateProfileRequest): Promise<UserBasicResponse> => {
    const response = await apiClient.patch<UserBasicResponse>('/users/me', data);
    return response.data;
  },

  getBalance: async (): Promise<{ balance: number }> => {
    const response = await apiClient.get<{ balance: number }>('/users/me/balance');
    return response.data;
  },
};

// Room endpoints
export const roomApi = {
  list: async (params?: PaginationParams): Promise<RoomListResponse> => {
    const response = await apiClient.get<RoomListResponse>('/rooms', { params });
    return response.data;
  },

  get: async (roomId: string): Promise<RoomResponse> => {
    const response = await apiClient.get<RoomResponse>(`/rooms/${roomId}`);
    return response.data;
  },

  create: async (data: CreateRoomRequest): Promise<RoomResponse> => {
    const response = await apiClient.post<RoomResponse>('/rooms', data);
    return response.data;
  },

  join: async (data: JoinRoomRequest): Promise<{ position: number }> => {
    const response = await apiClient.post<{ position: number }>(`/rooms/${data.roomId}/join`, {
      buyInAmount: data.buyInAmount,
      position: data.position,
    });
    return response.data;
  },

  leave: async (roomId: string): Promise<void> => {
    await apiClient.post(`/rooms/${roomId}/leave`);
  },
};
