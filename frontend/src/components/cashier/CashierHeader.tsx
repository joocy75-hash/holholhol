'use client';

import { motion } from 'framer-motion';

export type WalletTab = 'deposit' | 'withdraw';

interface CashierHeaderProps {
  /** 사용자 잔액 (미래 확장용, 현재 미사용) */
  balance?: number;
  exchangeRate?: string | null;
  onBack: () => void;
  // 탭 관련
  activeTab: WalletTab;
  onTabChange: (tab: WalletTab) => void;
  showTabs?: boolean;
}

const quickSpring = { type: 'spring' as const, stiffness: 400, damping: 20 };

export default function CashierHeader({
  // balance는 미래 확장용으로 유지 (underscore prefix로 미사용 명시)
  balance: _balance,
  exchangeRate,
  onBack,
  activeTab,
  onTabChange,
  showTabs = true,
}: CashierHeaderProps) {
  // _balance는 향후 잔액 표시 기능 추가 시 사용 예정
  void _balance;
  const rate = exchangeRate ? parseFloat(exchangeRate) : null;
  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: '50%',
        transform: 'translateX(-50%)',
        width: '390px',
        background: 'linear-gradient(180deg, rgba(15, 23, 42, 0.95) 0%, rgba(15, 23, 42, 0.85) 100%)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        zIndex: 100,
        borderBottom: '1px solid rgba(255,255,255,0.08)',
      }}
    >
      {/* 상단 영역: 뒤로가기, 타이틀, 환율 */}
      <div
        style={{
          height: '56px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 16px',
        }}
      >
        {/* 뒤로가기 버튼 */}
        <motion.button
          onClick={onBack}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          transition={quickSpring}
          style={{
            width: '40px',
            height: '40px',
            background: 'rgba(255,255,255,0.08)',
            backdropFilter: 'blur(10px)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '12px',
            color: 'white',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z" />
          </svg>
        </motion.button>

        {/* 타이틀 */}
        <h1
          style={{
            fontFamily: 'Paperlogy, sans-serif',
            fontWeight: 700,
            fontSize: '18px',
            color: 'white',
            textShadow: '0 2px 8px rgba(0,0,0,0.3)',
            margin: 0,
            letterSpacing: '0.5px',
          }}
        >
          지갑
        </h1>

        {/* 환율 표시 */}
        <div
          style={{
            background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(217, 119, 6, 0.1) 100%)',
            padding: '8px 14px',
            borderRadius: '20px',
            border: '1px solid rgba(245, 158, 11, 0.2)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.5)' }}>1 USDT</span>
          <span
            style={{
              fontWeight: 700,
              fontSize: '13px',
              color: '#fbbf24',
              textShadow: '0 0 10px rgba(251, 191, 36, 0.3)',
            }}
          >
            {rate ? `${rate.toLocaleString()}원` : '-'}
          </span>
        </div>
      </div>

      {/* 탭 영역 */}
      {showTabs && (
        <div
          style={{
            display: 'flex',
            padding: '0 16px 12px',
            gap: '10px',
          }}
        >
          <motion.button
            onClick={() => onTabChange('deposit')}
            whileTap={{ scale: 0.98 }}
            transition={quickSpring}
            style={{
              flex: 1,
              padding: '14px',
              background:
                activeTab === 'deposit'
                  ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
                  : 'rgba(255,255,255,0.05)',
              border:
                activeTab === 'deposit'
                  ? 'none'
                  : '1px solid rgba(255,255,255,0.1)',
              borderRadius: '12px',
              color: 'white',
              fontWeight: 600,
              fontSize: '15px',
              cursor: 'pointer',
              transition: 'all 0.3s ease',
              boxShadow:
                activeTab === 'deposit'
                  ? '0 4px 15px rgba(245, 158, 11, 0.4), inset 0 1px 0 rgba(255,255,255,0.2)'
                  : 'none',
            }}
          >
            충전
          </motion.button>
          <motion.button
            onClick={() => onTabChange('withdraw')}
            whileTap={{ scale: 0.98 }}
            transition={quickSpring}
            style={{
              flex: 1,
              padding: '14px',
              background:
                activeTab === 'withdraw'
                  ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
                  : 'rgba(255,255,255,0.05)',
              border:
                activeTab === 'withdraw'
                  ? 'none'
                  : '1px solid rgba(255,255,255,0.1)',
              borderRadius: '12px',
              color: 'white',
              fontWeight: 600,
              fontSize: '15px',
              cursor: 'pointer',
              transition: 'all 0.3s ease',
              boxShadow:
                activeTab === 'withdraw'
                  ? '0 4px 15px rgba(245, 158, 11, 0.4), inset 0 1px 0 rgba(255,255,255,0.2)'
                  : 'none',
            }}
          >
            환전
          </motion.button>
        </div>
      )}
    </div>
  );
}
