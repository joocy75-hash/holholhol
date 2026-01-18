'use client';

import { useMemo } from 'react';
import { BettingChips } from './BettingChips';
import { MAX_SEATS, getTableConstants } from '@/constants/tableCoordinates';
import type { SeatInfo } from '@/hooks/table/useGameState';

interface ChipsRendererProps {
  maxSeats?: number;  // 6 또는 9 (기본값 9)
  seats: SeatInfo[];
  myPosition: number | null;
  collectingChips: { position: number; amount: number }[];
  isCollectingToPot: boolean;
  potChips: number;
  distributingChip: { amount: number; toPosition: number } | null;
  onDistributingComplete: () => void;
}

export function ChipsRenderer({
  maxSeats = MAX_SEATS,
  seats,
  myPosition,
  collectingChips,
  isCollectingToPot,
  potChips,
  distributingChip,
  onDistributingComplete,
}: ChipsRendererProps) {
  // 동적 좌표 선택 (6인 또는 9인)
  const tableConfig = useMemo(() => getTableConstants(maxSeats), [maxSeats]);

  // visualPosition 계산 (내 시점 기준 상대 위치)
  const getVisualPosition = (position: number) => {
    if (myPosition === null) return position;
    return (position - myPosition + maxSeats) % maxSeats;
  };

  return (
    <>
      {/* 베팅 칩 */}
      {seats.map((seat) => {
        const visualPosition = getVisualPosition(seat.position);
        const isBeingCollected = collectingChips.some(c => c.position === seat.position);
        if (seat.betAmount > 0 && !isBeingCollected) {
          return (
            <BettingChips
              key={`chip-${seat.position}`}
              amount={seat.betAmount}
              position={tableConfig.CHIPS[visualPosition]}
            />
          );
        }
        return null;
      })}

      {/* 수집 중인 칩 */}
      {collectingChips.map((chip, idx) => (
        <BettingChips
          key={`collecting-${idx}`}
          amount={chip.amount}
          position={tableConfig.CHIPS[getVisualPosition(chip.position)]}
          isAnimating={isCollectingToPot}
          animateTo={tableConfig.POT}
        />
      ))}

      {/* 중앙 POT 칩 - 검은 배경 숫자 라벨 없이 칩만 표시 */}
      {potChips > 0 && (
        <BettingChips
          amount={potChips}
          position={tableConfig.POT}
          hideLabel
        />
      )}

      {/* 분배 중인 칩 */}
      {distributingChip && (
        <BettingChips
          amount={distributingChip.amount}
          position={tableConfig.POT}
          isAnimating={true}
          animateTo={tableConfig.CHIPS[getVisualPosition(distributingChip.toPosition)]}
          onAnimationEnd={onDistributingComplete}
        />
      )}
    </>
  );
}
