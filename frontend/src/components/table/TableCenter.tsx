'use client';

import { useMemo } from 'react';
import { PlayingCard, type Card } from './PlayingCard';
import { isCardInBestFive } from './CommunityCards';
import type { HandResult } from '@/lib/handEvaluator';
import { MAX_SEATS, getTableConstants } from '@/constants/tableCoordinates';

interface TableCenterProps {
  maxSeats?: number;  // 6 또는 9 (기본값 9)
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
  maxSeats = MAX_SEATS,
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
  // 동적 좌표 선택 (6인 또는 9인)
  const tableConfig = useMemo(() => getTableConstants(maxSeats), [maxSeats]);
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
      {/* 커뮤니티 카드 5장 슬롯 - 고정 픽셀 좌표 (10% 확대) */}
      <div
        className="absolute flex gap-2 z-10"
        style={{
          top: tableConfig.COMMUNITY.y,
          left: tableConfig.COMMUNITY.x,
          transform: 'translate(-50%, -50%)',
        }}
        data-testid="community-cards"
      >
        {cardSlots.map((slot, idx) => (
          <div
            key={idx}
            className={`w-[44px] h-[62px] ${
              slot.isBestCard ? 'ring-2 ring-yellow-400 rounded shadow-lg shadow-yellow-400/50' : ''
            }`}
          >
            {slot.card ? (
              /* 카드가 있으면 플립 애니메이션으로 공개 */
              <div className="card-flip-container">
                <div className={`card-flip-inner ${slot.isRevealed ? 'flipped' : ''}`}>
                  {/* 뒷면 */}
                  <div className="card-flip-front">
                    <PlayingCard faceDown />
                  </div>
                  {/* 앞면 */}
                  <div className="card-flip-back">
                    <PlayingCard card={slot.card} />
                  </div>
                </div>
              </div>
            ) : (
              /* 빈 카드 슬롯 */
              <div className="w-full h-full rounded-md border-2 border-dashed border-white/20 bg-black/20" />
            )}
          </div>
        ))}
      </div>

      {/* 팟 금액 표시 - 배경 없이 숫자만 */}
      <div
        className="absolute flex flex-col items-center z-10"
        style={{
          top: tableConfig.POT_DISPLAY.y,
          left: tableConfig.POT_DISPLAY.x,
          transform: 'translate(-50%, -50%)',
        }}
      >
        {pot > 0 && (
          <div className="text-yellow-400 font-bold text-lg drop-shadow-[0_2px_4px_rgba(0,0,0,0.8)]">
            {animatedPot.toLocaleString()}
          </div>
        )}

        {/* 사이드 팟 */}
        {sidePots.length > 0 && (
          <div className="flex gap-2 mt-1">
            {sidePots.map((sp, idx) => (
              <div key={idx} className="text-yellow-300 text-xs drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)]">
                Side {idx + 1}: {sp.amount.toLocaleString()}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 족보 표시 - 고정 픽셀 좌표 */}
      {myHandAnalysis.hand && !isSpectator && (
        <div
          className="absolute z-10"
          style={{
            top: tableConfig.HAND_RANK.y,
            left: tableConfig.HAND_RANK.x,
            transform: 'translate(-50%, -50%)',
          }}
        >
          <div className="bg-gradient-to-r from-yellow-600/80 to-amber-600/80 px-2 py-0.5 rounded-full text-white text-[10px] font-bold shadow-lg">
            {myHandAnalysis.hand.name}
          </div>
        </div>
      )}
    </>
  );
}
