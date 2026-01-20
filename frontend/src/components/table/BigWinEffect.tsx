'use client';

import { useEffect, useLayoutEffect, useState, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { feedbackManager } from '@/lib/sounds';

interface BigWinEffectProps {
  /** 승리 금액 */
  amount: number;
  /** 표시 여부 */
  show: boolean;
  /** 완료 콜백 */
  onComplete?: () => void;
  /** 빅윈 기준 금액 (기본: 10BB) */
  bigWinThreshold?: number;
  /** 현재 빅블라인드 */
  bigBlind?: number;
}

/**
 * 빅 윈 이펙트 컴포넌트
 * 
 * 큰 팟 획득 시 화려한 시각 효과를 표시합니다.
 * - 배경 폭죽 효과
 * - 승리 금액 애니메이션
 * - 진동 피드백
 */
export default function BigWinEffect({
  amount,
  show,
  onComplete,
  bigWinThreshold = 10,
  bigBlind = 100,
}: BigWinEffectProps) {
  const [particles, setParticles] = useState<Particle[]>([]);
  const [coins, setCoins] = useState<Coin[]>([]);
  // 타이머 ref (클린업용)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 빅윈 여부 (10BB 이상)
  const isBigWin = amount >= bigBlind * bigWinThreshold;
  // 슈퍼 빅윈 (50BB 이상)
  const isSuperBigWin = amount >= bigBlind * 50;

  // 파티클 생성 - 저사양 기기 고려하여 개수 감소
  const generateParticles = useCallback(() => {
    const newParticles: Particle[] = [];
    // 파티클 수 최적화: 50→30, 30→20, 15→10 (저사양 기기 프레임 드롭 방지)
    const count = isSuperBigWin ? 30 : isBigWin ? 20 : 10;

    for (let i = 0; i < count; i++) {
      newParticles.push({
        id: i,
        x: Math.random() * 100,
        delay: Math.random() * 0.5,
        duration: 1 + Math.random() * 1,
        color: getRandomColor(),
        size: 4 + Math.random() * 6,
      });
    }
    setParticles(newParticles);
  }, [isBigWin, isSuperBigWin]);

  // 코인 생성 - 저사양 기기 고려하여 개수 감소
  const generateCoins = useCallback(() => {
    if (!isBigWin) return;

    const newCoins: Coin[] = [];
    // 코인 수 최적화: 20→12, 10→6 (저사양 기기 프레임 드롭 방지)
    const count = isSuperBigWin ? 12 : 6;

    for (let i = 0; i < count; i++) {
      newCoins.push({
        id: i,
        x: 20 + Math.random() * 60,
        delay: Math.random() * 0.8,
        rotation: Math.random() * 360,
      });
    }
    setCoins(newCoins);
  }, [isBigWin, isSuperBigWin]);

  // 파티클/코인 생성 - useLayoutEffect로 DOM 커밋 전에 동기적으로 실행
  // show 상태 변경 시 깜빡임 없이 즉시 렌더링되도록 함
  // 의도적 state 리셋: 이펙트 표시/숨김 시 파티클 초기화 필요
  /* eslint-disable react-hooks/set-state-in-effect */
  useLayoutEffect(() => {
    if (show) {
      generateParticles();
      generateCoins();
    } else {
      // show가 false가 되면 파티클과 코인 초기화
      setParticles([]);
      setCoins([]);
    }
  }, [show, generateParticles, generateCoins]);
  /* eslint-enable react-hooks/set-state-in-effect */

  // 피드백 및 타이머 - 일반 useEffect 사용 (부수 효과)
  useEffect(() => {
    // 기존 타이머 정리
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }

    if (show) {
      // 피드백 재생 (사운드/진동은 비동기로 OK)
      feedbackManager.playWin(isSuperBigWin);

      // 애니메이션 완료 후 콜백
      timerRef.current = setTimeout(() => {
        onComplete?.();
        timerRef.current = null;
      }, 3000);
    }

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [show, isSuperBigWin, onComplete]);

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            pointerEvents: 'none',
            zIndex: 1000,
            overflow: 'hidden',
          }}
        >
          {/* 배경 글로우 */}
          <motion.div
            initial={{ scale: 0, opacity: 0 }}
            animate={{ 
              scale: [0, 1.5, 1], 
              opacity: [0, 0.6, 0.3] 
            }}
            transition={{ duration: 1, ease: 'easeOut' }}
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              width: '150vw',
              height: '150vh',
              background: isSuperBigWin
                ? 'radial-gradient(circle, rgba(255,215,0,0.4) 0%, transparent 70%)'
                : 'radial-gradient(circle, rgba(34,197,94,0.3) 0%, transparent 70%)',
            }}
          />

          {/* 폭죽 파티클 */}
          {particles.map((particle) => (
            <motion.div
              key={particle.id}
              initial={{ 
                x: `${particle.x}vw`, 
                y: '100vh',
                scale: 0,
              }}
              animate={{ 
                y: '-20vh',
                scale: [0, 1, 1, 0],
                opacity: [0, 1, 1, 0],
              }}
              transition={{ 
                duration: particle.duration,
                delay: particle.delay,
                ease: 'easeOut',
              }}
              style={{
                position: 'absolute',
                width: particle.size,
                height: particle.size,
                borderRadius: '50%',
                background: particle.color,
                boxShadow: `0 0 ${particle.size * 2}px ${particle.color}`,
              }}
            />
          ))}

          {/* 코인 비 (빅윈 시) */}
          {coins.map((coin) => (
            <motion.div
              key={`coin-${coin.id}`}
              initial={{
                x: `${coin.x}vw`,
                y: '-10vh',
                rotate: 0,
                opacity: 1,
              }}
              animate={{
                y: '110vh',
                rotate: coin.rotation + 720,
                opacity: [1, 1, 0],
              }}
              transition={{
                duration: 2.5,
                delay: coin.delay,
                ease: 'easeIn',
              }}
              style={{
                position: 'absolute',
                width: 30,
                height: 30,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 24,
              }}
            >
              💰
            </motion.div>
          ))}

          {/* 승리 금액 표시 */}
          <motion.div
            initial={{ scale: 0, y: 50 }}
            animate={{ 
              scale: [0, 1.3, 1],
              y: [50, 0, 0],
            }}
            transition={{ 
              duration: 0.8,
              ease: 'backOut',
            }}
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              textAlign: 'center',
            }}
          >
            {/* 빅윈 라벨 */}
            {isBigWin && (
              <motion.div
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                style={{
                  fontSize: isSuperBigWin ? 32 : 24,
                  fontWeight: 800,
                  color: isSuperBigWin ? '#FFD700' : '#22C55E',
                  textShadow: isSuperBigWin
                    ? '0 0 20px rgba(255,215,0,0.8), 0 0 40px rgba(255,215,0,0.5)'
                    : '0 0 15px rgba(34,197,94,0.6)',
                  marginBottom: 8,
                  letterSpacing: 2,
                }}
              >
                {isSuperBigWin ? '🎰 SUPER BIG WIN! 🎰' : '🏆 BIG WIN! 🏆'}
              </motion.div>
            )}

            {/* 금액 */}
            <motion.div
              animate={{ 
                scale: [1, 1.05, 1],
              }}
              transition={{ 
                repeat: Infinity,
                duration: 0.8,
              }}
              style={{
                fontSize: isSuperBigWin ? 56 : isBigWin ? 48 : 36,
                fontWeight: 800,
                color: isSuperBigWin ? '#FFD700' : '#22C55E',
                textShadow: '0 4px 12px rgba(0,0,0,0.5)',
                fontFamily: 'var(--font-display, system-ui)',
              }}
            >
              +{formatAmount(amount)}
            </motion.div>

            {/* 칩 아이콘 */}
            <motion.div
              initial={{ opacity: 0, scale: 0 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.5 }}
              style={{
                marginTop: 12,
                fontSize: 14,
                color: 'rgba(255,255,255,0.7)',
              }}
            >
              CHIPS
            </motion.div>
          </motion.div>

          {/* 하단 스파클 라인 */}
          {isBigWin && (
            <motion.div
              initial={{ scaleX: 0, opacity: 0 }}
              animate={{ scaleX: 1, opacity: 1 }}
              transition={{ delay: 0.2, duration: 0.5 }}
              style={{
                position: 'absolute',
                bottom: '30%',
                left: '10%',
                right: '10%',
                height: 2,
                background: 'linear-gradient(90deg, transparent, #FFD700, transparent)',
              }}
            />
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// =============================================================================
// 유틸리티
// =============================================================================

interface Particle {
  id: number;
  x: number;
  delay: number;
  duration: number;
  color: string;
  size: number;
}

interface Coin {
  id: number;
  x: number;
  delay: number;
  rotation: number;
}

function getRandomColor(): string {
  const colors = [
    '#FFD700', // Gold
    '#FF6B6B', // Red
    '#4ECDC4', // Teal
    '#45B7D1', // Blue
    '#96CEB4', // Green
    '#FFEAA7', // Yellow
    '#DDA0DD', // Plum
    '#98D8C8', // Mint
  ];
  return colors[Math.floor(Math.random() * colors.length)];
}

function formatAmount(amount: number): string {
  if (amount >= 1000000) {
    return `${(amount / 1000000).toFixed(1)}M`;
  }
  if (amount >= 1000) {
    return `${(amount / 1000).toFixed(1)}K`;
  }
  return amount.toLocaleString();
}
