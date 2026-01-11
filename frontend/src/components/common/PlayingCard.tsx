import { memo } from 'react';
import { cn } from '@/lib/utils/cn';
import type { Card } from '@/types/game';
import type { CardSize } from '@/types/ui';
import { SUIT_SYMBOLS, SUIT_COLORS, RANK_DISPLAY, formatCardAccessible } from '@/lib/utils/cardFormatter';

interface PlayingCardProps {
  card: Card | null;
  size?: CardSize;
  highlighted?: boolean;
  disabled?: boolean;
  className?: string;
}

const sizeStyles: Record<CardSize, string> = {
  sm: 'w-10 h-14 text-sm',
  md: 'w-16 h-[88px] text-lg',
  lg: 'w-20 h-28 text-xl',
};

export const PlayingCard = memo(function PlayingCard({
  card,
  size = 'md',
  highlighted = false,
  disabled = false,
  className,
}: PlayingCardProps) {
  // Card back
  if (!card) {
    return (
      <div
        className={cn(
          'relative rounded-lg shadow-card overflow-hidden',
          'bg-gradient-to-br from-blue-700 to-blue-900',
          'border-2 border-blue-500',
          sizeStyles[size],
          disabled && 'opacity-50',
          className
        )}
        aria-label="카드 뒷면"
      >
        {/* Pattern */}
        <div className="absolute inset-2 rounded border border-blue-400/30">
          <div className="w-full h-full bg-[repeating-linear-gradient(45deg,transparent,transparent_5px,rgba(255,255,255,0.05)_5px,rgba(255,255,255,0.05)_10px)]" />
        </div>
      </div>
    );
  }

  const suitColor = SUIT_COLORS[card.suit];
  const textColorClass = suitColor === 'red' ? 'text-red-600' : 'text-gray-900';

  return (
    <div
      className={cn(
        'relative rounded-lg shadow-card overflow-hidden bg-white',
        'border-2',
        highlighted ? 'border-yellow-400 ring-2 ring-yellow-400/50' : 'border-gray-200',
        sizeStyles[size],
        disabled && 'opacity-50',
        className
      )}
      aria-label={formatCardAccessible(card)}
    >
      {/* Top-left corner */}
      <div className={cn('absolute top-1 left-1 leading-none font-bold', textColorClass)}>
        <div className="text-center">{RANK_DISPLAY[card.rank]}</div>
        <div className="text-center text-xs">{SUIT_SYMBOLS[card.suit]}</div>
      </div>

      {/* Center suit */}
      <div className={cn('absolute inset-0 flex items-center justify-center', textColorClass)}>
        <span className="text-2xl">{SUIT_SYMBOLS[card.suit]}</span>
      </div>

      {/* Bottom-right corner (inverted) */}
      <div className={cn('absolute bottom-1 right-1 leading-none font-bold rotate-180', textColorClass)}>
        <div className="text-center">{RANK_DISPLAY[card.rank]}</div>
        <div className="text-center text-xs">{SUIT_SYMBOLS[card.suit]}</div>
      </div>
    </div>
  );
});
