'use client';

import { useState, useEffect, useRef } from 'react';
import { PlayingCard } from './PlayingCard';
import { TABLE, MAX_SEATS } from '@/constants/tableCoordinates';

interface DealingAnimationProps {
  isDealing: boolean;
  dealingSequence: { position: number; cardIndex: number }[];
  onDealingComplete: () => void;
  myPosition: number | null; // 내 좌석 번호 (actualPosition -> visualIndex 변환용)
}

/**
 * actualPosition(실제 좌석 번호)을 visualIndex(화면상 위치)로 변환
 * visualIndex 0은 항상 화면 하단(ME)
 */
function actualToVisualIndex(actualPosition: number, myPosition: number | null): number {
  if (myPosition === null) {
    return actualPosition; // 관전자는 변환 없이 그대로 사용
  }
  return (actualPosition - myPosition + MAX_SEATS) % MAX_SEATS;
}

export function DealingAnimation({
  isDealing,
  dealingSequence,
  onDealingComplete,
  myPosition,
}: DealingAnimationProps) {
  const [visibleCards, setVisibleCards] = useState<{ position: number; cardIndex: number; visualIndex: number; key: string }[]>([]);
  const dealingIdRef = useRef(0);
  const myPositionRef = useRef(myPosition);
  const dealingSequenceRef = useRef(dealingSequence);
  const onDealingCompleteRef = useRef(onDealingComplete);

  // ref 업데이트 (의존성 배열 문제 방지)
  useEffect(() => {
    myPositionRef.current = myPosition;
    dealingSequenceRef.current = dealingSequence;
    onDealingCompleteRef.current = onDealingComplete;
  });

  useEffect(() => {
    if (!isDealing || dealingSequenceRef.current.length === 0) {
      setVisibleCards([]);
      dealingIdRef.current = 0;
      return;
    }

    const newDealingId = Date.now();
    dealingIdRef.current = newDealingId;
    setVisibleCards([]);

    console.log('🎴 DealingAnimation 시작:', {
      sequenceLength: dealingSequenceRef.current.length,
      dealingId: newDealingId,
      myPosition: myPositionRef.current,
    });

    let index = 0;

    const dealNextCard = () => {
      if (dealingIdRef.current !== newDealingId) {
        console.log('🎴 딜링 취소 (새 딜링 시작됨)');
        return;
      }

      if (index >= dealingSequenceRef.current.length) {
        console.log('🎴 딜링 완료, onDealingComplete 호출 대기...');
        setTimeout(() => {
          if (dealingIdRef.current === newDealingId) {
            console.log('🎴 onDealingComplete 실행');
            onDealingCompleteRef.current();
          }
        }, 500);
        return;
      }

      const deal = dealingSequenceRef.current[index];
      const visualIndex = actualToVisualIndex(deal.position, myPositionRef.current);

      console.log(`🎴 카드 딜링 [${index}]:`, {
        actualPosition: deal.position,
        visualIndex,
        target: TABLE.SEATS[visualIndex],
        myPosition: myPositionRef.current,
      });

      const dealSound = new Audio('/sounds/carddealing.webm');
      dealSound.volume = 0.4;
      dealSound.play().catch(() => {});

      const cardKey = `${newDealingId}-${index}`;

      setVisibleCards(prev => {
        if (prev.some(c => c.key === cardKey)) {
          return prev;
        }
        return [...prev, { ...deal, visualIndex, key: cardKey }];
      });
      index++;

      setTimeout(dealNextCard, 150);
    };

    const startTimer = setTimeout(dealNextCard, 150);

    return () => {
      clearTimeout(startTimer);
    };
  }, [isDealing]); // isDealing만 의존성으로 유지

  if (!isDealing) return null;

  const currentMyPosition = myPositionRef.current;

  return (
    <div className="absolute inset-0 pointer-events-none z-50">
      {visibleCards.map((deal) => {
        const visualIndex = actualToVisualIndex(deal.position, currentMyPosition);
        const target = TABLE.SEATS[visualIndex];
        // 프로필 위 카드 영역으로 조정 (y 좌표를 위로 이동)
        const cardTargetY = target.y - 60;
        const deltaX = target.x - TABLE.DEALING_CENTER.x;
        const deltaY = cardTargetY - TABLE.DEALING_CENTER.y;

        return (
          <div
            key={deal.key}
            className="dealing-card animating"
            style={{
              left: TABLE.DEALING_CENTER.x,
              top: TABLE.DEALING_CENTER.y,
              width: '36px',
              height: '50px',
              '--deal-x': `${deltaX}px`,
              '--deal-y': `${deltaY}px`,
              '--deal-rotate': `${(deal.cardIndex === 0 ? -5 : 5)}deg`,
            } as React.CSSProperties}
          >
            <div className="w-full h-full">
              <PlayingCard faceDown />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// 딜링 시퀀스 계산 함수 (SB부터 시계방향, 한 장씩 2바퀴)
export function calculateDealingSequence(
  activePlayers: number[],
  sbPosition: number | null
): { position: number; cardIndex: number }[] {
  if (activePlayers.length === 0) return [];

  // SB부터 시작하도록 정렬
  const sorted = [...activePlayers].sort((a, b) => a - b);
  const sbIndex = sbPosition !== null ? sorted.indexOf(sbPosition) : 0;
  const orderedPlayers = [
    ...sorted.slice(sbIndex),
    ...sorted.slice(0, sbIndex)
  ];

  // 2바퀴 (첫 번째 카드 -> 두 번째 카드)
  const sequence: { position: number; cardIndex: number }[] = [];
  for (let cardIndex = 0; cardIndex < 2; cardIndex++) {
    for (const position of orderedPlayers) {
      sequence.push({ position, cardIndex });
    }
  }
  return sequence;
}
