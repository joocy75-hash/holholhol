/**
 * @fileoverview 게임 상태 관리 훅
 * @module hooks/table/useGameState
 *
 * 포커 게임의 모든 상태를 중앙에서 관리하는 커스텀 훅입니다.
 *
 * @description
 * 이 훅은 포커 테이블의 전체 상태를 관리합니다:
 * - 좌석 정보 (seats): 각 좌석의 플레이어, 스택, 베팅 금액
 * - 게임 상태 (phase, pot, currentBet): 현재 게임 진행 상황
 * - 플레이어 카드 (myHoleCards, communityCards): 홀카드 및 커뮤니티 카드
 * - 쇼다운 상태 (winners, showdownCards): 승자 및 카드 공개 정보
 * - 딜러/블라인드 위치: 버튼, SB, BB 위치
 * - 애니메이션 상태: 딜링, 칩 수집/분배, 카드 공개
 *
 * @example
 * ```tsx
 * const gameState = useGameState();
 *
 * // 좌석 정보 접근
 * const { seats, myPosition } = gameState;
 *
 * // 게임 상태 업데이트
 * gameState.setGameState(prev => ({ ...prev, pot: 100 }));
 *
 * // 새 핸드 시작 시 초기화
 * gameState.resetForNewHand();
 * ```
 */

import { useState, useRef, useCallback } from 'react';
import type { Card } from '@/components/table/PlayingCard';

/**
 * 좌석 정보 인터페이스
 * 백엔드 TABLE_SNAPSHOT 구조와 일치합니다.
 *
 * @interface SeatInfo
 * @property {number} position - 좌석 번호 (0-8)
 * @property {Object|null} player - 플레이어 정보 (비어있으면 null)
 * @property {number} stack - 현재 스택 (칩 수량)
 * @property {string} status - 좌석 상태
 * @property {number} betAmount - 현재 라운드 베팅 금액
 * @property {number} totalBet - 핸드 전체 베팅 금액
 */
export interface SeatInfo {
  position: number;
  player: {
    userId: string;
    nickname: string;
    avatarUrl?: string;
  } | null;
  stack: number;
  status: 'empty' | 'active' | 'waiting' | 'folded' | 'sitting_out' | 'all_in';
  betAmount: number;
  totalBet: number;
}

export interface TableConfig {
  maxSeats: number;
  smallBlind: number;
  bigBlind: number;
  minBuyIn: number;
  maxBuyIn: number;
  turnTimeoutSeconds: number;
}

export interface GameState {
  tableId: string;
  players: { id: string; username: string; chips: number }[];
  communityCards: Card[];
  pot: number;
  currentPlayer: string | null;
  phase: 'waiting' | 'preflop' | 'flop' | 'turn' | 'river' | 'showdown';
  smallBlind: number;
  bigBlind: number;
  minRaise: number;
  currentBet: number;
}

export interface UseGameStateReturn {
  // 기본 상태
  gameState: GameState | null;
  setGameState: React.Dispatch<React.SetStateAction<GameState | null>>;
  tableConfig: TableConfig | null;
  setTableConfig: React.Dispatch<React.SetStateAction<TableConfig | null>>;
  seats: SeatInfo[];
  setSeats: React.Dispatch<React.SetStateAction<SeatInfo[]>>;
  seatsRef: React.MutableRefObject<SeatInfo[]>;

  // 플레이어 위치
  myPosition: number | null;
  setMyPosition: React.Dispatch<React.SetStateAction<number | null>>;

  // 카드 상태
  myHoleCards: Card[];
  setMyHoleCards: React.Dispatch<React.SetStateAction<Card[]>>;
  communityCardsRef: React.MutableRefObject<Card[]>;

  // 턴 상태
  currentTurnPosition: number | null;
  setCurrentTurnPosition: React.Dispatch<React.SetStateAction<number | null>>;
  turnStartTime: number | null;
  setTurnStartTime: React.Dispatch<React.SetStateAction<number | null>>;
  currentTurnTime: number;
  setCurrentTurnTime: React.Dispatch<React.SetStateAction<number>>;

  // 플레이어 액션 표시
  playerActions: Record<number, { type: string; amount?: number; timestamp: number }>;
  setPlayerActions: React.Dispatch<React.SetStateAction<Record<number, { type: string; amount?: number; timestamp: number }>>>;

  // 딜러/블라인드 위치
  dealerPosition: number | null;
  setDealerPosition: React.Dispatch<React.SetStateAction<number | null>>;
  smallBlindPosition: number | null;
  setSmallBlindPosition: React.Dispatch<React.SetStateAction<number | null>>;
  bigBlindPosition: number | null;
  setBigBlindPosition: React.Dispatch<React.SetStateAction<number | null>>;

  // 사이드 팟
  sidePots: { amount: number; eligiblePlayers: number[] }[];
  setSidePots: React.Dispatch<React.SetStateAction<{ amount: number; eligiblePlayers: number[] }[]>>;

  // 쇼다운 상태
  winnerPositions: number[];
  setWinnerPositions: React.Dispatch<React.SetStateAction<number[]>>;
  winnerAmounts: Record<number, number>;
  setWinnerAmounts: React.Dispatch<React.SetStateAction<Record<number, number>>>;
  winnerHandRanks: Record<number, string>;
  setWinnerHandRanks: React.Dispatch<React.SetStateAction<Record<number, string>>>;
  winnerBestCards: Record<number, Card[]>;
  setWinnerBestCards: React.Dispatch<React.SetStateAction<Record<number, Card[]>>>;
  showdownCards: Record<number, Card[]>;
  setShowdownCards: React.Dispatch<React.SetStateAction<Record<number, Card[]>>>;
  isShowdownDisplay: boolean;
  setIsShowdownDisplay: React.Dispatch<React.SetStateAction<boolean>>;
  showdownPhase: 'idle' | 'intro' | 'revealing' | 'winner_announced' | 'settling' | 'complete';
  setShowdownPhase: React.Dispatch<React.SetStateAction<'idle' | 'intro' | 'revealing' | 'winner_announced' | 'settling' | 'complete'>>;
  revealedPositions: Set<number>;
  setRevealedPositions: React.Dispatch<React.SetStateAction<Set<number>>>;
  allHandRanks: Record<number, string>;
  setAllHandRanks: React.Dispatch<React.SetStateAction<Record<number, string>>>;

  // Refs for async access
  isShowdownInProgressRef: React.MutableRefObject<boolean>;
  isDealingInProgressRef: React.MutableRefObject<boolean>;
  pendingHandStartedRef: React.MutableRefObject<unknown>;
  pendingHoleCardsRef: React.MutableRefObject<Card[] | null>;
  pendingTurnPromptRef: React.MutableRefObject<unknown>;
  pendingStackUpdatesRef: React.MutableRefObject<Record<number, number>>;

  // 딜링 상태
  isDealing: boolean;
  setIsDealing: React.Dispatch<React.SetStateAction<boolean>>;
  dealingSequence: { position: number; cardIndex: number }[];
  setDealingSequence: React.Dispatch<React.SetStateAction<{ position: number; cardIndex: number }[]>>;
  dealingComplete: boolean;
  setDealingComplete: React.Dispatch<React.SetStateAction<boolean>>;

  // 커뮤니티 카드 공개 상태
  revealedCommunityCount: number;
  setRevealedCommunityCount: React.Dispatch<React.SetStateAction<number>>;
  isRevealingCommunity: boolean;
  setIsRevealingCommunity: React.Dispatch<React.SetStateAction<boolean>>;

  // 칩 애니메이션 상태
  collectingChips: { position: number; amount: number }[];
  setCollectingChips: React.Dispatch<React.SetStateAction<{ position: number; amount: number }[]>>;
  distributingChip: { amount: number; toPosition: number } | null;
  setDistributingChip: React.Dispatch<React.SetStateAction<{ amount: number; toPosition: number } | null>>;
  isCollectingToPot: boolean;
  setIsCollectingToPot: React.Dispatch<React.SetStateAction<boolean>>;
  potChips: number;
  setPotChips: React.Dispatch<React.SetStateAction<number>>;

  // 카드 오픈 상태
  myCardsRevealed: boolean;
  setMyCardsRevealed: React.Dispatch<React.SetStateAction<boolean>>;

  // 유틸리티 함수
  resetForNewHand: () => void;
}

const DEFAULT_TURN_TIME = 15;

export function useGameState(): UseGameStateReturn {
  // 기본 상태
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [tableConfig, setTableConfig] = useState<TableConfig | null>(null);
  const [seats, setSeats] = useState<SeatInfo[]>([]);
  const seatsRef = useRef<SeatInfo[]>([]);

  // 플레이어 위치
  const [myPosition, setMyPosition] = useState<number | null>(null);

  // 카드 상태
  const [myHoleCards, setMyHoleCards] = useState<Card[]>([]);
  const communityCardsRef = useRef<Card[]>([]);

  // 턴 상태
  const [currentTurnPosition, setCurrentTurnPosition] = useState<number | null>(null);
  const [turnStartTime, setTurnStartTime] = useState<number | null>(null);
  const [currentTurnTime, setCurrentTurnTime] = useState<number>(DEFAULT_TURN_TIME);

  // 플레이어 액션 표시
  const [playerActions, setPlayerActions] = useState<Record<number, { type: string; amount?: number; timestamp: number }>>({});

  // 딜러/블라인드 위치
  const [dealerPosition, setDealerPosition] = useState<number | null>(null);
  const [smallBlindPosition, setSmallBlindPosition] = useState<number | null>(null);
  const [bigBlindPosition, setBigBlindPosition] = useState<number | null>(null);

  // 사이드 팟
  const [sidePots, setSidePots] = useState<{ amount: number; eligiblePlayers: number[] }[]>([]);

  // 쇼다운 상태
  const [winnerPositions, setWinnerPositions] = useState<number[]>([]);
  const [winnerAmounts, setWinnerAmounts] = useState<Record<number, number>>({});
  const [winnerHandRanks, setWinnerHandRanks] = useState<Record<number, string>>({});
  const [winnerBestCards, setWinnerBestCards] = useState<Record<number, Card[]>>({});
  const [showdownCards, setShowdownCards] = useState<Record<number, Card[]>>({});
  const [isShowdownDisplay, setIsShowdownDisplay] = useState(false);
  const [showdownPhase, setShowdownPhase] = useState<'idle' | 'intro' | 'revealing' | 'winner_announced' | 'settling' | 'complete'>('idle');
  const [revealedPositions, setRevealedPositions] = useState<Set<number>>(new Set());
  const [allHandRanks, setAllHandRanks] = useState<Record<number, string>>({});

  // Refs
  const isShowdownInProgressRef = useRef(false);
  const isDealingInProgressRef = useRef(false);
  const pendingHandStartedRef = useRef<unknown>(null);
  const pendingHoleCardsRef = useRef<Card[] | null>(null);
  const pendingTurnPromptRef = useRef<unknown>(null);
  const pendingStackUpdatesRef = useRef<Record<number, number>>({});

  // 딜링 상태
  const [isDealing, setIsDealing] = useState(false);
  const [dealingSequence, setDealingSequence] = useState<{ position: number; cardIndex: number }[]>([]);
  const [dealingComplete, setDealingComplete] = useState(false);

  // 커뮤니티 카드 공개 상태
  const [revealedCommunityCount, setRevealedCommunityCount] = useState(0);
  const [isRevealingCommunity, setIsRevealingCommunity] = useState(false);

  // 칩 애니메이션 상태
  const [collectingChips, setCollectingChips] = useState<{ position: number; amount: number }[]>([]);
  const [distributingChip, setDistributingChip] = useState<{ amount: number; toPosition: number } | null>(null);
  const [isCollectingToPot, setIsCollectingToPot] = useState(false);
  const [potChips, setPotChips] = useState<number>(0);

  // 카드 오픈 상태
  const [myCardsRevealed, setMyCardsRevealed] = useState(false);

  // 새 핸드 시작 시 상태 초기화
  const resetForNewHand = useCallback(() => {
    setPlayerActions({});
    setWinnerPositions([]);
    setWinnerAmounts({});
    setWinnerHandRanks({});
    setWinnerBestCards({});
    setShowdownCards({});
    setIsShowdownDisplay(false);
    setShowdownPhase('idle');
    setRevealedPositions(new Set());
    setAllHandRanks({});
    setRevealedCommunityCount(0);
    setIsRevealingCommunity(false);
    communityCardsRef.current = [];
    setCollectingChips([]);
    setDistributingChip(null);
    setIsCollectingToPot(false);
    setPotChips(0);
    setMyHoleCards([]);
    setMyCardsRevealed(false);
    setDealingComplete(false);
    setIsDealing(false);
    setDealingSequence([]);
    setTurnStartTime(null);
    setCurrentTurnPosition(null);
    setSidePots([]);
  }, []);

  return {
    gameState,
    setGameState,
    tableConfig,
    setTableConfig,
    seats,
    setSeats,
    seatsRef,
    myPosition,
    setMyPosition,
    myHoleCards,
    setMyHoleCards,
    communityCardsRef,
    currentTurnPosition,
    setCurrentTurnPosition,
    turnStartTime,
    setTurnStartTime,
    currentTurnTime,
    setCurrentTurnTime,
    playerActions,
    setPlayerActions,
    dealerPosition,
    setDealerPosition,
    smallBlindPosition,
    setSmallBlindPosition,
    bigBlindPosition,
    setBigBlindPosition,
    sidePots,
    setSidePots,
    winnerPositions,
    setWinnerPositions,
    winnerAmounts,
    setWinnerAmounts,
    winnerHandRanks,
    setWinnerHandRanks,
    winnerBestCards,
    setWinnerBestCards,
    showdownCards,
    setShowdownCards,
    isShowdownDisplay,
    setIsShowdownDisplay,
    showdownPhase,
    setShowdownPhase,
    revealedPositions,
    setRevealedPositions,
    allHandRanks,
    setAllHandRanks,
    isShowdownInProgressRef,
    isDealingInProgressRef,
    pendingHandStartedRef,
    pendingHoleCardsRef,
    pendingTurnPromptRef,
    pendingStackUpdatesRef,
    isDealing,
    setIsDealing,
    dealingSequence,
    setDealingSequence,
    dealingComplete,
    setDealingComplete,
    revealedCommunityCount,
    setRevealedCommunityCount,
    isRevealingCommunity,
    setIsRevealingCommunity,
    collectingChips,
    setCollectingChips,
    distributingChip,
    setDistributingChip,
    isCollectingToPot,
    setIsCollectingToPot,
    potChips,
    setPotChips,
    myCardsRevealed,
    setMyCardsRevealed,
    resetForNewHand,
  };
}
