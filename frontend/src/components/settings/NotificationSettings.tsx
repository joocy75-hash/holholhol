'use client';

import { useSettingsStore } from '@/stores/settings';
import SettingsSection from './SettingsSection';
import SettingsToggle from './SettingsToggle';

export default function NotificationSettings() {
  const {
    gameStartNotification,
    actionNotification,
    resultNotification,
    setGameStartNotification,
    setActionNotification,
    setResultNotification,
  } = useSettingsStore();

  return (
    <SettingsSection
      title="알림"
      icon={
        <svg width="18" height="18" viewBox="0 0 24 24" fill="#888">
          <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2zm-2 1H8v-6c0-2.48 1.51-4.5 4-4.5s4 2.02 4 4.5v6z" />
        </svg>
      }
    >
      <SettingsToggle
        label="게임 시작 알림"
        description="게임이 시작될 때 알림을 받습니다"
        value={gameStartNotification}
        onChange={setGameStartNotification}
      />
      <SettingsToggle
        label="액션 알림"
        description="내 차례가 되면 알림을 받습니다"
        value={actionNotification}
        onChange={setActionNotification}
      />
      <SettingsToggle
        label="결과 알림"
        description="핸드 결과를 알림으로 받습니다"
        value={resultNotification}
        onChange={setResultNotification}
        showDivider={false}
      />
    </SettingsSection>
  );
}
