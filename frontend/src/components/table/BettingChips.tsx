'use client';

import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  staggeredChip,
  floatingNumber,
  CHIP_CONSTANTS,
  calculateCurvedPath,
  pathToKeyframes,
  springTransition,
} from '@/lib/animations';

interface BettingChipsProps {
  amount: number;
  position: { x: number; y: number };  // 고정 픽셀 좌표
  isAnimating?: boolean;
  animateTo?: { x: number; y: number };  // 고정 픽셀 좌표
  onAnimationEnd?: () => void;
  /** 새 베팅 애니메이션 활성화 */
  showBetAnimation?: boolean;
  /** 베팅 시작 위치 (픽셀) */
  betStartPosition?: { x: number; y: number };
  /** 금액 라벨 숨기기 (중앙 POT용) */
  hideLabel?: boolean;
}

// 칩 색상 결정 (금액에 따라)
const getChipColor = (amt: number) => {
  if (amt >= 1000) return { bg: '#8B5CF6', border: '#A78BFA' }; // purple
  if (amt >= 500) return { bg: '#3B82F6', border: '#60A5FA' }; // blue
  if (amt >= 100) return { bg: '#22C55E', border: '#4ADE80' }; // green
  if (amt >= 25) return { bg: '#EF4444', border: '#F87171' }; // red
  return { bg: '#9CA3AF', border: '#D1D5DB' }; // gray
};

// 칩 개수 계산 (최대 5개)
const getChipCount = (amount: number) => Math.min(Math.ceil(amount / 100), 5);

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
 * 베팅 칩 컴포넌트 (Framer Motion 버전)
 * - 정적 칩 스택 표시
 * - 베팅 시 곡선 경로 애니메이션
 * - Floating Number 효과
 */
export function BettingChips({
  amount,
  position,
  isAnimating = false,
  animateTo,
  onAnimationEnd,
  showBetAnimation = false,
  betStartPosition,
  hideLabel = false,
}: BettingChipsProps) {
  const [showFloatingNumber, setShowFloatingNumber] = useState(false);
  const [animationComplete, setAnimationComplete] = useState(false);

  const chipCount = getChipCount(amount);
  const chipColor = getChipColor(amount);

  // 애니메이션 완료 처리
  const handleAnimationComplete = useCallback(() => {
    setAnimationComplete(true);
    onAnimationEnd?.();
  }, [onAnimationEnd]);

  // 첫 칩 도착 시 floating number 표시
  const handleFirstChipArrived = useCallback(() => {
    setShowFloatingNumber(true);
  }, []);

  // 애니메이션 상태 리셋 - 렌더링 중 처리
  const [lastBetState, setLastBetState] = useState({ showBetAnimation, amount });
  if (showBetAnimation !== lastBetState.showBetAnimation || amount !== lastBetState.amount) {
    setLastBetState({ showBetAnimation, amount });
    if (showBetAnimation && (animationComplete || showFloatingNumber)) {
      setAnimationComplete(false);
      setShowFloatingNumber(false);
    }
  }

  if (amount <= 0) return null;

  // 베팅 애니메이션 모드
  if (showBetAnimation && betStartPosition && !animationComplete) {
    // 고정 픽셀 좌표 직접 사용
    const path = calculateCurvedPath(
      betStartPosition,
      { x: position.x, y: position.y },
      { curvature: 0.25, direction: 'up' }
    );
    const keyframes = pathToKeyframes(path);

    return (
      <div className="absolute inset-0 pointer-events-none z-50">
        <AnimatePresence>
          {/* 애니메이션 칩들 */}
          {Array.from({ length: chipCount }).map((_, index) => (
            <motion.div
              key={`bet-chip-${index}`}
              className="absolute"
              style={{
                left: betStartPosition.x,
                top: betStartPosition.y,
              }}
              variants={staggeredChip}
              initial="initial"
              animate={{
                x: keyframes.x.map(x => x - betStartPosition.x),
                y: keyframes.y.map(y => y - betStartPosition.y),
                opacity: 1,
                scale: 1,
              }}
              transition={{
                duration: CHIP_CONSTANTS.MOVE_DURATION / 1000,
                delay: index * (CHIP_CONSTANTS.STAGGER_DELAY / 1000),
                ease: [0.25, 0.1, 0.25, 1],
              }}
              onAnimationComplete={() => {
                if (index === 0) handleFirstChipArrived();
                if (index === chipCount - 1) handleAnimationComplete();
              }}
            >
              <div
                className="w-8 h-3 rounded-full shadow-md"
                style={{
                  background: `linear-gradient(135deg, ${chipColor.bg} 0%, ${chipColor.border} 100%)`,
                  border: `2px solid ${chipColor.border}`,
                }}
              />
            </motion.div>
          ))}

          {/* Floating Number */}
          {showFloatingNumber && (
            <motion.div
              className="absolute text-xl font-bold text-yellow-400 drop-shadow-lg"
              style={{
                left: position.x,
                top: position.y,
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

  // 팟 이동 애니메이션 모드 (곡선 경로)
  if (isAnimating && animateTo) {
    const path = calculateCurvedPath(
      position,
      animateTo,
      { curvature: 0.3, direction: 'up' }
    );
    const keyframes = pathToKeyframes(path);

    return (
      <div className="absolute inset-0 pointer-events-none z-50">
        <AnimatePresence>
          {Array.from({ length: chipCount }).map((_, index) => (
            <motion.div
              key={`collect-chip-${index}`}
              className="absolute -translate-x-1/2 -translate-y-1/2"
              style={{
                left: position.x,
                top: position.y,
              }}
              initial={{ opacity: 1, scale: 1 }}
              animate={{
                x: keyframes.x.map(x => x - position.x),
                y: keyframes.y.map(y => y - position.y),
                opacity: 1,
                scale: [1, 1, 0.9, 0.8],
              }}
              transition={{
                duration: 0.5,
                delay: index * 0.03,
                ease: [0.4, 0, 0.2, 1],
              }}
              onAnimationComplete={() => {
                if (index === chipCount - 1) handleAnimationComplete();
              }}
            >
              <div
                className="w-8 h-3 rounded-full shadow-md"
                style={{
                  background: `linear-gradient(135deg, ${chipColor.bg} 0%, ${chipColor.border} 100%)`,
                  border: `2px solid ${chipColor.border}`,
                }}
              />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    );
  }

  // 정적 칩 스택 표시
  return (
    <motion.div
      className="absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center z-30"
      style={{ top: position.y, left: position.x }}
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={springTransition}
    >
      <ChipStack chipCount={chipCount} chipColor={chipColor} />
      {!hideLabel && <AmountLabel amount={amount} />}
    </motion.div>
  );
}

// 칩 스택 컴포넌트
function ChipStack({ 
  chipCount, 
  chipColor 
}: { 
  chipCount: number; 
  chipColor: { bg: string; border: string };
}) {
  return (
    <div className="relative flex flex-col-reverse items-center">
      {Array.from({ length: chipCount }).map((_, i) => (
        <motion.div
          key={i}
          className="w-8 h-3 rounded-full shadow-md"
          style={{
            marginTop: i > 0 ? '-6px' : '0',
            background: `linear-gradient(135deg, ${chipColor.bg} 0%, ${chipColor.border} 100%)`,
            border: `2px solid ${chipColor.border}`,
          }}
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: i * 0.05 }}
        />
      ))}
    </div>
  );
}

// 금액 라벨 컴포넌트
function AmountLabel({ amount }: { amount: number }) {
  return (
    <motion.div 
      className="mt-1 px-2 py-0.5 bg-black/80 rounded text-white text-[10px] font-bold whitespace-nowrap"
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
    >
      {amount.toLocaleString()}
    </motion.div>
  );
}
