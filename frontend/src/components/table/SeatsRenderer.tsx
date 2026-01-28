'use client';

import { useMemo } from 'react';
import { PlayerSeat, type Player } from './PlayerSeat';
import type { Card } from './PlayingCard';
import type { SeatInfo } from '@/hooks/table/useGameState';
import { MAX_SEATS, getTableConstants, MY_SEAT_Y } from '@/constants/tableCoordinates';

interface SeatsRendererProps {
  maxSeats?: number;  // 6 또는 9 (기본값 9)
  seats: SeatInfo[];
  myPosition: number | null;
  myHoleCards: Card[];
  myCardsRevealed: boolean;
  dealingComplete: boolean;
  currentTurnPosition: number | null;
  currentTurnTime: number;
  turnStartTime: number | null;
  winnerPositions: number[];
  winnerAmounts: Record<number, number>;
  winnerBestCards: Record<number, Card[]>;
  showdownCards: Record<number, Card[]>;
  revealedPositions: Set<number>;
  allHandRanks: Record<number, string>;
  playerActions: Record<number, { type: string; amount?: number; timestamp: number }>;
  gameInProgress: boolean;
  isSpectator: boolean;
  onAutoFold: () => void;
  onSeatClick: (position: number) => void;
  onRevealCards: () => void;
  // 중간 입장 옵션
  sittingOutPositions?: Set<number>;
  onJoinModeToggle?: (wantActive: boolean) => void;
}

export function SeatsRenderer({
  maxSeats = MAX_SEATS,
  seats,
  myPosition,
  myHoleCards,
  myCardsRevealed,
  dealingComplete,
  currentTurnPosition,
  currentTurnTime,
  turnStartTime,
  winnerPositions,
  winnerAmounts,
  winnerBestCards,
  showdownCards,
  revealedPositions,
  allHandRanks,
  playerActions,
  gameInProgress,
  isSpectator,
  onAutoFold,
  onSeatClick,
  onRevealCards,
  // 중간 입장 옵션
  sittingOutPositions,
  onJoinModeToggle,
}: SeatsRendererProps) {
  // 동적 좌표 선택 (6인 또는 9인)
  const tableConfig = useMemo(() => getTableConstants(maxSeats), [maxSeats]);

  // DEBUG: myHoleCards 확인
  console.log(`🎴 [SeatsRenderer] maxSeats=${maxSeats}, myPosition=${myPosition}, myHoleCards=${JSON.stringify(myHoleCards)}, dealingComplete=${dealingComplete}`);

  return (
    <>
      {tableConfig.SEATS.map((pos, visualIndex) => {
        const actualPosition = myPosition !== null
          ? (visualIndex + myPosition) % maxSeats
          : visualIndex;
        const seat = seats.find(s => s.position === actualPosition);
        const isWinner = winnerPositions.includes(actualPosition);
        const winAmount = winnerAmounts[actualPosition];
        const showdownHoleCards = showdownCards[actualPosition];
        const isRevealed = revealedPositions.has(actualPosition);
        const handRank = allHandRanks[actualPosition];
        const isCurrentTurn = currentTurnPosition === actualPosition;
        const isMe = actualPosition === myPosition;

        // 화면 하단 중앙 좌석(visualIndex=0):
        // - 내가 앉아있고, 게임 진행 중 & 딜링 완료 & 카드를 받았을 때만 88%
        // - 그 외 모든 경우 (관전자, 대기 중, 중간 참여 등) → 70% 고정
        const hasMyCards = myHoleCards.length > 0;
        const isAtPlayingPosition = isMe && gameInProgress && dealingComplete && hasMyCards;
        const seatPosition = visualIndex === 0
          ? { x: pos.x, y: isAtPlayingPosition ? MY_SEAT_Y.PLAYING : MY_SEAT_Y.WAITING }
          : pos;

        const player: Player | undefined = seat?.player ? {
          id: seat.player.userId,
          username: seat.player.nickname,
          chips: seat.stack,
          cards: isMe ? myHoleCards : (showdownHoleCards || []),
          bet: seat.betAmount,
          folded: seat.status === 'folded',
          isActive: seat.status === 'active' || seat.status === 'all_in',
          seatIndex: actualPosition,
          hasCards: dealingComplete && (isMe ? myHoleCards.length > 0 : true),
          isWinner,
          winAmount,
          winHandRank: handRank,
          avatarId: seat.player.avatarUrl ?? null, // avatar_url에 아바타 ID 저장
        } : undefined;

        // DEBUG: 폴드 상태 추적
        if (seat?.player && seat.status === 'folded') {
          console.log(`🔴 [FOLD_DEBUG] SeatsRenderer: seat ${actualPosition} status='folded', player.folded=${player?.folded}`);
        }

        // 빈 좌석 클릭 가능 조건: 플레이어가 없고, 관전자(아직 앉지 않은 사용자)일 때
        const canClickEmptySeat = !seat?.player && isSpectator;

        // DEBUG: 빈 좌석 클릭 조건 확인
        if (!seat?.player) {
          console.log(`🪑 [Seat ${actualPosition}] canClick=${canClickEmptySeat}, isSpectator=${isSpectator}, hasPlayer=${!!seat?.player}`);
        }

        // 본인 좌석에서 sitting_out 여부 확인 (seat.status 또는 sittingOutPositions 사용)
        const isSittingOut = isMe && (seat?.status === 'sitting_out' || sittingOutPositions?.has(actualPosition));
        // 본인이 착석했고 sitting_out 상태일 때 토글 표시 (게임 중에도 sitting_out이면 표시)
        // 게임 중이 아니거나, sitting_out 상태일 때 토글 표시
        const showToggle = isMe && player && !isSpectator && (!gameInProgress || isSittingOut);

        return (
          <PlayerSeat
            key={visualIndex}
            position={seatPosition}
            seatPosition={actualPosition}
            player={player}
            isCurrentUser={isMe}
            isActive={isCurrentTurn}
            lastAction={playerActions[actualPosition]}
            turnStartTime={isCurrentTurn ? turnStartTime : null}
            turnTime={currentTurnTime}
            onAutoFold={isMe ? onAutoFold : undefined}
            onSeatClick={canClickEmptySeat ? () => onSeatClick(actualPosition) : undefined}
            showJoinBubble={canClickEmptySeat}
            bestFiveCards={winnerBestCards[actualPosition]}
            isCardsRevealed={isMe ? myCardsRevealed : undefined}
            onRevealCards={isMe ? onRevealCards : undefined}
            isDealingComplete={dealingComplete}
            isShowdownRevealed={isRevealed}
            gameInProgress={gameInProgress}
            // 중간 입장 옵션
            isSittingOut={isSittingOut}
            onJoinModeToggle={isMe ? onJoinModeToggle : undefined}
            showJoinModeToggle={showToggle}
          />
        );
      })}
    </>
  );
}
