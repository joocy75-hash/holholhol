'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { DepositRequestResponse } from '@/lib/api';

interface DepositQRViewProps {
  deposit: DepositRequestResponse;
}

export default function DepositQRView({ deposit }: DepositQRViewProps) {
  // 초기값으로 deposit.remaining_seconds 사용
  // 부모에서 key={deposit.id}를 전달하므로 deposit 변경 시 컴포넌트가 리마운트됨
  // 따라서 props 동기화 useEffect 불필요 (cascading render 방지)
  const [remainingSeconds, setRemainingSeconds] = useState(deposit.remaining_seconds);

  // 1초마다 카운트다운 감소
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
    <div style={{ padding: '20px', textAlign: 'center', position: 'relative', zIndex: 1 }}>
      {/* 상태 배너 */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card"
        style={{
          padding: '14px 20px',
          marginBottom: '24px',
          background:
            deposit.status === 'pending'
              ? 'linear-gradient(135deg, rgba(251, 191, 36, 0.15) 0%, rgba(245, 158, 11, 0.08) 100%)'
              : deposit.status === 'confirmed'
              ? 'linear-gradient(135deg, rgba(34, 197, 94, 0.15) 0%, rgba(22, 163, 74, 0.08) 100%)'
              : 'linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(220, 38, 38, 0.08) 100%)',
          borderColor:
            deposit.status === 'pending'
              ? 'rgba(251, 191, 36, 0.3)'
              : deposit.status === 'confirmed'
              ? 'rgba(34, 197, 94, 0.3)'
              : 'rgba(239, 68, 68, 0.3)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px' }}>
          {deposit.status === 'pending' && (
            <motion.div
              animate={{ scale: [1, 1.2, 1] }}
              transition={{ duration: 1.5, repeat: Infinity }}
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                background: '#fbbf24',
                boxShadow: '0 0 10px rgba(251, 191, 36, 0.5)',
              }}
            />
          )}
          <p
            style={{
              color:
                deposit.status === 'pending'
                  ? '#fbbf24'
                  : deposit.status === 'confirmed'
                  ? '#22c55e'
                  : '#ef4444',
              fontWeight: 600,
              margin: 0,
              fontSize: '15px',
            }}
          >
            {deposit.status === 'pending'
              ? '입금 대기 중'
              : deposit.status === 'confirmed'
              ? '입금 확인됨'
              : '만료됨'}
          </p>
        </div>
      </motion.div>

      {/* 금액 정보 */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="glass-card"
        style={{
          padding: '24px',
          marginBottom: '24px',
        }}
      >
        <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '13px', marginBottom: '8px', margin: 0 }}>
          입금 금액
        </p>
        <p
          className="glow-text-gold"
          style={{
            fontSize: '36px',
            fontWeight: 700,
            marginBottom: '8px',
            margin: '10px 0',
          }}
        >
          {deposit.calculated_usdt} USDT
        </p>
        <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: '14px', margin: 0 }}>
          ({parseInt(deposit.requested_krw.toString()).toLocaleString()}원)
        </p>
      </motion.div>

      {/* QR 코드 */}
      {!isExpired && deposit.status === 'pending' && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
          style={{
            background: 'white',
            padding: '20px',
            borderRadius: '20px',
            display: 'inline-block',
            marginBottom: '24px',
            boxShadow: '0 8px 30px rgba(0,0,0,0.3), 0 0 40px rgba(251, 191, 36, 0.1)',
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
              style={{ width: '200px', height: '200px', borderRadius: '8px' }}
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
                borderRadius: '8px',
              }}
            >
              QR 코드 로딩 중...
            </div>
          )}
        </motion.div>
      )}

      {/* 메모 (지갑 주소) */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="glass-card"
        style={{
          padding: '16px',
          marginBottom: '20px',
        }}
      >
        <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '12px', marginBottom: '8px', margin: 0 }}>
          입금 메모 (필수)
        </p>
        <p
          style={{
            color: '#fbbf24',
            fontSize: '14px',
            fontFamily: 'monospace',
            wordBreak: 'break-all',
            margin: '8px 0 0 0',
            fontWeight: 600,
            letterSpacing: '0.5px',
          }}
        >
          {deposit.memo}
        </p>
      </motion.div>

      {/* 타이머 */}
      {deposit.status === 'pending' && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="glass-card"
          style={{
            padding: '20px',
            marginBottom: '20px',
            background: isExpiringSoon
              ? 'linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(220, 38, 38, 0.08) 100%)'
              : undefined,
            borderColor: isExpiringSoon ? 'rgba(239, 68, 68, 0.3)' : undefined,
          }}
        >
          <p
            style={{
              color: isExpiringSoon ? '#f87171' : 'rgba(255,255,255,0.5)',
              fontSize: '12px',
              marginBottom: '8px',
              margin: 0,
            }}
          >
            남은 시간
          </p>
          <p
            style={{
              color: isExpiringSoon ? '#ef4444' : 'white',
              fontSize: '32px',
              fontWeight: 700,
              fontFamily: 'monospace',
              margin: '8px 0 0 0',
              textShadow: isExpiringSoon ? '0 0 15px rgba(239, 68, 68, 0.5)' : 'none',
            }}
          >
            {isExpired ? '만료됨' : formatTime(remainingSeconds)}
          </p>
        </motion.div>
      )}

      {/* 안내 메시지 */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="glass-card"
        style={{
          padding: '18px',
          textAlign: 'left',
          background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(37, 99, 235, 0.05) 100%)',
          borderColor: 'rgba(59, 130, 246, 0.2)',
        }}
      >
        <p
          style={{
            color: '#60a5fa',
            fontSize: '14px',
            fontWeight: 600,
            marginBottom: '12px',
            margin: 0,
          }}
        >
          입금 안내
        </p>
        <ul
          style={{
            color: 'rgba(255,255,255,0.6)',
            fontSize: '13px',
            paddingLeft: '18px',
            margin: '12px 0 0 0',
            lineHeight: 1.8,
          }}
        >
          <li>TON 지갑에서 위 QR코드를 스캔하세요</li>
          <li>메모(memo)를 반드시 입력해주세요</li>
          <li>입금 확인까지 1-3분 소요됩니다</li>
          <li>시간 만료 시 새로 요청해주세요</li>
        </ul>
      </motion.div>
    </div>
  );
}
