// Admin User Types
export enum AdminRole {
  VIEWER = 'viewer',
  OPERATOR = 'operator',
  SUPERVISOR = 'supervisor',
  ADMIN = 'admin',
}

export interface AdminUser {
  id: string;
  username: string;
  email: string;
  role: AdminRole;
  isActive: boolean;
  lastLogin: string | null;
  createdAt: string;
}

// Auth Types
export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  accessToken: string;
  tokenType?: string;
  requiresTwoFactor: boolean;
  twoFactorToken?: string;
}

export interface TwoFactorRequest {
  twoFactorToken: string;
  code: string;
}

// Dashboard Types
export interface DashboardMetrics {
  ccu: number;
  dau: number;
  activeRooms: number;
  totalPlayers: number;
  serverHealth: ServerHealth;
}

export interface ServerHealth {
  cpu: number;
  memory: number;
  latency: number;
  status: 'healthy' | 'warning' | 'critical';
}

export interface RevenueStats {
  daily: number;
  weekly: number;
  monthly: number;
  currency: 'KRW';
}


// User Management Types
export interface User {
  id: string;
  username: string;
  email: string;
  balance: number;
  createdAt: string;
  lastLogin: string | null;
  isBanned: boolean;
}

export interface UserDetail extends User {
  loginHistory: LoginHistory[];
  transactions: Transaction[];
  recentHands: HandSummary[];
}

export interface LoginHistory {
  id: string;
  ipAddress: string;
  userAgent: string;
  createdAt: string;
}

export interface Transaction {
  id: string;
  type: 'deposit' | 'withdrawal' | 'game_win' | 'game_loss' | 'adjustment';
  amountUsdt: number;
  amountKrw: number;
  createdAt: string;
}

// Crypto Types
export enum TransactionStatus {
  PENDING = 'pending',
  CONFIRMING = 'confirming',
  CONFIRMED = 'confirmed',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
  REJECTED = 'rejected',
}

export interface CryptoDeposit {
  id: string;
  userId: string;
  username: string;
  txHash: string;
  fromAddress: string;
  toAddress: string;
  amountUsdt: number;
  amountKrw: number;
  exchangeRate: number;
  confirmations: number;
  status: TransactionStatus;
  detectedAt: string;
  confirmedAt: string | null;
  creditedAt: string | null;
}

export interface CryptoWithdrawal {
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
  status: TransactionStatus;
  requestedAt: string;
  approvedBy: string | null;
  approvedAt: string | null;
  processedAt: string | null;
  rejectionReason: string | null;
}

export interface WalletBalance {
  address: string;
  balanceUsdt: number;
  balanceKrw: number;
  pendingWithdrawalsUsdt: number;
  pendingWithdrawalsKrw: number;
  exchangeRate: number;
  lastUpdated: string;
}

export interface ExchangeRate {
  rate: number;
  source: string;
  timestamp: string;
}

// Hand Types
export interface HandSummary {
  id: string;
  roomId: string;
  potSize: number;
  winnerId: string;
  createdAt: string;
}

// Ban Types
export interface Ban {
  id: string;
  userId: string;
  username: string;
  banType: 'temporary' | 'permanent' | 'chat_only';
  reason: string;
  expiresAt: string | null;
  createdBy: string;
  createdAt: string;
}

// Audit Log Types
export interface AuditLog {
  id: string;
  adminUserId: string;
  adminUsername: string;
  action: string;
  targetType: string;
  targetId: string;
  details: Record<string, unknown>;
  ipAddress: string;
  createdAt: string;
}

// API Response Types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface ApiError {
  code: number;
  message: string;
  details?: Record<string, unknown>;
}
