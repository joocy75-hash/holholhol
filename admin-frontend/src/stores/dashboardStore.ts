import { create } from 'zustand';
import type { DashboardMetrics, ExchangeRate } from '@/types';

interface DashboardState {
  metrics: DashboardMetrics | null;
  exchangeRate: ExchangeRate | null;
  isLoading: boolean;
  error: string | null;
  setMetrics: (metrics: DashboardMetrics) => void;
  setExchangeRate: (rate: ExchangeRate) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  metrics: null,
  exchangeRate: null,
  isLoading: false,
  error: null,
  setMetrics: (metrics) => set({ metrics }),
  setExchangeRate: (rate) => set({ exchangeRate: rate }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}));
