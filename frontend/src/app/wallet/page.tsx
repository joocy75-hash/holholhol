'use client';

import { useEffect, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuthStore } from '@/stores/auth';
import { useDepositStore } from '@/stores/deposit';
// WithdrawStep 타입은 store 내부에서만 사용되므로 import 제거
import { useWithdrawStore } from '@/stores/withdraw';
import CashierHeader, { WalletTab } from '@/components/cashier/CashierHeader';
import AmountSelector from '@/components/cashier/AmountSelector';
import DepositQRView from '@/components/cashier/DepositQRView';
import WithdrawAmountSelector from '@/components/cashier/WithdrawAmountSelector';
import WithdrawAddressInput from '@/components/cashier/WithdrawAddressInput';
import WithdrawConfirm from '@/components/cashier/WithdrawConfirm';
import BottomNavigation from '@/components/lobby/BottomNavigation';

type DepositStep = 'select' | 'qr' | 'complete';

const fadeIn = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
};

const slideLeft = {
  initial: { opacity: 0, x: 20 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -20 },
};

const slideRight = {
  initial: { opacity: 0, x: -20 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: 20 },
};

const springTransition = { type: 'spring' as const, stiffness: 300, damping: 25 };

export default function WalletPage() {
  const router = useRouter();
  const { user, isAuthenticated, fetchUser } = useAuthStore();

  // 탭 상태
  const [activeTab, setActiveTab] = useState<WalletTab>('deposit');

  // 충전 관련 상태
  const {
    currentDeposit,
    exchangeRate: depositExchangeRate,
    isLoading: depositLoading,
    error: depositError,
    fetchExchangeRate: fetchDepositRate,
    createDeposit,
    clearDeposit,
    clearError: clearDepositError,
  } = useDepositStore();

  // 충전 단계 상태 (내부 관리용)
  const [depositStepState, setDepositStep] = useState<DepositStep>('select');

  // 입금 상태가 confirmed일 때 자동으로 complete 단계로 전환 (파생 상태)
  // useEffect 내 setState 대신 useMemo로 파생하여 cascading render 방지
  const depositStep: DepositStep = useMemo(() => {
    if (currentDeposit?.status === 'confirmed') {
      return 'complete';
    }
    return depositStepState;
  }, [currentDeposit?.status, depositStepState]);

  // 환전 관련 상태
  const {
    step: withdrawStep,
    amount: withdrawAmount,
    address: withdrawAddress,
    calculatedUsdt,
    exchangeRate: withdrawExchangeRate,
    transaction,
    isLoading: withdrawLoading,
    error: withdrawError,
    setStep: setWithdrawStep,
    setAmount: setWithdrawAmount,
    setAddress: setWithdrawAddress,
    fetchExchangeRate: fetchWithdrawRate,
    requestWithdraw,
    reset: resetWithdraw,
    clearError: clearWithdrawError,
  } = useWithdrawStore();

  // 인증 체크
  useEffect(() => {
    if (!isAuthenticated) {
      fetchUser().catch(() => router.push('/login'));
    }
  }, [isAuthenticated, fetchUser, router]);

  // 환율 조회
  useEffect(() => {
    fetchDepositRate();
    fetchWithdrawRate();
  }, [fetchDepositRate, fetchWithdrawRate]);

  // 입금 상태 변경 감지 - useMemo 파생 상태로 이동 (위 depositStep 참조)

  // 페이지 이탈 시 정리
  useEffect(() => {
    return () => {
      clearDeposit();
      resetWithdraw();
    };
  }, [clearDeposit, resetWithdraw]);

  // 탭 전환 시 상태 초기화
  const handleTabChange = (tab: WalletTab) => {
    if (tab !== activeTab) {
      setActiveTab(tab);
      // 각 탭 초기화
      if (tab === 'deposit') {
        clearDeposit();
        setDepositStep('select');
      } else {
        resetWithdraw();
      }
    }
  };

  // 충전 관련 핸들러
  const handleDepositAmountSelect = async (amount: number) => {
    clearDepositError();
    const success = await createDeposit(amount);
    if (success) {
      setDepositStep('qr');
    }
  };

  const handleDepositBack = () => {
    if (depositStep === 'qr') {
      clearDeposit();
      setDepositStep('select');
    } else {
      router.push('/lobby');
    }
  };

  const handleDepositComplete = () => {
    clearDeposit();
    router.push('/lobby');
  };

  // 환전 관련 핸들러
  const handleWithdrawAmountSelect = (amount: number) => {
    clearWithdrawError();
    setWithdrawAmount(amount);
    setWithdrawStep('address');
  };

  const handleWithdrawAddressConfirm = () => {
    setWithdrawStep('confirm');
  };

  const handleWithdrawConfirm = async () => {
    await requestWithdraw();
  };

  const handleWithdrawDone = () => {
    resetWithdraw();
    router.push('/lobby');
  };

  // 뒤로가기 핸들러
  const handleBack = () => {
    if (activeTab === 'deposit') {
      handleDepositBack();
    } else {
      // 환전 탭
      if (withdrawStep === 'address') {
        setWithdrawStep('amount');
      } else if (withdrawStep === 'confirm') {
        setWithdrawStep('address');
      } else {
        router.push('/lobby');
      }
    }
  };

  // 탭 표시 여부 (진행 중일 때 숨김)
  const showTabs =
    (activeTab === 'deposit' && depositStep === 'select') ||
    (activeTab === 'withdraw' && withdrawStep === 'amount');

  // 헤더 높이 계산
  const headerHeight = showTabs ? 112 : 56;

  return (
    <div className="page-bg-gradient" style={{ position: 'relative', width: '390px', minHeight: '858px', margin: '0 auto' }}>
      {/* 노이즈 텍스처 */}
      <div className="noise-overlay" />

      {/* 배경 장식 */}
      <div
        style={{
          position: 'absolute',
          top: '-15%',
          right: '-15%',
          width: '300px',
          height: '300px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(245, 158, 11, 0.2) 0%, transparent 70%)',
          filter: 'blur(60px)',
          pointerEvents: 'none',
        }}
      />
      <div
        style={{
          position: 'absolute',
          bottom: '20%',
          left: '-10%',
          width: '250px',
          height: '250px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(59, 130, 246, 0.15) 0%, transparent 70%)',
          filter: 'blur(50px)',
          pointerEvents: 'none',
        }}
      />
      {/* 헤더 */}
      <CashierHeader
        balance={user?.balance || 0}
        exchangeRate={activeTab === 'deposit' ? depositExchangeRate : withdrawExchangeRate}
        onBack={handleBack}
        activeTab={activeTab}
        onTabChange={handleTabChange}
        showTabs={showTabs}
      />

      {/* 컨텐츠 */}
      <div style={{ paddingTop: `${headerHeight}px`, paddingBottom: '120px' }}>
        <AnimatePresence mode="wait">
          {/* ===== 충전 탭 ===== */}
          {activeTab === 'deposit' && (
            <motion.div
              key="deposit-tab"
              variants={slideRight}
              initial="initial"
              animate="animate"
              exit="exit"
              transition={springTransition}
            >
              <AnimatePresence mode="wait">
                {depositStep === 'select' && (
                  <motion.div
                    key="deposit-select"
                    variants={fadeIn}
                    initial="initial"
                    animate="animate"
                    exit="exit"
                  >
                    <AmountSelector
                      exchangeRate={depositExchangeRate}
                      balance={user?.balance || 0}
                      onSelect={handleDepositAmountSelect}
                      isLoading={depositLoading}
                    />
                  </motion.div>
                )}

                {depositStep === 'qr' && currentDeposit && (
                  <motion.div
                    key="deposit-qr"
                    variants={slideLeft}
                    initial="initial"
                    animate="animate"
                    exit="exit"
                    transition={springTransition}
                  >
                    {/* key prop으로 deposit 변경 시 컴포넌트 리마운트하여 state 초기화 */}
                    <DepositQRView key={currentDeposit.id} deposit={currentDeposit} />
                  </motion.div>
                )}

                {depositStep === 'complete' && (
                  <motion.div
                    key="deposit-complete"
                    variants={fadeIn}
                    initial="initial"
                    animate="animate"
                  >
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
                        onClick={handleDepositComplete}
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

              {/* 충전 에러 메시지 */}
              {depositError && (
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
                  {depositError}
                </motion.div>
              )}
            </motion.div>
          )}

          {/* ===== 환전 탭 ===== */}
          {activeTab === 'withdraw' && (
            <motion.div
              key="withdraw-tab"
              variants={slideLeft}
              initial="initial"
              animate="animate"
              exit="exit"
              transition={springTransition}
            >
              <AnimatePresence mode="wait">
                {withdrawStep === 'amount' && (
                  <motion.div
                    key="withdraw-amount"
                    variants={fadeIn}
                    initial="initial"
                    animate="animate"
                    exit="exit"
                  >
                    <WithdrawAmountSelector
                      balance={user?.balance || 0}
                      exchangeRate={withdrawExchangeRate}
                      onSelect={handleWithdrawAmountSelect}
                      isLoading={withdrawLoading}
                    />
                  </motion.div>
                )}

                {withdrawStep === 'address' && withdrawAmount && (
                  <motion.div
                    key="withdraw-address"
                    variants={slideLeft}
                    initial="initial"
                    animate="animate"
                    exit="exit"
                    transition={springTransition}
                  >
                    <WithdrawAddressInput
                      amount={withdrawAmount}
                      calculatedUsdt={calculatedUsdt}
                      address={withdrawAddress}
                      onAddressChange={setWithdrawAddress}
                      onConfirm={handleWithdrawAddressConfirm}
                      onBack={() => setWithdrawStep('amount')}
                      isLoading={withdrawLoading}
                      error={withdrawError}
                    />
                  </motion.div>
                )}

                {(withdrawStep === 'confirm' || withdrawStep === 'complete') && withdrawAmount && (
                  <motion.div
                    key="withdraw-confirm"
                    variants={slideLeft}
                    initial="initial"
                    animate="animate"
                    exit="exit"
                    transition={springTransition}
                  >
                    <WithdrawConfirm
                      amount={withdrawAmount}
                      calculatedUsdt={calculatedUsdt}
                      address={withdrawAddress}
                      exchangeRate={withdrawExchangeRate}
                      onConfirm={handleWithdrawConfirm}
                      onBack={() => setWithdrawStep('address')}
                      isLoading={withdrawLoading}
                      error={withdrawError}
                      isComplete={withdrawStep === 'complete'}
                      transaction={transaction}
                      onDone={handleWithdrawDone}
                    />
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* 하단 네비게이션 */}
      <BottomNavigation />
    </div>
  );
}
