import { memo } from 'react';
import { cn } from '@/lib/utils/cn';
import { Avatar } from '@/components/common/Avatar';
import { PlayingCard } from '@/components/common/PlayingCard';
import type { SeatState, Card } from '@/types/game';
import { formatDollars } from '@/lib/utils/currencyFormatter';

interface SeatProps {
  seat: SeatState | null;
  position: number; // used for seat identification
  isMe: boolean;
  showHoleCards?: boolean;
  holeCards?: [Card, Card] | null;
  onClick?: () => void;
}

const statusDisplay: Record<string, { text: string; className: string }> = {
  folded: { text: 'FOLD', className: 'bg-surface/80 text-text-muted' },
  all_in: { text: 'ALL-IN', className: 'bg-danger text-white font-bold' },
  sitting_out: { text: '자리비움', className: 'bg-surface/80 text-text-muted' },
  disconnected: { text: '연결 끊김', className: 'bg-surface/80 text-danger border border-dashed' },
};

export const Seat = memo(function Seat({
  seat,
  position: _position, // Reserved for future use (e.g., positioning)
  isMe,
  showHoleCards = false,
  holeCards,
  onClick,
}: SeatProps) {
  // Empty seat
  if (!seat?.player) {
    return (
      <button
        onClick={onClick}
        className={cn(
          'w-24 h-28 rounded-lg border-2 border-dashed border-surface-light',
          'flex flex-col items-center justify-center gap-2',
          'hover:border-primary hover:bg-surface/30 transition-all',
          'text-text-muted hover:text-text'
        )}
      >
        <span className="text-2xl">+</span>
        <span className="text-xs">착석하기</span>
      </button>
    );
  }

  const { player, stack, betAmount, status, isCurrentTurn, isDealer, lastAction } = seat;
  const statusInfo = status !== 'active' ? statusDisplay[status] : null;

  return (
    <div
      className={cn(
        'relative w-28 rounded-lg transition-all',
        isCurrentTurn && 'ring-2 ring-warning ring-offset-2 ring-offset-felt',
        isMe && 'ring-2 ring-primary'
      )}
    >
      {/* Dealer button */}
      {isDealer && (
        <div className="absolute -top-2 -right-2 w-6 h-6 bg-white rounded-full flex items-center justify-center text-xs font-bold text-felt shadow-chip z-10">
          D
        </div>
      )}

      {/* Main seat card */}
      <div
        className={cn(
          'bg-surface/90 backdrop-blur rounded-lg p-2',
          statusInfo && 'opacity-70'
        )}
      >
        {/* Avatar and name */}
        <div className="flex items-center gap-2 mb-2">
          <Avatar
            name={player.nickname}
            src={player.avatarUrl}
            size="sm"
            status={status === 'disconnected' ? 'offline' : undefined}
          />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-text truncate">
              {player.nickname}
              {isMe && <span className="text-primary ml-1">★</span>}
            </p>
            <p className="text-xs text-success font-medium">{formatDollars(stack)}</p>
          </div>
        </div>

        {/* Status overlay */}
        {statusInfo && (
          <div
            className={cn(
              'absolute inset-0 rounded-lg flex items-center justify-center',
              statusInfo.className
            )}
          >
            <span className="text-sm">{statusInfo.text}</span>
          </div>
        )}

        {/* Hole cards - show for me or during showdown */}
        {(isMe || showHoleCards) && holeCards && status === 'active' && (
          <div className="flex justify-center gap-1 mt-2">
            <PlayingCard card={holeCards[0]} size="sm" />
            <PlayingCard card={holeCards[1]} size="sm" />
          </div>
        )}

        {/* Hidden cards for opponents */}
        {!isMe && !showHoleCards && status === 'active' && (
          <div className="flex justify-center gap-1 mt-2">
            <PlayingCard card={null} size="sm" />
            <PlayingCard card={null} size="sm" />
          </div>
        )}

        {/* Last action badge */}
        {lastAction && (
          <div className="absolute -bottom-3 left-1/2 -translate-x-1/2 px-2 py-0.5 bg-primary rounded text-xs text-white font-medium">
            {lastAction.type.toUpperCase()}
            {lastAction.amount !== undefined && ` ${formatDollars(lastAction.amount)}`}
          </div>
        )}
      </div>

      {/* Bet amount */}
      {betAmount > 0 && (
        <div className="absolute -bottom-8 left-1/2 -translate-x-1/2">
          <div className="flex items-center gap-1 px-2 py-1 bg-surface rounded-full">
            <div className="w-4 h-4 rounded-full bg-gradient-to-br from-red-500 to-red-700 shadow-chip" />
            <span className="text-xs font-medium text-text">{formatDollars(betAmount)}</span>
          </div>
        </div>
      )}
    </div>
  );
});
