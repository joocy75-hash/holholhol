'use client';

import { useState, useRef, useCallback } from 'react';

export interface Card {
  rank: string;
  suit: string;
}

// ========================================
// 카드 스프라이트 시스템 (Cards.png)
// 이미지: 784x480, 카드: 56x80, 14열 x 6행
// ========================================
const CARD_SPRITE = {
  path: '/assets/cards/Cards.png',
  cardWidth: 56,
  cardHeight: 80,
  // 행 인덱스: 슈트 매핑
  suitRow: {
    h: 0, hearts: 0,
    s: 1, spades: 1,
    d: 2, diamonds: 2,
    c: 3, clubs: 3,
  } as Record<string, number>,
  // 열 인덱스: 랭크 매핑 (0=뒷면, 1-13=A-K)
  rankCol: {
    'A': 1, '2': 2, '3': 3, '4': 4, '5': 5,
    '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
    'T': 10, 'J': 11, 'Q': 12, 'K': 13,
  } as Record<string, number>,
};

interface PlayingCardProps {
  card?: Card;
  faceDown?: boolean;
  animate?: boolean;
}

export function PlayingCard({ card, faceDown = false, animate = false }: PlayingCardProps) {
  const shadowStyle = 'shadow-[0_4px_12px_rgba(0,0,0,0.4),0_2px_4px_rgba(0,0,0,0.3)]';
  const animateClass = animate ? 'animate-card-deal' : '';

  // 스프라이트 기본 스타일 (14열 x 6행)
  // background-size 1400% 600%로 각 카드가 컨테이너에 맞게 확대
  const baseStyle = {
    backgroundImage: `url(${CARD_SPRITE.path})`,
    backgroundSize: '1400% 600%',
    backgroundRepeat: 'no-repeat' as const,
  };

  // 카드 뒷면 (col 0, row 3 - 파란 체크 패턴)
  // row 3 = 3/5 * 100 = 60%
  if (faceDown || !card) {
    return (
      <div
        className={`playing-card-sprite ${animateClass} ${shadowStyle}`}
        style={{
          ...baseStyle,
          backgroundPosition: '0% 60%',
        }}
      />
    );
  }

  // 카드 데이터 유효성 검사
  if (!card.suit || !card.rank) {
    console.warn('Invalid card data:', card);
    return (
      <div
        className={`playing-card-sprite ${animateClass} ${shadowStyle}`}
        style={{
          ...baseStyle,
          backgroundPosition: '0% 60%',
        }}
      />
    );
  }

  // 카드 앞면 - 백분율 위치 계산
  // 14열 스프라이트에서 col/13 * 100%, 6행에서 row/5 * 100%
  const suitLower = card.suit.toLowerCase();
  const rankUpper = card.rank.toUpperCase();
  const row = CARD_SPRITE.suitRow[suitLower] ?? 0;
  const col = CARD_SPRITE.rankCol[rankUpper] ?? 1;

  // 백분율 위치: col/(총열-1), row/(총행-1)
  const xPercent = (col / 13) * 100;
  const yPercent = (row / 5) * 100;

  return (
    <div
      className={`playing-card-sprite ${animateClass} ${shadowStyle}`}
      style={{
        ...baseStyle,
        backgroundPosition: `${xPercent}% ${yPercent}%`,
      }}
    />
  );
}

interface FlippableCardProps {
  card: Card;
  isRevealed: boolean;
  canFlip: boolean;
  onFlip: () => void;
}

// 플립 가능한 카드 컴포넌트 (메인 플레이어용)
export function FlippableCard({
  card,
  isRevealed,
  canFlip,
  onFlip
}: FlippableCardProps) {
  const shadowStyle = 'shadow-[0_4px_12px_rgba(0,0,0,0.4),0_2px_4px_rgba(0,0,0,0.3)]';

  // 스프라이트 기본 스타일 (14열 x 6행)
  const baseStyle = {
    backgroundImage: `url(${CARD_SPRITE.path})`,
    backgroundSize: '1400% 600%',
    backgroundRepeat: 'no-repeat' as const,
  };

  // 카드 앞면 위치 계산
  const suitLower = card.suit.toLowerCase();
  const rankUpper = card.rank.toUpperCase();
  const row = CARD_SPRITE.suitRow[suitLower] ?? 0;
  const col = CARD_SPRITE.rankCol[rankUpper] ?? 1;
  const xPercent = (col / 13) * 100;
  const yPercent = (row / 5) * 100;

  return (
    <div
      className={`card-flip-container ${canFlip && !isRevealed ? 'card-tappable' : ''}`}
      onClick={() => canFlip && !isRevealed && onFlip()}
    >
      <div className={`card-flip-inner ${isRevealed ? 'flipped' : ''}`}>
        {/* 뒷면 - 파란 체크 패턴 (row 3) */}
        <div className="card-flip-front">
          <div
            className={`playing-card-sprite ${shadowStyle}`}
            style={{
              ...baseStyle,
              backgroundPosition: '0% 60%',
            }}
          />
        </div>
        {/* 앞면 */}
        <div className="card-flip-back">
          <div
            className={`playing-card-sprite ${shadowStyle}`}
            style={{
              ...baseStyle,
              backgroundPosition: `${xPercent}% ${yPercent}%`,
            }}
          />
        </div>
      </div>
    </div>
  );
}

// 스와이프하여 카드 오픈 컴포넌트
interface SwipeToRevealProps {
  children: React.ReactNode;
  onReveal: () => void;
  isRevealed: boolean;
  disabled?: boolean;
}

export function SwipeToReveal({
  children,
  onReveal,
  isRevealed,
  disabled = false,
}: SwipeToRevealProps) {
  const [dragX, setDragX] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const startXRef = useRef(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const THRESHOLD = 100; // 스와이프 완료 기준 거리 (px)
  const MAX_DRAG = 120; // 최대 드래그 거리

  const handleStart = useCallback((clientX: number) => {
    if (disabled || isRevealed) return;
    setIsDragging(true);
    startXRef.current = clientX;
  }, [disabled, isRevealed]);

  const handleMove = useCallback((clientX: number) => {
    if (!isDragging || disabled || isRevealed) return;
    const diff = clientX - startXRef.current;
    // 오른쪽으로만 드래그 가능
    const clampedDiff = Math.max(0, Math.min(diff, MAX_DRAG));
    setDragX(clampedDiff);
  }, [isDragging, disabled, isRevealed]);

  const handleEnd = useCallback(() => {
    if (!isDragging) return;
    setIsDragging(false);

    if (dragX >= THRESHOLD && !isRevealed && !disabled) {
      onReveal();
    }
    setDragX(0);
  }, [isDragging, dragX, isRevealed, disabled, onReveal]);

  // 마우스 이벤트
  const onMouseDown = (e: React.MouseEvent) => handleStart(e.clientX);
  const onMouseMove = (e: React.MouseEvent) => handleMove(e.clientX);
  const onMouseUp = () => handleEnd();
  const onMouseLeave = () => handleEnd();

  // 터치 이벤트
  const onTouchStart = (e: React.TouchEvent) => handleStart(e.touches[0].clientX);
  const onTouchMove = (e: React.TouchEvent) => handleMove(e.touches[0].clientX);
  const onTouchEnd = () => handleEnd();

  // 진행률 (0 ~ 1)
  const progress = dragX / THRESHOLD;

  if (isRevealed || disabled) {
    return <>{children}</>;
  }

  return (
    <div
      ref={containerRef}
      className="relative select-none touch-none"
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={onMouseLeave}
      onTouchStart={onTouchStart}
      onTouchMove={onTouchMove}
      onTouchEnd={onTouchEnd}
    >
      {children}

      {/* 스와이프 오버레이 */}
      <div
        className="absolute inset-0 flex items-center justify-center pointer-events-none z-20"
        style={{ opacity: 1 - progress * 0.8 }}
      >
        <div className="relative w-full max-w-[180px] h-10 bg-black/60 rounded-full overflow-hidden border border-white/20">
          {/* 슬라이더 트랙 */}
          <div
            className="absolute inset-0 bg-gradient-to-r from-green-500/50 to-green-400/50"
            style={{
              width: `${Math.min(progress * 100, 100)}%`,
              transition: isDragging ? 'none' : 'width 0.2s ease-out'
            }}
          />

          {/* 슬라이더 핸들 */}
          <div
            className="absolute top-1/2 -translate-y-1/2 w-8 h-8 bg-white rounded-full shadow-lg flex items-center justify-center"
            style={{
              left: `${4 + (progress * 70)}%`,
              transition: isDragging ? 'none' : 'left 0.2s ease-out'
            }}
          >
            <span className="text-black text-lg">→</span>
          </div>

          {/* 텍스트 */}
          <div className="absolute inset-0 flex items-center justify-center">
            <span
              className="text-white text-xs font-medium tracking-wider ml-8"
              style={{ opacity: 1 - progress }}
            >
              SLIDE TO OPEN
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// 카드 형식 변환 함수 (문자열 "As", "Kh" → Card 객체)
export function parseCard(card: string | Card | null | undefined): Card | null {
  if (!card) return null;
  if (typeof card === 'object' && card.rank && card.suit) {
    return card;
  }
  if (typeof card === 'string' && card.length >= 2) {
    return { rank: card.slice(0, -1), suit: card.slice(-1) };
  }
  return null;
}

export function parseCards(cards: (string | Card | null | undefined)[] | null | undefined): Card[] {
  if (!cards || !Array.isArray(cards)) return [];
  return cards.map(parseCard).filter((c): c is Card => c !== null);
}
