// Auth types
export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  nickname: string;
}

export interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresIn: number;
}

export interface RefreshTokenRequest {
  refreshToken: string;
}

// User types
export interface UserBasicResponse {
  id: string;
  email: string;
  nickname: string;
  avatarUrl: string | null;
  balance: number;
  createdAt: string;
}

export interface UserProfileResponse extends UserBasicResponse {
  totalGames: number;
  totalWins: number;
  totalEarnings: number;
}

export interface UpdateProfileRequest {
  nickname?: string;
  avatarUrl?: string;
}

// Room types
export interface CreateRoomRequest {
  name: string;
  smallBlind: number;
  bigBlind: number;
  maxSeats: 2 | 6 | 9;
  minBuyIn: number;
  maxBuyIn: number;
}

export interface RoomResponse {
  id: string;
  name: string;
  smallBlind: number;
  bigBlind: number;
  maxSeats: number;
  minBuyIn: number;
  maxBuyIn: number;
  playerCount: number;
  status: 'waiting' | 'playing' | 'full';
  createdAt: string;
  ownerId: string;
}

export interface RoomListResponse {
  rooms: RoomResponse[];
  total: number;
  page: number;
  pageSize: number;
}

export interface JoinRoomRequest {
  roomId: string;
  buyInAmount: number;
  position?: number;
}

// Pagination
export interface PaginationParams {
  page?: number;
  pageSize?: number;
}

// Error response
export interface ApiErrorResponse {
  errorCode: string;
  message: string;
  details?: Record<string, unknown>;
}

// Common response wrapper
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: ApiErrorResponse;
}
