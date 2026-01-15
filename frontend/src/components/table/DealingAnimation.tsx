'use client';

import { useState, useEffect, useRef } from 'react';
import { PlayingCard } from './PlayingCard';
import { SEAT_POSITIONS } from './PlayerSeat';

interface DealingAnimationProps {
  isDealing: boolean;
  dealingSequence: { position: number; cardIndex: number }[];
  onDealingComplete: () => void;
  tableCenter: { x: number; y: number };
  playerPositions: Record<number, { x: number; y: number }>;
  myPosition: number | null; // 내 좌석 번호 (actualPosition -> visualIndex 변환용)
}

/**
 * actualPosition(실제 좌석 번호)을 visualIndex(화면상 위치)로 변환
 * visualIndex 0은 항상 화면 하단(ME)
 * 
 * 예: myPosition=3인 경우
 * - actualPosition 3 -> visualIndex 0 (ME)
 * - actualPosition 4 -> visualIndex 1
 * - actualPosition 0 -> visualIndex 6
 */
function actualToVisualIndex(actualPosition: number, myPosition: number | null): number {
  if (myPosition === null) {
    return actualPosition; // 관전자는 변환 없이 그대로 사용
  }
  // myPosition을 기준으로 visualIndex 계산
  // myPosition은 visualIndex 0에 해당
  const visualIndex = (actualPosition - myPosition + SEAT_POSITIONS.length) % SEAT_POSITIONS.length;
  return visualIndex;
}

export function DealingAnimation({
  isDealing,
  dealingSequence,
  onDealingComplete,
  tableCenter,
  playerPositions,
  myPosition,
}: DealingAnimationProps) {
  const [visibleCards, setVisibleCards] = useState<{ position: number; cardIndex: number; visualIndex: number; key: string }[]>([]);
  const dealingIdRef = useRef(0);
  const containerRef = useRef<HTMLDivElement>(null);
  
  // playerPositions와 tableCenter를 ref로 저장하여 useEffect 의존성에서 제외
  const playerPositionsRef = useRef(playerPositions);
  const tableCenterRef = useRef(tableCenter);
  const myPositionRef = useRef(myPosition);
  
  // ref 업데이트
  useEffect(() => {
    playerPositionsRef.current = playerPositions;
    tableCenterRef.current = tableCenter;
    myPositionRef.current = myPosition;
  }, [playerPositions, tableCenter, myPosition]);

  useEffect(() => {
    if (!isDealing || dealingSequence.length === 0) {
      setVisibleCards([]);
      dealingIdRef.current = 0;
      return;
    }

    const newDealingId = Date.now();
    dealingIdRef.current = newDealingId;
    setVisibleCards([]);

    console.log('🎴 DealingAnimation 시작:', {
      sequenceLength: dealingSequence.length,
      dealingId: newDealingId,
      myPosition: myPositionRef.current,
    });

    let index = 0;

    const getTargetPosition = (visualIndex: number): { x: number; y: number } => {
      const positions = playerPositionsRef.current;
      const center = tableCenterRef.current;
      
      if (positions[visualIndex]) {
        return positions[visualIndex];
      }
      
      const seatPos = SEAT_POSITIONS[visualIndex];
      if (seatPos && containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        const topPercent = parseFloat(seatPos.top) / 100;
        const leftPercent = parseFloat(seatPos.left) / 100;
        return {
          x: rect.width * leftPercent,
          y: rect.height * topPercent,
        };
      }
      
      return center;
    };

    const dealNextCard = () => {
      if (dealingIdRef.current !== newDealingId) {
        console.log('🎴 딜링 취소 (새 딜링 시작됨)');
        return;
      }

      if (index >= dealingSequence.length) {
        console.log('🎴 딜링 완료, onDealingComplete 호출 대기...');
        // 애니메이션이 완전히 끝날 때까지 조금 더 대기 (forwards 설정 유지 시간)
        setTimeout(() => {
          if (dealingIdRef.current === newDealingId) {
            console.log('🎴 onDealingComplete 실행');
            onDealingComplete();
          }
        }, 500);
        return;
      }

      const deal = dealingSequence[index];
      // actualPosition을 visualIndex로 변환
      const visualIndex = actualToVisualIndex(deal.position, myPositionRef.current);
      const target = getTargetPosition(visualIndex);
      
      console.log(`🎴 카드 딜링 [${index}]:`, { 
        actualPosition: deal.position, 
        visualIndex,
        target,
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
  }, [isDealing, dealingSequence, onDealingComplete]);

  if (!isDealing) return null;

  // 렌더링 시 현재 값 사용
  const currentTableCenter = tableCenterRef.current;
  const currentPlayerPositions = playerPositionsRef.current;
  const currentMyPosition = myPositionRef.current;

  const getTargetPositionForRender = (visualIndex: number): { x: number; y: number } => {
    if (currentPlayerPositions[visualIndex]) {
      return currentPlayerPositions[visualIndex];
    }
    
    const seatPos = SEAT_POSITIONS[visualIndex];
    if (seatPos && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const topPercent = parseFloat(seatPos.top) / 100;
      const leftPercent = parseFloat(seatPos.left) / 100;
      return {
        x: rect.width * leftPercent,
        y: rect.height * topPercent,
      };
    }
    
    return currentTableCenter;
  };

  return (
    <div ref={containerRef} className="absolute inset-0 pointer-events-none z-50">
      {visibleCards.map((deal) => {
        // 저장된 visualIndex 사용 (deal 시점의 myPosition 기준으로 계산됨)
        // 렌더링 시에도 일관성을 위해 현재 myPosition으로 재계산
        const visualIndex = actualToVisualIndex(deal.position, currentMyPosition);
        const target = getTargetPositionForRender(visualIndex);
        const deltaX = target.x - currentTableCenter.x;
        const deltaY = target.y - currentTableCenter.y;

        return (
          <div
            key={deal.key}
            className="dealing-card animating"
            style={{
              left: currentTableCenter.x,
              top: currentTableCenter.y,
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
