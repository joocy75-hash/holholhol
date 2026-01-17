'use client';

import { motion } from 'framer-motion';

interface MenuListProps {
  onEditProfile: () => void;
  onChangePassword: () => void;
  onLogout: () => void;
}

interface MenuItemProps {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  color?: string;
}

function MenuItem({ icon, label, onClick, color = 'white' }: MenuItemProps) {
  return (
    <motion.button
      onClick={onClick}
      whileHover={{ backgroundColor: 'rgba(255,255,255,0.1)' }}
      whileTap={{ scale: 0.98 }}
      style={{
        width: '100%',
        padding: '16px',
        background: 'transparent',
        border: 'none',
        borderBottom: '1px solid rgba(255,255,255,0.1)',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        cursor: 'pointer',
        color,
      }}
    >
      {icon}
      <span style={{ fontSize: '16px', flex: 1, textAlign: 'left' }}>{label}</span>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="#666">
        <path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z" />
      </svg>
    </motion.button>
  );
}

export default function MenuList({ onEditProfile, onChangePassword, onLogout }: MenuListProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      style={{
        margin: '0 20px 20px',
        background: 'rgba(255,255,255,0.05)',
        borderRadius: '16px',
        border: '1px solid rgba(255,255,255,0.1)',
        overflow: 'hidden',
      }}
    >
      <MenuItem
        icon={
          <svg width="24" height="24" viewBox="0 0 24 24" fill="#888">
            <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
          </svg>
        }
        label="프로필 수정"
        onClick={onEditProfile}
      />

      <MenuItem
        icon={
          <svg width="24" height="24" viewBox="0 0 24 24" fill="#888">
            <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z" />
          </svg>
        }
        label="비밀번호 변경"
        onClick={onChangePassword}
      />

      <MenuItem
        icon={
          <svg width="24" height="24" viewBox="0 0 24 24" fill="#888">
            <path d="M13 3h-2v10h2V3zm4.83 2.17l-1.42 1.42C17.99 7.86 19 9.81 19 12c0 3.87-3.13 7-7 7s-7-3.13-7-7c0-2.19 1.01-4.14 2.58-5.42L6.17 5.17C4.23 6.82 3 9.26 3 12c0 4.97 4.03 9 9 9s9-4.03 9-9c0-2.74-1.23-5.18-3.17-6.83z" />
          </svg>
        }
        label="로그아웃"
        onClick={onLogout}
        color="#ef4444"
      />
    </motion.div>
  );
}
