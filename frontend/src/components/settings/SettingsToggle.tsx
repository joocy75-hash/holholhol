'use client';

import { motion } from 'framer-motion';

interface SettingsToggleProps {
  label: string;
  description?: string;
  value: boolean;
  onChange: (value: boolean) => void;
  showDivider?: boolean;
}

export default function SettingsToggle({
  label,
  description,
  value,
  onChange,
  showDivider = true,
}: SettingsToggleProps) {
  return (
    <div
      style={{
        padding: '16px',
        borderBottom: showDivider ? '1px solid rgba(255,255,255,0.1)' : 'none',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}
    >
      <div style={{ flex: 1, marginRight: '16px' }}>
        <p style={{ margin: 0, color: 'white', fontSize: '15px', fontWeight: 500 }}>
          {label}
        </p>
        {description && (
          <p style={{ margin: '4px 0 0', color: '#888', fontSize: '12px' }}>
            {description}
          </p>
        )}
      </div>
      <motion.button
        onClick={() => onChange(!value)}
        whileTap={{ scale: 0.9 }}
        style={{
          width: '50px',
          height: '28px',
          borderRadius: '14px',
          background: value
            ? 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)'
            : 'rgba(255,255,255,0.2)',
          border: 'none',
          cursor: 'pointer',
          position: 'relative',
          transition: 'background 0.2s',
        }}
      >
        <motion.div
          animate={{ x: value ? 22 : 0 }}
          transition={{ type: 'spring', stiffness: 500, damping: 30 }}
          style={{
            position: 'absolute',
            top: '2px',
            left: '2px',
            width: '24px',
            height: '24px',
            borderRadius: '12px',
            background: 'white',
            boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
          }}
        />
      </motion.button>
    </div>
  );
}
