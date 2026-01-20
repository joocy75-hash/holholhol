'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  scaleIn,
  slideUp,
  flipSpring,
} from '@/lib/animations';

interface Card {
  rank: string;
  suit: string;
}

interface FoldOptionsProps {
  /** 홀카드 */
  cards: Card[];
  /** 표시 여부 */
  isVisible: boolean;
  /** 선택 완료 콜백 */
  onSelect: (option: FoldOption) => void;
  /** 타이머 만료 콜백 */
  onTimeout?: () => void;
  /** 타이머 시간 (초) */
  timerSeconds?: number;
  /** 딜러 위치 (카드 이동 방향) */
  dealerPosition?: { x: number; y: number };
}

export type FoldOption = 'show-card-1' | 'show-card-2' | 'show-all' | 'muck';

// 슈트 심볼 매핑
const SUIT_SYMBOLS: Record<string, string> = {
  hearts: '♥', h: '♥',
  diamonds: '♦', d: '♦',
  clubs: '♣', c: '♣',
  spades: '♠', s: '♠',
};

// 슈트 색상 매핑
const SUIT_COLORS: Record<string, string> = {
  hearts: 'text-red-500', h: 'text-red-500',
  diamonds: 'text-red-500', d: 'text-red-500',
  clubs: 'text-gray-900', c: 'text-gray-900',
  spades: 'text-gray-900', s: 'text-gray-900',
};

/**
 * 폴드 시 Show/Muck 선택 컴포넌트
 * - 카드 위에 투명 버튼 오버레이
 * - 3초 카운트다운 타이머
 * - Show: 카드 플립 후 1-2초 홀드
 * - Muck: 뒷면 상태로 딜러 방향 슬라이드
 */
export default function FoldOptions({
  cards,
  isVisible,
  onSelect,
  onTimeout,
  timerSeconds = 3,
  dealerPosition = { x: 0, y: -200 },
}: FoldOptionsProps) {
  const [timeLeft, setTimeLeft] = useState(timerSeconds);
  const [selectedOption, setSelectedOption] = useState<FoldOption | null>(null);
  const [animationPhase, setAnimationPhase] = useState<'selecting' | 'showing' | 'mucking' | 'done'>('selecting');
  const [revealedCards, setRevealedCards] = useState<Set<number>>(new Set());

  // 선택 처리
  const handleSelect = useCallback((option: FoldOption) => {
    if (selectedOption) return;
    
    setSelectedOption(option);

    if (option === 'muck') {
      setAnimationPhase('mucking');
      setTimeout(() => {
        setAnimationPhase('done');
        onSelect(option);
      }, 800);
    } else {
      setAnimationPhase('showing');
      
      // 공개할 카드 결정
      const cardsToReveal = new Set<number>();
      if (option === 'show-card-1') cardsToReveal.add(0);
      if (option === 'show-card-2') cardsToReveal.add(1);
      if (option === 'show-all') {
        cardsToReveal.add(0);
        cardsToReveal.add(1);
      }
      setRevealedCards(cardsToReveal);

      // 1.5초 홀드 후 완료
      setTimeout(() => {
        setAnimationPhase('done');
        onSelect(option);
      }, 1500);
    }
  }, [selectedOption, onSelect]);

  // 타이머 ref (클린업용)
  const timerIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // timerSeconds를 ref로 추적하여 클로저 문제 방지
  const timerSecondsRef = useRef(timerSeconds);
  // 이전 isVisible 추적 (렌더링 중 상태 변경 방지)
  const prevIsVisibleRef = useRef(isVisible);

  // timerSecondsRef 업데이트 - 렌더링 중 ref 변경 방지를 위해 useEffect로 이동
  useEffect(() => {
    timerSecondsRef.current = timerSeconds;
  }, [timerSeconds]);

  // 리셋 - useEffect로 이동하여 렌더링 중 상태 변경 방지
  useEffect(() => {
    if (isVisible && !prevIsVisibleRef.current) {
      setTimeLeft(timerSecondsRef.current);
      setSelectedOption(null);
      setAnimationPhase('selecting');
      setRevealedCards(new Set());
    }
    prevIsVisibleRef.current = isVisible;
  }, [isVisible]);

  // 타이머
  useEffect(() => {
    // 기존 타이머 정리
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }

    if (!isVisible || selectedOption) return;

    timerIntervalRef.current = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          if (timerIntervalRef.current) {
            clearInterval(timerIntervalRef.current);
            timerIntervalRef.current = null;
          }
          handleSelect('muck');
          onTimeout?.();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
        timerIntervalRef.current = null;
      }
    };
  }, [isVisible, selectedOption, onTimeout, handleSelect]);

  if (!isVisible) return null;

  return (
    <div className="relative" data-testid="fold-options">
      {/* 카드 컨테이너 */}
      <div className="flex gap-4">
        {cards.map((card, index) => (
          <FoldCard
            key={index}
            card={card}
            index={index}
            isRevealed={revealedCards.has(index)}
            isMucking={animationPhase === 'mucking'}
            dealerPosition={dealerPosition}
          />
        ))}
      </div>

      {/* 선택 버튼 오버레이 */}
      <AnimatePresence>
        {animationPhase === 'selecting' && (
          <motion.div
            className="absolute inset-0 flex flex-col items-center justify-center gap-2"
            variants={scaleIn}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            {/* 타이머 */}
            <motion.div
              className="absolute -top-8 left-1/2 -translate-x-1/2 px-3 py-1 bg-red-500 rounded-full text-white text-sm font-bold"
              animate={{
                scale: timeLeft <= 1 ? [1, 1.2, 1] : 1,
              }}
              transition={{ duration: 0.3 }}
            >
              {timeLeft}초
            </motion.div>

            {/* 버튼 그룹 */}
            <motion.div
              className="flex flex-col gap-1 bg-black/80 rounded-lg p-2"
              variants={slideUp}
              initial="initial"
              animate="animate"
            >
              <OptionButton
                onClick={() => handleSelect('show-card-1')}
                label="카드 1 오픈"
                testId="fold-show-card-1"
              />
              <OptionButton
                onClick={() => handleSelect('show-card-2')}
                label="카드 2 오픈"
                testId="fold-show-card-2"
              />
              <OptionButton
                onClick={() => handleSelect('show-all')}
                label="모두 오픈"
                variant="highlight"
                testId="fold-show-all"
              />
              <OptionButton
                onClick={() => handleSelect('muck')}
                label="그냥 버리기"
                variant="muted"
                testId="fold-muck"
              />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// 옵션 버튼 컴포넌트
function OptionButton({
  onClick,
  label,
  variant = 'default',
  testId,
}: {
  onClick: () => void;
  label: string;
  variant?: 'default' | 'highlight' | 'muted';
  testId: string;
}) {
  const variantStyles = {
    default: 'bg-gray-700 hover:bg-gray-600 text-white',
    highlight: 'bg-yellow-500 hover:bg-yellow-400 text-black font-bold',
    muted: 'bg-gray-800 hover:bg-gray-700 text-gray-400',
  };

  return (
    <motion.button
      className={`px-4 py-1.5 rounded text-xs ${variantStyles[variant]}`}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      onClick={onClick}
      data-testid={testId}
    >
      {label}
    </motion.button>
  );
}

// 폴드 카드 컴포넌트
function FoldCard({
  card,
  index,
  isRevealed,
  isMucking,
  dealerPosition,
}: {
  card: Card;
  index: number;
  isRevealed: boolean;
  isMucking: boolean;
  dealerPosition: { x: number; y: number };
}) {
  const suitLower = card.suit.toLowerCase();
  const suitSymbol = SUIT_SYMBOLS[suitLower] || card.suit;
  const suitColor = SUIT_COLORS[suitLower] || 'text-gray-900';

  return (
    <motion.div
      className="relative w-[70px] h-[100px]"
      style={{ perspective: 1000 }}
      animate={
        isMucking
          ? {
              x: dealerPosition.x,
              y: dealerPosition.y,
              opacity: 0,
              scale: 0.8,
            }
          : {}
      }
      transition={{
        duration: 0.6,
        delay: index * 0.1,
        ease: 'easeIn',
      }}
      data-testid={`fold-card-${index}`}
    >
      <motion.div
        className="absolute inset-0"
        style={{ transformStyle: 'preserve-3d' }}
        animate={{ rotateY: isRevealed ? 180 : 0 }}
        transition={flipSpring}
      >
        {/* 카드 뒷면 */}
        <div
          className="absolute inset-0 rounded-xl bg-gradient-to-br from-blue-800 to-blue-900 border-2 border-blue-600 shadow-lg"
          style={{ backfaceVisibility: 'hidden' }}
        >
          <div className="absolute inset-2 rounded-lg border border-blue-500/30 bg-blue-700/20">
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-8 h-8 rounded-full border-2 border-blue-400/50" />
            </div>
          </div>
        </div>

        {/* 카드 앞면 */}
        <motion.div
          className="absolute inset-0 rounded-xl bg-white border-2 border-gray-200 shadow-lg overflow-hidden"
          style={{ 
            backfaceVisibility: 'hidden',
            rotateY: 180,
          }}
        >
          <div className={`flex flex-col items-center justify-center h-full font-bold ${suitColor}`}>
            <span className="text-2xl leading-none">{card.rank}</span>
            <span className="text-3xl leading-none mt-1">{suitSymbol}</span>
          </div>

          {/* 코너 표시 */}
          <div className={`absolute top-1 left-1.5 text-xs ${suitColor}`}>
            <div className="leading-none font-bold">{card.rank}</div>
            <div className="leading-none text-sm">{suitSymbol}</div>
          </div>
          <div className={`absolute bottom-1 right-1.5 text-xs ${suitColor} rotate-180`}>
            <div className="leading-none font-bold">{card.rank}</div>
            <div className="leading-none text-sm">{suitSymbol}</div>
          </div>
        </motion.div>
      </motion.div>

      {/* 공개 효과 */}
      {isRevealed && (
        <motion.div
          className="absolute inset-0 rounded-xl ring-2 ring-yellow-400/50 pointer-events-none"
          initial={{ opacity: 0 }}
          animate={{ opacity: [0, 1, 0.5] }}
          transition={{ duration: 0.6 }}
        />
      )}
    </motion.div>
  );
}
