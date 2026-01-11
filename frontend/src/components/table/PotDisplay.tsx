import { memo } from 'react';
import { formatDollars } from '@/lib/utils/currencyFormatter';

interface SidePot {
  amount: number;
  eligiblePositions: number[];
}

interface PotDisplayProps {
  mainPot: number;
  sidePots?: SidePot[];
}

export const PotDisplay = memo(function PotDisplay({ mainPot, sidePots = [] }: PotDisplayProps) {
  const totalPot = mainPot + sidePots.reduce((sum, pot) => sum + pot.amount, 0);

  return (
    <div className="flex flex-col items-center gap-2">
      {/* Main pot */}
      <div className="flex items-center gap-2 px-4 py-2 bg-surface/80 backdrop-blur rounded-full">
        {/* Chip stack visual */}
        <div className="relative w-8 h-8">
          <div className="absolute bottom-0 left-0 w-6 h-6 rounded-full bg-gradient-to-br from-red-500 to-red-700 shadow-chip" />
          <div className="absolute bottom-1 left-1 w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 shadow-chip" />
          <div className="absolute bottom-2 left-2 w-6 h-6 rounded-full bg-gradient-to-br from-green-500 to-green-700 shadow-chip" />
        </div>

        <div className="text-center">
          <p className="text-xs text-text-muted">팟</p>
          <p className="text-lg font-bold text-text">{formatDollars(totalPot)}</p>
        </div>
      </div>

      {/* Side pots */}
      {sidePots.length > 0 && (
        <div className="flex gap-2">
          {sidePots.map((pot, index) => (
            <div
              key={index}
              className="px-2 py-1 bg-surface/60 rounded text-xs"
              title={`참가자: ${pot.eligiblePositions.length}명`}
            >
              <span className="text-text-muted">사이드팟 {index + 1}:</span>{' '}
              <span className="font-medium text-text">{formatDollars(pot.amount)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
});
