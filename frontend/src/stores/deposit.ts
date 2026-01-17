import { create } from 'zustand';
import { depositApi, DepositRequestResponse } from '@/lib/api';

interface DepositState {
  // 현재 입금 요청
  currentDeposit: DepositRequestResponse | null;

  // 환율
  exchangeRate: string | null;

  // 상태
  isLoading: boolean;
  error: string | null;

  // 폴링 인터벌 ID
  pollingIntervalId: number | null;

  // Actions
  fetchExchangeRate: () => Promise<void>;
  createDeposit: (amountKrw: number) => Promise<boolean>;
  startPolling: () => void;
  stopPolling: () => void;
  clearDeposit: () => void;
  clearError: () => void;
}

export const useDepositStore = create<DepositState>((set, get) => ({
  currentDeposit: null,
  exchangeRate: null,
  isLoading: false,
  error: null,
  pollingIntervalId: null,

  fetchExchangeRate: async () => {
    try {
      const response = await depositApi.getRate();
      set({ exchangeRate: response.data.usdt_krw });
    } catch (error) {
      console.error('환율 조회 실패:', error);
      // 환율 조회 실패 시 기본값 설정 (개발용)
      set({ exchangeRate: '1400' });
    }
  },

  createDeposit: async (amountKrw: number) => {
    set({ isLoading: true, error: null });
    try {
      const response = await depositApi.createRequest({ requested_krw: amountKrw });
      set({ currentDeposit: response.data, isLoading: false });
      get().startPolling();
      return true;
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : '입금 요청 생성에 실패했습니다';
      set({
        error: errorMessage,
        isLoading: false,
      });
      return false;
    }
  },

  startPolling: () => {
    const { currentDeposit, pollingIntervalId } = get();
    if (pollingIntervalId || !currentDeposit) return;

    const intervalId = window.setInterval(async () => {
      const deposit = get().currentDeposit;
      if (!deposit) {
        get().stopPolling();
        return;
      }

      try {
        const response = await depositApi.getStatus(deposit.id);

        // 상태 업데이트
        set((state) => ({
          currentDeposit: state.currentDeposit
            ? {
                ...state.currentDeposit,
                status: response.data.status,
                remaining_seconds: response.data.remaining_seconds,
                confirmed_at: response.data.confirmed_at,
                tx_hash: response.data.tx_hash,
              }
            : null,
        }));

        // 완료/만료 시 폴링 중지
        if (response.data.status !== 'pending' || response.data.is_expired) {
          get().stopPolling();
        }
      } catch (error) {
        console.error('상태 조회 실패:', error);
      }
    }, 5000); // 5초 간격

    set({ pollingIntervalId: intervalId });
  },

  stopPolling: () => {
    const { pollingIntervalId } = get();
    if (pollingIntervalId) {
      clearInterval(pollingIntervalId);
      set({ pollingIntervalId: null });
    }
  },

  clearDeposit: () => {
    get().stopPolling();
    set({ currentDeposit: null, error: null });
  },

  clearError: () => set({ error: null }),
}));
