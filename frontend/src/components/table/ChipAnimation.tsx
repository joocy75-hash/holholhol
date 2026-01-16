'use client';

import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  staggeredChip,
  floatingNumber,
  CHIP_CONSTANTS,
  calculateCurvedPath,
  pathToKeyframes,
  Point,
} from '@/lib/animations';

interface ChipAnimationProps {
  /** 베팅 금액 */
  amount: number;
  /** 시작 위치 (플레이어 좌석) */
  startPosition: Point;
  /** 끝 위치 (테이블 중앙) */
  endPosition: Point;
  /** 애니메이션 시작 트리거 */
  isAnimating: boolean;
  /** 애니메이션 완료 콜백 (사운드 트리거용) */
  onAnimationComplete?: () => void;
  /** 첫 칩 도착 콜백 (숫자 팝업용) */
  onFirstChipArrived?: () => void;
  /** 칩 색상 (기본: 금색) */
  chipColor?: string;
  /** 고유 키 (외부에서 제어) */
  animationKey?: number;
}

// 금액에 따른 칩 개수 계산
function getChipCount(amount: number): number {
  if (amount >= 10000) return 5;
  if (amount >= 5000) return 4;
  if (amount >= 1000) return 3;
  if (amount >= 500) return 2;
  return 1;
}

// 금액 포맷팅
function formatAmount(amount: number): string {
  if (amount >= 10000) {
    return `+${(amount / 10000).toFixed(1)}만`;
  }
  if (amount >= 1000) {
    return `+${(amount / 1000).toFixed(1)}천`;
  }
  return `+${amount.toLocaleString()}`;
}

/**
 * 베팅 칩 이동 애니메이션 컴포넌트
 * - Staggered 칩 이동 (0.05초 간격)
 * - 곡선 경로 (베지어 곡선)
 * - Floating Number 효과
 * - 효과음 동기화 포인트
 */
export default function ChipAnimation({
  amount,
  startPosition,
  endPosition,
  isAnimating,
  onAnimationComplete,
  onFirstChipArrived,
  chipColor = '#FFD700',
  animationKey = 0,
}: ChipAnimationProps) {
  // showFloatingNumber는 animationKey가 변경될 때 리셋됨
  // 이는 새 애니메이션이 시작될 때마다 발생
  const [showFloatingNumber, setShowFloatingNumber] = useState(false);
  const [lastAnimationKey, setLastAnimationKey] = useState(animationKey);
  
  // animationKey가 변경되면 floating number 리셋
  if (animationKey !== lastAnimationKey) {
    setLastAnimationKey(animationKey);
    if (showFloatingNumber) {
      setShowFloatingNumber(false);
    }
  }

  const chipCount = getChipCount(amount);
  
  // 곡선 경로 계산
  const path = calculateCurvedPath(startPosition, endPosition, {
    curvature: 0.25,
    direction: 'up',
  });
  const keyframes = pathToKeyframes(path);

  // 첫 칩 도착 처리
  const handleFirstChipArrived = useCallback(() => {
    setShowFloatingNumber(true);
    onFirstChipArrived?.();
  }, [onFirstChipArrived]);

  // 전체 애니메이션 완료 처리
  const handleAnimationComplete = useCallback(() => {
    onAnimationComplete?.();
  }, [onAnimationComplete]);

  if (!isAnimating) return null;

  return (
    <div className="absolute inset-0 pointer-events-none z-50">
      <AnimatePresence>
        {/* 칩들 */}
        {Array.from({ length: chipCount }).map((_, index) => (
          <motion.div
            key={`${animationKey}-chip-${index}`}
            className="absolute w-8 h-8"
            style={{
              left: startPosition.x - 16,
              top: startPosition.y - 16,
            }}
            variants={staggeredChip}
            initial="initial"
            animate={{
              x: keyframes.x.map(x => x - startPosition.x),
              y: keyframes.y.map(y => y - startPosition.y),
              opacity: 1,
              scale: 1,
            }}
            transition={{
              duration: CHIP_CONSTANTS.MOVE_DURATION / 1000,
              delay: index * (CHIP_CONSTANTS.STAGGER_DELAY / 1000),
              ease: [0.25, 0.1, 0.25, 1], // 부드러운 곡선
            }}
            onAnimationComplete={() => {
              if (index === 0) {
                handleFirstChipArrived();
              }
              if (index === chipCount - 1) {
                handleAnimationComplete();
              }
            }}
          >
            {/* 칩 아이콘 */}
            <div
              className="w-full h-full rounded-full shadow-lg flex items-center justify-center"
              style={{
                background: `linear-gradient(135deg, ${chipColor} 0%, #B8860B 100%)`,
                border: '2px solid #8B6914',
              }}
            >
              <div
                className="w-5 h-5 rounded-full border-2"
                style={{ borderColor: '#8B6914' }}
              />
            </div>
          </motion.div>
        ))}

        {/* Floating Number */}
        {showFloatingNumber && (
          <motion.div
            key={`${animationKey}-number`}
            className="absolute text-2xl font-bold text-yellow-400 drop-shadow-lg"
            style={{
              left: endPosition.x,
              top: endPosition.y,
              transform: 'translate(-50%, -50%)',
            }}
            variants={floatingNumber}
            initial="initial"
            animate="animate"
            onAnimationComplete={() => setShowFloatingNumber(false)}
          >
            {formatAmount(amount)}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/**
 * 칩 애니메이션 훅 - 컴포넌트에서 쉽게 사용
 */
export function useChipAnimation() {
  const [animationState, setAnimationState] = useState<{
    isAnimating: boolean;
    amount: number;
    startPosition: Point;
    endPosition: Point;
    key: number;
  } | null>(null);

  const triggerAnimation = useCallback((
    amount: number,
    startPosition: Point,
    endPosition: Point
  ) => {
    setAnimationState(prev => ({
      isAnimating: true,
      amount,
      startPosition,
      endPosition,
      key: (prev?.key ?? 0) + 1,
    }));
  }, []);

  const stopAnimation = useCallback(() => {
    setAnimationState(null);
  }, []);

  return {
    animationState,
    triggerAnimation,
    stopAnimation,
  };
}

