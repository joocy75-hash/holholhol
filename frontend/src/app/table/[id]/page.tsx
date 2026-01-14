'use client';

import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { wsClient } from '@/lib/websocket';
import { analyzeHand, HandResult } from '@/lib/handEvaluator';
import { HandRankingGuide, CardSqueeze } from '@/components/table/pmang';

interface Card {
  rank: string;
  suit: string;
}

// 백엔드 TABLE_SNAPSHOT 구조에 맞춤
interface SeatInfo {
  position: number;
  player: {
    userId: string;
    nickname: string;
    avatarUrl?: string;
  } | null;
  stack: number;
  status: 'empty' | 'active' | 'waiting' | 'folded';
  betAmount: number;      // 현재 라운드 베팅
  totalBet: number;       // 핸드 전체 누적 베팅 (칩 표시용)
}

interface TableConfig {
  maxSeats: number;
  smallBlind: number;
  bigBlind: number;
  minBuyIn: number;
  maxBuyIn: number;
  turnTimeoutSeconds: number;
}

// 이전 호환성을 위한 인터페이스
interface Player {
  id: string;
  username: string;
  chips: number;
  cards: Card[];
  bet: number;
  folded: boolean;
  isActive: boolean;
  seatIndex: number;
  hasCards?: boolean; // 카드를 받았는지 여부 (봇 카드 뒷면 표시용)
  isWinner?: boolean; // 승자 여부 (WIN 표시용)
  winAmount?: number; // 승리 금액
  winHandRank?: string; // 승리 족보 (예: "풀하우스", "스트레이트")
}

interface GameState {
  tableId: string;
  players: Player[];
  communityCards: Card[];
  pot: number;
  currentPlayer: string | null;
  phase: 'waiting' | 'preflop' | 'flop' | 'turn' | 'river' | 'showdown';
  smallBlind: number;
  bigBlind: number;
  minRaise: number;
  currentBet: number;
}

// 카드 형식 변환 함수 (문자열 "As", "Kh" → Card 객체)
function parseCard(card: string | Card | null | undefined): Card | null {
  if (!card) return null;
  if (typeof card === 'object' && card.rank && card.suit) {
    return card;
  }
  if (typeof card === 'string' && card.length >= 2) {
    return { rank: card.slice(0, -1), suit: card.slice(-1) };
  }
  return null;
}

function parseCards(cards: (string | Card | null | undefined)[] | null | undefined): Card[] {
  if (!cards || !Array.isArray(cards)) return [];
  return cards.map(parseCard).filter((c): c is Card => c !== null);
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

// 카드 비교 함수 (rank와 suit 모두 일치하는지 확인)
function isSameCard(card1: Card, card2: Card): boolean {
  const normalizeRank = (r: string) => r.toUpperCase();
  const normalizeSuit = (s: string) => s.toLowerCase();
  return normalizeRank(card1.rank) === normalizeRank(card2.rank) &&
         normalizeSuit(card1.suit) === normalizeSuit(card2.suit);
}

// 카드가 bestFive에 포함되는지 확인
function isCardInBestFive(card: Card, bestFive: Card[]): boolean {
  return bestFive.some(bc => isSameCard(card, bc));
}

function PlayingCard({ card, faceDown = false, animate = false }: { card?: Card; faceDown?: boolean; animate?: boolean }) {
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

// 플립 가능한 카드 컴포넌트 (메인 플레이어용)
function FlippableCard({
  card,
  isRevealed,
  canFlip,
  onFlip
}: {
  card: Card;
  isRevealed: boolean;
  canFlip: boolean;
  onFlip: () => void;
}) {
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

// 딜링 애니메이션에 사용할 플레이어 좌표 계산
interface DealTarget {
  position: number;
  x: number;
  y: number;
}

// 딜링 애니메이션 컴포넌트
function DealingAnimation({
  isDealing,
  dealingSequence,
  onDealingComplete,
  tableCenter,
  playerPositions,
}: {
  isDealing: boolean;
  dealingSequence: { position: number; cardIndex: number }[];
  onDealingComplete: () => void;
  tableCenter: { x: number; y: number };
  playerPositions: Record<number, { x: number; y: number }>;
}) {
  const [currentDealIndex, setCurrentDealIndex] = useState(-1);
  const [visibleCards, setVisibleCards] = useState<{ position: number; cardIndex: number; key: string }[]>([]);
  const dealingIdRef = useRef(0); // 현재 딜링 세션 ID (동기적 체크용)

  useEffect(() => {
    if (!isDealing || dealingSequence.length === 0) {
      setCurrentDealIndex(-1);
      setVisibleCards([]);
      dealingIdRef.current = 0;
      return;
    }

    // 새로운 딜링 세션 시작 - 고유 ID 생성
    const newDealingId = Date.now();
    dealingIdRef.current = newDealingId;

    // 이전 카드 즉시 제거
    setVisibleCards([]);
    setCurrentDealIndex(-1);

    console.log('🎴 DealingAnimation 시작:', {
      isDealing,
      sequenceLength: dealingSequence.length,
      dealingId: newDealingId,
      tableCenter,
      playerPositions,
      positionKeys: Object.keys(playerPositions),
    });

    // 딜링 시작
    let index = 0;

    const dealNextCard = () => {
      // 딜링 ID가 변경되었으면 중단 (새 딜링이 시작됨)
      if (dealingIdRef.current !== newDealingId) {
        console.log('🎴 딜링 취소 (새 딜링 시작됨)');
        return;
      }

      if (index >= dealingSequence.length) {
        // 모든 카드 딜링 완료
        console.log('🎴 딜링 완료');
        setTimeout(() => {
          if (dealingIdRef.current === newDealingId) {
            onDealingComplete();
          }
        }, 400);
        return;
      }

      const deal = dealingSequence[index];
      const target = playerPositions[deal.position];
      console.log(`🎴 카드 딜링 [${index}]:`, { deal, target });

      const currentIndex = index;
      const cardKey = `${newDealingId}-${currentIndex}`;

      // 중복 체크 후 추가
      setVisibleCards(prev => {
        if (prev.some(c => c.key === cardKey)) {
          return prev; // 이미 있으면 추가하지 않음
        }
        return [...prev, { ...deal, key: cardKey }];
      });
      setCurrentDealIndex(currentIndex);
      index++;

      // 다음 카드 딜링 (0.15초 간격)
      setTimeout(dealNextCard, 150);
    };

    // 첫 카드 딜링 시작 (약간의 지연으로 상태 정리 시간 확보)
    const startTimer = setTimeout(dealNextCard, 150);

    // Cleanup
    return () => {
      clearTimeout(startTimer);
    };
  }, [isDealing, dealingSequence, onDealingComplete, tableCenter, playerPositions]);

  if (!isDealing) return null;

  console.log('🎴 DealingAnimation 렌더링:', { visibleCards: visibleCards.length, tableCenter });

  return (
    <div className="absolute inset-0 pointer-events-none z-50">
      {visibleCards.map((deal, idx) => {
        const target = playerPositions[deal.position];
        if (!target) return null;

        const deltaX = target.x - tableCenter.x;
        const deltaY = target.y - tableCenter.y;

        return (
          <div
            key={deal.key}
            className="dealing-card animating"
            style={{
              left: tableCenter.x,
              top: tableCenter.y,
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

// 액션 라벨 매핑 (한글)
const ACTION_LABELS: Record<string, { text: string; className: string }> = {
  fold: { text: '폴드', className: 'bg-[#722f37]/90' },      // 다크버건디
  check: { text: '체크', className: 'bg-[#14532d]/90' },     // 다크그린
  call: { text: '콜', className: 'bg-[#1e3a5f]/90' },        // 짙은 파란색
  bet: { text: '베팅', className: 'bg-[#4c1d95]/90' },       // 짙은 보라색
  raise: { text: '레이즈', className: 'bg-[#4c1d95]/90' },   // 짙은 보라색
  all_in: { text: '올인', className: 'bg-[#ea580c]/90' },    // 주황색
  timeout: { text: '시간초과', className: 'bg-[#722f37]/90' }, // 다크버건디 (레거시)
  timeout_fold: { text: '시간초과', className: 'bg-[#722f37]/90' }, // 다크버건디
  timeout_check: { text: '자동체크', className: 'bg-[#14532d]/90' }, // 다크그린
};

// 허용된 액션 타입 인터페이스
interface AllowedAction {
  type: string;
  amount?: number;    // 콜 금액 등
  minAmount?: number; // 최소 베팅/레이즈 금액
  maxAmount?: number; // 최대 베팅/레이즈 금액
}

// 턴 타이머 설정 (서버와 동기화)
const DEFAULT_TURN_TIME = 15; // 기본 턴 시간 15초 (UTG는 20초)
const COUNTDOWN_START = 10; // 카운트다운 표시 시작 (마지막 10초)

function PlayerSeat({
  player,
  position,
  seatPosition,
  isCurrentUser,
  isActive,
  lastAction,
  turnStartTime,
  turnTime = DEFAULT_TURN_TIME,
  onAutoFold,
  handResult,
  draws,
  onSeatClick,
  showJoinBubble,
  bestFiveCards,
  isCardsRevealed,
  onRevealCards,
  isDealingComplete,
  isEliminated,
  isShowdownRevealed,
}: {
  player?: Player;
  position: { top: string; left: string };
  seatPosition: number;
  isCurrentUser: boolean;
  isActive: boolean;
  lastAction?: { type: string; amount?: number; timestamp: number } | null;
  turnStartTime?: number | null; // 턴 시작 시간 (밀리초)
  turnTime?: number; // 이번 턴 시간 (초, UTG=20, 나머지=15)
  onAutoFold?: () => void; // 자동 폴드 콜백
  handResult?: HandResult | null; // 현재 족보 (자기 자신만)
  draws?: string[]; // 드로우 가능성 (플러시 드로우 등)
  onSeatClick?: (position: number) => void; // 빈 좌석 클릭 핸들러
  showJoinBubble?: boolean; // 게임참여하기 말풍선 표시 여부
  bestFiveCards?: Card[]; // 승자의 bestFive 카드 (하이라이트용)
  isCardsRevealed?: boolean; // 카드 오픈 여부 (메인 플레이어)
  onRevealCards?: () => void; // 카드 오픈 핸들러
  isDealingComplete?: boolean; // 딜링 완료 여부
  isEliminated?: boolean; // 탈락 여부 (퇴장 애니메이션)
  isShowdownRevealed?: boolean; // 쇼다운 시 카드 공개 여부 (제출 모션용)
}) {
  // 액션 표시 여부 관리 (3초 후 자동 숨김)
  const [visibleAction, setVisibleAction] = useState<typeof lastAction>(null);
  // 턴 타이머 상태
  const [timeRemaining, setTimeRemaining] = useState<number | null>(null);
  const [showCountdown, setShowCountdown] = useState(false);

  // 액션 표시 효과
  useEffect(() => {
    // lastAction이 null이면 visibleAction도 즉시 null로 설정 (새 핸드 시작 시)
    if (!lastAction) {
      setVisibleAction(null);
      return;
    }

    const showTimer = setTimeout(() => {
      setVisibleAction(lastAction);
    }, 0);

    const hideTimer = setTimeout(() => {
      setVisibleAction(null);
    }, 3000);

    return () => {
      clearTimeout(showTimer);
      clearTimeout(hideTimer);
    };
  }, [lastAction]);

  // 턴 타이머 효과
  useEffect(() => {
    if (!isActive || !turnStartTime) {
      const resetTimer = setTimeout(() => {
        setTimeRemaining(null);
        setShowCountdown(false);
      }, 0);
      return () => clearTimeout(resetTimer);
    }

    // 클라이언트 시간 기준으로 타이머 시작
    const clientTurnStartTime = Date.now();
    const turnTimeMs = (turnTime || DEFAULT_TURN_TIME) * 1000;
    let autoFoldTriggered = false;

    console.log(`⏱️ Timer started: ${turnTime}s`);

    const updateTimer = () => {
      const elapsed = Date.now() - clientTurnStartTime;
      const remaining = turnTimeMs - elapsed;

      // 시간 초과 시 자동 폴드
      if (remaining <= 0) {
        setTimeRemaining(0);
        setShowCountdown(false);
        if (isCurrentUser && onAutoFold && !autoFoldTriggered) {
          autoFoldTriggered = true;
          console.log('⏰ Auto-fold triggered by timer');
          onAutoFold();
        }
        return;
      }

      setTimeRemaining(remaining / 1000);
      // 마지막 10초부터 카운트다운 표시
      setShowCountdown(remaining <= COUNTDOWN_START * 1000);
    };

    const initTimer = setTimeout(updateTimer, 0);
    const interval = setInterval(updateTimer, 100);

    return () => {
      clearTimeout(initTimer);
      clearInterval(interval);
    };
  }, [isActive, turnStartTime, turnTime, isCurrentUser, onAutoFold]);

  const showAction = visibleAction !== null;
  const actionInfo = visibleAction ? ACTION_LABELS[visibleAction.type.toLowerCase()] || { text: visibleAction.type.toUpperCase(), className: 'bg-gray-500/80' } : null;

  // 타이머 진행률 계산 (10초 기준)
  const timerProgress = timeRemaining !== null && showCountdown
    ? Math.max(0, (timeRemaining / COUNTDOWN_START) * 100)
    : 100;

  if (!player) {
    return (
      <div
        className="player-seat cursor-pointer hover:opacity-80 transition-opacity"
        style={position}
        data-testid={`seat-${seatPosition}`}
        data-occupied="false"
        onClick={() => onSeatClick?.(seatPosition)}
      >
        {/* 게임참여하기 말풍선 */}
        {showJoinBubble && (
          <div className="absolute -top-12 left-1/2 -translate-x-1/2 whitespace-nowrap z-10 animate-bounce">
            <div className="relative bg-[var(--neon-purple)] text-white px-4 py-2 rounded-lg text-sm font-bold shadow-lg">
              게임참여하기
              {/* 말풍선 꼬리 */}
              <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-0 h-0 border-l-[8px] border-r-[8px] border-t-[8px] border-l-transparent border-r-transparent border-t-[var(--neon-purple)]" />
            </div>
          </div>
        )}
        <div className={`player-avatar bg-[var(--surface-hover)] flex items-center justify-center ${showJoinBubble ? 'opacity-100 ring-2 ring-[var(--neon-purple)] ring-offset-2 ring-offset-transparent' : 'opacity-30'}`}>
          <span className="text-xl text-[var(--text-muted)]">▼</span>
        </div>
        <div className="player-info flex flex-col items-center invisible">
          <span className="player-name">-</span>
          <span className="player-chips text-xs">0</span>
        </div>
        {/* 베팅 영역 placeholder (h-[20px]) - 플레이어와 동일한 구조 */}
        <div className="h-[20px] mt-1" />
      </div>
    );
  }

  // 폴드 상태 스타일
  const foldedClass = player.folded ? 'opacity-40 grayscale' : '';
  // 액션 표시 중일 때 z-index 높임 (다른 player-seat 위에 표시)
  const actionZIndex = showAction ? 'z-50' : '';
  // 승리자 글로우 효과
  const winnerClass = player.isWinner ? 'winner-glow' : '';
  // 탈락 애니메이션
  const eliminatedClass = isEliminated ? 'player-eliminated' : '';

  return (
    <div className={`player-seat ${foldedClass} ${actionZIndex} ${winnerClass} ${eliminatedClass}`} style={position} data-testid={`seat-${seatPosition}`} data-occupied="true" data-is-me={isCurrentUser ? 'true' : 'false'} data-status={player.folded ? 'folded' : (player.isActive ? 'active' : 'waiting')}>
      {/* 메인 플레이어 카드 (프로필 위) - 플립 기능 포함 */}
      {isCurrentUser && (
        <div className="flex flex-col items-center mb-3">
          {/* 폴드하지 않았을 때: 정상 카드 표시 */}
          {player.cards.length > 0 && !player.folded && isDealingComplete && (
            <div
              className={`flex gap-1.5 relative ${isShowdownRevealed ? 'my-cards-revealed' : ''}`}
              onClick={() => !isCardsRevealed && onRevealCards?.()}
            >
              {player.cards.map((card, i) => (
                <div key={i} className="w-[57px] h-[80px]">
                  <FlippableCard
                    card={card}
                    isRevealed={isCardsRevealed ?? false}
                    canFlip={!isCardsRevealed && !!onRevealCards}
                    onFlip={onRevealCards ?? (() => {})}
                  />
                </div>
              ))}
              {/* 탭하여 오픈 - 카드 위 중앙에 하나만 표시 */}
              {!isCardsRevealed && onRevealCards && (
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                  <div className="px-3 py-1 bg-black/70 rounded-full text-white text-xs font-medium animate-pulse">
                    👆 OPEN
                  </div>
                </div>
              )}
            </div>
          )}
          {/* 폴드했을 때: 카드 뒷면 + 흑백 효과 + FOLD 배지 */}
          {player.folded && (
            <div className="flex gap-1.5 relative grayscale [&_.playing-card-sprite]:!animate-none">
              {[0, 1].map((i) => (
                <div key={i} className="w-[57px] h-[80px]">
                  <PlayingCard faceDown />
                </div>
              ))}
              {/* FOLD 배지 - 카드 위에 표시 */}
              <div className="absolute inset-0 flex items-center justify-center z-10">
                <span className="px-2 py-0.5 bg-red-500/80 text-white text-xs font-bold rounded">
                  FOLD
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 아바타 wrapper - 액션 모달과 타이머의 기준점 */}
      <div className="relative flex items-center justify-center">
        {/* 액션 표시 - 좌석 위치에 따라 동적 배치 */}
        {showAction && actionInfo && visibleAction && (() => {
          // 상단 플레이어 (7, 8): 아바타 아래로 표시
          const isTopSeat = [7, 8].includes(seatPosition);
          // 하단 플레이어 (0): 카드 위에 표시 (더 위로)
          const isBottomSeat = seatPosition === 0;
          // 좌측 플레이어 (1, 3, 5): 프로필 왼쪽에 표시
          const isLeftSeat = [1, 3, 5].includes(seatPosition);
          // 우측 플레이어 (2, 4, 6): 프로필 오른쪽에 표시
          const isRightSeat = [2, 4, 6].includes(seatPosition);

          let positionStyle: React.CSSProperties = {};

          if (isTopSeat) {
            // 상단: 아바타 아래로
            positionStyle = {
              top: '100%',
              left: '50%',
              transform: 'translateX(-50%)',
              marginTop: '8px',
            };
          } else if (isBottomSeat) {
            // 하단 (0번): 카드 위에 표시하므로 더 위로
            positionStyle = {
              bottom: '100%',
              left: '50%',
              transform: 'translateX(-50%)',
              marginBottom: '110px', // 카드 높이 + 간격
            };
          } else if (isLeftSeat) {
            // 좌측 플레이어: 프로필 오른쪽에 표시 (카드가 오른쪽에 겹쳐있으므로 그 위)
            positionStyle = {
              top: '50%',
              left: '100%',
              transform: 'translateY(-50%)',
              marginLeft: '8px',
            };
          } else if (isRightSeat) {
            // 우측 플레이어: 프로필 왼쪽에 표시 (카드가 왼쪽에 겹쳐있으므로 그 위)
            positionStyle = {
              top: '50%',
              right: '100%',
              transform: 'translateY(-50%)',
              marginRight: '8px',
            };
          } else {
            // 기본: 아바타 위
            positionStyle = {
              bottom: '100%',
              left: '50%',
              transform: 'translateX(-50%)',
              marginBottom: '8px',
            };
          }

          return (
            <div className="absolute z-50" style={positionStyle}>
              <div className={`px-3 py-1.5 rounded-full text-white text-sm font-bold shadow-xl animate-bounce-in-center whitespace-nowrap ${actionInfo.className}`}>
                {actionInfo.text}
                {!!visibleAction.amount && ` ${visibleAction.amount.toLocaleString()}`}
              </div>
            </div>
          );
        })()}

        {/* 프로필 아바타 + 턴 타이머 통합 */}
        <div className="relative" data-testid={isActive ? "turn-timer" : undefined} data-time-remaining={isActive ? Math.ceil(timeRemaining || 0) : undefined}>
          {/* SVG 원형 프로그레스 바 (턴일 때만) */}
          {isActive && (
            <svg
              className="absolute -inset-1 w-[calc(100%+8px)] h-[calc(100%+8px)] -rotate-90"
              viewBox="0 0 100 100"
            >
              {/* 배경 원 (턴 표시) */}
              <circle
                cx="50"
                cy="50"
                r="46"
                fill="none"
                stroke={showCountdown ? "rgba(255,255,255,0.2)" : "var(--accent)"}
                strokeWidth="4"
              />
              {/* 진행 원 (카운트다운 타이머) */}
              {showCountdown && (
                <circle
                  cx="50"
                  cy="50"
                  r="46"
                  fill="none"
                  stroke={
                    timerProgress > 40
                      ? '#22c55e'  // 녹색
                      : timerProgress > 20
                        ? '#f59e0b'  // 황색
                        : '#ef4444'  // 빨강
                  }
                  strokeWidth="4"
                  strokeLinecap="round"
                  strokeDasharray={`${(timerProgress / 100) * 289} 289`}
                  className="transition-all duration-100"
                />
              )}
            </svg>
          )}

          {/* 프로필 아바타 */}
          <div className={`player-avatar ${isCurrentUser ? 'border-[var(--primary)]' : ''} ${player.folded ? 'bg-gray-600' : ''} ${player.isWinner ? 'winner-avatar' : ''}`}>
            {player.username.charAt(0).toUpperCase()}
          </div>

          {/* 카운트다운 숫자 (우측 상단 뱃지) */}
          {isActive && showCountdown && (
            <div
              className={`absolute -top-1 -right-1 w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${
                timerProgress > 40
                  ? 'bg-green-500 text-white'
                  : timerProgress > 20
                    ? 'bg-yellow-500 text-black'
                    : 'bg-red-500 text-white'
              }`}
              data-testid="timeout-indicator"
            >
              {Math.ceil(timeRemaining || 0)}
            </div>
          )}
        </div>

        {/* 다른 플레이어 카드 오픈 시 - 프로필 정중앙 배치 */}
        {!isCurrentUser && !player.folded && isDealingComplete && player.cards.length > 0 && (() => {
          return (
            <div className="absolute flex gap-0.5 z-20 left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
              {player.cards.map((card, i) => {
                const hasBestFiveInfo = bestFiveCards && bestFiveCards.length > 0;
                const isInBestFive = hasBestFiveInfo && isCardInBestFive(card, bestFiveCards);
                const shouldHighlight = player.isWinner && (!hasBestFiveInfo || isInBestFive);
                const shouldDim = player.isWinner && hasBestFiveInfo && !isInBestFive;
                const cardClass = `w-[32px] h-[44px] ${shouldHighlight ? 'ring-2 ring-yellow-400 rounded shadow-lg shadow-yellow-400/50' : ''} ${shouldDim ? 'opacity-40 grayscale' : ''}`;
                return (
                  <div key={i} className={cardClass}>
                    <PlayingCard card={card} />
                  </div>
                );
              })}
            </div>
          );
        })()}

        {/* 다른 플레이어 카드 뒷면 - 좌석 위치에 따라 좌/우 배치 */}
        {!isCurrentUser && !player.folded && isDealingComplete && player.hasCards && player.cards.length === 0 && (() => {
          const isLeftSeat = [1, 3, 5, 7].includes(seatPosition);
          const isRightSeat = [2, 4, 6, 8].includes(seatPosition);

          const positionClass = isLeftSeat
            ? '-bottom-1 left-1/2'  // 오른쪽으로 겹침
            : isRightSeat
            ? '-bottom-1 right-1/2'  // 왼쪽으로 겹침
            : '-bottom-1 left-1/2 -translate-x-1/2';  // 중앙

          return (
            <div className={`absolute flex -space-x-2 ${positionClass}`}>
              <div className="w-[18px] h-[25px]"><PlayingCard faceDown /></div>
              <div className="w-[18px] h-[25px]"><PlayingCard faceDown /></div>
            </div>
          );
        })()}
      </div>

      {/* 닉네임 → 보유금액 순서 */}
      <div className="player-info flex flex-col items-center gap-0.5">
        <span className={`player-name block text-[10px] font-medium truncate max-w-[64px] ${player.folded ? 'line-through text-gray-500' : ''}`} title={player.username}>{player.username}</span>
        <span className="player-chips text-xs text-[var(--accent)]" data-testid={isCurrentUser ? 'my-stack' : `stack-${seatPosition}`}>{player.chips.toLocaleString()}</span>
      </div>

      {/* WIN 배지 - 절대 위치 (레이아웃에 영향 없음) */}
      {player.isWinner && (
        <div className="absolute -top-16 left-1/2 -translate-x-1/2 px-4 py-2 bg-gradient-to-r from-yellow-400 to-yellow-600 text-black text-sm font-bold rounded-lg shadow-xl shadow-yellow-500/50 animate-bounce z-10" data-testid={`win-badge-${seatPosition}`}>
          <div className="text-center text-lg">WIN!</div>
          {player.winHandRank && (
            <div className="text-xs text-yellow-900 text-center font-semibold">{player.winHandRank}</div>
          )}
          {player.winAmount !== undefined && player.winAmount > 0 && (
            <div className="text-xs text-yellow-800 text-center">+{player.winAmount.toLocaleString()}</div>
          )}
        </div>
      )}

      {/* ========================================
          폴드 표시 영역 (고정 높이: 20px)
          - 폴드 상태만 표시
          - 없어도 공간 유지
          ======================================== */}
      <div className="h-[28px] flex items-center justify-center mt-1">
        {/* 현재 유저는 프로필 위에 큰 카드로 표시, 다른 플레이어는 여기서 작은 카드로 표시 */}
        {player.folded && !isCurrentUser && (
          <div className="flex gap-0.5 relative grayscale [&_.playing-card-sprite]:!animate-none">
            {[0, 1].map((i) => (
              <div key={i} className="w-[18px] h-[25px]">
                <PlayingCard faceDown />
              </div>
            ))}
            {/* FOLD 배지 - 카드 위에 표시 */}
            <div className="absolute inset-0 flex items-center justify-center z-10">
              <span className="px-1 py-0.5 bg-red-500/80 text-white text-[8px] font-bold rounded">
                FOLD
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Seat positions for 9-max table - vertical layout
// Top: 2, Sides: 2-2-2, Bottom: 1 (player)
const SEAT_POSITIONS = [
  { top: '80%', left: '50%' },   // 0 - bottom center (ME/Player)
  { top: '57%', left: '9%' },    // 1 - lower left
  { top: '57%', left: '91%' },   // 2 - lower right
  { top: '38%', left: '10%' },   // 3 - mid left
  { top: '38%', left: '90%' },   // 4 - mid right
  { top: '25%', left: '18%' },   // 5 - upper left
  { top: '25%', left: '82%' },   // 6 - upper right
  { top: '17%', left: '35%' },   // 7 - top left
  { top: '17%', left: '65%' },   // 8 - top right
];

// 칩 베팅 위치 (플레이어와 중앙 POT 사이)
const CHIP_POSITIONS = [
  { top: '63%', left: '50%' },   // 0 - bottom center
  { top: '58%', left: '22%' },   // 1 - lower left
  { top: '58%', left: '78%' },   // 2 - lower right
  { top: '42%', left: '23%' },   // 3 - mid left
  { top: '42%', left: '77%' },   // 4 - mid right
  { top: '32%', left: '28%' },   // 5 - upper left
  { top: '32%', left: '72%' },   // 6 - upper right
  { top: '28%', left: '42%' },   // 7 - top left
  { top: '28%', left: '58%' },   // 8 - top right
];

// POT 위치 (중앙, POT 글씨 위쪽)
const POT_POSITION = { top: '32%', left: '50%' };

// ========================================
// 칩 스택 컴포넌트
// ========================================
interface ChipAnimation {
  id: string;
  fromPosition: { top: string; left: string };
  toPosition: { top: string; left: string };
  amount: number;
  startTime: number;
}

function BettingChips({
  amount,
  position,
  isAnimating = false,
  animateTo,
  onAnimationEnd,
}: {
  amount: number;
  position: { top: string; left: string };
  isAnimating?: boolean;
  animateTo?: { top: string; left: string };
  onAnimationEnd?: () => void;
}) {
  const [currentPos, setCurrentPos] = useState(position);
  const [opacity, setOpacity] = useState(1);

  useEffect(() => {
    if (isAnimating && animateTo) {
      // 애니메이션 시작
      const timer = setTimeout(() => {
        setCurrentPos(animateTo);
      }, 50);

      // 애니메이션 종료
      const endTimer = setTimeout(() => {
        setOpacity(0);
        setTimeout(() => {
          onAnimationEnd?.();
        }, 100);
      }, 500);

      return () => {
        clearTimeout(timer);
        clearTimeout(endTimer);
      };
    } else {
      setCurrentPos(position);
      setOpacity(1);
    }
  }, [isAnimating, animateTo, position, onAnimationEnd]);

  if (amount <= 0) return null;

  // 칩 색상 결정 (금액에 따라)
  const getChipColor = (amt: number) => {
    if (amt >= 1000) return 'bg-purple-500 border-purple-300';
    if (amt >= 500) return 'bg-blue-500 border-blue-300';
    if (amt >= 100) return 'bg-green-500 border-green-300';
    if (amt >= 25) return 'bg-red-500 border-red-300';
    return 'bg-gray-400 border-gray-200';
  };

  // 칩 개수 계산 (최대 5개)
  const chipCount = Math.min(Math.ceil(amount / 100), 5);

  return (
    <div
      className="absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center z-30 transition-all duration-500 ease-out"
      style={{
        top: currentPos.top,
        left: currentPos.left,
        opacity,
      }}
    >
      {/* 칩 스택 */}
      <div className="relative flex flex-col-reverse items-center">
        {Array.from({ length: chipCount }).map((_, i) => (
          <div
            key={i}
            className={`w-8 h-3 rounded-full border-2 shadow-md ${getChipColor(amount)}`}
            style={{ marginTop: i > 0 ? '-6px' : '0' }}
          />
        ))}
      </div>
      {/* 금액 표시 */}
      <div className="mt-1 px-2 py-0.5 bg-black/80 rounded text-white text-[10px] font-bold whitespace-nowrap">
        {amount.toLocaleString()}
      </div>
    </div>
  );
}

// 바이인 모달 컴포넌트 (피망 스타일)
function BuyInModal({
  config,
  userBalance,
  onConfirm,
  onCancel,
  isLoading,
  tableName = '테이블',
}: {
  config: TableConfig;
  userBalance: number;
  onConfirm: (buyIn: number) => void;
  onCancel: () => void;
  isLoading: boolean;
  tableName?: string;
}) {
  const minBuyIn = config.minBuyIn || 400;
  const maxBuyIn = Math.min(config.maxBuyIn || 2000, userBalance);
  const [buyIn, setBuyIn] = useState(minBuyIn);

  const isValidBuyIn = buyIn >= minBuyIn && buyIn <= maxBuyIn;
  const insufficientBalance = userBalance < minBuyIn;

  console.log('🎰 BuyInModal rendered:', { minBuyIn, maxBuyIn, buyIn, isValidBuyIn, insufficientBalance, userBalance });

  // 슬라이더 퍼센트 계산
  const sliderPercent = maxBuyIn > minBuyIn
    ? ((buyIn - minBuyIn) / (maxBuyIn - minBuyIn)) * 100
    : 100;

  const handleMin = () => setBuyIn(minBuyIn);
  const handleMax = () => setBuyIn(maxBuyIn);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 animate-backdrop" data-testid="buyin-modal">
      {/* 바텀시트 */}
      <div
        className="w-full max-w-[500px] animate-bottom-sheet"
        style={{
          backgroundImage: "url('/assets/ui/buyin/bg-panel.png')",
          backgroundSize: '100% 100%',
          backgroundRepeat: 'no-repeat',
        }}
      >
        <div className="px-6 pt-8 pb-6">
          {/* 제목 */}
          <h2 className="text-center text-white text-xl font-bold mb-2">바이인</h2>

          {/* 테이블 정보 */}
          <p className="text-center text-[#4FC3F7] text-base mb-6 underline underline-offset-4">
            {tableName} {config.smallBlind.toLocaleString()}/{config.bigBlind.toLocaleString()}
          </p>

          {insufficientBalance ? (
            <div className="mb-6 p-4 rounded-lg bg-red-500/20 text-red-400 text-center" data-testid="buyin-error">
              잔액이 부족합니다. 최소 바이인: {minBuyIn.toLocaleString()}
            </div>
          ) : (
            <>
              {/* MIN/MAX 바 - 698x73 @2x → 349x36.5 @1x */}
              <div
                className="relative h-[37px] mb-6 flex items-center"
                style={{
                  backgroundImage: "url('/assets/ui/buyin/bar-minmax.png')",
                  backgroundSize: '100% 100%',
                }}
              >
                {/* MIN 버튼 - 144x70 @2x → 72x35 @1x */}
                <button
                  onClick={handleMin}
                  className="absolute left-0 top-0 bottom-0 w-[72px] flex items-center justify-center text-white font-bold text-xs transition-all duration-150 hover:brightness-125 active:scale-95 active:brightness-90"
                  style={{
                    backgroundImage: "url('/assets/ui/buyin/btn-min.png')",
                    backgroundSize: '100% 100%',
                  }}
                >
                  MIN
                </button>

                {/* 금액 표시 */}
                <span className="absolute left-1/2 -translate-x-1/2 text-[#FFD700] text-xl font-bold">
                  {buyIn.toLocaleString()}
                </span>

                {/* MAX 버튼 - 144x70 @2x → 72x35 @1x */}
                <button
                  onClick={handleMax}
                  className="absolute right-0 top-0 bottom-0 w-[72px] flex items-center justify-center text-white font-bold text-xs transition-all duration-150 hover:brightness-125 active:scale-95 active:brightness-90"
                  style={{
                    backgroundImage: "url('/assets/ui/buyin/btn-max.png')",
                    backgroundSize: '100% 100%',
                  }}
                >
                  MAX
                </button>
              </div>

              {/* 최소/최대 표시 */}
              <div className="flex justify-between text-[#FFD700] text-sm mb-2 px-2">
                <span>{minBuyIn.toLocaleString()}</span>
                <span className="text-gray-500">- - - - - - - - - - - - - -</span>
                <span>{maxBuyIn.toLocaleString()}</span>
              </div>

              {/* 슬라이더 */}
              <div className="relative h-[52px] mb-6 mx-2">
                {/* 트랙 배경 */}
                <div
                  className="absolute top-1/2 -translate-y-1/2 left-[24px] right-[24px] h-[26px]"
                  style={{
                    backgroundImage: "url('/assets/ui/buyin/slider-track.png')",
                    backgroundSize: '100% 100%',
                    opacity: 0.3,
                  }}
                />
                {/* 트랙 채워진 부분 */}
                <div
                  className="absolute top-1/2 -translate-y-1/2 left-[24px] h-[26px]"
                  style={{
                    width: `calc((100% - 48px) * ${sliderPercent / 100})`,
                    backgroundImage: "url('/assets/ui/buyin/slider-track.png')",
                    backgroundSize: '100% 100%',
                  }}
                />
                {/* 슬라이더 input (투명) */}
                <input
                  type="range"
                  min={minBuyIn}
                  max={maxBuyIn}
                  value={buyIn}
                  onChange={(e) => setBuyIn(parseInt(e.target.value))}
                  className="absolute top-0 left-[24px] right-[24px] h-full opacity-0 cursor-pointer z-10"
                  style={{ width: 'calc(100% - 48px)' }}
                  data-testid="buyin-slider"
                />
                {/* 노브 */}
                <div
                  className="absolute top-1/2 -translate-y-1/2 w-[48px] h-[48px] pointer-events-none"
                  style={{
                    left: `calc(${sliderPercent / 100} * (100% - 48px))`,
                    backgroundImage: "url('/assets/ui/buyin/slider-thumb.png')",
                    backgroundSize: 'contain',
                    backgroundPosition: 'center',
                    backgroundRepeat: 'no-repeat',
                  }}
                />
              </div>
            </>
          )}

          {/* 보유 골드 */}
          <div
            className="relative h-[42px] mb-6 flex items-center justify-between px-4"
            style={{
              backgroundImage: "url('/assets/ui/buyin/bar-balance.png')",
              backgroundSize: '100% 100%',
            }}
          >
            <span className="text-gray-400 text-sm">보유 골드</span>
            <div className="flex items-center gap-2">
              <img
                src="/assets/ui/buyin/icon-gold.png"
                alt="gold"
                className="w-6 h-6 object-contain"
              />
              <span className="text-[#FFD700] text-base font-bold">
                {userBalance.toLocaleString()}
              </span>
            </div>
          </div>

          {/* 버튼 영역 */}
          <div className="flex">
            <button
              onClick={onCancel}
              disabled={isLoading}
              className="flex-[258] h-[73px] flex items-center justify-center text-gray-700 font-bold text-base transition-all duration-150 hover:brightness-110 active:scale-[0.97] active:brightness-95"
              style={{
                backgroundImage: "url('/assets/ui/buyin/btn-cancel.png')",
                backgroundSize: '100% 100%',
              }}
              data-testid="buyin-cancel"
            >
              닫기
            </button>
            <button
              onClick={() => onConfirm(buyIn)}
              disabled={isLoading || !isValidBuyIn || insufficientBalance}
              className="flex-[431] h-[73px] flex items-center justify-center text-white font-bold text-base transition-all duration-150 hover:brightness-110 hover:shadow-lg hover:shadow-orange-500/30 active:scale-[0.97] active:brightness-95 disabled:opacity-50 disabled:hover:brightness-100 disabled:hover:shadow-none disabled:active:scale-100"
              style={{
                backgroundImage: "url('/assets/ui/buyin/btn-confirm.png')",
                backgroundSize: '100% 100%',
              }}
              data-testid="buyin-confirm"
            >
              {isLoading ? '참여 중...' : '확인'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// 숫자 애니메이션 훅 - 증가할 때만 애니메이션 (감소 시 즉시 변경)
function useAnimatedNumber(value: number, duration: number = 500) {
  const [displayValue, setDisplayValue] = useState(value);
  const previousValue = useRef(value);
  const animationRef = useRef<number | null>(null);

  useEffect(() => {
    const startValue = previousValue.current;
    const endValue = value;
    const diff = endValue - startValue;

    // 이전 애니메이션 취소
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
    }

    // 값이 같으면 바로 설정
    if (diff === 0) {
      setDisplayValue(value);
      return;
    }

    // 감소할 때는 애니메이션 없이 즉시 변경 (새 핸드 시작 시 pot이 0으로 리셋될 때)
    if (diff < 0) {
      setDisplayValue(value);
      previousValue.current = value;
      return;
    }

    // 증가할 때만 애니메이션
    const startTime = performance.now();

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // easeOutQuart 이징 함수 - 빠르게 시작해서 천천히 끝남
      const easeProgress = 1 - Math.pow(1 - progress, 4);

      const currentValue = Math.round(startValue + diff * easeProgress);
      setDisplayValue(currentValue);

      if (progress < 1) {
        animationRef.current = requestAnimationFrame(animate);
      } else {
        setDisplayValue(endValue);
        previousValue.current = endValue;
      }
    };

    animationRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [value, duration]);

  return displayValue;
}

// 개발용 어드민 패널 컴포넌트
function DevAdminPanel({
  tableId,
  onReset,
  onAddBot,
  onStartBotLoop,
  isResetting,
  isAddingBot,
  isStartingLoop,
}: {
  tableId: string;
  onReset: () => void;
  onAddBot: () => void;
  onStartBotLoop: () => void;
  isResetting: boolean;
  isAddingBot: boolean;
  isStartingLoop: boolean;
}) {
  const [isOpen, setIsOpen] = useState(true); // 기본 펼침

  return (
    <div className="fixed bottom-4 right-4 z-50">
      {/* 패널 (기본 펼침) */}
      {isOpen ? (
        <div className="w-64 bg-gray-900 border border-gray-700 rounded-lg shadow-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <span>🛠</span> DEV 패널
            </h3>
            <button
              onClick={() => setIsOpen(false)}
              className="text-gray-400 hover:text-white transition-colors"
            >
              ✕
            </button>
          </div>

          <div className="space-y-2">
            {/* 봇 자동 루프 시작 */}
            <button
              onClick={onStartBotLoop}
              disabled={isStartingLoop}
              className="w-full px-3 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-900 disabled:opacity-50 text-white text-sm rounded transition-colors flex items-center justify-center gap-2"
            >
              {isStartingLoop ? (
                <>
                  <span className="animate-spin">⏳</span> 시작 중...
                </>
              ) : (
                <>
                  <span>🤖</span> 봇 자동 루프 시작
                </>
              )}
            </button>

            {/* 봇 추가 */}
            <button
              onClick={onAddBot}
              disabled={isAddingBot}
              className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-900 disabled:opacity-50 text-white text-sm rounded transition-colors flex items-center justify-center gap-2"
            >
              {isAddingBot ? (
                <>
                  <span className="animate-spin">⏳</span> 추가 중...
                </>
              ) : (
                <>
                  <span>🤖</span> 봇 1개 추가
                </>
              )}
            </button>

            {/* 전체 리셋 (봇 제거 + 테이블 리셋 통합) */}
            <button
              onClick={onReset}
              disabled={isResetting}
              className="w-full px-3 py-2 bg-red-600 hover:bg-red-700 disabled:bg-red-900 disabled:opacity-50 text-white text-sm rounded transition-colors flex items-center justify-center gap-2"
            >
              {isResetting ? (
                <>
                  <span className="animate-spin">⏳</span> 리셋 중...
                </>
              ) : (
                <>
                  <span>🔄</span> 전체 리셋
                </>
              )}
            </button>

            {/* 테이블 ID 표시 */}
            <div className="mt-3 pt-3 border-t border-gray-700">
              <p className="text-xs text-gray-500">Table ID:</p>
              <p className="text-xs text-gray-400 font-mono truncate">{tableId}</p>
            </div>
          </div>
        </div>
      ) : (
        /* 토글 버튼 (접힘 상태) */
        <button
          onClick={() => setIsOpen(true)}
          className="w-12 h-12 rounded-full bg-gray-800 border border-gray-600 text-white flex items-center justify-center shadow-lg hover:bg-gray-700 transition-colors"
          title="개발자 도구"
        >
          ⚙
        </button>
      )}
    </div>
  );
}

export default function TablePage() {
  const params = useParams();
  const router = useRouter();
  const tableId = params.id as string;

  const { user, fetchUser } = useAuthStore();
  const [gameState, setGameState] = useState<GameState | null>(null);
  const communityCardsRef = useRef<Card[]>([]); // HAND_RESULT에서 최신 커뮤니티 카드 접근용
  const [tableConfig, setTableConfig] = useState<TableConfig | null>(null);
  const [seats, setSeats] = useState<SeatInfo[]>([]);
  const seatsRef = useRef<SeatInfo[]>([]); // HAND_STARTED에서 최신 seats 접근용
  const [myPosition, setMyPosition] = useState<number | null>(null);
  const [raiseAmount, setRaiseAmount] = useState(0);
  const [showRaiseSlider, setShowRaiseSlider] = useState(false); // 레이즈 슬라이더 팝업
  const [isConnected, setIsConnected] = useState(false);
  const [isLeaving, setIsLeaving] = useState(false);
  const [isJoining, setIsJoining] = useState(false);
  const [showBuyInModal, setShowBuyInModal] = useState(false);
  const [isAddingBot, setIsAddingBot] = useState(false);
  const [isStartingLoop, setIsStartingLoop] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [myHoleCards, setMyHoleCards] = useState<Card[]>([]);
  const [currentTurnPosition, setCurrentTurnPosition] = useState<number | null>(null);
  const [countdown, setCountdown] = useState<number | null>(null);
  // 각 플레이어의 마지막 액션 저장 { position: { type: 'call', amount: 100 } }
  const [playerActions, setPlayerActions] = useState<Record<number, { type: string; amount?: number; timestamp: number }>>({});
  // 턴 시작 시간 추적 (서버 타임스탬프)
  const [turnStartTime, setTurnStartTime] = useState<number | null>(null);
  // 현재 턴 시간 (UTG=20초, 나머지=15초)
  const [currentTurnTime, setCurrentTurnTime] = useState<number>(DEFAULT_TURN_TIME);
  // 자동 폴드 방지 (중복 호출 방지)
  const [hasAutoFolded, setHasAutoFolded] = useState(false);
  // 서버에서 받은 허용된 액션 목록
  const [allowedActions, setAllowedActions] = useState<AllowedAction[]>([]);
  // 대기 중인 턴 위치 (액션 효과 후 적용)
  const [pendingTurnPosition, setPendingTurnPosition] = useState<number | null>(null);
  // 액션 효과 표시 중 여부
  const [isShowingActionEffect, setIsShowingActionEffect] = useState(false);
  // DEV 패널 상태
  const [isResetting, setIsResetting] = useState(false);
  // 쇼다운 상태 (핸드 결과)
  const [winnerPositions, setWinnerPositions] = useState<number[]>([]);
  const [winnerAmounts, setWinnerAmounts] = useState<Record<number, number>>({}); // position -> 승리 금액
  const [winnerHandRanks, setWinnerHandRanks] = useState<Record<number, string>>({}); // position -> 족보명
  const [winnerBestCards, setWinnerBestCards] = useState<Record<number, Card[]>>({}); // position -> bestFive (승리 족보 카드 5장)
  const [showdownCards, setShowdownCards] = useState<Record<number, Card[]>>({}); // position -> cards
  // 쇼다운 표시 상태 (TABLE_SNAPSHOT의 phase 덮어쓰기와 별개로 관리)
  const [isShowdownDisplay, setIsShowdownDisplay] = useState(false);
  // 순차적 쇼다운 상태
  const [showdownRevealOrder, setShowdownRevealOrder] = useState<number[]>([]); // 카드 공개 순서 (position 배열)
  const [revealedPositions, setRevealedPositions] = useState<Set<number>>(new Set()); // 이미 공개된 position들
  const [showdownPhase, setShowdownPhase] = useState<'idle' | 'intro' | 'revealing' | 'winner_announced' | 'settling' | 'complete'>('idle');
  const [allHandRanks, setAllHandRanks] = useState<Record<number, string>>({}); // 모든 플레이어 족보 (position -> 족보명)
  const [allBestFive, setAllBestFive] = useState<Record<number, Card[]>>({}); // 모든 플레이어 bestFive
  // 쇼다운 애니메이션 진행 중 플래그 및 대기 중인 HAND_STARTED 데이터
  const isShowdownInProgressRef = useRef(false);
  const pendingHandStartedRef = useRef<any>(null);
  const pendingHoleCardsRef = useRef<Card[] | null>(null); // 쇼다운 중 받은 홀카드 저장
  const pendingTurnPromptRef = useRef<any>(null); // 쇼다운 중 받은 TURN_PROMPT 저장
  // 딜러 버튼 및 블라인드 위치
  const [dealerPosition, setDealerPosition] = useState<number | null>(null);
  const [smallBlindPosition, setSmallBlindPosition] = useState<number | null>(null);
  const [bigBlindPosition, setBigBlindPosition] = useState<number | null>(null);
  // 사이드 팟
  const [sidePots, setSidePots] = useState<{ amount: number; eligiblePlayers: number[] }[]>([]);
  // 탈락한 플레이어 (퇴장 애니메이션용)
  const [eliminatedPositions, setEliminatedPositions] = useState<number[]>([]);

  // 딜링 애니메이션 상태
  const [isDealing, setIsDealing] = useState(false);
  const [dealingSequence, setDealingSequence] = useState<{ position: number; cardIndex: number }[]>([]);
  const [dealingComplete, setDealingComplete] = useState(false);

  // 커뮤니티 카드 순차 공개 상태
  const [revealedCommunityCount, setRevealedCommunityCount] = useState(0); // 공개된 커뮤니티 카드 수
  const [pendingCommunityCards, setPendingCommunityCards] = useState<Card[]>([]); // 대기 중인 커뮤니티 카드
  const [isRevealingCommunity, setIsRevealingCommunity] = useState(false); // 커뮤니티 카드 공개 애니메이션 중

  // 칩 애니메이션 상태
  const [collectingChips, setCollectingChips] = useState<{ position: number; amount: number }[]>([]);
  const [distributingChip, setDistributingChip] = useState<{ amount: number; toPosition: number } | null>(null);
  const [isCollectingToPot, setIsCollectingToPot] = useState(false); // 칩 수집 애니메이션 중
  const [potChips, setPotChips] = useState<number>(0); // 중앙 POT에 쌓인 칩 (수집 완료 후 표시)
  // 테이블 중앙 좌표 (딜링 시작점)
  const tableRef = useRef<HTMLDivElement>(null);
  const [tableCenter, setTableCenter] = useState({ x: 0, y: 0 });
  // 플레이어 위치 좌표 (딜링 목적지)
  const [playerPositions, setPlayerPositions] = useState<Record<number, { x: number; y: number }>>({});

  // 카드 오픈 상태 (메인 플레이어)
  const [myCardsRevealed, setMyCardsRevealed] = useState(false);
  const cardRevealTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const CARD_AUTO_REVEAL_DELAY = 10000; // 10초 후 자동 오픈

  // seatsRef 동기화 (이벤트 핸들러에서 최신 seats 접근용)
  useEffect(() => {
    seatsRef.current = seats;
  }, [seats]);

  // 관전자 여부: myPosition이 null이면 관전자
  const isSpectator = myPosition === null;
  const isMyTurn = currentTurnPosition !== null && currentTurnPosition === myPosition;

  // 팟 숫자 애니메이션
  const animatedPot = useAnimatedNumber(gameState?.pot ?? 0, 600);

  // 딜링 시퀀스 계산 함수 (SB부터 시계방향, 한 장씩 2바퀴)
  const calculateDealingSequence = useCallback((
    activePlayers: number[],
    sbPosition: number | null
  ): { position: number; cardIndex: number }[] => {
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
  }, []);

  // 카드 오픈 핸들러 (메인 플레이어)
  const handleRevealCards = useCallback(() => {
    setMyCardsRevealed(true);
    // 타이머 취소
    if (cardRevealTimeoutRef.current) {
      clearTimeout(cardRevealTimeoutRef.current);
      cardRevealTimeoutRef.current = null;
    }
  }, []);

  // 카드 받았을 때 자동 오픈 타이머 시작
  useEffect(() => {
    if (myHoleCards.length > 0 && !myCardsRevealed && dealingComplete) {
      // 10초 후 자동 오픈
      cardRevealTimeoutRef.current = setTimeout(() => {
        setMyCardsRevealed(true);
      }, CARD_AUTO_REVEAL_DELAY);

      return () => {
        if (cardRevealTimeoutRef.current) {
          clearTimeout(cardRevealTimeoutRef.current);
        }
      };
    }
  }, [myHoleCards.length, myCardsRevealed, dealingComplete, CARD_AUTO_REVEAL_DELAY]);

  // 새 핸드 시작 시 상태 초기화
  useEffect(() => {
    if (gameState?.phase === 'waiting') {
      setMyCardsRevealed(false);
      setDealingComplete(false);
      setIsDealing(false);
      setDealingSequence([]);
    }
  }, [gameState?.phase]);

  // Fallback: 카드를 받았는데 딜링이 시작되지 않았으면 2초 후 dealingComplete로 설정
  useEffect(() => {
    if (myHoleCards.length > 0 && !isDealing && !dealingComplete) {
      const timeout = setTimeout(() => {
        setDealingComplete(true);
      }, 2000);
      return () => clearTimeout(timeout);
    }
  }, [myHoleCards.length, isDealing, dealingComplete]);

  // 딜링 완료 핸들러
  const handleDealingComplete = useCallback(() => {
    setIsDealing(false);
    setDealingComplete(true);
  }, []);

  // 테이블 중앙 좌표 계산
  useEffect(() => {
    const updateTableCenter = () => {
      if (tableRef.current) {
        const rect = tableRef.current.getBoundingClientRect();
        setTableCenter({
          x: rect.width / 2,
          y: rect.height * 0.45, // 테이블 중앙보다 약간 위
        });
      }
    };
    updateTableCenter();
    window.addEventListener('resize', updateTableCenter);
    return () => window.removeEventListener('resize', updateTableCenter);
  }, []);

  // 플레이어 위치 좌표 계산 (딜링 목적지)
  useEffect(() => {
    const updatePlayerPositions = () => {
      if (!tableRef.current) return;
      const rect = tableRef.current.getBoundingClientRect();
      const positions: Record<number, { x: number; y: number }> = {};

      // 실제 position -> 시각적 position 매핑 (상대 위치)
      seats.forEach((seat) => {
        const visualIndex = myPosition !== null
          ? (seat.position - myPosition + SEAT_POSITIONS.length) % SEAT_POSITIONS.length
          : seat.position;

        const seatPos = SEAT_POSITIONS[visualIndex];
        if (seatPos) {
          const topPercent = parseFloat(seatPos.top) / 100;
          const leftPercent = parseFloat(seatPos.left) / 100;
          positions[seat.position] = {
            x: rect.width * leftPercent,
            y: rect.height * topPercent - 30, // 프로필 위로 조정
          };
        }
      });

      setPlayerPositions(positions);
    };

    updatePlayerPositions();
    window.addEventListener('resize', updatePlayerPositions);
    return () => window.removeEventListener('resize', updatePlayerPositions);
  }, [seats, myPosition]);

  // Connect to WebSocket
  useEffect(() => {
    fetchUser();

    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/login');
      return;
    }

    wsClient
      .connect(token)
      .then(() => {
        setIsConnected(true);
        // Subscribe to table (백엔드는 tableId를 기대)
        wsClient.send('SUBSCRIBE_TABLE', { tableId: tableId });
      })
      .catch((err) => {
        setError('서버 연결에 실패했습니다.');
        console.error(err);
      });

    // Event handlers
    const unsubTableSnapshot = wsClient.on('TABLE_SNAPSHOT', (data) => {
      console.log('TABLE_SNAPSHOT received:', data);
      // 백엔드 TABLE_SNAPSHOT 구조 처리
      if (data.config) {
        setTableConfig(data.config);
      }
      if (data.seats) {
        // 백엔드에서 보내는 seats 배열 사용 (빈 좌석 포함)
        // player가 null인 좌석은 빈 좌석으로 처리
        const formattedSeats = data.seats
          .filter((s: any) => s.player !== null)
          .map((s: any) => ({
            position: s.position,
            player: s.player,
            stack: s.stack,
            status: s.status,
            betAmount: s.betAmount || 0,
            totalBet: s.totalBet || 0,  // 핸드 전체 누적 베팅
          }));
        setSeats(formattedSeats);
      }
      // state.players에서 좌석 업데이트 (personalized state 형식)
      // 주의: data.seats가 있으면 이미 처리했으므로 덮어쓰지 않음
      if (!data.seats && data.state?.players) {
        const playersArray = Array.isArray(data.state.players)
          ? data.state.players
          : Object.values(data.state.players);
        const formattedSeats = playersArray
          .filter((p: any) => p !== null)
          .map((p: any) => ({
            position: p.seat ?? p.position,
            player: {
              userId: p.userId,
              nickname: p.username || p.nickname,
            },
            stack: p.stack,
            status: p.status,
            betAmount: p.bet || 0,
            totalBet: p.totalBet || 0,  // 핸드 전체 누적 베팅
          }));
        if (formattedSeats.length > 0) {
          setSeats(formattedSeats);
        }
      }
      // myPosition 설정: null은 관전자, 숫자는 착석 위치
      // data.myPosition이 명시적으로 제공되면 그 값 사용 (null 포함)
      if ('myPosition' in data) {
        setMyPosition(data.myPosition);  // null이면 관전자
      } else if (data.state && 'myPosition' in data.state) {
        setMyPosition(data.state.myPosition);
      }
      // myHoleCards 추출 (직접 필드 또는 state 내부에서)
      let extractedCards: Card[] | null = null;

      if (data.myHoleCards && data.myHoleCards.length > 0) {
        // 카드 형식 변환 ("As" -> { rank: "A", suit: "s" })
        extractedCards = data.myHoleCards.map((card: string | Card) => {
          if (typeof card === 'string') {
            return { rank: card.slice(0, -1), suit: card.slice(-1) };
          }
          return card;
        });
      } else if (data.state?.players && data.state?.myPosition !== undefined) {
        // action.py의 _broadcast_personalized_states에서 오는 형식
        const myPlayer = data.state.players[data.state.myPosition];
        if (myPlayer?.holeCards && myPlayer.holeCards.length > 0) {
          extractedCards = myPlayer.holeCards.map((card: string | Card) => {
            if (typeof card === 'string') {
              return { rank: card.slice(0, -1), suit: card.slice(-1) };
            }
            return card;
          });
        }
      }

      // 쇼다운 진행 중에는 카드를 pendingHoleCardsRef에 저장 (나중에 적용)
      if (extractedCards && extractedCards.length > 0) {
        if (isShowdownInProgressRef.current) {
          console.log('🎴 Showdown in progress, saving hole cards for later:', extractedCards);
          pendingHoleCardsRef.current = extractedCards;
        } else {
          setMyHoleCards(extractedCards);
        }
      }
      // hand 정보 또는 state 정보에서 phase, pot 등 업데이트
      // 쇼다운 중에는 pot/phase 업데이트 차단 (새 핸드 데이터가 쇼다운 애니메이션을 방해하지 않도록)
      const stateData = data.hand || data.state || data;
      const isShowdownBlocking = isShowdownInProgressRef.current;
      if (stateData.pot !== undefined || stateData.phase) {
        setGameState((prev) => ({
          ...(prev || {
            tableId: data.tableId,
            players: [],
            communityCards: [],
            pot: 0,
            currentPlayer: null,
            phase: 'waiting' as const,
            smallBlind: data.config?.smallBlind || stateData.smallBlind || 10,
            bigBlind: data.config?.bigBlind || stateData.bigBlind || 20,
            minRaise: 0,
            currentBet: 0,
          }),
          phase: isShowdownBlocking ? (prev?.phase || 'showdown') : (stateData.phase || 'waiting'),
          pot: isShowdownBlocking ? (prev?.pot ?? 0) : (stateData.pot ?? prev?.pot ?? 0),
          // 쇼다운 표시 중에는 기존 커뮤니티 카드 유지 (빈 배열로 덮어쓰기 방지)
          communityCards: (stateData.communityCards && stateData.communityCards.length > 0)
            ? parseCards(stateData.communityCards)
            : (prev?.communityCards || []),
          currentBet: stateData.currentBet ?? prev?.currentBet ?? 0,
        }));
        if (stateData.currentTurn !== undefined) {
          setCurrentTurnPosition(stateData.currentTurn);
        }
      }
      // 딜러 버튼 및 블라인드 위치 업데이트
      if (data.dealerPosition !== undefined) {
        setDealerPosition(data.dealerPosition);
      } else if (stateData.dealer !== undefined) {
        setDealerPosition(stateData.dealer);
      }
      if (stateData.smallBlindSeat !== undefined) {
        setSmallBlindPosition(stateData.smallBlindSeat);
      }
      if (stateData.bigBlindSeat !== undefined) {
        setBigBlindPosition(stateData.bigBlindSeat);
      }
      // 사이드 팟 업데이트
      if (stateData.sidePots && Array.isArray(stateData.sidePots)) {
        setSidePots(stateData.sidePots.map((sp: any) => ({
          amount: sp.amount,
          eligiblePlayers: sp.eligiblePlayers || sp.eligible_positions || [],
        })));
      }
    });

    const unsubTableUpdate = wsClient.on('TABLE_STATE_UPDATE', (data) => {
      const changes = data.changes || {};
      // updateType은 data 또는 changes 안에 있을 수 있음
      const updateType = data.updateType || changes.updateType;

      console.log('TABLE_STATE_UPDATE received:', { updateType, changes });

      // seat_taken 처리: 새 플레이어가 착석했을 때
      if (updateType === 'seat_taken' && changes.position !== undefined) {
        setSeats((prevSeats) => {
          // 이미 해당 위치에 플레이어가 있는지 확인
          const existingIdx = prevSeats.findIndex(s => s.position === changes.position);
          const newSeat: SeatInfo = {
            position: changes.position,
            player: {
              userId: changes.userId,
              nickname: changes.nickname || changes.userId,
            },
            stack: changes.stack || 0,
            status: 'active',
            betAmount: 0,
          };

          if (existingIdx >= 0) {
            // 기존 좌석 업데이트
            const updated = [...prevSeats];
            updated[existingIdx] = newSeat;
            return updated;
          } else {
            // 새 좌석 추가
            return [...prevSeats, newSeat];
          }
        });

        // 현재 유저가 착석한 경우 myPosition 업데이트
        if (changes.userId === user?.id) {
          setMyPosition(changes.position);
        }
      }

      // player_left 처리: 플레이어가 떠났을 때
      if (updateType === 'player_left' && changes.position !== undefined) {
        setSeats((prevSeats) => prevSeats.filter(s => s.position !== changes.position));
        if (changes.userId === user?.id) {
          setMyPosition(null);
        }
      }

      // bot_added 처리: 봇이 추가됐을 때
      if (updateType === 'bot_added' && changes.position !== undefined) {
        setSeats((prevSeats) => {
          const existingIdx = prevSeats.findIndex(s => s.position === changes.position);
          const newSeat: SeatInfo = {
            position: changes.position,
            player: {
              userId: changes.botId,
              nickname: changes.nickname || `Bot_${changes.botId?.slice(-4)}`,
            },
            stack: changes.stack || 0,
            status: 'active',
            betAmount: 0,
          };

          if (existingIdx >= 0) {
            const updated = [...prevSeats];
            updated[existingIdx] = newSeat;
            return updated;
          } else {
            return [...prevSeats, newSeat];
          }
        });
      }

      // playerJoined 처리: 새 플레이어(봇 포함)가 착석했을 때 (dev API에서 사용)
      // 주의: bot_added일 때는 이미 위에서 처리했으므로 건너뜀
      if (changes.playerJoined && updateType !== 'bot_added') {
        const { position, username, stack, isBot } = changes.playerJoined;
        setSeats((prevSeats) => {
          const existingIdx = prevSeats.findIndex(s => s.position === position);
          const newSeat: SeatInfo = {
            position: position,
            player: {
              userId: isBot ? `bot_${position}` : username,
              nickname: username,
            },
            stack: stack || 0,
            status: 'active',
            betAmount: 0,
          };

          if (existingIdx >= 0) {
            const updated = [...prevSeats];
            updated[existingIdx] = newSeat;
            return updated;
          } else {
            return [...prevSeats, newSeat];
          }
        });
      }

      // gameState 업데이트 (pot, phase, currentBet 등)
      // 쇼다운 중에는 pot/phase 업데이트 차단 (새 핸드 데이터가 쇼다운 애니메이션을 방해하지 않도록)
      setGameState((prev) => {
        if (!prev) return prev;
        const isShowdownBlocking = isShowdownInProgressRef.current;
        return {
          ...prev,
          pot: isShowdownBlocking ? prev.pot : (changes.pot ?? prev.pot),
          phase: isShowdownBlocking ? prev.phase : (changes.phase ?? prev.phase),
          currentBet: changes.currentBet ?? prev.currentBet,
          currentPlayer: changes.currentPlayer ?? prev.currentPlayer,
        };
      });

      // 사이드 팟 업데이트
      if (changes.sidePots && Array.isArray(changes.sidePots)) {
        setSidePots(changes.sidePots.map((sp: any) => ({
          amount: sp.amount,
          eligiblePlayers: sp.eligiblePlayers || sp.eligible_positions || [],
        })));
      }

      // 플레이어 스택/베팅 실시간 업데이트
      if (changes.players && Array.isArray(changes.players)) {
        setSeats((prevSeats) => {
          return prevSeats.map((seat) => {
            const playerUpdate = changes.players.find(
              (p: { position: number }) => p.position === seat.position
            );
            if (playerUpdate && seat.player) {
              return {
                ...seat,
                stack: playerUpdate.stack ?? seat.stack,
                betAmount: playerUpdate.bet ?? seat.betAmount,
                totalBet: playerUpdate.totalBet ?? seat.totalBet,  // 핸드 전체 누적
                status: playerUpdate.status ?? seat.status,
              };
            }
            return seat;
          });
        });
      }

      // seats 업데이트가 있으면 반영
      if (changes.seats) {
        setSeats(changes.seats);
      }

      // lastAction이 있으면 플레이어 액션 표시 (시퀀싱 처리)
      if (changes.lastAction) {
        const { type, amount, position } = changes.lastAction;

        // 1. 액션 효과 표시 시작
        setIsShowingActionEffect(true);
        setPlayerActions((prev) => ({
          ...prev,
          [position]: { type, amount, timestamp: Date.now() },
        }));

        // 2. currentPlayer가 있으면 대기열에 저장 (즉시 적용 안 함)
        // 중요: 턴 변경 시 타이머는 TURN_PROMPT에서 설정됨
        if (changes.currentPlayer !== undefined) {
          setPendingTurnPosition(changes.currentPlayer);
          // 턴이 변경되므로 이전 타이머 즉시 무효화
          setTurnStartTime(null);
        }

        // 3. 액션 효과 표시 후 턴 전환 (1초 후)
        setTimeout(() => {
          setIsShowingActionEffect(false);
          // 대기 중인 턴 위치가 있으면 적용
          // 주의: 타이머는 여기서 설정하지 않음 (TURN_PROMPT에서 설정)
          setPendingTurnPosition((pending) => {
            if (pending !== null) {
              setCurrentTurnPosition(pending);
            }
            return null;
          });
        }, 1000);
      } else {
        // lastAction 없이 currentPlayer만 변경되면 즉시 적용
        if (changes.currentPlayer !== undefined) {
          // 턴 변경 시 타이머 리셋 (TURN_PROMPT에서 새로 설정됨)
          setTurnStartTime(null);
          setCurrentTurnPosition(changes.currentPlayer);
        }
      }
    });

    // ACTION_RESULT 핸들러 - 액션 결과 처리
    // 주의: playerActions 업데이트는 TABLE_STATE_UPDATE에서만 처리 (중복 방지)
    const unsubActionResult = wsClient.on('ACTION_RESULT', (data) => {
      console.log('ACTION_RESULT received:', data);
      if (data.success && data.action) {
        // 타이머 즉시 정지 - 액션이 완료되면 카운트다운 종료
        setTurnStartTime(null);
        // 내 액션이 성공하면 allowedActions 초기화 (버튼 숨김)
        setAllowedActions([]);
        // 주의: playerActions 업데이트는 TABLE_STATE_UPDATE에서 처리
        // 여기서 하지 않음으로써 중복 효과 방지
      } else if (!data.success) {
        setError(data.errorMessage || '액션 처리에 실패했습니다.');
        // should_refresh 플래그가 있으면 게임 상태 갱신
        if (data.shouldRefresh) {
          console.log('Refreshing game state due to action error...');
          wsClient.send('SUBSCRIBE_TABLE', { tableId: tableId });
        }
      }
    });

    // SEAT_RESULT 핸들러 - 바이인 후 좌석 배정 결과
    const unsubSeatResult = wsClient.on('SEAT_RESULT', (data) => {
      setIsJoining(false);
      if (data.success) {
        setMyPosition(data.position);
        setShowBuyInModal(false);
        // 테이블 상태 새로고침
        wsClient.send('SUBSCRIBE_TABLE', { tableId: tableId });
        // 잔액 업데이트
        fetchUser();
      } else {
        setError(data.errorMessage || '좌석 배정에 실패했습니다.');
      }
    });

    const unsubError = wsClient.on('ERROR', (data) => {
      // 백엔드 ERROR 형식: { errorCode, errorMessage, details }
      setError(data.errorMessage || data.message || '오류가 발생했습니다.');
      setIsLeaving(false); // Reset leaving state on error
    });

    const unsubLeaveResult = wsClient.on('LEAVE_RESULT', (data) => {
      if (data.success) {
        router.push('/lobby');
      } else if (data.errorCode === 'TABLE_NOT_SEATED') {
        // 관전자(앉지 않은 사용자)도 로비로 이동 가능
        router.push('/lobby');
      } else {
        setError(data.errorMessage || '테이블 퇴장에 실패했습니다.');
        setIsLeaving(false);
      }
    });

    // ADD_BOT_RESULT 핸들러 - 봇 추가 결과
    const unsubAddBotResult = wsClient.on('ADD_BOT_RESULT', (data) => {
      setIsAddingBot(false);
      if (data.success) {
        // 테이블 상태 새로고침
        wsClient.send('SUBSCRIBE_TABLE', { tableId: tableId });
      } else {
        setError(data.errorMessage || '봇 추가에 실패했습니다.');
      }
    });

    // START_BOT_LOOP_RESULT 핸들러 - 봇 자동 루프 결과
    const unsubBotLoopResult = wsClient.on('START_BOT_LOOP_RESULT', (data) => {
      setIsStartingLoop(false);
      if (data.success) {
        console.log(`[BOT-LOOP] ${data.botsAdded}개 봇 추가됨, 게임 시작: ${data.gameStarted}`);
        // 테이블 상태 새로고침
        wsClient.send('SUBSCRIBE_TABLE', { tableId: tableId });
      } else {
        setError(data.errorMessage || '봇 루프 시작에 실패했습니다.');
      }
    });

    // GAME_STARTING 핸들러 - 게임 시작 카운트다운
    const unsubGameStarting = wsClient.on('GAME_STARTING', (data) => {
      console.log('GAME_STARTING received:', data);
      const countdownSeconds = data.countdownSeconds || 5;
      setCountdown(countdownSeconds);

      // 카운트다운 타이머
      let remaining = countdownSeconds;
      const timer = setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
          clearInterval(timer);
          setCountdown(null);
        } else {
          setCountdown(remaining);
        }
      }, 1000);
    });

    // HAND_STARTED 처리 함수 (쇼다운 완료 후 호출될 수 있음)
    const processHandStarted = (data: any) => {
      console.log('🎴 Processing HAND_STARTED:', data);
      console.log('🎴 data.myHoleCards:', data.myHoleCards);
      console.log('🎴 data.seats:', data.seats);
      console.log('🎴 Current seatsRef:', seatsRef.current);

      // 카운트다운 종료
      setCountdown(null);

      // 이전 핸드 액션 초기화
      setPlayerActions({});
      setAllowedActions([]); // 허용된 액션도 초기화

      // 시퀀싱 상태 초기화
      setPendingTurnPosition(null);
      setIsShowingActionEffect(false);

      // 타이머 초기화 (새 핸드 시작)
      setTurnStartTime(null);
      setCurrentTurnPosition(null);

      // 쇼다운 상태 완전 초기화
      setWinnerPositions([]);
      setWinnerAmounts({});
      setWinnerHandRanks({});
      setWinnerBestCards({});
      setShowdownCards({});
      setIsShowdownDisplay(false);
      // 순차적 쇼다운 상태 초기화
      setShowdownRevealOrder([]);
      setRevealedPositions(new Set());
      setShowdownPhase('idle');
      setAllHandRanks({});
      setAllBestFive({});
      // 주의: isShowdownInProgressRef는 여기서 초기화하지 않음
      // completeShowdown에서만 관리하여 레이스 컨디션 방지
      // 커뮤니티 카드 순차 공개 상태 초기화
      setRevealedCommunityCount(0);
      setPendingCommunityCards([]);
      setIsRevealingCommunity(false);
      communityCardsRef.current = []; // ref도 초기화

      // 칩 애니메이션 상태 초기화
      setCollectingChips([]);
      setDistributingChip(null);
      setIsCollectingToPot(false);
      setPotChips(0);

      // 이전 핸드 카드 초기화 (새 카드가 오기 전까지 빈 상태)
      setMyHoleCards([]);

      // 게임 상태 업데이트
      setGameState((prev) => {
        const base = prev || {
          tableId: data.tableId,
          players: [],
          communityCards: [],
          pot: 0,
          currentPlayer: null,
          phase: 'waiting' as const,
          smallBlind: 10,
          bigBlind: 20,
          minRaise: 0,
          currentBet: 0,
        };
        return {
          ...base,
          tableId: data.tableId,
          phase: data.phase || 'preflop',
          pot: data.pot || 0,
          communityCards: parseCards(data.communityCards),
        };
      });

      // 내 위치 업데이트
      if (data.myPosition !== null && data.myPosition !== undefined) {
        setMyPosition(data.myPosition);
      }

      // 내 홀카드 저장 (pendingHoleCardsRef 우선 사용)
      if (pendingHoleCardsRef.current && pendingHoleCardsRef.current.length > 0) {
        console.log('🎴 Using pending hole cards:', pendingHoleCardsRef.current);
        setMyHoleCards(pendingHoleCardsRef.current);
        pendingHoleCardsRef.current = null;
      } else if (data.myHoleCards && data.myHoleCards.length > 0) {
        setMyHoleCards(data.myHoleCards);
      }

      // 현재 턴 위치 저장
      if (data.currentTurn !== null && data.currentTurn !== undefined) {
        setCurrentTurnPosition(data.currentTurn);
      }

      // 딜러 버튼 및 블라인드 위치 업데이트
      if (data.dealer !== undefined) {
        setDealerPosition(data.dealer);
      }
      if (data.smallBlindSeat !== undefined) {
        setSmallBlindPosition(data.smallBlindSeat);
      }
      if (data.bigBlindSeat !== undefined) {
        setBigBlindPosition(data.bigBlindSeat);
      }

      // 사이드 팟 초기화 (새 핸드 시작)
      setSidePots([]);

      // seats 업데이트 (data.seats가 있으면 업데이트, 없으면 기존 seatsRef 사용)
      let seatsToUse = seatsRef.current;
      if (data.seats) {
        const formattedSeats = data.seats.map((s: any) => ({
          position: s.position,
          player: {
            userId: s.userId,
            nickname: s.nickname,
          },
          stack: s.stack,
          status: s.status,
          betAmount: s.betAmount || 0,
        }));
        setSeats(formattedSeats);
        seatsToUse = formattedSeats;
      }

      // 딜링 애니메이션 시작 (활성 플레이어만)
      const activePlayers = seatsToUse
        .filter((s: SeatInfo) => s.player && (s.status === 'active' || s.status === 'waiting'))
        .map((s: SeatInfo) => s.position);

      console.log('🎴 딜링 준비:', { seatsToUse, activePlayers });

      if (activePlayers.length >= 2) {
        const sbPos = data.smallBlindSeat ?? smallBlindPosition;
        const sequence = calculateDealingSequence(activePlayers, sbPos);

        console.log('🎴 딜링 시퀀스 계산:', { sequence, sbPos, activePlayers });

        // 카드 오픈 상태 초기화
        setMyCardsRevealed(false);
        setDealingComplete(false);
        setDealingSequence(sequence);

        // playerPositions 계산을 위해 약간 지연 후 딜링 시작
        setTimeout(() => {
          console.log('🎴 딜링 시작:', { sequence, activePlayers });
          setIsDealing(true);
        }, 300);
      } else {
        console.warn('⚠️ 활성 플레이어가 2명 미만:', activePlayers.length, seatsToUse);
        // Fallback: 딜링 없이 바로 완료 상태로
        setDealingComplete(true);
      }

      // 대기 중인 TURN_PROMPT 처리 (쇼다운 중에 도착한 경우)
      if (pendingTurnPromptRef.current) {
        console.log('🎯 Processing pending TURN_PROMPT after HAND_STARTED');
        const pendingTurnData = pendingTurnPromptRef.current;
        pendingTurnPromptRef.current = null;

        // 딜링 완료 후 TURN_PROMPT 적용 (약간의 지연)
        setTimeout(() => {
          // currentBet 업데이트
          if (pendingTurnData.currentBet !== undefined) {
            setGameState((prev) => {
              if (!prev) return prev;
              return { ...prev, currentBet: pendingTurnData.currentBet };
            });
          }

          // minRaise 업데이트
          const raiseAction = pendingTurnData.allowedActions?.find((a: any) => a.type === 'raise' || a.type === 'bet');
          if (raiseAction?.minAmount) {
            setGameState((prev) => {
              if (!prev) return prev;
              return { ...prev, minRaise: raiseAction.minAmount };
            });
            setRaiseAmount(raiseAction.minAmount);
          }

          // 턴 위치 설정
          setCurrentTurnPosition(pendingTurnData.position);
          // 타이머 새로 시작
          setTurnStartTime(Date.now());
          // 자동 폴드 플래그 리셋
          setHasAutoFolded(false);
          // 허용된 액션 설정
          if (pendingTurnData.allowedActions) {
            setAllowedActions(pendingTurnData.allowedActions);
          }
          console.log('🎯 Pending TURN_PROMPT applied:', pendingTurnData.position);
        }, 500); // 딜링 애니메이션 시작 후 적용
      }
    };

    // HAND_STARTED 핸들러 - 새 핸드 시작 (쇼다운 중이면 대기)
    const unsubHandStart = wsClient.on('HAND_STARTED', (data) => {
      console.log('HAND_STARTED received:', data);
      console.log('🎴 HAND_STARTED - isShowdownInProgress:', isShowdownInProgressRef.current);

      // 쇼다운 애니메이션이 진행 중이면 대기열에 저장
      if (isShowdownInProgressRef.current) {
        console.log('⏳ Showdown in progress, queuing HAND_STARTED');
        pendingHandStartedRef.current = data;
        return;
      }

      // 쇼다운 중이 아니면 즉시 처리
      processHandStarted(data);
    });

    // TURN_PROMPT 적용 함수 (핸들러 및 processHandStarted에서 재사용)
    const applyTurnPromptData = (data: any) => {
      console.log('🎯 Applying TURN_PROMPT:', data);

      // currentBet 업데이트
      if (data.currentBet !== undefined) {
        setGameState((prev) => {
          if (!prev) return prev;
          return { ...prev, currentBet: data.currentBet };
        });
      }

      // minRaise 업데이트
      const raiseAction = data.allowedActions?.find((a: any) => a.type === 'raise' || a.type === 'bet');
      if (raiseAction?.minAmount) {
        setGameState((prev) => {
          if (!prev) return prev;
          return { ...prev, minRaise: raiseAction.minAmount };
        });
        setRaiseAmount(raiseAction.minAmount);
      }

      // 턴 위치 설정
      setCurrentTurnPosition(data.position);
      // 서버 타이머 정보 적용
      setTurnStartTime(data.turnStartTime || Date.now());
      setCurrentTurnTime(data.turnTime || DEFAULT_TURN_TIME);
      // 자동 폴드 플래그 리셋
      setHasAutoFolded(false);
      // 허용된 액션 설정
      if (data.allowedActions) {
        setAllowedActions(data.allowedActions);
      }
    };

    // TURN_PROMPT 핸들러 - 차례 알림
    // 서버에서 제공하는 turnStartTime을 사용하여 모든 클라이언트가 동일한 타이머를 표시
    const unsubTurnPrompt = wsClient.on('TURN_PROMPT', (data) => {
      console.log('TURN_PROMPT received:', data);
      console.log('🎯 TURN_PROMPT - isShowdownInProgress:', isShowdownInProgressRef.current);

      // 쇼다운 진행 중이면 대기열에 저장
      if (isShowdownInProgressRef.current) {
        console.log('⏳ Showdown in progress, queuing TURN_PROMPT');
        pendingTurnPromptRef.current = data;
        return;
      }

      // 액션 효과 표시 중이면 대기
      setIsShowingActionEffect((showing) => {
        if (showing) {
          // 액션 효과 표시 중 - 대기열에 저장하고 나중에 적용
          setPendingTurnPosition(data.position);
          setTimeout(() => {
            applyTurnPromptData(data);
          }, 800); // 액션 효과 끝난 후 적용
        } else {
          // 액션 효과 없음 - 즉시 적용
          applyTurnPromptData(data);
        }
        return showing;
      });
    });

    // TURN_CHANGED 핸들러 - 봇 플레이 중 턴 변경
    // 액션 효과가 표시 중이면 대기열에 저장
    const unsubTurnChanged = wsClient.on('TURN_CHANGED', (data) => {
      console.log('TURN_CHANGED received:', data);

      // currentBet 업데이트 (항상 즉시)
      if (data.currentBet !== undefined) {
        setGameState((prev) => {
          if (!prev) return prev;
          return { ...prev, currentBet: data.currentBet };
        });
      }

      // 턴이 변경되면 타이머 초기화 (다음 TURN_PROMPT에서 새로 시작)
      setTurnStartTime(null);

      // 턴 위치 업데이트 (액션 효과 표시 중이면 대기열에 저장)
      if (data.currentPlayer !== undefined && data.currentPlayer !== null) {
        setIsShowingActionEffect((showing) => {
          if (showing) {
            // 액션 효과 표시 중 - 대기열에 저장
            setPendingTurnPosition(data.currentPlayer);
          } else {
            // 액션 효과 없음 - 즉시 적용
            setCurrentTurnPosition(data.currentPlayer);
          }
          return showing;
        });
      }
    });

    // TIMEOUT_FOLD 핸들러 - 타임아웃으로 인한 자동 체크/폴드
    const unsubTimeoutFold = wsClient.on('TIMEOUT_FOLD', (data) => {
      console.log('⏰ TIMEOUT_FOLD received:', data);
      // 타임아웃 액션 표시 (체크 또는 폴드)
      if (data.position !== undefined) {
        // 실제 수행된 액션 표시 (체크 가능하면 체크, 아니면 폴드)
        const actionType = data.action === 'check' ? 'timeout_check' : 'timeout_fold';
        setPlayerActions((prev) => ({
          ...prev,
          [data.position]: {
            type: actionType,
            timestamp: Date.now(),
          },
        }));
      }
    });

    // COMMUNITY_CARDS 핸들러 - 커뮤니티 카드 업데이트 (플롭/턴/리버)
    // 자연스러운 딜레이와 순차 공개 애니메이션 적용
    const unsubCommunityCards = wsClient.on('COMMUNITY_CARDS', (data) => {
      console.log('COMMUNITY_CARDS received:', data);
      if (data.cards) {
        const newCards = parseCards(data.cards);
        // communityCardsRef를 사용하여 현재 카드 수를 정확히 가져옴 (클로저 이슈 방지)
        const currentCount = communityCardsRef.current.length;
        const newCardCount = newCards.length;

        // 새로 추가되는 카드 수 계산
        const cardsToReveal = newCardCount - currentCount;
        console.log(`🃏 Community cards: current=${currentCount}, new=${newCardCount}, toReveal=${cardsToReveal}`);

        if (cardsToReveal > 0) {
          // 커뮤니티 카드 공개 애니메이션 시작
          setIsRevealingCommunity(true);

          // 1. 먼저 페이즈 변경 (즉시)
          setGameState((prev) => {
            if (!prev) return prev;
            return { ...prev, phase: data.phase || prev.phase };
          });

          // 칩은 핸드 종료 시까지 각 플레이어 앞에 유지 (피망 스타일)
          // HAND_RESULT에서만 칩 수집 애니메이션 실행

          // 2. 0.8초 대기 후 카드 공개 시작 (베팅 라운드 종료 → 카드 딜 느낌)
          setTimeout(() => {
            // 카드 데이터 저장 및 ref 업데이트
            setGameState((prev) => {
              if (!prev) return prev;
              communityCardsRef.current = newCards; // ref도 업데이트
              return { ...prev, communityCards: newCards };
            });

            // 3. 순차적으로 카드 공개 (각 카드당 0.3초 간격)
            const CARD_REVEAL_DELAY = 300;
            for (let i = 0; i < cardsToReveal; i++) {
              setTimeout(() => {
                setRevealedCommunityCount(currentCount + i + 1);

                // 마지막 카드 공개 완료
                if (i === cardsToReveal - 1) {
                  setTimeout(() => {
                    setIsRevealingCommunity(false);
                  }, 300);
                }
              }, CARD_REVEAL_DELAY * i);
            }
          }, 800);
        } else {
          // 카드 수가 같거나 적으면 즉시 업데이트 (새 핸드 시작 등)
          setGameState((prev) => {
            if (!prev) return prev;
            communityCardsRef.current = newCards; // ref도 업데이트
            return { ...prev, communityCards: newCards, phase: data.phase || prev.phase };
          });
          setRevealedCommunityCount(newCardCount);
        }
      }
    });

    // 쇼다운 완료 처리 함수 (대기 중인 HAND_STARTED 처리)
    const completeShowdown = () => {
      console.log('✅ Showdown complete');

      // 대기 중인 HAND_STARTED 데이터 먼저 캡처 (나중에 처리하기 위해)
      const pendingData = pendingHandStartedRef.current;
      pendingHandStartedRef.current = null;

      // 쇼다운 UI 정리 (settling 페이즈로 전환)
      setShowdownPhase('settling');

      // 0.5초 대기 후 UI 완전 정리 및 다음 핸드 시작
      setTimeout(() => {
        // 쇼다운 UI 완전 정리
        setShowdownPhase('idle');
        setWinnerPositions([]);
        setWinnerAmounts({});
        setWinnerHandRanks({});
        setWinnerBestCards({});
        setShowdownCards({});
        setIsShowdownDisplay(false);
        setShowdownRevealOrder([]);
        setRevealedPositions(new Set());
        setAllHandRanks({});
        setAllBestFive({});
        setPotChips(0); // POT 칩 초기화

        // 플래그 해제 (새 HAND_STARTED 직접 처리 가능)
        isShowdownInProgressRef.current = false;

        // 대기 중인 HAND_STARTED 처리 (0.3초 추가 딜레이 후)
        setTimeout(() => {
          if (pendingData) {
            console.log('🎴 Processing pending HAND_STARTED after delay');
            processHandStarted(pendingData);
          } else {
            console.log('⚠️ No pending HAND_STARTED to process');
          }
        }, 300);
      }, 500);
    };

    // HAND_RESULT 핸들러 - 핸드 종료 및 쇼다운
    const unsubHandResult = wsClient.on('HAND_RESULT', (data) => {
      console.log('HAND_RESULT received:', data);

      // 쇼다운 진행 중 플래그 설정
      isShowdownInProgressRef.current = true;

      // 타이머 및 턴 완전 초기화 (핸드 종료)
      setTurnStartTime(null);
      setCurrentTurnPosition(null);
      setAllowedActions([]);

      // 액션 표시 초기화 (이전 핸드 액션 라벨 제거)
      setPlayerActions({});

      // 시퀀싱 상태 초기화
      setPendingTurnPosition(null);
      setIsShowingActionEffect(false);

      // 남은 베팅 칩 수집 애니메이션 (totalBet: 핸드 전체 누적 베팅 사용)
      const currentSeats = seatsRef.current;
      const chipsToCollect = currentSeats
        .filter(s => s.totalBet > 0)
        .map(s => ({ position: s.position, amount: s.totalBet }));

      const totalChipsAmount = chipsToCollect.reduce((sum, c) => sum + c.amount, 0);

      if (chipsToCollect.length > 0) {
        setCollectingChips(chipsToCollect);
        setTimeout(() => setIsCollectingToPot(true), 100);

        // 칩 수집 완료 후 (600ms) → POT에 칩 표시
        setTimeout(() => {
          setCollectingChips([]);
          setIsCollectingToPot(false);
          setPotChips(totalChipsAmount); // 중앙에 칩 표시
        }, 700);
      }

      // 페이즈를 showdown으로 변경 + 커뮤니티 카드 유지
      setGameState((prev) => {
        if (!prev) return prev;
        const newCommunityCards = data.communityCards
          ? data.communityCards.map((card: string) => ({
              rank: card.slice(0, -1),
              suit: card.slice(-1),
            }))
          : prev.communityCards;
        return { ...prev, phase: 'showdown', communityCards: newCommunityCards };
      });

      // 쇼다운이 아닌 경우 (모두 폴드로 승자 결정)
      if (!data.showdown || data.showdown.length === 0) {
        // 1.2초 후 승자 표시 (칩 수집 완료 대기)
        setTimeout(() => {
          setIsShowdownDisplay(true);
          if (data.winners && data.winners.length > 0) {
            const winnerSeats = data.winners.map((w: { seat: number }) => w.seat);
            setWinnerPositions(winnerSeats);
            setShowdownPhase('winner_announced');
            const amounts: Record<number, number> = {};
            let totalWinAmount = 0;
            data.winners.forEach((w: { seat: number; amount: number }) => {
              amounts[w.seat] = w.amount;
              totalWinAmount += w.amount;
            });
            setWinnerAmounts(amounts);

            // 1초 대기 후 POT에서 승자에게 칩 분배
            if (winnerSeats.length > 0 && totalWinAmount > 0) {
              setTimeout(() => {
                setPotChips(0); // POT 칩 제거
                setDistributingChip({
                  amount: totalWinAmount,
                  toPosition: winnerSeats[0],
                });
              }, 1000);
            }
          }
          fetchUser();

          // 5초 후 쇼다운 완료 처리 (정산 확인 시간)
          setTimeout(() => {
            completeShowdown();
          }, 5000);
        }, 1200);
        return;
      }

      // ========================================
      // 순차적 쇼다운 시작 (인트로 애니메이션 포함)
      // ========================================

      // 커뮤니티 카드 파싱
      let communityCards: Card[] = [];
      if (data.communityCards && data.communityCards.length > 0) {
        communityCards = data.communityCards.map((card: string) => ({
          rank: card.slice(0, -1),
          suit: card.slice(-1),
        }));
      }
      if (communityCards.length === 0 && communityCardsRef.current.length > 0) {
        communityCards = communityCardsRef.current;
      }

      // 쇼다운 카드 및 족보 계산 (모든 플레이어)
      const cardsMap: Record<number, Card[]> = {};
      const handRanksAll: Record<number, string> = {};
      const bestCardsAll: Record<number, Card[]> = {};
      const positions: number[] = [];

      data.showdown.forEach((sd: { seat: number; position: number; holeCards: string[] }) => {
        const pos = sd.seat ?? sd.position;
        if (sd.holeCards && sd.holeCards.length > 0) {
          positions.push(pos);
          const holeCards = sd.holeCards.map((card: string) => ({
            rank: card.slice(0, -1),
            suit: card.slice(-1),
          }));
          cardsMap[pos] = holeCards;

          if (communityCards.length >= 3) {
            const result = analyzeHand(holeCards, communityCards);
            if (result.hand) {
              handRanksAll[pos] = result.hand.name;
              bestCardsAll[pos] = result.hand.bestFive;
            }
          }
        }
      });

      // 공개 순서 결정
      const currentDealer = dealerPosition ?? 0;
      const maxSeats = 9;
      const sortedPositions = [...positions].sort((a, b) => {
        const aOffset = (a - currentDealer + maxSeats) % maxSeats;
        const bOffset = (b - currentDealer + maxSeats) % maxSeats;
        return aOffset - bOffset;
      });

      // 승자 정보 저장
      const winnerSeats = data.winners?.map((w: { seat: number }) => w.seat) || [];
      const amounts: Record<number, number> = {};
      data.winners?.forEach((w: { seat: number; amount: number }) => {
        amounts[w.seat] = w.amount;
      });
      const winnerHandRanksMap: Record<number, string> = {};
      const winnerBestCardsMap: Record<number, Card[]> = {};
      winnerSeats.forEach((pos: number) => {
        if (handRanksAll[pos]) winnerHandRanksMap[pos] = handRanksAll[pos];
        if (bestCardsAll[pos]) winnerBestCardsMap[pos] = bestCardsAll[pos];
      });

      // 타이밍 상수
      const INTRO_DURATION = 1500; // 인트로 애니메이션 시간
      const REVEAL_DELAY = 1500; // 각 플레이어 공개 간격
      const WINNER_DISPLAY_TIME = 4000; // 승자 표시 시간 (정산 확인)

      // 쇼다운 카드 데이터를 먼저 설정 (intro 중에도 자신의 카드가 보이도록)
      setShowdownCards(cardsMap);
      setAllHandRanks(handRanksAll);
      setAllBestFive(bestCardsAll);
      setShowdownRevealOrder(sortedPositions);

      // 1단계: 인트로 애니메이션 ("SHOWDOWN!" 텍스트)
      console.log('🎭 Showdown intro starting');
      setIsShowdownDisplay(true);
      setShowdownPhase('intro');
      setRevealedPositions(new Set());

      // 2단계: 인트로 후 카드 공개 시작
      setTimeout(() => {
        console.log('🎭 Intro complete, starting reveal');
        setShowdownPhase('revealing');

        // 3단계: 순차적 카드 공개
        sortedPositions.forEach((pos, index) => {
          setTimeout(() => {
            setRevealedPositions(prev => new Set([...prev, pos]));
            console.log(`🃏 Revealing cards for position ${pos}`);

            // 마지막 플레이어 공개 후 승자 발표
            if (index === sortedPositions.length - 1) {
              setTimeout(() => {
                // 4단계: 승자 발표
                setShowdownPhase('winner_announced');
                setWinnerPositions(winnerSeats);
                setWinnerAmounts(amounts);
                setWinnerHandRanks(winnerHandRanksMap);
                setWinnerBestCards(winnerBestCardsMap);
                console.log('🏆 Winner announced:', winnerSeats);

                // POT에서 첫 번째 승자에게 칩 분배 애니메이션
                const totalWinAmount = Object.values(amounts).reduce((sum, amt) => sum + amt, 0);
                if (winnerSeats.length > 0 && totalWinAmount > 0) {
                  // 1초 대기 후 POT 칩을 승자에게 분배
                  setTimeout(() => {
                    setPotChips(0); // POT 칩 제거
                    setDistributingChip({
                      amount: totalWinAmount,
                      toPosition: winnerSeats[0],
                    });
                  }, 1000);
                }

                // 5단계: 승자 표시 후 쇼다운 완료
                setTimeout(() => {
                  completeShowdown();
                }, WINNER_DISPLAY_TIME);
              }, 800);
            }
          }, REVEAL_DELAY * index);
        });
      }, INTRO_DURATION);

      // 잔액 업데이트
      fetchUser();
    });

    // PLAYER_ELIMINATED 핸들러 - 플레이어 탈락 (stack=0)
    const unsubPlayerEliminated = wsClient.on('PLAYER_ELIMINATED', (data) => {
      console.log('PLAYER_ELIMINATED received:', data);
      if (data.eliminatedPlayers && data.eliminatedPlayers.length > 0) {
        const eliminatedSeats = data.eliminatedPlayers.map((p: { seat: number }) => p.seat);
        setEliminatedPositions(eliminatedSeats);

        // 탈락 애니메이션 후 seats 상태 업데이트 (3초 후)
        setTimeout(() => {
          setSeats(prev => prev.map(seat => {
            if (eliminatedSeats.includes(seat.position)) {
              return { ...seat, stack: 0, status: 'sitting_out' };
            }
            return seat;
          }));
          // 애니메이션 상태 초기화 (다음 핸드 전까지 유지하다가)
          setEliminatedPositions([]);
        }, 3000);
      }
    });

    // Handle reconnection - update connected state
    const unsubConnectionState = wsClient.on('CONNECTION_STATE', (data) => {
      if (data.state === 'connected') {
        setIsConnected(true);
        // Re-subscribe to table after reconnection
        wsClient.send('SUBSCRIBE_TABLE', { tableId: tableId });
      } else {
        setIsConnected(false);
      }
    });

    // Handle send failures - notify user when actions fail to send
    const unsubSendFailed = wsClient.on('SEND_FAILED', (data) => {
      if (data.event !== 'PING') { // Ignore PING failures
        setError(`액션 전송 실패: 서버에 연결되지 않았습니다.`);
      }
    });

    // Handle connection lost
    const unsubConnectionLost = wsClient.on('CONNECTION_LOST', () => {
      setIsConnected(false);
      setError('서버와의 연결이 끊어졌습니다. 페이지를 새로고침해주세요.');
    });

    return () => {
      unsubTableSnapshot();
      unsubTableUpdate();
      unsubActionResult();
      unsubSeatResult();
      unsubError();
      unsubLeaveResult();
      unsubAddBotResult();
      unsubBotLoopResult();
      unsubGameStarting();
      unsubHandStart();
      unsubTurnPrompt();
      unsubTurnChanged();
      unsubTimeoutFold();
      unsubCommunityCards();
      unsubHandResult();
      unsubPlayerEliminated();
      unsubConnectionState();
      unsubSendFailed();
      unsubConnectionLost();
      wsClient.send('UNSUBSCRIBE_TABLE', { tableId: tableId });
    };
  }, [tableId, router, fetchUser, user?.id]);

  // Action handlers - 백엔드는 tableId, actionType을 기대
  const handleFold = useCallback(() => {
    setShowRaiseSlider(false);
    wsClient.send('ACTION_REQUEST', {
      tableId: tableId,
      actionType: 'fold',
    });
  }, [tableId]);

  const handleCheck = useCallback(() => {
    setShowRaiseSlider(false);
    wsClient.send('ACTION_REQUEST', {
      tableId: tableId,
      actionType: 'check',
    });
  }, [tableId]);

  const handleCall = useCallback(() => {
    setShowRaiseSlider(false);
    wsClient.send('ACTION_REQUEST', {
      tableId: tableId,
      actionType: 'call',
    });
  }, [tableId]);

  const handleRaise = useCallback(() => {
    setShowRaiseSlider(false);
    wsClient.send('ACTION_REQUEST', {
      tableId: tableId,
      actionType: 'raise',
      amount: raiseAmount,
    });
  }, [tableId, raiseAmount]);

  const handleAllIn = useCallback(() => {
    setShowRaiseSlider(false);
    wsClient.send('ACTION_REQUEST', {
      tableId: tableId,
      actionType: 'all_in',
    });
  }, [tableId]);

  // 자동 폴드 핸들러 (타이머 만료 시)
  const handleAutoFold = useCallback(() => {
    if (hasAutoFolded) return; // 중복 호출 방지
    setHasAutoFolded(true);
    setShowRaiseSlider(false);
    console.log('Auto-fold triggered');
    wsClient.send('ACTION_REQUEST', {
      tableId: tableId,
      actionType: 'fold',
    });
  }, [tableId, hasAutoFolded]);

  const handleLeave = useCallback(() => {
    if (isLeaving) return;
    setIsLeaving(true);
    setError(null);
    wsClient.send('LEAVE_REQUEST', { tableId: tableId });
    // Navigation will happen in LEAVE_RESULT handler
  }, [tableId, isLeaving]);


  // 참여하기 버튼 클릭 - 바이인 모달 표시
  const handleJoinClick = useCallback(() => {
    console.log('🎯 handleJoinClick called, isSpectator:', myPosition === null, 'user:', !!user);
    setError(null);
    setShowBuyInModal(true);
  }, [myPosition, user]);

  // 바이인 확인 - SEAT_REQUEST 전송
  const handleBuyInConfirm = useCallback((buyIn: number) => {
    setIsJoining(true);
    wsClient.send('SEAT_REQUEST', {
      tableId: tableId,
      buyInAmount: buyIn,
    });
  }, [tableId]);

  // 바이인 취소
  const handleBuyInCancel = useCallback(() => {
    setShowBuyInModal(false);
  }, []);

  // 게임 시작 핸들러
  const handleStartGame = useCallback(() => {
    wsClient.send('START_GAME', { tableId: tableId });
  }, [tableId]);

  // 봇 추가 핸들러
  const handleAddBot = useCallback(() => {
    if (isAddingBot) return;
    setIsAddingBot(true);
    setError(null);
    wsClient.send('ADD_BOT_REQUEST', {
      tableId: tableId,
      buyIn: tableConfig?.minBuyIn || 1000,
    });
  }, [tableId, tableConfig, isAddingBot]);

  // 봇 자동 루프 시작 핸들러
  const handleStartBotLoop = useCallback(() => {
    if (isStartingLoop) return;
    setIsStartingLoop(true);
    setError(null);
    wsClient.send('START_BOT_LOOP_REQUEST', {
      tableId: tableId,
      botCount: 4,
      buyIn: tableConfig?.minBuyIn || 1000,
    });
  }, [tableId, tableConfig, isStartingLoop]);

  // [DEV] 전체 리셋 핸들러 (봇 제거 + 테이블 리셋 통합)
  const handleDevReset = useCallback(async () => {
    if (isResetting) return;
    setIsResetting(true);
    setError(null);
    try {
      const token = localStorage.getItem('access_token');
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

      // 1. 먼저 봇 제거
      await fetch(`${baseUrl}/api/v1/rooms/${tableId}/dev/remove-bots`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });

      // 2. 테이블 리셋
      const res = await fetch(`${baseUrl}/api/v1/rooms/${tableId}/dev/reset`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const data = await res.json();
      if (data.success) {
        // 상태 초기화
        setSeats([]);
        setMyPosition(null);
        setMyHoleCards([]);
        setCurrentTurnPosition(null);
        setPlayerActions({});
        setAllowedActions([]);
        setGameState(null);
        // 테이블 다시 구독
        wsClient.send('SUBSCRIBE_TABLE', { tableId });
      } else {
        setError(data.message || '리셋 실패');
      }
    } catch (err) {
      setError('리셋 중 오류 발생');
    } finally {
      setIsResetting(false);
    }
  }, [tableId, isResetting]);

  // 내 좌석 정보 가져오기
  const mySeat = seats.find((s) => s.player?.userId === user?.id);
  const myStack = mySeat?.stack || 0;

  // 실시간 족보 계산 (내 홀카드 + 커뮤니티 카드)
  const myHandAnalysis = useMemo(() => {
    if (myHoleCards.length === 0) return { hand: null, draws: [] };
    const communityCards = gameState?.communityCards || [];
    return analyzeHand(myHoleCards, communityCards);
  }, [myHoleCards, gameState?.communityCards]);

  // communityCardsRef 업데이트 (HAND_RESULT에서 접근용)
  useEffect(() => {
    if (gameState?.communityCards) {
      communityCardsRef.current = gameState.communityCards;
    }
  }, [gameState?.communityCards]);

  // 서버에서 받은 allowedActions 기반으로 액션 정보 추출
  const canFold = allowedActions.some(a => a.type === 'fold');
  const canCheck = allowedActions.some(a => a.type === 'check');
  const canCall = allowedActions.some(a => a.type === 'call');
  const canBet = allowedActions.some(a => a.type === 'bet');
  const canRaise = allowedActions.some(a => a.type === 'raise');

  // 콜 금액은 서버에서 받은 값 사용
  const callAction = allowedActions.find(a => a.type === 'call');
  const callAmount = callAction?.minAmount || callAction?.amount || 0;

  // 레이즈/베팅 최소/최대값
  const raiseOrBetAction = allowedActions.find(a => a.type === 'raise' || a.type === 'bet');
  const minRaiseAmount = raiseOrBetAction?.minAmount || gameState?.minRaise || 0;
  const maxRaiseAmount = raiseOrBetAction?.maxAmount || myStack;

  // 좌석 데이터를 Player 형식으로 변환 (상대적 위치 적용)
  const getRelativePosition = (playerSeatIndex: number) => {
    if (myPosition === null) return playerSeatIndex; // 관전자는 그대로
    const totalSeats = SEAT_POSITIONS.length;
    return (playerSeatIndex - myPosition + totalSeats) % totalSeats;
  };

  return (
    <div className="min-h-screen flex justify-center items-center bg-black">
      {/* Mobile container - 배경 이미지 비율(2218:4518 ≈ 1:2.04)에 맞춤 */}
      <div
        className="w-full max-w-[500px] max-h-screen flex flex-col bg-contain bg-center bg-no-repeat relative"
        style={{
          backgroundImage: "url('/assets/images/backgrounds/background_game.webp')",
          aspectRatio: '2218 / 4518',
        }}
      >
      {/* 좌표 그리드 (개발용) - 전체 화면 */}
      <div className="absolute inset-0 pointer-events-none z-50">
        {/* 가로선 (10% 간격) */}
        {[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100].map((percent) => (
          <div
            key={`h-${percent}`}
            className="absolute left-0 right-0 border-t border-cyan-500/30"
            style={{ top: `${percent}%` }}
          >
            <span className="absolute left-1 text-[10px] text-cyan-400 bg-black/50 px-1">
              {percent}%
            </span>
          </div>
        ))}
        {/* 세로선 (10% 간격) */}
        {[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100].map((percent) => (
          <div
            key={`v-${percent}`}
            className="absolute top-0 bottom-0 border-l border-cyan-500/30"
            style={{ left: `${percent}%` }}
          >
            <span className="absolute top-1 text-[10px] text-cyan-400 bg-black/50 px-1">
              {percent}%
            </span>
          </div>
        ))}
        {/* 현재 좌석 위치 표시 */}
        {SEAT_POSITIONS.map((pos, i) => (
          <div
            key={`seat-marker-${i}`}
            className="absolute w-4 h-4 bg-red-500 rounded-full border-2 border-white flex items-center justify-center text-[8px] text-white font-bold"
            style={{
              top: pos.top,
              left: pos.left,
              transform: 'translate(-50%, -50%)',
            }}
          >
            {i}
          </div>
        ))}
      </div>

      {/* Header */}
      <header className="px-4 py-3">
        <div className="flex justify-between items-center max-w-7xl mx-auto">
          <button
            onClick={handleLeave}
            disabled={isLeaving}
            className="btn btn-secondary btn-sm"
            data-testid="leave-button"
          >
            {isLeaving ? '퇴장 중...' : '← 로비로 돌아가기'}
          </button>

          <div className="flex items-center gap-4">
            <div className="text-center" data-testid="game-phase" data-phase={gameState?.phase || 'waiting'}>
              <div className="text-xs text-[var(--text-muted)]">페이즈</div>
              <div className="text-sm font-bold uppercase">
                {gameState?.phase || 'waiting'}
              </div>
            </div>
            <div className="text-center">
              <div className="text-xs text-[var(--text-muted)]">블라인드</div>
              <div className="text-sm font-bold">
                {gameState?.smallBlind || 0} / {gameState?.bigBlind || 0}
              </div>
            </div>
            <div className="text-center">
              <div className="text-xs text-[var(--text-muted)]">팟</div>
              <div className="text-sm font-bold text-[var(--accent)] tabular-nums">
                {animatedPot.toLocaleString()}
              </div>
            </div>
            <div
              className={`badge ${
                isConnected ? 'badge-success' : 'badge-error'
              }`}
            >
              {isConnected ? 'Connected' : 'Disconnected'}
            </div>
          </div>
        </div>
      </header>

      {/* Error Banner - 절대 위치로 레이아웃 영향 없음 */}
      {error && (
        <div className="absolute top-14 left-0 right-0 z-50 bg-[var(--error-bg)] text-[var(--error)] p-3 text-center text-sm">
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-4 underline"
          >
            닫기
          </button>
        </div>
      )}

      {/* Game Table */}
      <main ref={tableRef} className="flex-1 relative overflow-hidden" data-testid="poker-table">
          {/* 딜링 애니메이션 */}
          <DealingAnimation
            isDealing={isDealing}
            dealingSequence={dealingSequence}
            onDealingComplete={handleDealingComplete}
            tableCenter={tableCenter}
            playerPositions={playerPositions}
          />

          {/* Community Cards - centered on table felt */}
          <div className="absolute top-[48%] left-1/2 -translate-x-1/2 -translate-y-1/2 flex gap-[5px]" data-testid="community-cards">
            {gameState?.communityCards?.map((card, i) => {
              // 공개된 카드만 표시 (revealedCommunityCount 기준)
              const isRevealed = i < revealedCommunityCount;
              // 새로 공개되는 카드인지 확인 (좌측부터 순서대로 애니메이션)
              const isNewlyRevealed = isRevealingCommunity && i === revealedCommunityCount - 1;
              // 쇼다운 시 bestFive에 포함된 카드인지 확인
              const allBestCards = Object.values(winnerBestCards).flat();
              const isInWinningHand = isShowdownDisplay && allBestCards.length > 0 && isCardInBestFive(card, allBestCards);
              const shouldDim = isShowdownDisplay && allBestCards.length > 0 && !isInWinningHand;

              // 커뮤니티 카드 wrapper 스타일 (크기: 47x66, 기존 대비 10% 축소)
              // 애니메이션은 PlayingCard 내부에서 처리
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
              length: 5 - (gameState?.communityCards?.length || 0),
            }).map((_, i) => (
              <div
                key={`placeholder-${i}`}
                className="w-[47px] h-[66px] rounded-md border-[1.8px] border-dashed border-white/20"
              />
            ))}
          </div>

          {/* Pot Display */}
          <div className="absolute top-[39%] left-1/2 -translate-x-1/2 text-center" data-testid="pot-amount">
            <div className="text-white font-bold text-xl drop-shadow-lg tabular-nums">
              {animatedPot.toLocaleString()}
            </div>
          </div>

          {/* 내 족보 표시 - 커뮤니티 카드와 내 홀카드 사이 */}
          {!isSpectator && myHoleCards.length > 0 && myCardsRevealed && myHandAnalysis.hand && (
            <div className="absolute top-[54%] left-1/2 -translate-x-1/2 z-10">
              <div className="px-3 py-1 bg-black/70 backdrop-blur-sm rounded text-center">
                <span className="text-sm font-bold text-yellow-400">
                  {myHandAnalysis.hand.description}
                </span>
                {myHandAnalysis.draws && myHandAnalysis.draws.length > 0 && (
                  <span className="text-sm text-cyan-400 ml-1">
                    + {myHandAnalysis.draws[0]}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Side Pots Display */}
          {sidePots.length > 0 && (
            <div className="absolute top-[42%] left-1/2 -translate-x-1/2 flex gap-2">
              {sidePots.map((sidePot, index) => (
                <div
                  key={index}
                  className="px-2 py-1 bg-yellow-600/80 rounded text-xs text-white"
                  data-testid={`side-pot-${index}`}
                  data-amount={sidePot.amount}
                  data-players={sidePot.eligiblePlayers.join(',')}
                >
                  Side Pot {index + 1}: {sidePot.amount.toLocaleString()}
                </div>
              ))}
            </div>
          )}

          {/* Dealer Button */}
          {dealerPosition !== null && SEAT_POSITIONS[getRelativePosition(dealerPosition)] && gameState?.phase !== 'waiting' && (
            <div
              className="absolute w-6 h-6 rounded-full bg-white text-black text-[10px] font-bold flex items-center justify-center shadow-lg border-2 border-yellow-400 z-20"
              style={{
                top: SEAT_POSITIONS[getRelativePosition(dealerPosition)].top,
                left: SEAT_POSITIONS[getRelativePosition(dealerPosition)].left,
                transform: 'translate(-180%, -70%)',
              }}
              data-testid="dealer-button"
              data-position={dealerPosition}
            >
              D
            </div>
          )}

          {/* Small Blind Marker */}
          {smallBlindPosition !== null && gameState?.phase !== 'waiting' && (
            <div
              className="absolute w-5 h-5 rounded-full bg-blue-500 text-white text-[10px] font-bold flex items-center justify-center shadow-lg z-10"
              style={{
                top: SEAT_POSITIONS[getRelativePosition(smallBlindPosition)]?.top,
                left: SEAT_POSITIONS[getRelativePosition(smallBlindPosition)]?.left,
                transform: 'translate(50%, -50%)',
              }}
              data-testid="small-blind-marker"
              data-position={smallBlindPosition}
            >
              SB
            </div>
          )}

          {/* Big Blind Marker */}
          {bigBlindPosition !== null && gameState?.phase !== 'waiting' && (
            <div
              className="absolute w-5 h-5 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center shadow-lg z-10"
              style={{
                top: SEAT_POSITIONS[getRelativePosition(bigBlindPosition)]?.top,
                left: SEAT_POSITIONS[getRelativePosition(bigBlindPosition)]?.left,
                transform: 'translate(50%, 50%)',
              }}
              data-testid="big-blind-marker"
              data-position={bigBlindPosition}
            >
              BB
            </div>
          )}


          {/* Countdown Overlay */}
          {countdown !== null && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/50 z-20">
              <div className="text-center animate-pulse">
                <div className="text-6xl font-bold text-white mb-4 drop-shadow-lg">
                  {countdown}
                </div>
                <div className="text-xl text-white/80 drop-shadow-lg">
                  게임이 곧 시작됩니다!
                </div>
              </div>
            </div>
          )}

          {/* Player Seats - 상대적 위치 적용 */}
          {SEAT_POSITIONS.map((pos, visualIndex) => {
            // seats 배열에서 해당 시각적 위치에 맞는 플레이어 찾기
            const seat = seats.find((s) => getRelativePosition(s.position) === visualIndex);

            // 현재 유저인지 확인
            const isCurrentUser = seat?.player?.userId === user?.id;

            // 게임이 진행 중인지 확인 (waiting이 아니면 카드를 받은 상태)
            const gameInProgress = gameState?.phase && gameState.phase !== 'waiting';

            // 쇼다운 시 상대방 카드 (공개된 카드) - 순차 공개 적용
            // revealedPositions에 포함된 위치만 카드 표시
            const isPositionRevealed = seat && revealedPositions.has(seat.position);
            const showdownPlayerCards = (seat && isShowdownDisplay && isPositionRevealed) ? showdownCards[seat.position] : undefined;

            // 카드 결정: 내 카드 / 쇼다운 시 공개된 카드 / 빈 배열
            // 쇼다운 중에는 자신도 showdownCards에서 카드를 가져와야 함 (새 핸드 시작으로 myHoleCards가 변경되어도 쇼다운 UI는 유지)
            const playerCards = isCurrentUser
              ? (showdownPhase !== 'idle' && seat && showdownCards[seat.position]?.length > 0
                  ? showdownCards[seat.position]
                  : myHoleCards)
              : (showdownPlayerCards || []);

            // seat 데이터를 Player 형식으로 변환
            const player = seat?.player ? {
              id: seat.player.userId,
              username: seat.player.nickname,
              chips: seat.stack,
              cards: playerCards,
              bet: seat.betAmount,
              folded: seat.status === 'folded',
              isActive: seat.status === 'active',
              seatIndex: seat.position,
              // 게임 진행 중이고 폴드하지 않았으면 카드를 가진 것
              hasCards: !!(gameInProgress && seat.status !== 'folded' && seat.status !== 'waiting'),
              // 승자 여부 - showdownPhase가 winner_announced일 때만 표시
              isWinner: showdownPhase === 'winner_announced' && winnerPositions.includes(seat.position),
              // 승리 금액
              winAmount: showdownPhase === 'winner_announced' ? winnerAmounts[seat.position] : undefined,
              // 족보 - 순차 공개 중에는 공개된 플레이어의 족보 표시, 승자 발표 후에는 승자 족보
              winHandRank: isPositionRevealed ? allHandRanks[seat.position] : undefined,
            } : undefined;

            // 현재 턴인지 확인 (position 기반)
            const isActiveTurn = seat?.position === currentTurnPosition;

            // 해당 플레이어의 마지막 액션
            const lastAction = seat ? playerActions[seat.position] : null;

            return (
              <PlayerSeat
                key={visualIndex}
                player={player}
                position={pos}
                seatPosition={visualIndex}
                isCurrentUser={isCurrentUser}
                isActive={isActiveTurn}
                lastAction={lastAction}
                turnStartTime={isActiveTurn ? turnStartTime : null}
                turnTime={isActiveTurn ? currentTurnTime : undefined}
                onAutoFold={isCurrentUser && isActiveTurn ? handleAutoFold : undefined}
                handResult={isCurrentUser ? myHandAnalysis.hand : null}
                draws={isCurrentUser ? myHandAnalysis.draws : []}
                onSeatClick={isSpectator ? () => handleJoinClick() : undefined}
                showJoinBubble={isSpectator && visualIndex === 0 && !player}
                bestFiveCards={seat && showdownPhase === 'winner_announced' ? winnerBestCards[seat.position] : undefined}
                isCardsRevealed={isCurrentUser ? (myCardsRevealed || ['intro', 'revealing', 'winner_announced'].includes(showdownPhase)) : undefined}
                onRevealCards={isCurrentUser ? handleRevealCards : undefined}
                isDealingComplete={dealingComplete}
                isEliminated={seat ? eliminatedPositions.includes(seat.position) : false}
                isShowdownRevealed={isCurrentUser && seat ? revealedPositions.has(seat.position) : false}
              />
            );
          })}

          {/* ========================================
              베팅 칩 렌더링
              - 각 플레이어의 베팅 칩 표시
              - 수집/분배 애니메이션 지원
              ======================================== */}
          {/* 각 좌석의 베팅 칩 (totalBet: 핸드 전체 누적 베팅) */}
          {seats.map((seat) => {
            const visualPosition = getRelativePosition(seat.position);
            // 수집 애니메이션 중인 칩은 여기서 렌더링하지 않음
            const isBeingCollected = collectingChips.some(c => c.position === seat.position);
            if (seat.totalBet > 0 && !isBeingCollected) {
              return (
                <BettingChips
                  key={`chip-${seat.position}`}
                  amount={seat.totalBet}
                  position={CHIP_POSITIONS[visualPosition]}
                />
              );
            }
            return null;
          })}

          {/* 수집 중인 칩 (POT으로 이동 애니메이션) */}
          {collectingChips.map((chip, idx) => (
            <BettingChips
              key={`collecting-${idx}`}
              amount={chip.amount}
              position={CHIP_POSITIONS[getRelativePosition(chip.position)]}
              isAnimating={isCollectingToPot}
              animateTo={POT_POSITION}
            />
          ))}

          {/* 중앙 POT에 쌓인 칩 (수집 완료 후, 분배 전) */}
          {potChips > 0 && (
            <BettingChips
              amount={potChips}
              position={POT_POSITION}
            />
          )}

          {/* 분배 중인 칩 (POT에서 승자로 이동) */}
          {distributingChip && (
            <BettingChips
              amount={distributingChip.amount}
              position={POT_POSITION}
              isAnimating={true}
              animateTo={CHIP_POSITIONS[getRelativePosition(distributingChip.toPosition)]}
              onAnimationEnd={() => {
                setDistributingChip(null);
              }}
            />
          )}
      </main>

      {/* ========================================
          쇼다운 인트로 오버레이
          - 화면 어둡게 + "SHOWDOWN!" 텍스트 애니메이션
          ======================================== */}
      {showdownPhase === 'intro' && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 animate-fade-in px-4">
          <div className="text-center max-w-full">
            <h1 className="text-[clamp(2.5rem,12vw,6rem)] font-black text-transparent bg-clip-text bg-gradient-to-r from-yellow-400 via-red-500 to-yellow-400 animate-showdown-text drop-shadow-[0_0_30px_rgba(255,200,0,0.8)]">
              SHOWDOWN!
            </h1>
            <div className="mt-4 text-white/80 text-lg md:text-xl animate-pulse">
              카드를 공개합니다
            </div>
          </div>
        </div>
      )}


      {/* ========================================
          하단 액션 패널 (고정 높이: 120px)
          - 모든 상태에서 동일한 높이 유지
          - 레이아웃 시프트 방지
          ======================================== */}
      <footer className="px-4 py-2 relative">
        <div className="max-w-4xl mx-auto h-[120px]">
          {/* 관전자 모드: 빈 공간 (프로필 말풍선으로 참여 유도) */}
          {isSpectator ? (
            <div className="text-center">
              <p className="text-[var(--text-secondary)] text-sm">
                관전 중 - 위 프로필을 클릭하여 참여하세요
              </p>
            </div>
          ) : isMyTurn ? (
            <div className="absolute -top-12 left-0 right-0 flex flex-col items-center gap-2">
              {/* 레이즈 슬라이더 팝업 */}
              {showRaiseSlider && (canBet || canRaise) && (
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 bg-black/90 border border-white/20 rounded-lg p-4 min-w-[280px] z-50">
                  <div className="flex flex-col gap-3">
                    <div className="flex items-center justify-between">
                      <span className="text-white text-sm">레이즈 금액</span>
                      <button
                        onClick={() => setShowRaiseSlider(false)}
                        className="text-white/60 hover:text-white text-xl leading-none"
                      >
                        ×
                      </button>
                    </div>
                    <input
                      type="range"
                      min={minRaiseAmount}
                      max={maxRaiseAmount}
                      value={raiseAmount}
                      onChange={(e) => setRaiseAmount(parseInt(e.target.value))}
                      className="w-full"
                      data-testid="raise-slider"
                    />
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        value={raiseAmount}
                        onChange={(e) => setRaiseAmount(parseInt(e.target.value) || minRaiseAmount)}
                        className="flex-1 bg-white/10 border border-white/20 rounded px-3 py-2 text-white text-center"
                        min={minRaiseAmount}
                        max={maxRaiseAmount}
                        data-testid="raise-input"
                      />
                      <button
                        onClick={() => {
                          handleRaise();
                          setShowRaiseSlider(false);
                        }}
                        disabled={raiseAmount < minRaiseAmount}
                        className="bg-yellow-500 hover:bg-yellow-400 disabled:bg-gray-500 text-black font-bold px-4 py-2 rounded transition-colors"
                      >
                        확인
                      </button>
                    </div>
                    {/* 퀵 버튼 */}
                    <div className="flex gap-2">
                      <button
                        onClick={() => setRaiseAmount(minRaiseAmount)}
                        className="flex-1 bg-white/10 hover:bg-white/20 text-white text-xs py-1 rounded"
                      >
                        최소
                      </button>
                      <button
                        onClick={() => setRaiseAmount(Math.floor((minRaiseAmount + maxRaiseAmount) / 2))}
                        className="flex-1 bg-white/10 hover:bg-white/20 text-white text-xs py-1 rounded"
                      >
                        1/2
                      </button>
                      <button
                        onClick={() => setRaiseAmount(Math.floor(maxRaiseAmount * 0.75))}
                        className="flex-1 bg-white/10 hover:bg-white/20 text-white text-xs py-1 rounded"
                      >
                        3/4
                      </button>
                      <button
                        onClick={() => setRaiseAmount(maxRaiseAmount)}
                        className="flex-1 bg-white/10 hover:bg-white/20 text-white text-xs py-1 rounded"
                      >
                        MAX
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* 액션 버튼 영역 */}
              <div className="flex gap-2 justify-center items-center">
                {/* 폴드 버튼 */}
                {canFold && (
                  <button
                    onClick={handleFold}
                    className="relative hover:scale-105 active:scale-95 transition-transform"
                    data-testid="fold-button"
                  >
                    <img src="/assets/ui/btn_fold.png?v=3" alt="폴드" className="h-[53px]" />
                    <span className="absolute inset-0 flex items-center justify-center text-white font-bold text-sm drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)]">
                      폴드
                    </span>
                  </button>
                )}

                {/* 체크 버튼 */}
                {canCheck && (
                  <button
                    onClick={handleCheck}
                    className="relative hover:scale-105 active:scale-95 transition-transform"
                    data-testid="check-button"
                  >
                    <img src="/assets/ui/btn_check.png?v=3" alt="체크" className="h-[53px]" />
                    <span className="absolute inset-0 flex items-center justify-center text-white font-bold text-sm drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)]">
                      체크
                    </span>
                  </button>
                )}

                {/* 콜 버튼 */}
                {canCall && (
                  <button
                    onClick={handleCall}
                    className="relative hover:scale-105 active:scale-95 transition-transform"
                    data-testid="call-button"
                  >
                    <img src="/assets/ui/btn_call.png?v=3" alt="콜" className="h-[53px]" />
                    <span className="absolute inset-0 flex items-center justify-center text-white font-bold text-sm drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)]">
                      콜{callAmount > 0 && <span className="text-yellow-300">({callAmount.toLocaleString()})</span>}
                    </span>
                  </button>
                )}

                {/* 레이즈 버튼 - 클릭하면 슬라이더 팝업 */}
                {(canBet || canRaise) && (
                  <button
                    onClick={() => setShowRaiseSlider(!showRaiseSlider)}
                    className="relative hover:scale-105 active:scale-95 transition-transform"
                    data-testid="raise-button"
                  >
                    <img src="/assets/ui/btn_raise.png?v=3" alt="레이즈" className="h-[53px]" />
                    <span className="absolute inset-0 flex items-center justify-center text-white font-bold text-sm drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)]">
                      레이즈<span className="text-yellow-300">({raiseAmount.toLocaleString()})</span>
                    </span>
                  </button>
                )}

                {/* 올인 버튼 */}
                {(canRaise || canBet || canCall) && (
                  <button
                    onClick={handleAllIn}
                    className="relative hover:scale-105 active:scale-95 transition-transform"
                    data-testid="allin-button"
                  >
                    <img src="/assets/ui/btn_allin.png?v=3" alt="올인" className="h-[53px]" />
                    <span className="absolute inset-0 flex items-center justify-center text-white font-bold text-sm drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)]">
                      올인
                    </span>
                  </button>
                )}
              </div>
            </div>
          ) : (
            /* 내 턴이 아닐 때 - 대기 상태 */
            <div className="flex flex-col items-center justify-center h-full">
              {currentTurnPosition !== null ? (
                <p className="text-[var(--text-secondary)] text-sm">
                  다른 플레이어의 차례를 기다리는 중...
                </p>
              ) : gameState?.phase === 'waiting' || !gameState?.phase ? (
                <div className="flex flex-col items-center gap-2">
                  <p className="text-[var(--text-secondary)] text-sm">
                    참가자: {seats.filter(s => s.player && s.status !== 'empty').length}명
                  </p>
                  <button
                    onClick={handleStartGame}
                    disabled={seats.filter(s => s.player && s.status !== 'empty').length < 2}
                    className="px-6 py-2 rounded-lg font-bold text-black bg-gradient-to-r from-yellow-400 via-yellow-500 to-amber-500 hover:from-yellow-300 hover:via-yellow-400 hover:to-amber-400 disabled:from-gray-500 disabled:via-gray-600 disabled:to-gray-700 disabled:text-gray-400 disabled:cursor-not-allowed shadow-lg transition-all duration-200"
                  >
                    게임 시작
                  </button>
                  {seats.filter(s => s.player && s.status !== 'empty').length < 2 && (
                    <p className="text-xs text-[var(--text-muted)]">
                      2명 이상이 필요합니다
                    </p>
                  )}
                </div>
              ) : (
                <p className="text-[var(--text-secondary)] text-sm">
                  게임 진행 중...
                </p>
              )}
            </div>
          )}

        </div>
      </footer>

      {/* 바이인 모달 */}
      {showBuyInModal && user && (
        <BuyInModal
          config={tableConfig || {
            maxSeats: 9,
            smallBlind: 10,
            bigBlind: 20,
            minBuyIn: 400,
            maxBuyIn: 2000,
            turnTimeoutSeconds: 30,
          }}
          userBalance={user.balance || 0}
          onConfirm={handleBuyInConfirm}
          onCancel={handleBuyInCancel}
          isLoading={isJoining}
          tableName={gameState?.tableId || tableId}
        />
      )}

      {/* 피망 스타일: 족보 가이드 */}
      {!isSpectator && myHoleCards.length > 0 && (
        <HandRankingGuide
          holeCards={myHoleCards}
          communityCards={gameState?.communityCards || []}
          isVisible={true}
          position="right"
        />
      )}

      </div>

      {/* DEV 어드민 패널 - 최상위 레벨에 배치 */}
      <DevAdminPanel
        tableId={tableId}
        onReset={handleDevReset}
        onAddBot={handleAddBot}
        onStartBotLoop={handleStartBotLoop}
        isResetting={isResetting}
        isAddingBot={isAddingBot}
        isStartingLoop={isStartingLoop}
      />
    </div>
  );
}
