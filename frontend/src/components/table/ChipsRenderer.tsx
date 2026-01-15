'use client';

import { BettingChips } from './BettingChips';
import { CHIP_POSITIONS, POT_POSITION, SEAT_POSITIONS } from './PlayerSeat';
import type { SeatInfo } from '@/hooks/table/useGameState';

interface ChipsRendererProps {
  seats: SeatInfo[];
  myPosition: number | null;
  collectingChips: { position: number; amount: number }[];
  isCollectingToPot: boolean;
  potChips: number;
  distributingChip: { amount: number; toPosition: number } | null;
  onDistributingComplete: () => void;
}

export function ChipsRenderer({
  seats,
  myPosition,
  collectingChips,
  isCollectingToPot,
  potChips,
  distributingChip,
  onDistributingComplete,
}: ChipsRendererProps) {
  const getRelativePosition = (position: number) => {
    if (myPosition === null) return position;
    return (position - myPosition + SEAT_POSITIONS.length) % SEAT_POSITIONS.length;
  };

  return (
    <>
      {/* 베팅 칩 */}
      {seats.map((seat) => {
        const visualPosition = getRelativePosition(seat.position);
        const isBeingCollected = collectingChips.some(c => c.position === seat.position);
        if (seat.betAmount > 0 && !isBeingCollected) {
          return (
            <BettingChips
              key={`chip-${seat.position}`}
              amount={seat.betAmount}
              position={CHIP_POSITIONS[visualPosition]}
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
          position={CHIP_POSITIONS[getRelativePosition(chip.position)]}
          isAnimating={isCollectingToPot}
          animateTo={POT_POSITION}
        />
      ))}

      {/* 중앙 POT 칩 */}
      {potChips > 0 && (
        <BettingChips amount={potChips} position={POT_POSITION} />
      )}

      {/* 분배 중인 칩 */}
      {distributingChip && (
        <BettingChips
          amount={distributingChip.amount}
          position={POT_POSITION}
          isAnimating={true}
          animateTo={CHIP_POSITIONS[getRelativePosition(distributingChip.toPosition)]}
          onAnimationEnd={onDistributingComplete}
        />
      )}
    </>
  );
}
