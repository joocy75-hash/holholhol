'use client';

import { useState, useEffect, memo, useRef } from 'react';
import { PlayingCard, FlippableCard, type Card } from './PlayingCard';
import { TurnTimer, DEFAULT_TURN_TIME } from './TimerDisplay';
import type { HandResult } from '@/lib/handEvaluator';
import { TABLE } from '@/constants/tableCoordinates';
import { Avatar } from '@/components/common';
import { VIPBadge } from '@/components/common/VIPBadge';

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

// 액션 라벨 매핑 (한글) - 말풍선 색상용 filter 클래스
const ACTION_LABELS: Record<string, { text: string; filterClass: string }> = {
  fold: { text: '폴드', filterClass: 'bubble-fold' },           // 빨간색
  check: { text: '체크', filterClass: 'bubble-check' },         // 초록색
  call: { text: '콜', filterClass: 'bubble-call' },             // 파란색
  bet: { text: '베팅', filterClass: 'bubble-bet' },             // 보라색
  raise: { text: '레이즈', filterClass: 'bubble-raise' },       // 보라색
  all_in: { text: '올인', filterClass: 'bubble-allin' },        // 주황색
  timeout: { text: '시간초과', filterClass: 'bubble-fold' },    // 빨간색 (레거시)
  timeout_fold: { text: '시간초과', filterClass: 'bubble-fold' }, // 빨간색
  timeout_check: { text: '자동체크', filterClass: 'bubble-check' }, // 초록색
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
  avatarId?: string | null; // 아바타 ID (1-10)
  vipLevel?: string | null; // VIP 등급 (bronze, silver, gold, platinum, diamond)
}

interface PlayerSeatProps {
  player?: Player;
  position: { x: number; y: number };  // 고정 픽셀 좌표
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

// React.memo를 위한 비교 함수 - 중요한 props 변경시에만 리렌더
function arePlayerSeatPropsEqual(
  prevProps: PlayerSeatProps,
  nextProps: PlayerSeatProps
): boolean {
  // 플레이어 변경 확인
  if (!prevProps.player && !nextProps.player) {
    // 둘 다 빈 좌석이면 onSeatClick 변경만 확인
    return prevProps.onSeatClick === nextProps.onSeatClick &&
           prevProps.showJoinBubble === nextProps.showJoinBubble;
  }
  if (!prevProps.player || !nextProps.player) return false;

  // 핵심 플레이어 상태 비교
  const playerEqual =
    prevProps.player.id === nextProps.player.id &&
    prevProps.player.chips === nextProps.player.chips &&
    prevProps.player.folded === nextProps.player.folded &&
    prevProps.player.isActive === nextProps.player.isActive &&
    prevProps.player.isWinner === nextProps.player.isWinner &&
    prevProps.player.cards.length === nextProps.player.cards.length &&
    prevProps.player.hasCards === nextProps.player.hasCards;

  // 턴 및 게임 상태 비교
  const stateEqual =
    prevProps.isCurrentUser === nextProps.isCurrentUser &&
    prevProps.isActive === nextProps.isActive &&
    prevProps.turnStartTime === nextProps.turnStartTime &&
    prevProps.isDealingComplete === nextProps.isDealingComplete &&
    prevProps.isShowdownRevealed === nextProps.isShowdownRevealed &&
    prevProps.isCardsRevealed === nextProps.isCardsRevealed &&
    prevProps.gameInProgress === nextProps.gameInProgress;

  // 액션 비교 (timestamp 기반)
  const actionEqual =
    (!prevProps.lastAction && !nextProps.lastAction) ||
    (prevProps.lastAction?.timestamp === nextProps.lastAction?.timestamp);

  return playerEqual && stateEqual && actionEqual;
}

export const PlayerSeat = memo(function PlayerSeat({
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
  isDealingComplete,
  isShowdownRevealed,
  gameInProgress,
}: PlayerSeatProps) {
  // 사용하지 않는 props (향후 기능 확장용)
  void _handResult;
  void _draws;

  // 표시할 카드: 서버에서 받은 카드만 사용 (캐시 없음)
  const displayCards = player?.cards ?? [];

  // DEBUG: 카드 렌더링 조건 확인 (0번 플레이어만)
  if (isCurrentUser && player) {
    const shouldShowCards = isCurrentUser && (isDealingComplete || player.folded) && (displayCards.length > 0 || player.folded);
    console.log(`🃏 [ME] folded=${player.folded}, cards=${player.cards.length}, displayCards=${displayCards.length}, isDealingComplete=${isDealingComplete}, isCardsRevealed=${isCardsRevealed}, shouldShow=${shouldShowCards}`);
  }

  // 액션 표시 여부 관리 (3초 후 자동 숨김)
  const [visibleAction, setVisibleAction] = useState<typeof lastAction>(null);
  // 타이머 추적 ref (클린업 최적화)
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 액션 표시 효과 - 통합된 단일 useEffect
  // 의도적 state 리셋: lastAction props 변경 시 액션 표시 상태 동기화 필요
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    // 기존 타이머 정리
    if (hideTimerRef.current) {
      clearTimeout(hideTimerRef.current);
      hideTimerRef.current = null;
    }

    // lastAction이 null이면 즉시 숨김 (새 핸드 시작 시)
    if (!lastAction) {
      setVisibleAction(null);
      return;
    }

    // 즉시 표시
    setVisibleAction(lastAction);

    // 3초 후 숨김
    hideTimerRef.current = setTimeout(() => {
      setVisibleAction(null);
      hideTimerRef.current = null;
    }, 3000);

    return () => {
      if (hideTimerRef.current) {
        clearTimeout(hideTimerRef.current);
        hideTimerRef.current = null;
      }
    };
  }, [lastAction]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const showAction = visibleAction !== null;
  const actionInfo = visibleAction ? ACTION_LABELS[visibleAction.type.toLowerCase()] || { text: visibleAction.type.toUpperCase(), className: 'bg-gray-500/80' } : null;

  if (!player) {
    // 빈 좌석 - 클릭 가능 여부에 따라 다르게 렌더링
    const isClickable = !!onSeatClick;

    return (
      <div
        className={`player-seat ${isClickable ? 'cursor-pointer hover:opacity-80' : ''} transition-all duration-500 ease-out z-[35]`}
        style={{ top: position.y, left: position.x }}
        data-testid={`seat-${seatPosition}`}
        data-occupied="false"
      >
        {/* 클릭 가능한 영역 - 전체를 덮는 버튼 */}
        {isClickable && (
          <button
            type="button"
            className="absolute inset-0 -m-4 z-[40] bg-transparent"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              console.log(`[SEAT ${seatPosition}] Empty seat button clicked`);
              onSeatClick(seatPosition);
            }}
            aria-label={`좌석 ${seatPosition} 선택`}
          />
        )}

        {/* 아바타 wrapper - 점유된 좌석과 동일한 구조 */}
        <div className="relative flex items-center justify-center">
          {/* 프로필 아바타 - 심플한 화살표 */}
          <div className="player-avatar bg-[var(--surface-hover)] flex items-center justify-center pointer-events-none overflow-hidden opacity-60">
            <img
              src="/assets/images/ui/dealer-arrow.png"
              alt="Join"
              className="w-6 h-6 object-contain"
              style={{
                transform: 'rotate(180deg)'
              }}
            />
          </div>
        </div>
        {/* 닉네임 → 보유금액 - 점유된 좌석과 동일한 구조 (opacity-0으로 공간 유지) */}
        <div className="player-info flex flex-col items-center gap-0.5 opacity-0 pointer-events-none">
          <span className="player-name block text-[10px] font-medium truncate max-w-[64px]">-</span>
          <span className="player-chips text-xs">0</span>
        </div>
        {/* 폴드 표시 영역 - 점유된 좌석과 동일한 높이 (h-[28px]) */}
        <div className="h-[28px] flex items-center justify-center mt-1 pointer-events-none" />
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
      className={`player-seat ${foldedClass} ${actionZIndex} ${winnerClass} ${spotlightClass} transition-all duration-500 ease-out z-30`}
      style={{ top: position.y, left: position.x }}
      data-testid={`seat-${seatPosition}`}
      data-occupied="true"
      data-is-me={isCurrentUser ? 'true' : 'false'}
      data-status={player.folded ? 'folded' : (player.isActive ? 'active' : 'waiting')}
    >
      {/* 메인 플레이어 카드 - 게임 진행 중일 때만 표시 */}
      {/* 폴드 시에는 isDealingComplete와 관계없이 표시 (폴드 어둡게 처리를 위해) */}
      {isCurrentUser && gameInProgress && (isDealingComplete || player.folded) && (displayCards.length > 0 || player.folded) && (
        <div
          className="absolute left-1/2 -translate-x-1/2 flex flex-col items-center"
          style={{ bottom: 'calc(100% + 51px)' }}
        >
          {/* 카드 컨테이너 - 클릭하여 오픈 */}
          <div
            className={`hand-cards-base ${isShowdownRevealed ? 'hand-cards-spread' : 'hand-cards-stacked'} ${player.folded ? 'hand-cards-folded' : ''} ${!isCardsRevealed && !player.folded && onRevealCards ? 'cursor-pointer' : ''}`}
            onClick={() => {
              if (!isCardsRevealed && !player.folded && onRevealCards) {
                onRevealCards();
              }
            }}
          >
            {displayCards.length > 0 ? (
              displayCards.map((card, i) => (
                <div
                  key={i}
                  className={`w-[89px] h-[125px] hand-card-${i}`}
                  style={player.folded ? { filter: 'brightness(0.5)' } : undefined}
                >
                  {player.folded ? (
                    // 폴드 시: 오픈 여부에 따라 앞면/뒷면 결정
                    isCardsRevealed ? (
                      <PlayingCard card={card} />
                    ) : (
                      <PlayingCard faceDown />
                    )
                  ) : (
                    <FlippableCard
                      card={card}
                      isRevealed={isCardsRevealed ?? false}
                      canFlip={false}
                      onFlip={() => {}}
                    />
                  )}
                </div>
              ))
            ) : (
              [0, 1].map((i) => (
                <div
                  key={i}
                  className={`w-[89px] h-[125px] hand-card-${i}`}
                  style={player.folded ? { filter: 'brightness(0.5)' } : undefined}
                >
                  <PlayingCard faceDown />
                </div>
              ))
            )}
          </div>
          {/* 탭 힌트 - 카드 오픈 전에만 표시 */}
          {!isCardsRevealed && !player.folded && onRevealCards && displayCards.length > 0 && (
            <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
              <span className="px-2 py-1 bg-black/70 text-white text-xs font-medium rounded animate-pulse">
                👆 TAP TO OPEN
              </span>
            </div>
          )}
          {/* FOLD 배지 */}
          {player.folded && (
            <div className="absolute inset-0 flex items-center justify-center z-10">
              <span className="px-2 py-0.5 bg-red-500/80 text-white text-xs font-bold rounded">
                FOLD
              </span>
            </div>
          )}
        </div>
      )}

      {/* 아바타 wrapper - 액션 모달과 타이머의 기준점 */}
      <div className="relative flex items-center justify-center">
        {/* 액션 표시 - 말풍선 (좌/우 배치) */}
        {showAction && actionInfo && visibleAction && (() => {
          // 좌측 좌석 (1, 3, 5, 7): 프로필 오른쪽에 배치 (꼬리 왼쪽)
          const isLeftSeat = [1, 3, 5, 7].includes(seatPosition);

          const positionStyle: React.CSSProperties = isLeftSeat
            ? { top: '50%', left: '100%', transform: 'translateY(-50%)', marginLeft: '8px' }
            : { top: '50%', right: '100%', transform: 'translateY(-50%)', marginRight: '8px' };

          return (
            <div className="absolute z-[60]" style={positionStyle}>
              <div className={`speech-bubble ${isLeftSeat ? 'bubble-left' : 'bubble-right'} ${actionInfo.filterClass}`}>
                {actionInfo.text}
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
          <Avatar
            avatarId={player.avatarId ?? null}
            size="md"
            nickname={player.username}
            isCurrentUser={isCurrentUser}
            isFolded={player.folded}
            isWinner={player.isWinner}
            isActive={isActive}
            showVIPBadge={false}
          />
        </TurnTimer>

        {/* 다른 플레이어 카드 오픈 시 - 프로필 정중앙 배치 (쇼다운 시에만) */}
        {!isCurrentUser && !player.folded && player.cards.length > 0 && isShowdownRevealed && (() => {
          return (
            <div className="absolute flex gap-0.5 z-20 left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
              {player.cards.map((card, i) => {
                const hasBestFiveInfo = bestFiveCards && bestFiveCards.length > 0;
                const isInBestFive = hasBestFiveInfo && isCardInBestFive(card, bestFiveCards);
                const shouldHighlight = player.isWinner && (!hasBestFiveInfo || isInBestFive);
                const cardClass = `w-[32px] h-[44px] ${shouldHighlight ? 'ring-2 ring-yellow-400 rounded shadow-lg shadow-yellow-400/50' : ''}`;
                return (
                  <div key={i} className={cardClass}>
                    <PlayingCard card={card} />
                  </div>
                );
              })}
            </div>
          );
        })()}

        {/* 다른 플레이어 카드 뒷면 - 좌석 위치에 따라 좌/우 배치 (게임 진행 중에만) */}
        {!isCurrentUser && !player.folded && player.hasCards && player.cards.length === 0 && gameInProgress && (() => {
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

        {/* 다른 플레이어 FOLD 배지 - 프로필 정중앙 */}
        {!isCurrentUser && player.folded && (
          <div className="absolute inset-0 flex items-center justify-center z-20">
            <span className="px-1.5 py-0.5 bg-red-500/80 text-white text-[10px] font-bold rounded">
              FOLD
            </span>
          </div>
        )}
      </div>

      {/* 닉네임 + VIP 배지 → 보유금액 순서 */}
      <div className="player-info flex flex-col items-center gap-0.5">
        <div className="flex items-center gap-1">
          <span className={`player-name block text-[10px] font-medium truncate max-w-[50px] ${player.folded ? 'line-through text-gray-500' : ''}`} title={player.username}>{player.username}</span>
          {player.vipLevel && <VIPBadge level={player.vipLevel} size="xs" />}
        </div>
        <span className="player-chips text-xs text-[var(--accent)]" data-testid={isCurrentUser ? 'my-stack' : `stack-${seatPosition}`}>{player.chips.toLocaleString()}</span>
      </div>

      {/* WINNER 배지 - 절대 위치 (레이아웃에 영향 없음) */}
      {player.isWinner && (
        <div className={`absolute left-1/2 -translate-x-1/2 px-2 py-1 bg-gradient-to-r from-yellow-400 to-yellow-600 text-black font-bold rounded shadow-lg shadow-yellow-500/50 animate-bounce z-10 ${isCurrentUser ? '-top-3' : '-top-12'}`} data-testid={`win-badge-${seatPosition}`}>
          <div className="text-center text-xs">WINNER</div>
          {player.winHandRank && (
            <div className="text-yellow-900 text-center font-semibold text-[8px]">{player.winHandRank}</div>
          )}
          {player.winAmount !== undefined && player.winAmount > 0 && (
            <div className="text-yellow-800 text-center text-[8px]">+{player.winAmount.toLocaleString()}</div>
          )}
        </div>
      )}

      {/* 하단 여백 (레이아웃 유지용) */}
      <div className="h-[28px] mt-1" />
    </div>
  );
}, arePlayerSeatPropsEqual);

// 좌표 상수는 tableCoordinates.ts에서 중앙 관리
// 기존 import 호환성을 위해 re-export
export {
  SEAT_POSITIONS_PERCENT as SEAT_POSITIONS,
  CHIP_POSITIONS_PERCENT as CHIP_POSITIONS,
  POT_POSITION_PERCENT as POT_POSITION,
  TABLE,
  GAME_SIZE,
} from '@/constants/tableCoordinates';
