'use client';

import { motion } from 'framer-motion';

type TabType = 'game' | 'transaction';

interface HistoryHeaderProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
}

export default function HistoryHeader({ activeTab, onTabChange }: HistoryHeaderProps) {
  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: '50%',
        transform: 'translateX(-50%)',
        width: '390px',
        background: 'var(--figma-gradient-header)',
        zIndex: 100,
        borderBottom: '1px solid rgba(255,255,255,0.1)',
      }}
    >
      {/* 타이틀 */}
      <div
        style={{
          height: '60px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
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
          기록
        </h1>
      </div>

      {/* 탭 */}
      <div
        style={{
          display: 'flex',
          padding: '0 20px 12px',
          gap: '12px',
        }}
      >
        <motion.button
          onClick={() => onTabChange('game')}
          whileTap={{ scale: 0.95 }}
          style={{
            flex: 1,
            padding: '10px',
            background: activeTab === 'game'
              ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
              : 'rgba(255,255,255,0.1)',
            border: 'none',
            borderRadius: '8px',
            color: 'white',
            fontSize: '14px',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'background 0.2s',
          }}
        >
          게임 기록
        </motion.button>
        <motion.button
          onClick={() => onTabChange('transaction')}
          whileTap={{ scale: 0.95 }}
          style={{
            flex: 1,
            padding: '10px',
            background: activeTab === 'transaction'
              ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
              : 'rgba(255,255,255,0.1)',
            border: 'none',
            borderRadius: '8px',
            color: 'white',
            fontSize: '14px',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'background 0.2s',
          }}
        >
          거래 내역
        </motion.button>
      </div>
    </div>
  );
}
