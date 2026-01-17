'use client';

import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import BottomNavigation from '@/components/lobby/BottomNavigation';
import SoundSettings from '@/components/settings/SoundSettings';
import NotificationSettings from '@/components/settings/NotificationSettings';
import SecuritySettings from '@/components/settings/SecuritySettings';
import AppInfo from '@/components/settings/AppInfo';

export default function SettingsPage() {
  const router = useRouter();

  return (
    <div
      style={{
        width: '390px',
        minHeight: '100vh',
        margin: '0 auto',
        background: 'var(--figma-bg-main)',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
      }}
    >
      {/* 헤더 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '16px 20px',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
        }}
      >
        <motion.button
          onClick={() => router.back()}
          whileTap={{ scale: 0.95 }}
          style={{
            background: 'transparent',
            border: 'none',
            padding: '8px',
            marginLeft: '-8px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
            <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z" />
          </svg>
        </motion.button>
        <h1
          style={{
            flex: 1,
            textAlign: 'center',
            color: 'white',
            fontSize: '18px',
            fontWeight: 600,
            margin: 0,
            marginRight: '24px',
          }}
        >
          설정
        </h1>
      </div>

      {/* 설정 내용 */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          paddingBottom: '100px',
        }}
      >
        {/* 사운드 설정 */}
        <SoundSettings />

        {/* 알림 설정 */}
        <NotificationSettings />

        {/* 보안 설정 */}
        <SecuritySettings />

        {/* 앱 정보 */}
        <AppInfo />
      </div>

      {/* 하단 네비게이션 */}
      <BottomNavigation />
    </div>
  );
}
