'use client';

import { useSettingsStore } from '@/stores/settings';
import SettingsSection from './SettingsSection';
import SettingsToggle from './SettingsToggle';
import SettingsSlider from './SettingsSlider';

export default function SoundSettings() {
  const {
    bgmEnabled,
    bgmVolume,
    sfxEnabled,
    sfxVolume,
    setBgmEnabled,
    setBgmVolume,
    setSfxEnabled,
    setSfxVolume,
  } = useSettingsStore();

  return (
    <SettingsSection
      title="사운드"
      icon={
        <svg width="18" height="18" viewBox="0 0 24 24" fill="#888">
          <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" />
        </svg>
      }
    >
      <SettingsToggle
        label="배경음악"
        description="게임 배경음악을 재생합니다"
        value={bgmEnabled}
        onChange={setBgmEnabled}
      />
      <SettingsSlider
        label="배경음악 음량"
        value={bgmVolume}
        onChange={setBgmVolume}
        disabled={!bgmEnabled}
      />
      <SettingsToggle
        label="효과음"
        description="버튼, 칩, 카드 효과음을 재생합니다"
        value={sfxEnabled}
        onChange={setSfxEnabled}
      />
      <SettingsSlider
        label="효과음 음량"
        value={sfxVolume}
        onChange={setSfxVolume}
        disabled={!sfxEnabled}
        showDivider={false}
      />
    </SettingsSection>
  );
}
