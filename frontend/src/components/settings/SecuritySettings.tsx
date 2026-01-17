'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { twoFactorApi, TwoFactorStatusResponse } from '@/lib/api';
import SettingsSection from './SettingsSection';
import TwoFactorModal from './TwoFactorModal';

export default function SecuritySettings() {
  const router = useRouter();
  const [twoFactorStatus, setTwoFactorStatus] = useState<TwoFactorStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showTwoFactorModal, setShowTwoFactorModal] = useState(false);

  useEffect(() => {
    loadTwoFactorStatus();
  }, []);

  const loadTwoFactorStatus = async () => {
    try {
      const response = await twoFactorApi.status();
      setTwoFactorStatus(response.data);
    } catch (error) {
      console.error('2FA 상태 조회 실패:', error);
      setTwoFactorStatus({ is_enabled: false, backup_codes_remaining: 0 });
    } finally {
      setIsLoading(false);
    }
  };

  const handleTwoFactorComplete = () => {
    setShowTwoFactorModal(false);
    loadTwoFactorStatus();
  };

  return (
    <>
      <SettingsSection
        title="보안"
        icon={
          <svg width="18" height="18" viewBox="0 0 24 24" fill="#888">
            <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z" />
          </svg>
        }
      >
        {/* 2FA 설정 */}
        <div
          style={{
            padding: '16px',
            borderBottom: '1px solid rgba(255,255,255,0.1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ flex: 1 }}>
            <p style={{ margin: 0, color: 'white', fontSize: '15px', fontWeight: 500 }}>
              2단계 인증 (2FA)
            </p>
            <p style={{ margin: '4px 0 0', color: '#888', fontSize: '12px' }}>
              {isLoading
                ? '로딩 중...'
                : twoFactorStatus?.is_enabled
                ? `활성화됨 (백업 코드 ${twoFactorStatus.backup_codes_remaining}개 남음)`
                : '비활성화됨'}
            </p>
          </div>
          <motion.button
            onClick={() => setShowTwoFactorModal(true)}
            whileTap={{ scale: 0.95 }}
            disabled={isLoading}
            style={{
              padding: '8px 16px',
              background: twoFactorStatus?.is_enabled
                ? 'rgba(239, 68, 68, 0.2)'
                : 'rgba(34, 197, 94, 0.2)',
              border: 'none',
              borderRadius: '8px',
              color: twoFactorStatus?.is_enabled ? '#ef4444' : '#22c55e',
              fontSize: '13px',
              fontWeight: 600,
              cursor: isLoading ? 'not-allowed' : 'pointer',
              opacity: isLoading ? 0.5 : 1,
            }}
          >
            {twoFactorStatus?.is_enabled ? '해제' : '설정'}
          </motion.button>
        </div>

        {/* 비밀번호 변경 */}
        <motion.div
          onClick={() => router.push('/profile')}
          whileTap={{ scale: 0.98 }}
          style={{
            padding: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            cursor: 'pointer',
          }}
        >
          <div>
            <p style={{ margin: 0, color: 'white', fontSize: '15px', fontWeight: 500 }}>
              비밀번호 변경
            </p>
            <p style={{ margin: '4px 0 0', color: '#888', fontSize: '12px' }}>
              마이페이지에서 변경
            </p>
          </div>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="#666">
            <path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z" />
          </svg>
        </motion.div>
      </SettingsSection>

      {/* 2FA 모달 */}
      <TwoFactorModal
        isOpen={showTwoFactorModal}
        onClose={() => setShowTwoFactorModal(false)}
        onComplete={handleTwoFactorComplete}
        isEnabled={twoFactorStatus?.is_enabled || false}
      />
    </>
  );
}
