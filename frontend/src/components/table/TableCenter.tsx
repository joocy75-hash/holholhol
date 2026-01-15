'use client';

import { PlayingCard, type Card } from './PlayingCard';
import { isCardInBestFive } from './CommunityCards';
import type { HandResult } from '@/lib/handEvaluator';

interface TableCenterProps {
  pot: number;
  animatedPot: number;
  sidePots: { amount: number; eligiblePlayers: number[] }[];
  communityCards: Card[];
  revealedCommunityCount: number;
  winnerPositions: number[];
  winnerBestCards: Record<number, Card[]>;
  myHandAnalysis: { hand: HandResult | null; draws: string[] };
  isSpectator: boolean;
}

export function TableCenter({
  pot,
  animatedPot,
  sidePots,
  communityCards,
  revealedCommunityCount,
  winnerPositions,
  winnerBestCards,
  myHandAnalysis,
  isSpectator,
}: TableCenterProps) {
  // 5장의 커뮤니티 카드 슬롯 생성
  const cardSlots = Array.from({ length: 5 }, (_, idx) => {
    const card = communityCards[idx];
    const isRevealed = idx < revealedCommunityCount;
    const isBestCard = card && winnerPositions.length > 0 &&
      winnerBestCards[winnerPositions[0]] &&
      isCardInBestFive(card, winnerBestCards[winnerPositions[0]]);
    return { card, isRevealed, isBestCard };
  });

  return (
    <>
      {/* 커뮤니티 카드 5장 슬롯 - POT 아래쪽 */}
      <div 
        className="absolute left-1/2 -translate-x-1/2 flex gap-1.5 z-10"
        style={{ top: '50%' }}
        data-testid="community-cards"
      >
        {cardSlots.map((slot, idx) => (
          <div
            key={idx}
            className={`w-[40px] h-[56px] transition-all duration-300 ${
              slot.card && slot.isRevealed 
                ? 'opacity-100 scale-100' 
                : slot.card 
                  ? 'opacity-0 scale-75' 
                  : ''
            } ${slot.isBestCard ? 'ring-2 ring-yellow-400 rounded shadow-lg shadow-yellow-400/50' : ''}`}
          >
            {slot.card ? (
              <PlayingCard card={slot.card} />
            ) : (
              /* 빈 카드 슬롯 */
              <div className="w-full h-full rounded-md border-2 border-dashed border-white/20 bg-black/20" />
            )}
          </div>
        ))}
      </div>

      {/* 팟 표시 - 커뮤니티 카드 위쪽 */}
      <div 
        className="absolute left-1/2 -translate-x-1/2 flex flex-col items-center z-10"
        style={{ top: '40%' }}
      >
        {pot > 0 && (
          <div className="bg-black/60 px-4 py-1 rounded-full text-yellow-400 font-bold">
            POT: {animatedPot.toLocaleString()}
          </div>
        )}

        {/* 사이드 팟 */}
        {sidePots.length > 0 && (
          <div className="flex gap-2 mt-1">
            {sidePots.map((sp, idx) => (
              <div key={idx} className="bg-black/40 px-2 py-0.5 rounded text-yellow-300 text-xs">
                Side {idx + 1}: {sp.amount.toLocaleString()}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 족보 표시 - 카드 아래쪽 */}
      {myHandAnalysis.hand && !isSpectator && (
        <div 
          className="absolute left-1/2 -translate-x-1/2 z-10"
          style={{ top: '62%' }}
        >
          <div className="bg-gradient-to-r from-yellow-600/80 to-amber-600/80 px-3 py-1 rounded-full text-white text-sm font-bold shadow-lg">
            {myHandAnalysis.hand.name}
          </div>
        </div>
      )}
    </>
  );
}
