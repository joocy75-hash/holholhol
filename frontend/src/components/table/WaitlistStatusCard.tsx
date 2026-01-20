'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { WaitlistSeatReadyPayload } from '@/types/websocket';

interface WaitlistStatusCardProps {
  position: number;
  onCancel: () => void;
  isLoading: boolean;
  seatReadyInfo: WaitlistSeatReadyPayload | null;
  onAcceptSeat: () => void;
}

export default function WaitlistStatusCard({
  position,
  onCancel,
  isLoading,
  seatReadyInfo,
  onAcceptSeat,
}: WaitlistStatusCardProps) {
  const [countdown, setCountdown] = useState<number>(seatReadyInfo?.expiresInSeconds || 30);

  // 카운트다운 타이머
  // 의도적 state 리셋: seatReadyInfo 변경 시 카운트다운 초기화 필요
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (!seatReadyInfo) return;

    setCountdown(seatReadyInfo.expiresInSeconds);

    const interval = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [seatReadyInfo]);
  /* eslint-enable react-hooks/set-state-in-effect */

  // 자리 준비됨 상태
  if (seatReadyInfo) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: '320px',
          background: 'linear-gradient(135deg, rgba(34, 197, 94, 0.2) 0%, rgba(22, 163, 74, 0.15) 100%)',
          borderRadius: '20px',
          padding: '28px',
          border: '2px solid rgba(34, 197, 94, 0.4)',
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.5), 0 0 40px rgba(34, 197, 94, 0.2)',
          zIndex: 150,
        }}
      >
        {/* 헤더 */}
        <div style={{ textAlign: 'center', marginBottom: '20px' }}>
          <motion.span
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 0.5, repeat: Infinity }}
            style={{ fontSize: '48px', display: 'block', marginBottom: '12px' }}
          >
            🎉
          </motion.span>
          <h3
            style={{
              fontSize: '20px',
              fontWeight: 700,
              color: '#22c55e',
              margin: '0 0 8px 0',
            }}
          >
            자리가 났습니다!
          </h3>
          <p
            style={{
              fontSize: '14px',
              color: 'rgba(255,255,255,0.7)',
              margin: 0,
            }}
          >
            {seatReadyInfo.message}
          </p>
        </div>

        {/* 카운트다운 */}
        <div
          style={{
            background: 'rgba(0,0,0,0.3)',
            borderRadius: '12px',
            padding: '16px',
            marginBottom: '20px',
            textAlign: 'center',
          }}
        >
          <p
            style={{
              margin: '0 0 8px 0',
              fontSize: '13px',
              color: 'rgba(255,255,255,0.5)',
            }}
          >
            남은 시간
          </p>
          <p
            style={{
              margin: 0,
              fontSize: '36px',
              fontWeight: 700,
              color: countdown <= 10 ? '#ef4444' : '#22c55e',
              fontFamily: 'monospace',
            }}
          >
            {countdown}초
          </p>
          {/* 프로그레스 바 */}
          <div
            style={{
              height: '4px',
              background: 'rgba(255,255,255,0.1)',
              borderRadius: '2px',
              marginTop: '12px',
              overflow: 'hidden',
            }}
          >
            <motion.div
              initial={{ width: '100%' }}
              animate={{ width: '0%' }}
              transition={{
                duration: seatReadyInfo.expiresInSeconds,
                ease: 'linear',
              }}
              style={{
                height: '100%',
                background: countdown <= 10 ? '#ef4444' : '#22c55e',
                borderRadius: '2px',
              }}
            />
          </div>
        </div>

        {/* 바이인 정보 */}
        <div
          style={{
            background: 'rgba(255,255,255,0.05)',
            borderRadius: '8px',
            padding: '12px',
            marginBottom: '16px',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: '14px',
            }}
          >
            <span style={{ color: 'rgba(255,255,255,0.5)' }}>바이인 금액</span>
            <span style={{ color: '#f59e0b', fontWeight: 700 }}>
              {seatReadyInfo.buyIn.toLocaleString()}원
            </span>
          </div>
        </div>

        {/* 버튼 */}
        <motion.button
          onClick={onAcceptSeat}
          disabled={isLoading || countdown === 0}
          whileHover={{ scale: isLoading ? 1 : 1.02 }}
          whileTap={{ scale: isLoading ? 1 : 0.98 }}
          style={{
            width: '100%',
            padding: '16px',
            background:
              isLoading || countdown === 0
                ? 'rgba(255,255,255,0.2)'
                : 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)',
            border: 'none',
            borderRadius: '12px',
            color: 'white',
            fontSize: '16px',
            fontWeight: 700,
            cursor: isLoading || countdown === 0 ? 'not-allowed' : 'pointer',
            boxShadow:
              isLoading || countdown === 0
                ? 'none'
                : '0 4px 20px rgba(34, 197, 94, 0.4)',
          }}
        >
          {isLoading ? (
            <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
              <motion.span
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                style={{ display: 'inline-block' }}
              >
                ⏳
              </motion.span>
              착석 중...
            </span>
          ) : countdown === 0 ? (
            '시간 초과'
          ) : (
            '지금 착석하기'
          )}
        </motion.button>
      </motion.div>
    );
  }

  // 일반 대기 중 상태
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        position: 'fixed',
        bottom: '100px',
        left: '50%',
        transform: 'translateX(-50%)',
        width: '320px',
        background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(37, 99, 235, 0.1) 100%)',
        borderRadius: '16px',
        padding: '20px',
        border: '1px solid rgba(59, 130, 246, 0.3)',
        boxShadow: '0 10px 40px rgba(0, 0, 0, 0.4)',
        zIndex: 100,
      }}
    >
      {/* 헤더 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <motion.span
            animate={{ rotate: 360 }}
            transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
            style={{ fontSize: '28px' }}
          >
            ⏳
          </motion.span>
          <div>
            <h4
              style={{
                margin: 0,
                fontSize: '16px',
                fontWeight: 700,
                color: 'white',
              }}
            >
              대기열 대기 중
            </h4>
            <p
              style={{
                margin: '4px 0 0 0',
                fontSize: '12px',
                color: 'rgba(255,255,255,0.5)',
              }}
            >
              자리가 나면 알려드립니다
            </p>
          </div>
        </div>

        {/* 순번 배지 */}
        <div
          style={{
            background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
            borderRadius: '12px',
            padding: '8px 16px',
            textAlign: 'center',
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: '20px',
              fontWeight: 700,
              color: 'white',
            }}
          >
            {position}번
          </p>
        </div>
      </div>

      {/* 취소 버튼 */}
      <motion.button
        onClick={onCancel}
        disabled={isLoading}
        whileHover={{ scale: isLoading ? 1 : 1.02 }}
        whileTap={{ scale: isLoading ? 1 : 0.98 }}
        style={{
          width: '100%',
          padding: '12px',
          background: 'rgba(255,255,255,0.08)',
          border: '1px solid rgba(255,255,255,0.15)',
          borderRadius: '10px',
          color: 'rgba(255,255,255,0.7)',
          fontSize: '14px',
          fontWeight: 600,
          cursor: isLoading ? 'not-allowed' : 'pointer',
          opacity: isLoading ? 0.5 : 1,
        }}
      >
        {isLoading ? '취소 중...' : '대기 취소'}
      </motion.button>
    </motion.div>
  );
}
