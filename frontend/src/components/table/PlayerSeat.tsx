'use client';

import { useState, useEffect } from 'react';
import { PlayingCard, FlippableCard, type Card } from './PlayingCard';
import { TurnTimer, DEFAULT_TURN_TIME } from './TimerDisplay';
import type { HandResult } from '@/lib/handEvaluator';

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

export interface Player {
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

interface PlayerSeatProps {
  player?: Player;
  position: { top: string; left: string };
  seatPosition: number;
  isCurrentUser: boolean;
  isActive: boolean;
  lastAction?: { type: string; amount?: number; timestamp: number } | null;
  turnStartTime?: number | null;
  turnTime?: number;
  onAutoFold?: () => void;
  handResult?: HandResult | null;
  draws?: string[];
  onSeatClick?: (position: number) => void;
  showJoinBubble?: boolean;
  bestFiveCards?: Card[];
  isCardsRevealed?: boolean;
  onRevealCards?: () => void;
  isDealingComplete?: boolean;
  isShowdownRevealed?: boolean;
  gameInProgress?: boolean; // 게임 진행 중 여부 (스폿라이트 효과용)
}

export function PlayerSeat({
  player,
  position,
  seatPosition,
  isCurrentUser,
  isActive,
  lastAction,
  turnStartTime,
  turnTime = DEFAULT_TURN_TIME,
  onAutoFold,
  handResult: _handResult,
  draws: _draws,
  onSeatClick,
  showJoinBubble,
  bestFiveCards,
  isCardsRevealed,
  onRevealCards,
  isShowdownRevealed,
  gameInProgress,
}: PlayerSeatProps) {
  // 사용하지 않는 props (향후 기능 확장용)
  void _handResult;
  void _draws;

  // DEBUG: 카드 렌더링 조건 확인
  if (isCurrentUser && player) {
    console.log(`🃏 [PlayerSeat ${seatPosition}] isCurrentUser=${isCurrentUser}, cards=${JSON.stringify(player.cards)}, folded=${player.folded}, cardsLength=${player.cards.length}`);
  }
  
  // 액션 표시 여부 관리 (3초 후 자동 숨김)
  const [visibleAction, setVisibleAction] = useState<typeof lastAction>(null);

  // 액션 표시 효과
  useEffect(() => {
    // lastAction이 null이면 visibleAction도 즉시 null로 설정 (새 핸드 시작 시)
    if (!lastAction) {
      const resetTimer = setTimeout(() => setVisibleAction(null), 0);
      return () => clearTimeout(resetTimer);
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

  const showAction = visibleAction !== null;
  const actionInfo = visibleAction ? ACTION_LABELS[visibleAction.type.toLowerCase()] || { text: visibleAction.type.toUpperCase(), className: 'bg-gray-500/80' } : null;

  if (!player) {
    // 빈 좌석 - 클릭 가능 여부에 따라 다르게 렌더링
    const isClickable = !!onSeatClick;
    
    return (
      <div
        className={`player-seat ${isClickable ? 'cursor-pointer hover:opacity-80' : ''} transition-opacity z-20`}
        style={{
          ...position,
          minWidth: '60px',
          minHeight: '80px',
        }}
        data-testid={`seat-${seatPosition}`}
        data-occupied="false"
      >
        {/* 클릭 가능한 영역 - 전체를 덮는 버튼 */}
        {isClickable && (
          <button
            type="button"
            className="absolute inset-0 -m-4 z-20 bg-transparent"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              console.log(`[SEAT ${seatPosition}] Empty seat button clicked`);
              onSeatClick(seatPosition);
            }}
            aria-label={`좌석 ${seatPosition} 선택`}
          />
        )}
        
        {/* 게임참여하기 말풍선 */}
        {showJoinBubble && (
          <div className="absolute -top-12 left-1/2 -translate-x-1/2 whitespace-nowrap z-10 animate-bounce pointer-events-none">
            <div className="relative bg-[var(--neon-purple)] text-white px-4 py-2 rounded-lg text-sm font-bold shadow-lg">
              게임참여하기
              {/* 말풍선 꼬리 */}
              <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-0 h-0 border-l-[8px] border-r-[8px] border-t-[8px] border-l-transparent border-r-transparent border-t-[var(--neon-purple)]" />
            </div>
          </div>
        )}
        <div className={`player-avatar bg-[var(--surface-hover)] flex items-center justify-center pointer-events-none ${showJoinBubble ? 'opacity-100 ring-2 ring-[var(--neon-purple)] ring-offset-2 ring-offset-transparent' : 'opacity-30'}`}>
          <span className="text-xl text-[var(--text-muted)]">▼</span>
        </div>
        <div className="player-info flex flex-col items-center invisible pointer-events-none">
          <span className="player-name">-</span>
          <span className="player-chips text-xs">0</span>
        </div>
        {/* 베팅 영역 placeholder (h-[20px]) - 플레이어와 동일한 구조 */}
        <div className="h-[20px] mt-1 pointer-events-none" />
      </div>
    );
  }

  // 폴드 상태 스타일 (스폿라이트와 별개로 항상 적용)
  const foldedClass = player.folded ? 'player-folded' : '';
  // 액션 표시 중일 때 z-index 높임 (다른 player-seat 및 칩 위에 표시)
  const actionZIndex = showAction ? 'z-[55]' : '';
  // 승리자 글로우 효과
  const winnerClass = player.isWinner ? 'winner-glow' : '';
  // 스폿라이트 효과 (현재 턴 플레이어에게만 적용)
  const spotlightClass = gameInProgress && !player.folded && isActive
    ? 'spotlight-active'
    : '';

  return (
    <div 
      className={`player-seat ${foldedClass} ${actionZIndex} ${winnerClass} ${spotlightClass} z-30`} 
      style={position} 
      data-testid={`seat-${seatPosition}`} 
      data-occupied="true" 
      data-is-me={isCurrentUser ? 'true' : 'false'} 
      data-status={player.folded ? 'folded' : (player.isActive ? 'active' : 'waiting')}
    >
      {/* 메인 플레이어 카드 (프로필 위) - 플립 기능 포함 */}
      {isCurrentUser && (
        <div className="flex flex-col items-center mb-3">
          {/* 폴드하지 않았을 때: 정상 카드 표시 - 카드가 있으면 바로 표시 */}
          {player.cards.length > 0 && !player.folded && (
            <div
              className={`relative ${isShowdownRevealed ? 'hand-cards-spread' : 'hand-cards-stacked'}`}
              onClick={() => !isCardsRevealed && onRevealCards?.()}
            >
              {player.cards.map((card, i) => (
                <div
                  key={i}
                  className={`w-[57px] h-[80px] ${isShowdownRevealed ? '' : `hand-card-${i}`}`}
                >
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
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
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
            // 하단 (0번): 카드 바로 위에 표시
            positionStyle = {
              bottom: '100%',
              left: '50%',
              transform: 'translateX(-50%)',
              marginBottom: '8px',
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
            <div className="absolute z-[60]" style={positionStyle}>
              <div className={`px-3 py-1.5 rounded-full text-white text-sm font-bold shadow-xl animate-bounce-in-center whitespace-nowrap ${actionInfo.className}`}>
                {actionInfo.text}
                {!!visibleAction.amount && ` ${visibleAction.amount.toLocaleString()}`}
              </div>
            </div>
          );
        })()}

        {/* 프로필 아바타 + 턴 타이머 통합 */}
        <TurnTimer
          isActive={isActive}
          turnStartTime={turnStartTime ?? null}
          turnTime={turnTime}
          isCurrentUser={isCurrentUser}
          onAutoFold={onAutoFold}
        >
          {/* 프로필 아바타 */}
          <div className={`player-avatar ${isCurrentUser ? 'border-[var(--primary)]' : ''} ${player.folded ? 'bg-gray-600' : ''} ${player.isWinner ? 'winner-avatar' : ''}`}>
            {player.username.charAt(0).toUpperCase()}
          </div>
        </TurnTimer>

        {/* 다른 플레이어 카드 오픈 시 - 프로필 정중앙 배치 */}
        {!isCurrentUser && !player.folded && player.cards.length > 0 && (() => {
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
        {!isCurrentUser && !player.folded && player.hasCards && player.cards.length === 0 && (() => {
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
export const SEAT_POSITIONS = [
  { top: '90%', left: '50%' },   // 0 - bottom center (ME/Player) - 테이블 끝
  { top: '70%', left: '9%' },    // 1 - lower left
  { top: '70%', left: '91%' },   // 2 - lower right
  { top: '52%', left: '10%' },   // 3 - mid left
  { top: '52%', left: '90%' },   // 4 - mid right
  { top: '35%', left: '18%' },   // 5 - upper left
  { top: '35%', left: '82%' },   // 6 - upper right
  { top: '21%', left: '35%' },   // 7 - top left (+4%)
  { top: '21%', left: '65%' },   // 8 - top right (+4%)
];

// 칩 베팅 위치 (플레이어와 중앙 POT 사이)
export const CHIP_POSITIONS = [
  { top: '75%', left: '50%' },   // 0 - bottom center (조정됨)
  { top: '62%', left: '22%' },   // 1 - lower left (+4%)
  { top: '62%', left: '78%' },   // 2 - lower right (+4%)
  { top: '48%', left: '23%' },   // 3 - mid left (+6%)
  { top: '48%', left: '77%' },   // 4 - mid right (+6%)
  { top: '38%', left: '28%' },   // 5 - upper left (+6%)
  { top: '38%', left: '72%' },   // 6 - upper right (+6%)
  { top: '28%', left: '42%' },   // 7 - top left (유지)
  { top: '28%', left: '58%' },   // 8 - top right (유지)
];

// POT 위치 (중앙, POT 글씨 위쪽)
export const POT_POSITION = { top: '32%', left: '50%' };
