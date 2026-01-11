// Connection status
export type ConnectionStatus = 'connected' | 'reconnecting' | 'disconnected';

// Toast types
export interface Toast {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
}

// Modal types
export type ModalType =
  | 'create-room'
  | 'join-room'
  | 'settings'
  | 'profile'
  | 'confirm-leave'
  | 'insufficient-balance'
  | null;

// Loading state
export interface LoadingState {
  isLoading: boolean;
  message?: string;
}

// Button variants
export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';
export type ButtonSize = 'sm' | 'md' | 'lg';

// Avatar sizes
export type AvatarSize = 'sm' | 'md' | 'lg';

// Card sizes
export type CardSize = 'sm' | 'md' | 'lg';

// Room filter state
export interface RoomFilters {
  blinds: string | null;
  seats: number | null;
  status: 'waiting' | 'playing' | 'full' | null;
  search: string;
}

// Chat message
export interface ChatMessage {
  id: string;
  type: 'user' | 'system';
  sender?: string;
  content: string;
  timestamp: Date;
}
