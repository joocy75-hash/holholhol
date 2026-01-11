import { memo } from 'react';
import { Seat } from './Seat';
import { CommunityCards } from './CommunityCards';
import { PotDisplay } from './PotDisplay';
import { useTableStore } from '@/stores/tableStore';

interface TableProps {
  onSeatClick: (position: number) => void;
}

// Seat positions for different table sizes (percentage-based positioning)
const SEAT_POSITIONS: Record<number, Array<{ left: string; top: string }>> = {
  2: [
    { left: '50%', top: '85%' }, // Bottom (me)
    { left: '50%', top: '15%' }, // Top
  ],
  6: [
    { left: '50%', top: '90%' },  // Bottom center (me)
    { left: '15%', top: '65%' },  // Bottom left
    { left: '15%', top: '35%' },  // Top left
    { left: '50%', top: '10%' },  // Top center
    { left: '85%', top: '35%' },  // Top right
    { left: '85%', top: '65%' },  // Bottom right
  ],
  9: [
    { left: '50%', top: '92%' },  // Bottom center (me)
    { left: '20%', top: '80%' },  // Bottom left
    { left: '5%', top: '55%' },   // Left
    { left: '20%', top: '20%' },  // Top left
    { left: '50%', top: '8%' },   // Top center
    { left: '80%', top: '20%' },  // Top right
    { left: '95%', top: '55%' },  // Right
    { left: '80%', top: '80%' },  // Bottom right
    { left: '50%', top: '92%' },  // Reserved (not used in 9-max usually)
  ],
};

export const Table = memo(function Table({ onSeatClick }: TableProps) {
  const {
    config,
    seats,
    phase,
    communityCards,
    pot,
    sidePots,
    myPosition,
    myHoleCards,
  } = useTableStore();

  const maxSeats = config?.maxSeats ?? 6;
  const positions = SEAT_POSITIONS[maxSeats] ?? SEAT_POSITIONS[6];
  const isShowdown = phase === 'showdown';

  return (
    <div className="relative w-full aspect-[16/9] max-w-4xl mx-auto">
      {/* Table felt */}
      <div className="absolute inset-[10%] table-felt shadow-lg">
        {/* Inner felt border */}
        <div className="absolute inset-4 rounded-[50%] border-2 border-felt-border/30" />

        {/* Center area */}
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
          {/* Community cards */}
          <CommunityCards
            cards={communityCards}
            phase={phase}
            winningCards={isShowdown ? communityCards : undefined}
          />

          {/* Pot display */}
          <PotDisplay mainPot={pot} sidePots={sidePots} />
        </div>
      </div>

      {/* Seats */}
      {positions.map((pos, index) => {
        const seat = seats.find((s) => s.position === index) ?? null;
        const isMe = index === myPosition;

        return (
          <div
            key={index}
            className="seat"
            style={{ left: pos.left, top: pos.top }}
          >
            <Seat
              seat={seat}
              position={index}
              isMe={isMe}
              showHoleCards={isShowdown}
              holeCards={isMe ? myHoleCards : seat?.holeCards}
              onClick={() => onSeatClick(index)}
            />
          </div>
        );
      })}
    </div>
  );
});
