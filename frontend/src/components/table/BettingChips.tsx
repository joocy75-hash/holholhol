'use client';

import { useState, useCallback, useMemo, memo, useLayoutEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { floatingNumber, CHIP_CONSTANTS } from '@/lib/animations';

interface BettingChipsProps {
  amount: number;
  position: { x: number; y: number };
  isAnimating?: boolean;
  animateTo?: { x: number; y: number };
  onAnimationEnd?: () => void;
  showBetAnimation?: boolean;
  betStartPosition?: { x: number; y: number };
  hideLabel?: boolean;
}

// 칩 이미지 경로 (색상별 개별 파일 - CSS 필터 제거로 성능 향상)
const CHIP_IMAGES = {
  purple: '/assets/chips/bluechip.svg',   // 1000단위
  green: '/assets/chips/greenchip.svg',   // 100단위
  red: '/assets/chips/chip_stack.svg',    // 10단위
} as const;

// 칩 이미지 크기
const CHIP_WIDTH = 16;
const CHIP_HEIGHT = 10;
const CHIP_V_OVERLAP = 7; // 세로 겹침
const CHIP_H_GAP = 1; // 가로 간격

// 칩 스택 타입
interface ChipStackData {
  src: string;
  count: number;
}

// 칩 배치 모드
type ChipMode = 'single' | 'double' | 'triple';

// 칩 스택 계산 (메모이제이션용 순수 함수)
function calculateChipStacks(amount: number): { stacks: ChipStackData[]; mode: ChipMode } {
  const stacks: ChipStackData[] = [];
  let remaining = amount;

  if (remaining >= 1000) {
    const count = Math.min(Math.floor(remaining / 1000), 5);
    stacks.push({ src: CHIP_IMAGES.purple, count });
    remaining -= count * 1000;
  }

  if (remaining >= 100) {
    const count = Math.min(Math.floor(remaining / 100), 5);
    stacks.push({ src: CHIP_IMAGES.green, count });
    remaining -= count * 100;
  }

  if (remaining > 0 || stacks.length === 0) {
    const count = Math.min(Math.max(Math.ceil(remaining / 10), 1), 5);
    stacks.push({ src: CHIP_IMAGES.red, count });
  }

  const mode: ChipMode =
    stacks.length === 1 ? 'single' :
    stacks.length === 2 ? 'double' : 'triple';

  return { stacks: stacks.slice(0, 3), mode };
}

// 금액 포맷팅
function formatAmount(amount: number): string {
  if (amount >= 10000) return `+${(amount / 10000).toFixed(1)}만`;
  if (amount >= 1000) return `+${(amount / 1000).toFixed(1)}천`;
  return `+${amount.toLocaleString()}`;
}

// 단일 칩 이미지 (CSS 필터 없음 - 성능 최적화)
const ChipImage = memo(function ChipImage({ src }: { src: string }) {
  return (
    <img
      src={src}
      alt=""
      width={CHIP_WIDTH}
      height={CHIP_HEIGHT}
    />
  );
});

// 세로 스택 (위로 쌓임, 위 칩이 앞에 보임)
const VerticalStack = memo(function VerticalStack({ stack }: { stack: ChipStackData }) {
  return (
    <div className="flex flex-col items-center">
      {Array.from({ length: stack.count }, (_, i) => (
        <div
          key={i}
          style={{
            marginTop: i > 0 ? -CHIP_V_OVERLAP : 0,
            zIndex: stack.count - i,  // 위 칩일수록 높은 z-index
          }}
        >
          <ChipImage src={stack.src} />
        </div>
      ))}
    </div>
  );
});

// 정적 칩 스택 (애니메이션 없음)
const StaticChipStack = memo(function StaticChipStack({
  stacks,
  mode
}: {
  stacks: ChipStackData[];
  mode: ChipMode
}) {
  if (mode === 'single') {
    return <VerticalStack stack={stacks[0]} />;
  }

  if (mode === 'double') {
    return (
      <div className="flex gap-1 items-end">
        {stacks.map((stack, i) => (
          <VerticalStack key={i} stack={stack} />
        ))}
      </div>
    );
  }

  // triple: 뒤 1줄 + 앞 2줄
  const backRow = stacks[0];
  const frontRows = stacks.slice(1);

  return (
    <div className="relative flex flex-col items-center">
      <div className="flex z-10">
        {Array.from({ length: backRow.count }, (_, i) => (
          <div key={i} style={{ marginLeft: i > 0 ? CHIP_H_GAP : 0 }}>
            <ChipImage src={backRow.src} />
          </div>
        ))}
      </div>
      <div className="flex gap-1 z-20" style={{ marginTop: -4 }}>
        {frontRows.map((stack, stackIndex) => (
          <div key={stackIndex} className="flex">
            {Array.from({ length: stack.count }, (_, i) => (
              <div key={i} style={{ marginLeft: i > 0 ? CHIP_H_GAP : 0 }}>
                <ChipImage src={stack.src} />
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
});

// 금액 라벨
const AmountLabel = memo(function AmountLabel({ amount }: { amount: number }) {
  return (
    <div className="mt-1 px-2 py-0.5 bg-black/80 rounded text-white text-[10px] font-bold whitespace-nowrap">
      {amount.toLocaleString()}
    </div>
  );
});

/**
 * 베팅 칩 컴포넌트 (최적화 버전)
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

  // 칩 스택 계산 메모이제이션
  const { stacks, mode } = useMemo(() => calculateChipStacks(amount), [amount]);

  const handleAnimationComplete = useCallback(() => {
    setAnimationComplete(true);
    onAnimationEnd?.();
  }, [onAnimationEnd]);

  const handleFirstChipArrived = useCallback(() => {
    setShowFloatingNumber(true);
  }, []);

  // 이전 상태 추적 (렌더링 중 상태 변경 방지)
  const prevBetStateRef = useRef({ showBetAnimation, amount });

  // 상태 리셋 - useLayoutEffect로 DOM 커밋 전에 동기적으로 실행
  // 새 베팅 애니메이션 시작 시 이전 애니메이션 상태를 즉시 리셋
  // 의도적 state 리셋: 새 베팅 시작 시 이전 애니메이션 상태 초기화 필요
  /* eslint-disable react-hooks/set-state-in-effect */
  useLayoutEffect(() => {
    const prevState = prevBetStateRef.current;
    const hasChanged = showBetAnimation !== prevState.showBetAnimation || amount !== prevState.amount;

    if (hasChanged) {
      prevBetStateRef.current = { showBetAnimation, amount };
      // 새 베팅 애니메이션 시작 시에만 상태 리셋
      if (showBetAnimation && (animationComplete || showFloatingNumber)) {
        setAnimationComplete(false);
        setShowFloatingNumber(false);
      }
    }
  }, [showBetAnimation, amount, animationComplete, showFloatingNumber]);
  /* eslint-enable react-hooks/set-state-in-effect */

  if (amount <= 0) return null;

  // 베팅 애니메이션 모드 (단순 직선 이동)
  if (showBetAnimation && betStartPosition && !animationComplete) {
    return (
      <div className="absolute inset-0 pointer-events-none z-50">
        <AnimatePresence>
          <motion.div
            key="bet-chip"
            className="absolute -translate-x-1/2 -translate-y-1/2"
            style={{ left: betStartPosition.x, top: betStartPosition.y }}
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{
              x: position.x - betStartPosition.x,
              y: position.y - betStartPosition.y,
              opacity: 1,
              scale: 1,
            }}
            transition={{
              duration: CHIP_CONSTANTS.MOVE_DURATION / 1000,
              ease: 'easeOut',
            }}
            onAnimationComplete={() => {
              handleFirstChipArrived();
              handleAnimationComplete();
            }}
          >
            <StaticChipStack stacks={stacks} mode={mode} />
          </motion.div>

          {showFloatingNumber && (
            <motion.div
              className="absolute text-xl font-bold text-yellow-400 drop-shadow-lg"
              style={{ left: position.x, top: position.y, transform: 'translate(-50%, -50%)' }}
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

  // 팟 이동 애니메이션 모드 (단순 직선 이동)
  if (isAnimating && animateTo) {
    return (
      <div className="absolute inset-0 pointer-events-none z-50">
        <motion.div
          className="absolute -translate-x-1/2 -translate-y-1/2"
          style={{ left: position.x, top: position.y }}
          initial={{ opacity: 1, scale: 1 }}
          animate={{
            x: animateTo.x - position.x,
            y: animateTo.y - position.y,
            scale: [1, 1, 0.9, 0.8],
            opacity: [1, 1, 1, 0],
          }}
          transition={{ duration: 0.4, ease: 'linear' }}
          onAnimationComplete={handleAnimationComplete}
        >
          <StaticChipStack stacks={stacks} mode={mode} />
        </motion.div>
      </div>
    );
  }

  // 정적 표시 (애니메이션 없음 - 가장 빠름)
  return (
    <div
      className="absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center z-30"
      style={{ top: position.y, left: position.x }}
    >
      <StaticChipStack stacks={stacks} mode={mode} />
      {!hideLabel && <AmountLabel amount={amount} />}
    </div>
  );
}
