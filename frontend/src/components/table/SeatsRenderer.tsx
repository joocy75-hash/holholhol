'use client';

import { PlayerSeat, SEAT_POSITIONS, type Player } from './PlayerSeat';
import type { Card } from './PlayingCard';
import type { SeatInfo } from '@/hooks/table/useGameState';

interface SeatsRendererProps {
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
}

export function SeatsRenderer({
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
}: SeatsRendererProps) {
  // DEBUG: myHoleCards 확인
  console.log(`🎴 [SeatsRenderer] myPosition=${myPosition}, myHoleCards=${JSON.stringify(myHoleCards)}, dealingComplete=${dealingComplete}`);
  
  return (
    <>
      {SEAT_POSITIONS.map((pos, visualIndex) => {
        const actualPosition = myPosition !== null
          ? (visualIndex + myPosition) % SEAT_POSITIONS.length
          : visualIndex;
        const seat = seats.find(s => s.position === actualPosition);
        const isWinner = winnerPositions.includes(actualPosition);
        const winAmount = winnerAmounts[actualPosition];
        const showdownHoleCards = showdownCards[actualPosition];
        const isRevealed = revealedPositions.has(actualPosition);
        const handRank = allHandRanks[actualPosition];
        const isCurrentTurn = currentTurnPosition === actualPosition;
        const isMe = actualPosition === myPosition;

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
        } : undefined;

        // 빈 좌석 클릭 가능 조건: 플레이어가 없고, 관전자(아직 앉지 않은 사용자)일 때
        const canClickEmptySeat = !seat?.player && isSpectator;

        return (
          <PlayerSeat
            key={visualIndex}
            position={pos}
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
          />
        );
      })}
    </>
  );
}
