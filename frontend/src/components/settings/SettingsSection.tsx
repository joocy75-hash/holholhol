'use client';

import { ReactNode } from 'react';

interface SettingsSectionProps {
  title: string;
  icon?: ReactNode;
  children: ReactNode;
}

export default function SettingsSection({ title, icon, children }: SettingsSectionProps) {
  return (
    <div
      style={{
        marginBottom: '24px',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          marginBottom: '12px',
          paddingLeft: '4px',
        }}
      >
        {icon}
        <h3
          style={{
            margin: 0,
            fontSize: '14px',
            fontWeight: 600,
            color: '#888',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          }}
        >
          {title}
        </h3>
      </div>
      <div
        style={{
          background: 'rgba(255,255,255,0.05)',
          borderRadius: '12px',
          border: '1px solid rgba(255,255,255,0.1)',
          overflow: 'hidden',
        }}
      >
        {children}
      </div>
    </div>
  );
}
