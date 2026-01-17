import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface SettingsState {
  // 사운드 설정
  bgmEnabled: boolean;
  bgmVolume: number;
  sfxEnabled: boolean;
  sfxVolume: number;

  // 알림 설정
  gameStartNotification: boolean;
  actionNotification: boolean;
  resultNotification: boolean;

  // 게임 설정
  autoFoldTimeout: boolean;
  showHandStrength: boolean;

  // 사운드 Actions
  toggleBgm: () => void;
  setBgmEnabled: (enabled: boolean) => void;
  setBgmVolume: (volume: number) => void;
  toggleSfx: () => void;
  setSfxEnabled: (enabled: boolean) => void;
  setSfxVolume: (volume: number) => void;

  // 알림 Actions
  setGameStartNotification: (enabled: boolean) => void;
  setActionNotification: (enabled: boolean) => void;
  setResultNotification: (enabled: boolean) => void;

  // 게임 Actions
  setAutoFoldTimeout: (enabled: boolean) => void;
  setShowHandStrength: (enabled: boolean) => void;

  // 전체 리셋
  resetSettings: () => void;
}

const defaultSettings = {
  bgmEnabled: true,
  bgmVolume: 50,
  sfxEnabled: true,
  sfxVolume: 70,
  gameStartNotification: true,
  actionNotification: true,
  resultNotification: true,
  autoFoldTimeout: false,
  showHandStrength: true,
};

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      ...defaultSettings,

      // 사운드 Actions
      toggleBgm: () => set((state) => ({ bgmEnabled: !state.bgmEnabled })),
      setBgmEnabled: (enabled) => set({ bgmEnabled: enabled }),
      setBgmVolume: (volume) => set({ bgmVolume: Math.max(0, Math.min(100, volume)) }),
      toggleSfx: () => set((state) => ({ sfxEnabled: !state.sfxEnabled })),
      setSfxEnabled: (enabled) => set({ sfxEnabled: enabled }),
      setSfxVolume: (volume) => set({ sfxVolume: Math.max(0, Math.min(100, volume)) }),

      // 알림 Actions
      setGameStartNotification: (enabled) => set({ gameStartNotification: enabled }),
      setActionNotification: (enabled) => set({ actionNotification: enabled }),
      setResultNotification: (enabled) => set({ resultNotification: enabled }),

      // 게임 Actions
      setAutoFoldTimeout: (enabled) => set({ autoFoldTimeout: enabled }),
      setShowHandStrength: (enabled) => set({ showHandStrength: enabled }),

      // 전체 리셋
      resetSettings: () => set(defaultSettings),
    }),
    {
      name: 'holdem-settings',
    }
  )
);
