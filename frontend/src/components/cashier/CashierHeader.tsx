'use client';

import { motion } from 'framer-motion';

interface CashierHeaderProps {
  balance: number;
  onBack: () => void;
  showBackButton?: boolean;
}

const quickSpring = { type: 'spring' as const, stiffness: 400, damping: 20 };

export default function CashierHeader({
  balance,
  onBack,
  showBackButton = false,
}: CashierHeaderProps) {
  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: '50%',
        transform: 'translateX(-50%)',
        width: '390px',
        height: '80px',
        background: 'var(--figma-gradient-header)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 16px',
        zIndex: 100,
        borderBottom: '1px solid rgba(255,255,255,0.1)',
      }}
    >
      {/* 뒤로가기 버튼 */}
      {showBackButton ? (
        <motion.button
          onClick={onBack}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          transition={quickSpring}
          style={{
            width: '40px',
            height: '40px',
            background: 'rgba(255,255,255,0.1)',
            border: 'none',
            borderRadius: '8px',
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
      ) : (
        <motion.button
          onClick={onBack}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          transition={quickSpring}
          style={{
            width: '40px',
            height: '40px',
            background: 'rgba(255,255,255,0.1)',
            border: 'none',
            borderRadius: '8px',
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
      )}

      {/* 타이틀 */}
      <h1
        style={{
          fontFamily: 'Paperlogy, sans-serif',
          fontWeight: 600,
          fontSize: '18px',
          color: 'white',
          textShadow: '0 2px 4px rgba(0,0,0,0.3)',
          margin: 0,
        }}
      >
        충전소
      </h1>

      {/* 잔액 표시 */}
      <div
        style={{
          background: 'rgba(0,0,0,0.3)',
          padding: '8px 12px',
          borderRadius: '20px',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
        }}
      >
        <span
          style={{
            fontWeight: 600,
            fontSize: '14px',
            color: 'var(--figma-balance-color)',
          }}
        >
          {balance.toLocaleString()}
        </span>
      </div>
    </div>
  );
}
