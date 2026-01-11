import { create } from 'zustand';
import type { ConnectionStatus, Toast, ModalType } from '@/types/ui';

interface UIState {
  // Connection
  connectionStatus: ConnectionStatus;

  // Toasts
  toasts: Toast[];

  // Modal
  activeModal: ModalType;
  modalData: Record<string, unknown>;

  // Actions
  setConnectionStatus: (status: ConnectionStatus) => void;
  showToast: (toast: Omit<Toast, 'id'>) => void;
  dismissToast: (id: string) => void;
  clearToasts: () => void;
  openModal: (modal: ModalType, data?: Record<string, unknown>) => void;
  closeModal: () => void;
}

let toastId = 0;

export const useUIStore = create<UIState>((set) => ({
  connectionStatus: 'disconnected',
  toasts: [],
  activeModal: null,
  modalData: {},

  setConnectionStatus: (status) => set({ connectionStatus: status }),

  showToast: (toast) => {
    const id = `toast-${++toastId}`;
    const duration = toast.duration ?? 3000;

    set((state) => ({
      toasts: [...state.toasts, { ...toast, id }],
    }));

    // Auto-dismiss after duration
    if (duration > 0) {
      setTimeout(() => {
        set((state) => ({
          toasts: state.toasts.filter((t) => t.id !== id),
        }));
      }, duration);
    }
  },

  dismissToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),

  clearToasts: () => set({ toasts: [] }),

  openModal: (modal, data = {}) =>
    set({
      activeModal: modal,
      modalData: data,
    }),

  closeModal: () =>
    set({
      activeModal: null,
      modalData: {},
    }),
}));

// Toast helper functions
export const toast = {
  success: (message: string, duration?: number) =>
    useUIStore.getState().showToast({ type: 'success', message, duration }),

  error: (message: string, duration?: number) =>
    useUIStore.getState().showToast({ type: 'error', message, duration }),

  warning: (message: string, duration?: number) =>
    useUIStore.getState().showToast({ type: 'warning', message, duration }),

  info: (message: string, duration?: number) =>
    useUIStore.getState().showToast({ type: 'info', message, duration }),
};
