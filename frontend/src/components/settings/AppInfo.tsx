'use client';

import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { useSettingsStore } from '@/stores/settings';
import SettingsSection from './SettingsSection';

export default function AppInfo() {
  const router = useRouter();
  const { logout } = useAuthStore();
  const { resetSettings } = useSettingsStore();

  const handleLogout = async () => {
    await logout();
    router.push('/login');
  };

  const handleResetSettings = () => {
    if (confirm('모든 설정을 기본값으로 초기화하시겠습니까?')) {
      resetSettings();
    }
  };

  return (
    <SettingsSection
      title="앱 정보"
      icon={
        <svg width="18" height="18" viewBox="0 0 24 24" fill="#888">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z" />
        </svg>
      }
    >
      {/* 버전 정보 */}
      <div
        style={{
          padding: '16px',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <p style={{ margin: 0, color: 'white', fontSize: '15px' }}>버전</p>
        <p style={{ margin: 0, color: '#888', fontSize: '14px' }}>1.0.0</p>
      </div>

      {/* 이용약관 */}
      <motion.div
        whileTap={{ scale: 0.98 }}
        style={{
          padding: '16px',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          cursor: 'pointer',
        }}
      >
        <p style={{ margin: 0, color: 'white', fontSize: '15px' }}>이용약관</p>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="#666">
          <path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z" />
        </svg>
      </motion.div>

      {/* 개인정보처리방침 */}
      <motion.div
        whileTap={{ scale: 0.98 }}
        style={{
          padding: '16px',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          cursor: 'pointer',
        }}
      >
        <p style={{ margin: 0, color: 'white', fontSize: '15px' }}>개인정보처리방침</p>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="#666">
          <path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z" />
        </svg>
      </motion.div>

      {/* 설정 초기화 */}
      <motion.div
        onClick={handleResetSettings}
        whileTap={{ scale: 0.98 }}
        style={{
          padding: '16px',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          cursor: 'pointer',
        }}
      >
        <p style={{ margin: 0, color: '#f59e0b', fontSize: '15px' }}>설정 초기화</p>
      </motion.div>

      {/* 로그아웃 */}
      <motion.div
        onClick={handleLogout}
        whileTap={{ scale: 0.98 }}
        style={{
          padding: '16px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          cursor: 'pointer',
        }}
      >
        <p style={{ margin: 0, color: '#ef4444', fontSize: '15px', fontWeight: 600 }}>로그아웃</p>
      </motion.div>
    </SettingsSection>
  );
}
