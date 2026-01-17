'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuthStore } from '@/stores/auth';
import HistoryHeader from '@/components/history/HistoryHeader';
import GameHistoryList from '@/components/history/GameHistoryList';
import TransactionList from '@/components/history/TransactionList';
import BottomNavigation from '@/components/lobby/BottomNavigation';

type TabType = 'game' | 'transaction';

export default function HistoryPage() {
  const router = useRouter();
  const { isAuthenticated, fetchUser } = useAuthStore();
  const [activeTab, setActiveTab] = useState<TabType>('game');

  // 인증 체크
  useEffect(() => {
    if (!isAuthenticated) {
      fetchUser().catch(() => router.push('/login'));
    }
  }, [isAuthenticated, fetchUser, router]);

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
      <HistoryHeader activeTab={activeTab} onTabChange={setActiveTab} />

      {/* 컨텐츠 */}
      <div style={{ paddingTop: '110px', paddingBottom: '120px' }}>
        <AnimatePresence mode="wait">
          {activeTab === 'game' && (
            <motion.div
              key="game"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.2 }}
            >
              <GameHistoryList />
            </motion.div>
          )}

          {activeTab === 'transaction' && (
            <motion.div
              key="transaction"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.2 }}
            >
              <TransactionList />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* 하단 네비게이션 */}
      <BottomNavigation />
    </div>
  );
}
