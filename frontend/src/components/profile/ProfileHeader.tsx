'use client';

import { motion } from 'framer-motion';
import { UserProfile } from '@/lib/api';
import { Avatar } from '@/components/common';

interface ProfileHeaderProps {
  user: UserProfile | null;
  onEditClick: () => void;
}

export default function ProfileHeader({ user, onEditClick }: ProfileHeaderProps) {
  return (
    <div
      style={{
        padding: '24px 20px',
        textAlign: 'center',
        background: 'linear-gradient(180deg, rgba(255,255,255,0.05) 0%, transparent 100%)',
      }}
    >
      {/* 아바타 */}
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        style={{
          position: 'relative',
          display: 'inline-block',
          margin: '0 auto 16px',
        }}
      >
        <Avatar
          avatarId={user?.avatar_url ?? null}
          size="xl"
          nickname={user?.nickname}
        />
        {/* 편집 버튼 */}
        <motion.button
          onClick={onEditClick}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          style={{
            position: 'absolute',
            bottom: 0,
            right: 0,
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            background: 'var(--figma-charge-btn-bg)',
            border: '2px solid var(--figma-bg-main)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="white">
            <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z" />
          </svg>
        </motion.button>
      </motion.div>

      {/* 닉네임 */}
      <h2
        style={{
          fontSize: '24px',
          fontWeight: 700,
          color: 'white',
          margin: '0 0 8px 0',
        }}
      >
        {user?.nickname || '로딩 중...'}
      </h2>

      {/* 이메일 */}
      <p
        style={{
          fontSize: '14px',
          color: '#888',
          margin: '0 0 16px 0',
        }}
      >
        {user?.email || ''}
      </p>

      {/* 잔액 */}
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          background: 'rgba(0,0,0,0.3)',
          padding: '12px 24px',
          borderRadius: '24px',
          border: '1px solid rgba(255,255,255,0.1)',
        }}
      >
        <span style={{ color: '#888', fontSize: '14px' }}>잔액</span>
        <span
          style={{
            color: 'var(--figma-balance-color)',
            fontSize: '20px',
            fontWeight: 700,
          }}
        >
          {user?.balance?.toLocaleString() || '0'}
        </span>
        <span style={{ color: '#888', fontSize: '14px' }}>USDT</span>
      </div>
    </div>
  );
}
