'use client';

import { PlayingCard, type Card } from './PlayingCard';

// 카드 비교 함수 (rank와 suit 모두 일치하는지 확인)
function isSameCard(card1: Card, card2: Card): boolean {
  const normalizeRank = (r: string) => r.toUpperCase();
  const normalizeSuit = (s: string) => s.toLowerCase();
  return normalizeRank(card1.rank) === normalizeRank(card2.rank) &&
         normalizeSuit(card1.suit) === normalizeSuit(card2.suit);
}

// 카드가 bestFive에 포함되는지 확인
export function isCardInBestFive(card: Card, bestFive: Card[]): boolean {
  return bestFive.some(bc => isSameCard(card, bc));
}

interface CommunityCardsProps {
  cards: Card[];
  revealedCount: number;
  isRevealingCommunity: boolean;
  isShowdownDisplay: boolean;
  winnerBestCards: Record<number, Card[]>;
}

export function CommunityCards({
  cards,
  revealedCount,
  isRevealingCommunity,
  isShowdownDisplay,
  winnerBestCards,
}: CommunityCardsProps) {
  // 모든 승자의 bestFive 카드 합치기
  const allBestCards = Object.values(winnerBestCards).flat();

  return (
    <div
      className="absolute top-[48%] left-1/2 -translate-x-1/2 -translate-y-1/2"
      data-testid="community-cards"
    >
      <div className="flex gap-[5px]">
        {cards?.map((card, i) => {
        // 공개된 카드만 표시 (revealedCount 기준)
        const isRevealed = i < revealedCount;
        // 새로 공개되는 카드인지 확인 (좌측부터 순서대로 애니메이션)
        const isNewlyRevealed = isRevealingCommunity && i === revealedCount - 1;
        // 쇼다운 시 bestFive에 포함된 카드인지 확인
        const isInWinningHand = isShowdownDisplay && allBestCards.length > 0 && isCardInBestFive(card, allBestCards);
        const shouldDim = isShowdownDisplay && allBestCards.length > 0 && !isInWinningHand;

        // 커뮤니티 카드 wrapper 스타일 (크기: 47x66, 기존 대비 10% 축소)
        const communityCardClass = `w-[47px] h-[66px] transition-all duration-300 ${
          isInWinningHand ? 'ring-2 ring-yellow-400 rounded shadow-lg shadow-yellow-400/50 scale-110' : ''
        } ${shouldDim ? 'opacity-40 grayscale' : ''}`;

        return (
          <div key={i} className={communityCardClass} data-testid={`community-card-${i}`} data-rank={card.rank} data-suit={card.suit}>
            {isRevealed ? <PlayingCard card={card} animate={isNewlyRevealed} /> : <PlayingCard faceDown />}
          </div>
        );
      })}
      {/* Placeholder cards */}
      {Array.from({
        length: 5 - (cards?.length || 0),
      }).map((_, i) => (
        <div
          key={`placeholder-${i}`}
          className="w-[47px] h-[66px] rounded-md border-[1.8px] border-dashed border-white/20"
        />
      ))}
      </div>
    </div>
  );
}
