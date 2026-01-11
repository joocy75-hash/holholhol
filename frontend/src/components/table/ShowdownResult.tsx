import { memo, useEffect, useState } from 'react';
import { Trophy } from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import { PlayingCard } from '@/components/common/PlayingCard';
import { Avatar } from '@/components/common/Avatar';
import type { ShowdownResult as ShowdownResultType } from '@/types/game';
import { formatDollars } from '@/lib/utils/currencyFormatter';
import { HAND_RANK_NAMES } from '@/types/game';

interface ShowdownResultProps {
  result: ShowdownResultType;
  nextHandDelay: number;
  onClose: () => void;
}

export const ShowdownResult = memo(function ShowdownResult({
  result,
  nextHandDelay,
  onClose,
}: ShowdownResultProps) {
  const [countdown, setCountdown] = useState(Math.ceil(nextHandDelay / 1000));

  useEffect(() => {
    const interval = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          onClose();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [nextHandDelay, onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 animate-fade-in">
      <div className="bg-surface rounded-modal shadow-modal p-6 max-w-lg w-full mx-4">
        {/* Header */}
        <div className="flex items-center justify-center gap-2 mb-6">
          <Trophy className="w-8 h-8 text-yellow-500" />
          <h2 className="text-2xl font-bold text-text">결과</h2>
        </div>

        {/* Winners */}
        <div className="space-y-4 mb-6">
          {result.winners.map((winner, index) => (
            <div
              key={index}
              className={cn(
                'p-4 rounded-lg',
                'bg-gradient-to-r from-yellow-500/20 to-yellow-500/5',
                'border border-yellow-500/50'
              )}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="relative">
                    <Avatar name={winner.nickname} size="md" />
                    <Trophy className="absolute -top-1 -right-1 w-5 h-5 text-yellow-500" />
                  </div>
                  <div>
                    <p className="font-semibold text-text">{winner.nickname}</p>
                    <p className="text-sm text-yellow-500 font-medium">
                      {HAND_RANK_NAMES[winner.handRank] || winner.handName}
                    </p>
                  </div>
                </div>
                <p className="text-xl font-bold text-success">
                  +{formatDollars(winner.winAmount)}
                </p>
              </div>

              {/* Winner's cards */}
              <div className="flex justify-center gap-2">
                <PlayingCard card={winner.holeCards[0]} size="sm" highlighted />
                <PlayingCard card={winner.holeCards[1]} size="sm" highlighted />
              </div>
            </div>
          ))}
        </div>

        {/* Losers */}
        {result.losers.length > 0 && (
          <div className="space-y-2 mb-6">
            <h3 className="text-sm font-medium text-text-muted">다른 플레이어</h3>
            <div className="grid grid-cols-2 gap-2">
              {result.losers.map((loser, index) => (
                <div key={index} className="p-2 rounded bg-surface-light/50">
                  <div className="flex items-center gap-2 mb-2">
                    <Avatar name={loser.nickname} size="sm" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-text truncate">
                        {loser.nickname}
                      </p>
                      <p className="text-xs text-text-muted">
                        {HAND_RANK_NAMES[loser.handRank] || loser.handName}
                      </p>
                    </div>
                  </div>
                  <div className="flex justify-center gap-1">
                    <PlayingCard card={loser.holeCards[0]} size="sm" disabled />
                    <PlayingCard card={loser.holeCards[1]} size="sm" disabled />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Countdown */}
        <div className="text-center">
          <p className="text-text-muted">
            다음 핸드까지 <span className="font-bold text-primary">{countdown}</span>초
          </p>
        </div>
      </div>
    </div>
  );
});
