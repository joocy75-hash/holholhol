'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

// 숫자 애니메이션 훅 - 증가할 때만 애니메이션 (감소 시 즉시 변경)
export function useAnimatedNumber(value: number, duration: number = 500) {
  // 첫 렌더링 시 value로 초기화
  const [displayValue, setDisplayValue] = useState(() => value);
  const previousValueRef = useRef(value);
  const animationRef = useRef<number | null>(null);
  const isFirstRenderRef = useRef(true);

  // 애니메이션 취소 함수
  const cancelAnimation = useCallback(() => {
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
    }
  }, []);

  useEffect(() => {
    // 첫 렌더링인 경우 애니메이션 없이 초기값 설정만 하고 끝
    if (isFirstRenderRef.current) {
      isFirstRenderRef.current = false;
      previousValueRef.current = value;
      return;
    }

    const startValue = previousValueRef.current;
    const endValue = value;
    const diff = endValue - startValue;

    // 이전 애니메이션 취소
    cancelAnimation();

    // 값이 같으면 아무것도 하지 않음
    if (diff === 0) {
      return;
    }

    // 감소할 때는 다음 프레임에 즉시 설정 (새 핸드 시작 시 pot이 0으로 리셋될 때)
    if (diff < 0) {
      animationRef.current = requestAnimationFrame(() => {
        setDisplayValue(value);
        previousValueRef.current = value;
        animationRef.current = null;
      });
      return cancelAnimation;
    }

    // 증가할 때만 애니메이션
    const startTime = performance.now();

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // easeOutQuart 이징 함수 - 빠르게 시작해서 천천히 끝남
      const easeProgress = 1 - Math.pow(1 - progress, 4);

      const currentValue = Math.round(startValue + diff * easeProgress);
      setDisplayValue(currentValue);

      if (progress < 1) {
        animationRef.current = requestAnimationFrame(animate);
      } else {
        setDisplayValue(endValue);
        previousValueRef.current = endValue;
        animationRef.current = null;
      }
    };

    animationRef.current = requestAnimationFrame(animate);

    return cancelAnimation;
  }, [value, duration, cancelAnimation]);

  return displayValue;
}

interface PotDisplayProps {
  pot: number;
  className?: string;
}

export function PotDisplay({ pot, className = '' }: PotDisplayProps) {
  const animatedPot = useAnimatedNumber(pot, 600);

  return (
    <div className={`text-center ${className}`} data-testid="pot-amount">
      <div className="text-white font-bold text-xl drop-shadow-lg tabular-nums">
        {animatedPot.toLocaleString()}
      </div>
    </div>
  );
}

interface SidePot {
  amount: number;
  eligiblePlayers: number[];
}

interface SidePotsDisplayProps {
  sidePots: SidePot[];
  className?: string;
}

export function SidePotsDisplay({ sidePots, className = '' }: SidePotsDisplayProps) {
  if (sidePots.length === 0) return null;

  return (
    <div className={`flex gap-2 ${className}`}>
      {sidePots.map((sidePot, index) => (
        <div
          key={index}
          className="px-2 py-1 bg-yellow-600/80 rounded text-xs text-white"
          data-testid={`side-pot-${index}`}
          data-amount={sidePot.amount}
          data-players={sidePot.eligiblePlayers.join(',')}
        >
          Side Pot {index + 1}: {sidePot.amount.toLocaleString()}
        </div>
      ))}
    </div>
  );
}

export type { SidePot };
