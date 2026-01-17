'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuthStore } from '@/stores/auth';
import { useDepositStore } from '@/stores/deposit';
import CashierHeader from '@/components/cashier/CashierHeader';
import AmountSelector from '@/components/cashier/AmountSelector';
import DepositQRView from '@/components/cashier/DepositQRView';
import BottomNavigation from '@/components/lobby/BottomNavigation';

type CashierStep = 'select' | 'qr' | 'complete';

const fadeIn = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
};

const slideUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -20 },
};

const springTransition = { type: 'spring', stiffness: 300, damping: 25 };

export default function CashierPage() {
  const router = useRouter();
  const { user, isAuthenticated, fetchUser } = useAuthStore();
  const {
    currentDeposit,
    exchangeRate,
    isLoading,
    error,
    fetchExchangeRate,
    createDeposit,
    clearDeposit,
    clearError,
  } = useDepositStore();

  const [step, setStep] = useState<CashierStep>('select');

  // 인증 체크
  useEffect(() => {
    if (!isAuthenticated) {
      fetchUser().catch(() => router.push('/login'));
    }
  }, [isAuthenticated, fetchUser, router]);

  // 환율 조회
  useEffect(() => {
    fetchExchangeRate();
  }, [fetchExchangeRate]);

  // 입금 상태 변경 감지
  useEffect(() => {
    if (currentDeposit?.status === 'confirmed') {
      setStep('complete');
    }
  }, [currentDeposit?.status]);

  // 페이지 이탈 시 정리
  useEffect(() => {
    return () => clearDeposit();
  }, [clearDeposit]);

  const handleAmountSelect = async (amount: number) => {
    clearError();
    const success = await createDeposit(amount);
    if (success) {
      setStep('qr');
    }
  };

  const handleBack = () => {
    if (step === 'qr') {
      clearDeposit();
      setStep('select');
    } else {
      router.push('/lobby');
    }
  };

  const handleComplete = () => {
    clearDeposit();
    router.push('/lobby');
  };

  return (
    <div
      style={{
        position: 'relative',
        width: '390px',
        minHeight: '858px',
        margin: '0 auto',
        background: 'var(--figma-bg-main)',
      }}
    >
      {/* 헤더 */}
      <CashierHeader
        balance={user?.balance || 0}
        onBack={handleBack}
        showBackButton={step === 'qr'}
      />

      {/* 컨텐츠 */}
      <div style={{ paddingTop: '80px', paddingBottom: '120px' }}>
        <AnimatePresence mode="wait">
          {step === 'select' && (
            <motion.div
              key="select"
              variants={fadeIn}
              initial="initial"
              animate="animate"
              exit="exit"
            >
              <AmountSelector
                exchangeRate={exchangeRate}
                onSelect={handleAmountSelect}
                isLoading={isLoading}
              />
            </motion.div>
          )}

          {step === 'qr' && currentDeposit && (
            <motion.div
              key="qr"
              variants={slideUp}
              initial="initial"
              animate="animate"
              exit="exit"
              transition={springTransition}
            >
              <DepositQRView deposit={currentDeposit} />
            </motion.div>
          )}

          {step === 'complete' && (
            <motion.div
              key="complete"
              variants={fadeIn}
              initial="initial"
              animate="animate"
            >
              {/* 입금 완료 화면 */}
              <div style={{ padding: '40px 20px', textAlign: 'center' }}>
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: 'spring', stiffness: 200, damping: 15 }}
                  style={{
                    width: '80px',
                    height: '80px',
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)',
                    margin: '0 auto 24px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    boxShadow: '0 4px 20px rgba(34, 197, 94, 0.4)',
                  }}
                >
                  <svg width="40" height="40" viewBox="0 0 24 24" fill="white">
                    <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
                  </svg>
                </motion.div>
                <h2
                  style={{
                    color: 'var(--figma-balance-color)',
                    fontSize: '24px',
                    fontWeight: 700,
                    marginBottom: '12px',
                  }}
                >
                  입금 완료!
                </h2>
                <p style={{ color: '#b3b3b3', marginBottom: '32px' }}>
                  {currentDeposit?.calculated_usdt} USDT가 충전되었습니다
                </p>
                <motion.button
                  onClick={handleComplete}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  style={{
                    width: '100%',
                    maxWidth: '280px',
                    padding: '16px 32px',
                    background: 'var(--figma-charge-btn-bg)',
                    border: 'none',
                    borderRadius: '12px',
                    color: 'white',
                    fontWeight: 600,
                    fontSize: '16px',
                    cursor: 'pointer',
                  }}
                >
                  로비로 돌아가기
                </motion.button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* 에러 메시지 */}
        {error && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            style={{
              margin: '20px',
              padding: '16px',
              background: 'rgba(239, 68, 68, 0.1)',
              borderRadius: '8px',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              color: '#ef4444',
              textAlign: 'center',
            }}
          >
            {error}
          </motion.div>
        )}
      </div>

      {/* 하단 네비게이션 */}
      <BottomNavigation />
    </div>
  );
}
