'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { DepositRequestResponse } from '@/lib/api';

interface DepositQRViewProps {
  deposit: DepositRequestResponse;
}

export default function DepositQRView({ deposit }: DepositQRViewProps) {
  const [remainingSeconds, setRemainingSeconds] = useState(deposit.remaining_seconds);

  // 카운트다운 타이머
  useEffect(() => {
    setRemainingSeconds(deposit.remaining_seconds);
  }, [deposit.remaining_seconds]);

  useEffect(() => {
    const timer = setInterval(() => {
      setRemainingSeconds((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const isExpiringSoon = remainingSeconds < 300; // 5분 미만
  const isExpired = remainingSeconds <= 0 || deposit.status === 'expired';

  return (
    <div style={{ padding: '20px', textAlign: 'center' }}>
      {/* 상태 배너 */}
      <div
        style={{
          background:
            deposit.status === 'pending'
              ? 'rgba(250, 196, 71, 0.1)'
              : deposit.status === 'confirmed'
              ? 'rgba(34, 197, 94, 0.1)'
              : 'rgba(239, 68, 68, 0.1)',
          borderRadius: '8px',
          padding: '12px',
          marginBottom: '24px',
          border: `1px solid ${
            deposit.status === 'pending'
              ? 'rgba(250, 196, 71, 0.3)'
              : deposit.status === 'confirmed'
              ? 'rgba(34, 197, 94, 0.3)'
              : 'rgba(239, 68, 68, 0.3)'
          }`,
        }}
      >
        <p
          style={{
            color:
              deposit.status === 'pending'
                ? 'var(--figma-balance-color)'
                : deposit.status === 'confirmed'
                ? '#22c55e'
                : '#ef4444',
            fontWeight: 600,
            margin: 0,
          }}
        >
          {deposit.status === 'pending'
            ? '입금 대기 중'
            : deposit.status === 'confirmed'
            ? '입금 확인됨'
            : '만료됨'}
        </p>
      </div>

      {/* 금액 정보 */}
      <div
        style={{
          background: 'rgba(255,255,255,0.05)',
          borderRadius: '12px',
          padding: '20px',
          marginBottom: '24px',
          border: '1px solid rgba(255,255,255,0.1)',
        }}
      >
        <p style={{ color: '#888', fontSize: '14px', marginBottom: '8px', margin: 0 }}>
          입금 금액
        </p>
        <p
          style={{
            color: 'var(--figma-balance-color)',
            fontSize: '32px',
            fontWeight: 700,
            marginBottom: '8px',
            margin: '8px 0',
          }}
        >
          {deposit.calculated_usdt} USDT
        </p>
        <p style={{ color: '#666', fontSize: '14px', margin: 0 }}>
          ({parseInt(deposit.requested_krw.toString()).toLocaleString()}원)
        </p>
      </div>

      {/* QR 코드 */}
      {!isExpired && deposit.status === 'pending' && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          style={{
            background: 'white',
            padding: '16px',
            borderRadius: '16px',
            display: 'inline-block',
            marginBottom: '24px',
          }}
        >
          {deposit.qr_data ? (
            <img
              src={
                deposit.qr_data.startsWith('data:')
                  ? deposit.qr_data
                  : `data:image/png;base64,${deposit.qr_data}`
              }
              alt="TON Deposit QR"
              style={{ width: '200px', height: '200px' }}
            />
          ) : (
            <div
              style={{
                width: '200px',
                height: '200px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: '#f0f0f0',
                color: '#666',
              }}
            >
              QR 코드 로딩 중...
            </div>
          )}
        </motion.div>
      )}

      {/* 메모 (지갑 주소) */}
      <div
        style={{
          background: 'rgba(255,255,255,0.05)',
          borderRadius: '8px',
          padding: '12px',
          marginBottom: '24px',
          border: '1px solid rgba(255,255,255,0.1)',
        }}
      >
        <p style={{ color: '#888', fontSize: '12px', marginBottom: '4px', margin: 0 }}>
          입금 메모 (필수)
        </p>
        <p
          style={{
            color: 'white',
            fontSize: '14px',
            fontFamily: 'monospace',
            wordBreak: 'break-all',
            margin: '8px 0 0 0',
          }}
        >
          {deposit.memo}
        </p>
      </div>

      {/* 타이머 */}
      {deposit.status === 'pending' && (
        <div
          style={{
            background: isExpiringSoon
              ? 'rgba(239, 68, 68, 0.1)'
              : 'rgba(255,255,255,0.05)',
            borderRadius: '8px',
            padding: '16px',
            border: `1px solid ${
              isExpiringSoon ? 'rgba(239, 68, 68, 0.3)' : 'rgba(255,255,255,0.1)'
            }`,
          }}
        >
          <p
            style={{
              color: isExpiringSoon ? '#ef4444' : '#888',
              fontSize: '12px',
              marginBottom: '4px',
              margin: 0,
            }}
          >
            남은 시간
          </p>
          <p
            style={{
              color: isExpiringSoon ? '#ef4444' : 'white',
              fontSize: '28px',
              fontWeight: 700,
              fontFamily: 'monospace',
              margin: '8px 0 0 0',
            }}
          >
            {isExpired ? '만료됨' : formatTime(remainingSeconds)}
          </p>
        </div>
      )}

      {/* 안내 메시지 */}
      <div
        style={{
          marginTop: '24px',
          padding: '16px',
          background: 'rgba(59, 130, 246, 0.1)',
          borderRadius: '8px',
          textAlign: 'left',
          border: '1px solid rgba(59, 130, 246, 0.3)',
        }}
      >
        <p
          style={{
            color: '#60a5fa',
            fontSize: '14px',
            fontWeight: 600,
            marginBottom: '8px',
            margin: 0,
          }}
        >
          입금 안내
        </p>
        <ul
          style={{
            color: '#888',
            fontSize: '12px',
            paddingLeft: '16px',
            margin: '8px 0 0 0',
          }}
        >
          <li style={{ marginBottom: '4px' }}>TON 지갑에서 위 QR코드를 스캔하세요</li>
          <li style={{ marginBottom: '4px' }}>메모(memo)를 반드시 입력해주세요</li>
          <li style={{ marginBottom: '4px' }}>입금 확인까지 1-3분 소요됩니다</li>
          <li>시간 만료 시 새로 요청해주세요</li>
        </ul>
      </div>
    </div>
  );
}
