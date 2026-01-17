'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';

interface AmountSelectorProps {
  exchangeRate: string | null;
  onSelect: (amount: number) => void;
  isLoading: boolean;
}

const PRESET_AMOUNTS = [
  { krw: 10000, label: '1만원' },
  { krw: 30000, label: '3만원' },
  { krw: 50000, label: '5만원' },
  { krw: 100000, label: '10만원' },
  { krw: 300000, label: '30만원' },
  { krw: 500000, label: '50만원' },
];

const quickSpring = { type: 'spring' as const, stiffness: 400, damping: 20 };

export default function AmountSelector({
  exchangeRate,
  onSelect,
  isLoading,
}: AmountSelectorProps) {
  const [customAmount, setCustomAmount] = useState<string>('');
  const [selectedPreset, setSelectedPreset] = useState<number | null>(null);

  const rate = exchangeRate ? parseFloat(exchangeRate) : null;

  const calculateUsdt = (krw: number): string => {
    if (!rate) return '-';
    return (krw / rate).toFixed(2);
  };

  const handlePresetClick = (amount: number) => {
    setSelectedPreset(amount);
    setCustomAmount('');
  };

  const handleCustomChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.replace(/[^0-9]/g, '');
    setCustomAmount(value);
    setSelectedPreset(null);
  };

  const handleSubmit = () => {
    const amount = selectedPreset || parseInt(customAmount) || 0;
    if (amount >= 10000) {
      onSelect(amount);
    }
  };

  const currentAmount = selectedPreset || parseInt(customAmount) || 0;
  const isValid = currentAmount >= 10000;

  return (
    <div style={{ padding: '20px' }}>
      {/* 환율 표시 */}
      <div
        style={{
          background: 'rgba(255,255,255,0.05)',
          borderRadius: '12px',
          padding: '16px',
          marginBottom: '24px',
          textAlign: 'center',
          border: '1px solid rgba(255,255,255,0.1)',
        }}
      >
        <p style={{ color: '#888', fontSize: '12px', marginBottom: '4px', margin: 0 }}>
          현재 환율
        </p>
        <p
          style={{
            color: 'white',
            fontSize: '18px',
            fontWeight: 600,
            margin: '8px 0 0 0',
          }}
        >
          1 USDT = {rate ? `${rate.toLocaleString()}원` : '로딩 중...'}
        </p>
      </div>

      {/* 프리셋 금액 버튼 */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '12px',
          marginBottom: '24px',
        }}
      >
        {PRESET_AMOUNTS.map(({ krw, label }) => (
          <motion.button
            key={krw}
            onClick={() => handlePresetClick(krw)}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            transition={quickSpring}
            style={{
              padding: '16px 8px',
              background:
                selectedPreset === krw
                  ? 'var(--figma-charge-btn-bg)'
                  : 'rgba(255,255,255,0.05)',
              border:
                selectedPreset === krw
                  ? '2px solid var(--figma-charge-btn-bg)'
                  : '1px solid rgba(255,255,255,0.1)',
              borderRadius: '12px',
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
          >
            <p
              style={{
                color: 'white',
                fontWeight: 600,
                fontSize: '16px',
                marginBottom: '4px',
                margin: 0,
              }}
            >
              {label}
            </p>
            <p
              style={{
                color: 'var(--figma-balance-color)',
                fontSize: '12px',
                margin: '4px 0 0 0',
              }}
            >
              {calculateUsdt(krw)} USDT
            </p>
          </motion.button>
        ))}
      </div>

      {/* 직접 입력 */}
      <div style={{ marginBottom: '24px' }}>
        <label
          style={{
            display: 'block',
            color: '#888',
            fontSize: '12px',
            marginBottom: '8px',
          }}
        >
          직접 입력 (최소 10,000원)
        </label>
        <div style={{ position: 'relative' }}>
          <input
            type="text"
            value={customAmount ? parseInt(customAmount).toLocaleString() : ''}
            onChange={handleCustomChange}
            placeholder="금액 입력"
            style={{
              width: '100%',
              padding: '16px',
              paddingRight: '40px',
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '12px',
              color: 'white',
              fontSize: '16px',
              outline: 'none',
              boxSizing: 'border-box',
            }}
          />
          <span
            style={{
              position: 'absolute',
              right: '16px',
              top: '50%',
              transform: 'translateY(-50%)',
              color: '#888',
            }}
          >
            원
          </span>
        </div>
        {customAmount && parseInt(customAmount) >= 10000 && (
          <p
            style={{
              color: 'var(--figma-balance-color)',
              fontSize: '14px',
              marginTop: '8px',
              margin: '8px 0 0 0',
            }}
          >
            = {calculateUsdt(parseInt(customAmount))} USDT
          </p>
        )}
      </div>

      {/* 충전 버튼 */}
      <motion.button
        onClick={handleSubmit}
        disabled={!isValid || isLoading}
        whileHover={isValid && !isLoading ? { scale: 1.02 } : {}}
        whileTap={isValid && !isLoading ? { scale: 0.98 } : {}}
        transition={quickSpring}
        style={{
          width: '100%',
          padding: '18px',
          background: isValid ? 'var(--figma-charge-btn-bg)' : 'rgba(255,255,255,0.1)',
          border: 'none',
          borderRadius: '12px',
          color: 'white',
          fontWeight: 700,
          fontSize: '18px',
          cursor: isValid && !isLoading ? 'pointer' : 'not-allowed',
          opacity: isValid ? 1 : 0.5,
        }}
      >
        {isLoading ? '처리 중...' : `${currentAmount.toLocaleString()}원 충전하기`}
      </motion.button>
    </div>
  );
}
