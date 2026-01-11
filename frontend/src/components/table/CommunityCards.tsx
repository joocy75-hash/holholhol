import { memo } from 'react';
import { cn } from '@/lib/utils/cn';
import { PlayingCard } from '@/components/common/PlayingCard';
import type { Card, HandPhase } from '@/types/game';

interface CommunityCardsProps {
  cards: Card[];
  phase: HandPhase | null;
  winningCards?: Card[];
}

function isCardInWinning(card: Card, winningCards?: Card[]): boolean {
  if (!winningCards) return false;
  return winningCards.some((w) => w.rank === card.rank && w.suit === card.suit);
}

export const CommunityCards = memo(function CommunityCards({
  cards,
  phase,
  winningCards,
}: CommunityCardsProps) {
  // Determine how many card slots to show
  const slotCount = 5;
  const isShowdown = phase === 'showdown';

  return (
    <div className="flex items-center justify-center gap-2">
      {Array.from({ length: slotCount }).map((_, index) => {
        const card = cards[index];
        const isWinning = card && isCardInWinning(card, winningCards);

        return (
          <div
            key={index}
            className={cn(
              'transition-all duration-300',
              card ? 'animate-fade-in' : 'opacity-30'
            )}
          >
            {card ? (
              <PlayingCard
                card={card}
                size="md"
                highlighted={isShowdown && isWinning}
              />
            ) : (
              <div className="w-16 h-[88px] rounded-lg border-2 border-dashed border-felt-border/50" />
            )}
          </div>
        );
      })}
    </div>
  );
});
