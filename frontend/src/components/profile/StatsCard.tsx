'use client';

import { motion } from 'framer-motion';
import { UserStats } from '@/lib/api';

interface StatsCardProps {
  stats: UserStats | null;
  isLoading: boolean;
}

interface StatItemProps {
  label: string;
  value: string | number;
  suffix?: string;
  color?: string;
}

function StatItem({ label, value, suffix = '', color = 'white' }: StatItemProps) {
  return (
    <div style={{ textAlign: 'center' }}>
      <p
        style={{
          fontSize: '12px',
          color: '#888',
          margin: '0 0 4px 0',
        }}
      >
        {label}
      </p>
      <p
        style={{
          fontSize: '18px',
          fontWeight: 700,
          color,
          margin: 0,
        }}
      >
        {value}
        {suffix && <span style={{ fontSize: '14px', fontWeight: 400 }}>{suffix}</span>}
      </p>
    </div>
  );
}

export default function StatsCard({ stats, isLoading }: StatsCardProps) {
  const winRate = stats && stats.total_hands > 0
    ? ((stats.hands_won / stats.total_hands) * 100).toFixed(1)
    : '0.0';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        margin: '0 20px 20px',
        padding: '20px',
        background: 'rgba(255,255,255,0.05)',
        borderRadius: '16px',
        border: '1px solid rgba(255,255,255,0.1)',
      }}
    >
      <h3
        style={{
          fontSize: '16px',
          fontWeight: 600,
          color: 'white',
          margin: '0 0 16px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="var(--figma-balance-color)">
          <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z" />
        </svg>
        게임 통계
      </h3>

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: '20px', color: '#888' }}>
          로딩 중...
        </div>
      ) : (
        <>
          {/* 첫 번째 줄 */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: '16px',
              marginBottom: '16px',
            }}
          >
            <StatItem
              label="총 핸드"
              value={stats?.total_hands?.toLocaleString() || '0'}
            />
            <StatItem
              label="승리"
              value={stats?.hands_won?.toLocaleString() || '0'}
            />
            <StatItem
              label="승률"
              value={winRate}
              suffix="%"
              color="var(--figma-balance-color)"
            />
          </div>

          {/* 구분선 */}
          <div
            style={{
              height: '1px',
              background: 'rgba(255,255,255,0.1)',
              margin: '16px 0',
            }}
          />

          {/* 두 번째 줄 */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: '16px',
            }}
          >
            <StatItem
              label="VPIP"
              value={stats?.vpip?.toFixed(1) || '0.0'}
              suffix="%"
            />
            <StatItem
              label="PFR"
              value={stats?.pfr?.toFixed(1) || '0.0'}
              suffix="%"
            />
            <StatItem
              label="최대 팟"
              value={stats?.biggest_pot?.toLocaleString() || '0'}
            />
          </div>
        </>
      )}
    </motion.div>
  );
}
