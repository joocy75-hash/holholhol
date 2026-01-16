'use client';

import { useState, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  easeInTransition,
  pulse,
  generateScatteredPositions,
  calculateCurvedPath,
  pathToKeyframes,
  Point,
  WINNER_CONSTANTS,
} from '@/lib/animations';

interface Winner {
  position: number;
  amount: number;
  seatPosition: Point;
}

interface PotCollectionProps {
  /** 총 팟 금액 */
  potAmount: number;
  /** 테이블 중앙 위치 */
  tableCenter: Point;
  /** 승자 정보 (복수 가능 - split pot) */
  winners: Winner[];
  /** 애니메이션 시작 트리거 */
  isAnimating: boolean;
  /** 애니메이션 완료 콜백 */
  onAnimationComplete?: () => void;
  /** 칩 수거 완료 콜백 */
  onChipsGathered?: () => void;
}

// 칩 색상
const CHIP_COLORS = [
  { bg: '#FFD700', border: '#B8860B' }, // gold
  { bg: '#8B5CF6', border: '#6D28D9' }, // purple
  { bg: '#3B82F6', border: '#1D4ED8' }, // blue
  { bg: '#22C55E', border: '#15803D' }, // green
  { bg: '#EF4444', border: '#B91C1C' }, // red
];

// 금액에 따른 칩 개수
function getChipCount(amount: number): number {
  if (amount >= 10000) return 8;
  if (amount >= 5000) return 6;
  if (amount >= 1000) return 4;
  return 3;
}

type AnimationPhase = 'idle' | 'gathering' | 'moving' | 'complete';

/**
 * 팟 수거 및 승자 이동 애니메이션 컴포넌트
 * - 흩어진 칩들 → 중앙 집결 (staggered)
 * - 중앙 → 승자 좌석 이동 (Ease-In 가속)
 * - Split pot 지원 (여러 승자)
 * - 2초 내 전체 시퀀스 완료
 */
export default function PotCollection({
  potAmount,
  tableCenter,
  winners,
  isAnimating,
  onAnimationComplete,
  onChipsGathered,
}: PotCollectionProps) {
  const [phase, setPhase] = useState<AnimationPhase>('idle');

  const chipCount = getChipCount(potAmount);
  
  // 흩어진 칩 위치 생성
  const scatteredPositions = useMemo(
    () => generateScatteredPositions(tableCenter, chipCount, 50),
    [tableCenter, chipCount]
  );

  // 각 승자별 칩 분배 계산
  const chipsPerWinner = useMemo(() => {
    if (winners.length === 0) return [];
    const perWinner = Math.floor(chipCount / winners.length);
    return winners.map((_, i) => 
      i === winners.length - 1 
        ? chipCount - perWinner * (winners.length - 1) 
        : perWinner
    );
  }, [chipCount, winners]);

  // 애니메이션 시작 감지
  const [lastIsAnimating, setLastIsAnimating] = useState(isAnimating);
  if (isAnimating !== lastIsAnimating) {
    setLastIsAnimating(isAnimating);
    if (isAnimating) {
      setPhase('gathering');
    } else {
      setPhase('idle');
    }
  }

  // 수거 완료 처리
  const handleGatherComplete = useCallback(() => {
    setPhase('moving');
    onChipsGathered?.();
  }, [onChipsGathered]);

  // 이동 완료 처리
  const handleMoveComplete = useCallback(() => {
    setPhase('complete');
    onAnimationComplete?.();
  }, [onAnimationComplete]);

  if (!isAnimating && phase === 'idle') return null;

  return (
    <div className="absolute inset-0 pointer-events-none z-50">
      <AnimatePresence mode="wait">
        {/* Phase 1: 흩어진 칩들이 중앙으로 모임 */}
        {phase === 'gathering' && (
          <GatheringChips
            key="gathering"
            scatteredPositions={scatteredPositions}
            tableCenter={tableCenter}
            chipCount={chipCount}
            onComplete={handleGatherComplete}
          />
        )}

        {/* Phase 2: 중앙에서 승자들에게 이동 */}
        {phase === 'moving' && winners.length > 0 && (
          <MovingToWinners
            key="moving"
            tableCenter={tableCenter}
            winners={winners}
            chipsPerWinner={chipsPerWinner}
            potAmount={potAmount}
            onComplete={handleMoveComplete}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

// 칩 수거 애니메이션
function GatheringChips({
  scatteredPositions,
  tableCenter,
  chipCount,
  onComplete,
}: {
  scatteredPositions: Point[];
  tableCenter: Point;
  chipCount: number;
  onComplete: () => void;
}) {
  const [completedCount, setCompletedCount] = useState(0);

  const handleChipComplete = useCallback(() => {
    setCompletedCount(prev => {
      const next = prev + 1;
      if (next >= chipCount) {
        setTimeout(onComplete, 100);
      }
      return next;
    });
  }, [chipCount, onComplete]);

  // completedCount is used for tracking animation progress
  void completedCount;

  return (
    <>
      {scatteredPositions.map((pos, index) => {
        const color = CHIP_COLORS[index % CHIP_COLORS.length];
        return (
          <motion.div
            key={`gather-${index}`}
            className="absolute w-8 h-8"
            initial={{ 
              x: pos.x - 16, 
              y: pos.y - 16,
              scale: 1,
              opacity: 1,
            }}
            animate={{ 
              x: tableCenter.x - 16, 
              y: tableCenter.y - 16,
              scale: 0.8,
            }}
            transition={{
              duration: 0.4,
              delay: index * 0.03, // 바깥쪽부터 순차적
              ease: 'easeOut',
            }}
            onAnimationComplete={handleChipComplete}
          >
            <div
              className="w-full h-full rounded-full shadow-lg"
              style={{
                background: `linear-gradient(135deg, ${color.bg} 0%, ${color.border} 100%)`,
                border: `2px solid ${color.border}`,
              }}
            />
          </motion.div>
        );
      })}
    </>
  );
}

// 승자에게 이동 애니메이션
function MovingToWinners({
  tableCenter,
  winners,
  chipsPerWinner,
  onComplete,
}: {
  tableCenter: Point;
  winners: Winner[];
  chipsPerWinner: number[];
  potAmount: number;
  onComplete: () => void;
}) {
  const [completedWinners, setCompletedWinners] = useState(0);

  // completedWinners is used for tracking animation progress
  void completedWinners;

  const handleWinnerComplete = useCallback(() => {
    setCompletedWinners(prev => {
      const next = prev + 1;
      if (next >= winners.length) {
        setTimeout(onComplete, 100);
      }
      return next;
    });
  }, [winners.length, onComplete]);

  return (
    <>
      {winners.map((winner, winnerIndex) => {
        const path = calculateCurvedPath(tableCenter, winner.seatPosition, {
          curvature: 0.2,
          direction: 'up',
        });
        const keyframes = pathToKeyframes(path);
        const chipCount = chipsPerWinner[winnerIndex];

        return (
          <WinnerChipGroup
            key={`winner-${winnerIndex}`}
            tableCenter={tableCenter}
            winnerPosition={winner.seatPosition}
            keyframes={keyframes}
            chipCount={chipCount}
            winnerAmount={winner.amount}
            delay={winnerIndex * 0.2}
            onComplete={winnerIndex === winners.length - 1 ? handleWinnerComplete : undefined}
          />
        );
      })}
    </>
  );
}

// 개별 승자 칩 그룹
function WinnerChipGroup({
  tableCenter,
  winnerPosition,
  keyframes,
  chipCount,
  winnerAmount,
  delay,
  onComplete,
}: {
  tableCenter: Point;
  winnerPosition: Point;
  keyframes: { x: number[]; y: number[] };
  chipCount: number;
  winnerAmount: number;
  delay: number;
  onComplete?: () => void;
}) {
  const [showPulse, setShowPulse] = useState(false);
  const [completedChips, setCompletedChips] = useState(0);

  // completedChips is used for tracking animation progress
  void completedChips;

  const handleChipComplete = useCallback(() => {
    setCompletedChips(prev => {
      const next = prev + 1;
      if (next >= chipCount) {
        setShowPulse(true);
        onComplete?.();
      }
      return next;
    });
  }, [chipCount, onComplete]);

  return (
    <>
      {/* 칩들 */}
      {Array.from({ length: chipCount }).map((_, index) => {
        const color = CHIP_COLORS[index % CHIP_COLORS.length];
        return (
          <motion.div
            key={`move-${index}`}
            className="absolute w-8 h-8"
            initial={{ 
              x: tableCenter.x - 16, 
              y: tableCenter.y - 16,
              scale: 0.8,
            }}
            animate={{
              x: keyframes.x.map(x => x - 16),
              y: keyframes.y.map(y => y - 16),
              scale: 1,
            }}
            transition={{
              ...easeInTransition,
              duration: WINNER_CONSTANTS.POT_MOVE_DURATION / 1000,
              delay: delay + index * 0.02,
            }}
            onAnimationComplete={handleChipComplete}
          >
            <div
              className="w-full h-full rounded-full shadow-lg"
              style={{
                background: `linear-gradient(135deg, ${color.bg} 0%, ${color.border} 100%)`,
                border: `2px solid ${color.border}`,
              }}
            />
          </motion.div>
        );
      })}

      {/* 승자 위치 펄스 효과 */}
      {showPulse && (
        <motion.div
          className="absolute w-16 h-16 rounded-full"
          style={{
            left: winnerPosition.x - 32,
            top: winnerPosition.y - 32,
            background: 'radial-gradient(circle, rgba(255,215,0,0.5) 0%, transparent 70%)',
          }}
          variants={pulse}
          initial="initial"
          animate="pulse"
        />
      )}

      {/* 금액 표시 */}
      {showPulse && (
        <motion.div
          className="absolute text-lg font-bold text-yellow-400 drop-shadow-lg"
          style={{
            left: winnerPosition.x,
            top: winnerPosition.y - 40,
            transform: 'translateX(-50%)',
          }}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          +{winnerAmount.toLocaleString()}
        </motion.div>
      )}
    </>
  );
}
