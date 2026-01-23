/**
 * @fileoverview WebSocket 연결 및 이벤트 핸들링 훅
 * @module hooks/table/useTableWebSocket
 *
 * 포커 테이블의 모든 WebSocket 이벤트를 처리하는 커스텀 훅입니다.
 *
 * @description
 * 이 훅은 서버와의 실시간 통신을 담당합니다:
 *
 * **테이블 상태 이벤트:**
 * - TABLE_SNAPSHOT: 테이블 전체 상태 스냅샷
 * - TABLE_STATE_UPDATE: 부분 상태 업데이트
 *
 * **게임 진행 이벤트:**
 * - HAND_STARTED: 새 핸드 시작
 * - HAND_RESULT: 핸드 결과 (쇼다운/승자)
 * - COMMUNITY_CARDS: 커뮤니티 카드 공개
 *
 * **턴 관리 이벤트:**
 * - TURN_PROMPT: 플레이어 턴 시작
 * - TURN_CHANGED: 턴 변경
 * - TIMEOUT_FOLD: 타임아웃 폴드
 *
 * **액션 결과 이벤트:**
 * - ACTION_RESULT: 액션 처리 결과
 * - SEAT_RESULT: 좌석 배정 결과
 *
 * **연결 상태 이벤트:**
 * - CONNECTION_STATE: 연결 상태 변경
 * - CONNECTION_LOST: 연결 끊김
 *
 * @example
 * ```tsx
 * const { isConnected, error, countdown } = useTableWebSocket({
 *   tableId: 'table-123',
 *   userId: 'user-456',
 *   gameState: gameStateHook,
 *   actions: actionsHook,
 *   fetchUser: fetchUserCallback,
 * });
 *
 * if (!isConnected) {
 *   return <LoadingSpinner />;
 * }
 *
 * if (error) {
 *   return <ErrorMessage message={error} />;
 * }
 * ```
 */

import { useEffect, useCallback, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { wsClient } from '@/lib/websocket';
import { soundManager, chipSoundManager } from '@/lib/sounds';
import { analyzeHand } from '@/lib/handEvaluator';
import { parseCards, type Card } from '@/components/table/PlayingCard';
import type { UseGameStateReturn, SeatInfo, GameState } from './useGameState';
import type { AllowedAction } from '@/types/table';

/** 기본 턴 시간 (초) */
const DEFAULT_TURN_TIME = 15;

interface UseTableWebSocketProps {
  tableId: string;
  userId?: string;
  gameState: UseGameStateReturn;
  actions: {
    setIsActionPending: (pending: boolean) => void;
    setAllowedActions: (actions: AllowedAction[]) => void;
    setHasAutoFolded: (folded: boolean) => void;
  };
  fetchUser: () => void;
  onStackZero?: () => void;  // 스택 0 알림 콜백
}

interface UseTableWebSocketReturn {
  isConnected: boolean;
  error: string | null;
  setError: (error: string | null) => void;
  countdown: number | null;
}

export function useTableWebSocket({
  tableId,
  userId,
  gameState,
  actions,
  fetchUser,
  onStackZero,
}: UseTableWebSocketProps): UseTableWebSocketReturn {
  const router = useRouter();
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState<number | null>(null);

  // 액션 효과 표시 중 여부
  const isShowingActionEffectRef = useRef(false);
  // 카운트다운 타이머 ref (중복 실행 방지)
  const countdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // 스택 0 콜백 ref (무한 루프 방지)
  const onStackZeroRef = useRef(onStackZero);
  onStackZeroRef.current = onStackZero;

  // 딜링 시퀀스 계산 함수 - visualIndex로 변환하여 반환
  const calculateDealingSequence = useCallback((
    activePlayers: number[],
    sbPosition: number | null,
    myPosition: number | null
  ): { position: number; cardIndex: number }[] => {
    if (activePlayers.length === 0) return [];
    const sorted = [...activePlayers].sort((a, b) => a - b);
    const sbIndex = sbPosition !== null ? sorted.indexOf(sbPosition) : 0;
    const orderedPlayers = [
      ...sorted.slice(sbIndex),
      ...sorted.slice(0, sbIndex)
    ];
    const sequence: { position: number; cardIndex: number }[] = [];
    const SEAT_COUNT = 9; // SEAT_POSITIONS.length
    for (let cardIndex = 0; cardIndex < 2; cardIndex++) {
      for (const position of orderedPlayers) {
        // 실제 좌석 위치를 visualIndex로 변환
        const visualIndex = myPosition !== null
          ? (position - myPosition + SEAT_COUNT) % SEAT_COUNT
          : position;
        sequence.push({ position: visualIndex, cardIndex });
      }
    }
    return sequence;
  }, []);

  // TURN_PROMPT 적용 함수
  const applyTurnPromptData = useCallback((data: {
    position: number;
    allowedActions?: AllowedAction[];
    currentBet?: number;
    turnStartTime?: number;
    turnTime?: number;
  }) => {
    console.log('🎯 Applying TURN_PROMPT:', {
      position: data.position,
      actionsCount: data.allowedActions?.length,
    });

    if (data.currentBet !== undefined) {
      gameState.setGameState((prev) => {
        if (!prev) return prev;
        return { ...prev, currentBet: data.currentBet! };
      });
    }

    const raiseAction = data.allowedActions?.find(a => a.type === 'raise' || a.type === 'bet');
    if (raiseAction?.minAmount) {
      gameState.setGameState((prev) => {
        if (!prev) return prev;
        return { ...prev, minRaise: raiseAction.minAmount! };
      });
    }

    gameState.setCurrentTurnPosition(data.position);
    gameState.setTurnStartTime(data.turnStartTime || Date.now());
    gameState.setCurrentTurnTime(data.turnTime || DEFAULT_TURN_TIME);
    actions.setHasAutoFolded(false);
    actions.setIsActionPending(false);

    if (data.allowedActions && data.allowedActions.length > 0) {
      actions.setAllowedActions(data.allowedActions);
    }
  }, [gameState, actions]);

  // HAND_STARTED 처리 함수
  const processHandStarted = useCallback((data: {
    tableId: string;
    phase?: string;
    pot?: number;
    communityCards?: string[];
    myPosition?: number | null;
    myHoleCards?: (string | Card)[];
    currentTurn?: number | null;
    dealer?: number;
    smallBlindSeat?: number;
    bigBlindSeat?: number;
    seats?: Array<{
      position: number;
      userId: string;
      nickname: string;
      stack: number;
      status: string;
      betAmount?: number;
    } | null>;
  }) => {
    console.log('🎴 Processing HAND_STARTED:', data);

    // 딜링 시작 플래그를 먼저 설정 (TABLE_SNAPSHOT에서 카드를 pendingHoleCardsRef에 저장하도록)
    gameState.isDealingInProgressRef.current = true;

    // pendingHoleCardsRef를 먼저 저장 (resetForNewHand 전에)
    // TABLE_SNAPSHOT이 HAND_STARTED보다 먼저 도착했을 수 있음
    const savedPendingCards = gameState.pendingHoleCardsRef.current;
    gameState.pendingHoleCardsRef.current = null;

    setCountdown(null);
    gameState.resetForNewHand();
    actions.setAllowedActions([]);
    actions.setIsActionPending(false);
    actions.setHasAutoFolded(false);
    isShowingActionEffectRef.current = false;

    gameState.setGameState((prev) => {
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
        phase: (data.phase as GameState['phase']) || 'preflop',
        pot: data.pot || 0,
        communityCards: parseCards(data.communityCards || []),
      };
    });

    if (data.myPosition !== null && data.myPosition !== undefined) {
      gameState.setMyPosition(data.myPosition);
    }

    const playOpenCardSound = () => {
      const openSound = new Audio('/sounds/opencard.webm');
      openSound.volume = 0.5;
      openSound.play().catch(() => {});
    };

    // 저장된 pendingHoleCards 우선 사용 (race condition 방지)
    if (savedPendingCards && savedPendingCards.length > 0) {
      console.log('🎴 [processHandStarted] Using savedPendingCards:', savedPendingCards);
      gameState.setMyHoleCards(savedPendingCards);
      playOpenCardSound();
    } else if (data.myHoleCards && data.myHoleCards.length > 0) {
      const cards = data.myHoleCards.map((card) => {
        if (typeof card === 'string') {
          return { rank: card.slice(0, -1), suit: card.slice(-1) };
        }
        return card;
      });
      console.log('🎴 [processHandStarted] Setting myHoleCards from data:', cards);
      gameState.setMyHoleCards(cards);
      playOpenCardSound();
    } else {
      console.log('🎴 [processHandStarted] No myHoleCards found! data.myHoleCards:', data.myHoleCards);
    }

    if (data.currentTurn !== null && data.currentTurn !== undefined) {
      gameState.setCurrentTurnPosition(data.currentTurn);
    }

    if (data.dealer !== undefined) gameState.setDealerPosition(data.dealer);
    if (data.smallBlindSeat !== undefined) gameState.setSmallBlindPosition(data.smallBlindSeat);
    if (data.bigBlindSeat !== undefined) gameState.setBigBlindPosition(data.bigBlindSeat);

    let seatsToUse = gameState.seatsRef.current;

    if (data.seats) {
      const seatsWithBlinds = data.seats
        .filter((s): s is NonNullable<typeof s> => s !== null)
        .map((s) => ({
          position: s.position,
          player: { userId: s.userId, nickname: s.nickname },
          stack: s.stack,
          status: s.status as SeatInfo['status'],
          betAmount: s.betAmount || 0,
          totalBet: 0,
        }));
      gameState.setSeats(seatsWithBlinds);
      seatsToUse = seatsWithBlinds;
    }

    const activePlayers = seatsToUse
      .filter((s) => s.player && (s.status === 'active' || s.status === 'waiting'))
      .map((s) => s.position);

    if (activePlayers.length >= 2) {
      const sbPos = data.smallBlindSeat ?? gameState.smallBlindPosition;
      const sequence = calculateDealingSequence(activePlayers, sbPos, gameState.myPosition);
      gameState.setDealingSequence(sequence);
      setTimeout(() => gameState.setIsDealing(true), 500);
    } else {
      gameState.setDealingComplete(true);
      gameState.isDealingInProgressRef.current = false;
    }

    // 대기 중인 TURN_PROMPT 처리
    if (gameState.pendingTurnPromptRef.current) {
      const pendingTurnData = gameState.pendingTurnPromptRef.current as Parameters<typeof applyTurnPromptData>[0];
      gameState.pendingTurnPromptRef.current = null;
      setTimeout(() => applyTurnPromptData(pendingTurnData), 500);
    }
  }, [gameState, actions, calculateDealingSequence, applyTurnPromptData]);

  // 쇼다운 완료 처리 함수
  const completeShowdown = useCallback(() => {
    console.log('✅ Showdown complete');
    gameState.pendingStackUpdatesRef.current = {};

    gameState.setShowdownPhase('settling');

    setTimeout(() => {
      gameState.setShowdownPhase('idle');
      gameState.setWinnerPositions([]);
      gameState.setWinnerAmounts({});
      gameState.setWinnerHandRanks({});
      gameState.setWinnerBestCards({});
      gameState.setShowdownCards({});
      gameState.setIsShowdownDisplay(false);
      gameState.setRevealedPositions(new Set());
      gameState.setAllHandRanks({});
      gameState.setPotChips(0);

      // 쇼다운 완료 후 pending STACK_ZERO 처리 (리바이 모달 표시)
      if (gameState.pendingStackZeroRef.current) {
        console.log('🎰 completeShowdown: Processing pending STACK_ZERO');
        gameState.pendingStackZeroRef.current = false;
        if (onStackZeroRef.current) {
          onStackZeroRef.current();
        }
      }

      // CRITICAL: pendingHandStartedRef를 먼저 읽고, isShowdownInProgressRef를 false로 설정
      // 이 순서가 중요함! 동기 블록에서 처리하여 race condition 방지
      // (JavaScript는 단일 스레드이므로 이 블록 실행 중에는 WebSocket 이벤트가 처리되지 않음)
      const pendingData = gameState.pendingHandStartedRef.current;
      gameState.pendingHandStartedRef.current = null;
      gameState.isShowdownInProgressRef.current = false;

      // 다음 핸드 시작 처리 (UI 전환을 위한 짧은 딜레이)
      setTimeout(() => {
        if (pendingData) {
          processHandStarted(pendingData as Parameters<typeof processHandStarted>[0]);
        }
      }, 300);
    }, 500);
  }, [gameState, processHandStarted]);

  // WebSocket 연결 및 이벤트 핸들러 설정
  useEffect(() => {
    // 사용자 정보 로드 (BuyInModal 등에서 필요)
    fetchUser();
    soundManager.init();

    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/login');
      return;
    }

    wsClient
      .connect(token)
      .then(() => {
        console.log('✅ [WS] Connected, sending SUBSCRIBE_TABLE for tableId:', tableId);
        setIsConnected(true);
        wsClient.send('SUBSCRIBE_TABLE', { tableId });
      })
      .catch((err) => {
        setError('서버 연결에 실패했습니다.');
        console.error(err);
      });

    // TABLE_SNAPSHOT 핸들러
    const unsubTableSnapshot = wsClient.on('TABLE_SNAPSHOT', (rawData) => {
      const data = rawData as Record<string, unknown>;
      const isStateRestore = data.isStateRestore === true;

      console.log('TABLE_SNAPSHOT received:', { isStateRestore, ...data });

      // 상태 복원 시 애니메이션 관련 상태 즉시 설정
      if (isStateRestore && !gameState.isDealingInProgressRef.current) {
        console.log('🔄 [STATE_RESTORE] Setting dealingComplete=true');
        gameState.setDealingComplete(true);
        gameState.setIsDealing(false);
      }

      // DEBUG: 버튼 표시 조건 확인
      const handData = data.hand as Record<string, unknown> | undefined;
      console.log('🎯 [BUTTON_DEBUG] conditions:', {
        currentTurn: handData?.currentTurn,
        myPosition: data.myPosition,
        isStateRestore,
        isDealingInProgress: gameState.isDealingInProgressRef.current,
        handExists: !!handData,
        phase: handData?.phase,
      });

      if (data.config) {
        console.log('📋 [TABLE_SNAPSHOT] Setting tableConfig:', data.config);
        gameState.setTableConfig(data.config as UseGameStateReturn['tableConfig']);
      } else {
        console.warn('⚠️ [TABLE_SNAPSHOT] No config in snapshot!');
      }

      // tableName 설정
      if (data.tableName) {
        gameState.setTableName(data.tableName as string);
      }

      if (data.seats) {
        const isShowdownBlocking = gameState.isShowdownInProgressRef.current;
        const isDealingBlocking = gameState.isDealingInProgressRef.current;

        if (isDealingBlocking) {
          console.log('🎴 Dealing blocking - skipping seats update');
        } else if (isShowdownBlocking) {
          // 쇼다운 중: stack은 pending으로 저장, status는 즉시 업데이트
          const seatsArray = data.seats as Array<{
            position: number;
            player: { userId: string; nickname: string } | null;
            stack?: number;
            status?: string;
          }>;
          seatsArray
            .filter(s => s.player !== null && s.stack !== undefined)
            .forEach(s => {
              gameState.pendingStackUpdatesRef.current[s.position] = s.stack!;
            });
          // status 즉시 업데이트 (폴드 어둡게 효과 등 UI 반영 필요)
          gameState.setSeats((prevSeats) => {
            return prevSeats.map((seat) => {
              const seatUpdate = seatsArray.find((s) => s.position === seat.position);
              if (seatUpdate && seat.player && seatUpdate.status) {
                return { ...seat, status: seatUpdate.status as SeatInfo['status'] };
              }
              return seat;
            });
          });
        } else {
          const formattedSeats = (data.seats as Array<{
            position: number;
            player: { userId: string; nickname: string } | null;
            stack: number;
            status: string;
            betAmount?: number;
            totalBet?: number;
          }>)
            .filter(s => s.player !== null)
            .map(s => ({
              position: s.position,
              player: s.player,
              stack: s.stack,
              status: s.status as SeatInfo['status'],
              betAmount: s.betAmount || 0,
              totalBet: s.totalBet || 0,
            }));
          gameState.setSeats(formattedSeats);
        }
      }

      // myPosition 설정 - data 또는 data.state에서 찾기
      const stateDataForPosition = (data.state || data) as Record<string, unknown>;
      if ('myPosition' in data) {
        gameState.setMyPosition(data.myPosition as number | null);
      } else if ('myPosition' in stateDataForPosition) {
        gameState.setMyPosition(stateDataForPosition.myPosition as number | null);
      }

      // myHoleCards 추출 - 여러 위치에서 찾기
      const stateData = (data.hand || data.state || data) as Record<string, unknown>;
      let extractedCards: Card[] | null = null;

      // DEBUG: TABLE_SNAPSHOT 구조 확인
      console.log('🔍 [TABLE_SNAPSHOT] Full structure:', {
        hasHand: !!data.hand,
        hasState: !!data.state,
        dataKeys: Object.keys(data),
        stateDataKeys: stateData ? Object.keys(stateData) : [],
        myPosition: data.myPosition ?? stateData?.myPosition,
        hasMyHoleCards: !!data.myHoleCards || !!(stateData as Record<string, unknown>)?.myHoleCards,
        playersCount: ((stateData as Record<string, unknown>)?.players as unknown[])?.length,
      });

      // 1. data.myHoleCards 또는 stateData.myHoleCards 확인
      const rawHoleCards = data.myHoleCards || stateData.myHoleCards;
      if (rawHoleCards && Array.isArray(rawHoleCards) && rawHoleCards.length > 0) {
        extractedCards = (rawHoleCards as (string | Card)[]).map((card) => {
          if (typeof card === 'string') {
            return { rank: card.slice(0, -1), suit: card.slice(-1) };
          }
          return card;
        });
        console.log('🎴 [TABLE_SNAPSHOT] Extracted myHoleCards from top level:', extractedCards);
      }

      // 2. stateData.players[myPosition].holeCards 확인 (백엔드 get_state_for_player 포맷)
      if (!extractedCards || extractedCards.length === 0) {
        const myPos = (data.myPosition ?? stateData.myPosition) as number | null;
        const players = stateData.players as Array<{ seat: number; holeCards?: string[] | null }> | undefined;

        console.log('🔍 [TABLE_SNAPSHOT] Looking for holeCards in players array:', {
          myPos,
          playersLength: players?.length,
          playerSeats: players?.map(p => p?.seat),
        });

        if (myPos !== null && players && Array.isArray(players)) {
          const myPlayerData = players.find(p => p && p.seat === myPos);
          console.log('🔍 [TABLE_SNAPSHOT] Found myPlayerData:', {
            found: !!myPlayerData,
            seat: myPlayerData?.seat,
            holeCards: myPlayerData?.holeCards,
          });

          if (myPlayerData?.holeCards && Array.isArray(myPlayerData.holeCards) && myPlayerData.holeCards.length > 0) {
            extractedCards = myPlayerData.holeCards.map((card: string) => ({
              rank: card.slice(0, -1),
              suit: card.slice(-1),
            }));
            console.log('🎴 [TABLE_SNAPSHOT] Extracted holeCards from players array:', extractedCards);
          }
        }
      }

      if (!extractedCards || extractedCards.length === 0) {
        console.log('🎴 [TABLE_SNAPSHOT] No myHoleCards found. data.myHoleCards:', data.myHoleCards, 'stateData.myHoleCards:', stateData.myHoleCards);
      }

      if (extractedCards && extractedCards.length > 0) {
        // 항상 pendingHoleCardsRef에도 저장 (HAND_STARTED에서 resetForNewHand로 인한 손실 방지)
        gameState.pendingHoleCardsRef.current = extractedCards;

        if (gameState.isShowdownInProgressRef.current) {
          // 쇼다운 중에는 저장만 (화면 갱신 방지)
          console.log('🎴 [TABLE_SNAPSHOT] Storing in pendingHoleCardsRef (showdown in progress)');
        } else {
          // 딜링 중이든 아니든, myHoleCards를 직접 설정 (카드가 보여야 함)
          // 딜링 애니메이션은 dealingSequence로 동작하므로 myHoleCards 설정과 무관
          console.log('🎴 [TABLE_SNAPSHOT] Setting myHoleCards directly + storing in pendingHoleCardsRef, isDealingInProgress:', gameState.isDealingInProgressRef.current);
          gameState.setMyHoleCards(extractedCards);

          // 새로고침 후 복구: 딜링 애니메이션 중이 아니면 dealingComplete도 설정
          // (딜링 중이면 DealingAnimation에서 완료 시 설정됨)
          if (!gameState.isDealingInProgressRef.current) {
            console.log('🎴 [TABLE_SNAPSHOT] Setting dealingComplete=true (not dealing)');
            gameState.setDealingComplete(true);
          }

          // 새로고침 후 복구: 카드 오픈 상태 복원 (isCardsRevealed)
          const myPos = data.myPosition as number | null;
          if (myPos !== null && data.seats && isStateRestore) {
            const mySeat = (data.seats as Array<{position: number; isCardsRevealed?: boolean}>)
              .find(s => s.position === myPos);
            if (mySeat?.isCardsRevealed) {
              console.log('🎴 [TABLE_SNAPSHOT] Restoring myCardsRevealed=true');
              gameState.setMyCardsRevealed(true);
            }
          }
        }
      }

      // 새로고침 후 복구: 커뮤니티 카드 공개 상태 복원
      // (애니메이션 없이 즉시 표시)
      if (stateData.communityCards && Array.isArray(stateData.communityCards)) {
        const communityCount = stateData.communityCards.length;
        if (communityCount > 0 && !gameState.isDealingInProgressRef.current && !gameState.isShowdownInProgressRef.current) {
          console.log('🃏 [TABLE_SNAPSHOT] Restoring communityCards count:', communityCount);
          gameState.setRevealedCommunityCount(communityCount);
          gameState.communityCardsRef.current = parseCards(stateData.communityCards as string[]);
        }
      }

      // 게임 상태 업데이트
      const isShowdownBlocking = gameState.isShowdownInProgressRef.current;

      console.log('🎯 [CURRENT_TURN] checking condition:', {
        'stateData.pot': stateData.pot,
        'stateData.phase': stateData.phase,
        'stateData.currentTurn': stateData.currentTurn,
        conditionMet: stateData.pot !== undefined || !!stateData.phase,
      });

      if (stateData.pot !== undefined || stateData.phase) {
        gameState.setGameState((prev) => ({
          ...(prev || {
            tableId: data.tableId as string,
            players: [],
            communityCards: [],
            pot: 0,
            currentPlayer: null,
            phase: 'waiting' as const,
            smallBlind: 10,
            bigBlind: 20,
            minRaise: 0,
            currentBet: 0,
          }),
          phase: isShowdownBlocking ? (prev?.phase || 'showdown') : ((stateData.phase as GameState['phase']) || prev?.phase || 'waiting'),
          pot: isShowdownBlocking ? (prev?.pot ?? 0) : ((stateData.pot as number) ?? prev?.pot ?? 0),
          communityCards: (stateData.communityCards && Array.isArray(stateData.communityCards) && stateData.communityCards.length > 0)
            ? parseCards(stateData.communityCards as string[])
            : (prev?.communityCards || []),
          currentBet: (stateData.currentBet as number) ?? prev?.currentBet ?? 0,
        }));

        if (stateData.currentTurn !== undefined) {
          console.log('🎯 [CURRENT_TURN] Setting currentTurnPosition to:', stateData.currentTurn);
          gameState.setCurrentTurnPosition(stateData.currentTurn as number);
        } else {
          console.log('🎯 [CURRENT_TURN] stateData.currentTurn is undefined, NOT setting');
        }
      } else {
        console.log('🎯 [CURRENT_TURN] Condition NOT met, skipping currentTurn update');
      }

      // 딜러/블라인드 위치
      if (data.dealerPosition !== undefined) {
        gameState.setDealerPosition(data.dealerPosition as number);
      }
      if (stateData.smallBlindSeat !== undefined) {
        gameState.setSmallBlindPosition(stateData.smallBlindSeat as number);
      }
      if (stateData.bigBlindSeat !== undefined) {
        gameState.setBigBlindPosition(stateData.bigBlindSeat as number);
      }

      // 사이드 팟
      if (stateData.sidePots && Array.isArray(stateData.sidePots)) {
        gameState.setSidePots(stateData.sidePots.map((sp: { amount: number; eligiblePlayers?: number[]; eligible_positions?: number[] }) => ({
          amount: sp.amount,
          eligiblePlayers: sp.eligiblePlayers || sp.eligible_positions || [],
        })));
      }

      // 새로고침 후 복구: 팟 칩 시각적 표시 복원
      // (게임 진행 중이고 딜링/쇼다운 애니메이션이 아닐 때)
      if (!gameState.isDealingInProgressRef.current && !gameState.isShowdownInProgressRef.current) {
        const potAmount = (stateData.pot as number) ?? 0;
        if (potAmount > 0) {
          console.log('💰 [TABLE_SNAPSHOT] Restoring potChips:', potAmount);
          gameState.setPotChips(potAmount);
        }
      }

      // 새로고침 후 복구: allowedActions 복원 (현재 턴인 경우)
      if (data.allowedActions && Array.isArray(data.allowedActions) && data.allowedActions.length > 0) {
        console.log('🎮 [TABLE_SNAPSHOT] Restoring allowedActions:', data.allowedActions);
        actions.setAllowedActions(data.allowedActions as AllowedAction[]);
      }
    });

    // TABLE_STATE_UPDATE 핸들러
    const unsubTableUpdate = wsClient.on('TABLE_STATE_UPDATE', (rawData) => {
      const data = rawData as Record<string, unknown>;
      const changes = (data.changes || {}) as Record<string, unknown>;
      const updateType = data.updateType || changes.updateType;

      console.log('TABLE_STATE_UPDATE received:', { updateType, changes });

      // seat_taken 처리
      if (updateType === 'seat_taken' && changes.position !== undefined) {
        gameState.setSeats((prevSeats) => {
          const existingIdx = prevSeats.findIndex(s => s.position === changes.position);
          const newSeat: SeatInfo = {
            position: changes.position as number,
            player: {
              userId: changes.userId as string,
              nickname: (changes.nickname || changes.userId) as string,
            },
            stack: (changes.stack as number) || 0,
            // 중간 입장: 착석 시 기본 상태는 sitting_out
            status: (changes.status as SeatInfo['status']) || 'sitting_out',
            betAmount: 0,
            totalBet: 0,
          };

          if (existingIdx >= 0) {
            const updated = [...prevSeats];
            updated[existingIdx] = newSeat;
            return updated;
          }
          return [...prevSeats, newSeat];
        });

        if (changes.userId === userId) {
          gameState.setMyPosition(changes.position as number);
        }
      }

      // player_left 처리
      if (updateType === 'player_left' && changes.position !== undefined) {
        gameState.setSeats((prevSeats) => prevSeats.filter(s => s.position !== changes.position));
        if (changes.userId === userId) {
          gameState.setMyPosition(null);
        }
      }

      // bot_added 처리
      if (updateType === 'bot_added' && changes.position !== undefined) {
        gameState.setSeats((prevSeats) => {
          const existingIdx = prevSeats.findIndex(s => s.position === changes.position);
          const newSeat: SeatInfo = {
            position: changes.position as number,
            player: {
              userId: changes.botId as string,
              nickname: (changes.nickname || `Bot_${(changes.botId as string)?.slice(-4)}`) as string,
            },
            stack: (changes.stack as number) || 0,
            status: 'active',
            betAmount: 0,
            totalBet: 0,
          };

          if (existingIdx >= 0) {
            const updated = [...prevSeats];
            updated[existingIdx] = newSeat;
            return updated;
          }
          return [...prevSeats, newSeat];
        });
      }

      // gameState 업데이트
      const isShowdownBlocking = gameState.isShowdownInProgressRef.current;
      gameState.setGameState((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          pot: isShowdownBlocking ? prev.pot : ((changes.pot as number) ?? prev.pot),
          phase: isShowdownBlocking ? prev.phase : ((changes.phase as GameState['phase']) ?? prev.phase),
          currentBet: (changes.currentBet as number) ?? prev.currentBet,
          currentPlayer: (changes.currentPlayer as string) ?? prev.currentPlayer,
        };
      });

      // 플레이어 스택/베팅 업데이트
      if (changes.players && Array.isArray(changes.players)) {
        const playersArray = changes.players as Array<{
          position: number;
          stack?: number;
          bet?: number;
          totalBet?: number;
          status?: SeatInfo['status'];
        }>;

        // DEBUG: 플레이어 상태 업데이트 추적
        const foldedPlayers = playersArray.filter((p) => p.status === 'folded');
        if (foldedPlayers.length > 0) {
          console.log(`🔴 [FOLD_DEBUG] TABLE_STATE_UPDATE: folded players=`, foldedPlayers.map(p => p.position), `isShowdownBlocking=${isShowdownBlocking}`);
        }

        if (isShowdownBlocking) {
          // 쇼다운 중 stack은 pending으로 저장
          playersArray.forEach((p) => {
            if (p.stack !== undefined) {
              gameState.pendingStackUpdatesRef.current[p.position] = p.stack;
            }
          });
          // status는 즉시 업데이트 (폴드 어둡게 효과 등 UI 반영 필요)
          gameState.setSeats((prevSeats) => {
            return prevSeats.map((seat) => {
              const playerUpdate = playersArray.find((p) => p.position === seat.position);
              if (playerUpdate && seat.player && playerUpdate.status !== undefined) {
                if (playerUpdate.status === 'folded') {
                  console.log(`🔴 [FOLD_DEBUG] Updating seat ${seat.position} status to 'folded' (showdown blocking)`);
                }
                return { ...seat, status: playerUpdate.status };
              }
              return seat;
            });
          });
        } else {
          gameState.setSeats((prevSeats) => {
            return prevSeats.map((seat) => {
              const playerUpdate = playersArray.find(
                (p) => p.position === seat.position
              );
              if (playerUpdate && seat.player) {
                if (playerUpdate.status === 'folded' && seat.status !== 'folded') {
                  console.log(`🔴 [FOLD_DEBUG] Updating seat ${seat.position} status to 'folded' (normal)`);
                }
                return {
                  ...seat,
                  stack: playerUpdate.stack ?? seat.stack,
                  betAmount: playerUpdate.bet ?? seat.betAmount,
                  totalBet: playerUpdate.totalBet ?? seat.totalBet,
                  status: playerUpdate.status ?? seat.status,
                };
              }
              return seat;
            });
          });
        }
      }

      // lastAction 처리
      if (changes.lastAction) {
        const { type, amount, position } = changes.lastAction as { type: string; amount?: number; position: number };
        soundManager.play(type);
        // 베팅 액션 시 칩 사운드 추가
        if (type === 'bet' || type === 'call' || type === 'raise') {
          chipSoundManager.playCall();
        } else if (type === 'all_in' || type === 'allin') {
          chipSoundManager.playAllin();
        }
        isShowingActionEffectRef.current = true;
        gameState.setPlayerActions((prev) => ({
          ...prev,
          [position]: { type, amount, timestamp: Date.now() },
        }));
        setTimeout(() => {
          isShowingActionEffectRef.current = false;
        }, 1000);
      }
    });

    // ACTION_RESULT 핸들러
    const unsubActionResult = wsClient.on('ACTION_RESULT', (rawData) => {
      const data = rawData as { success: boolean; action?: unknown; errorMessage?: string; shouldRefresh?: boolean };
      console.log('ACTION_RESULT received:', data);
      actions.setIsActionPending(false);

      if (data.success && data.action) {
        gameState.setTurnStartTime(null);
      } else if (!data.success) {
        setError(data.errorMessage || '액션 처리에 실패했습니다.');
        if (data.shouldRefresh) {
          wsClient.send('SUBSCRIBE_TABLE', { tableId });
        }
      }
    });

    // SEAT_RESULT 핸들러
    const unsubSeatResult = wsClient.on('SEAT_RESULT', (rawData) => {
      const data = rawData as { success: boolean; position?: number; errorMessage?: string };
      if (data.success) {
        gameState.setMyPosition(data.position!);
        // TABLE_STATE_UPDATE로 좌석 정보가 업데이트되므로 SUBSCRIBE_TABLE 불필요
        fetchUser();
      } else {
        setError(data.errorMessage || '좌석 배정에 실패했습니다.');
      }
    });

    // ERROR 핸들러
    const unsubError = wsClient.on('ERROR', (rawData) => {
      const data = rawData as { errorMessage?: string; message?: string };
      setError(data.errorMessage || data.message || '오류가 발생했습니다.');
    });

    // LEAVE_RESULT 핸들러
    const unsubLeaveResult = wsClient.on('LEAVE_RESULT', (rawData) => {
      const data = rawData as { success: boolean; errorCode?: string; errorMessage?: string };
      if (data.success || data.errorCode === 'TABLE_NOT_SEATED') {
        router.push('/lobby');
      } else {
        setError(data.errorMessage || '테이블 퇴장에 실패했습니다.');
      }
    });

    // GAME_STARTING 핸들러
    const unsubGameStarting = wsClient.on('GAME_STARTING', (rawData) => {
      const data = rawData as { countdownSeconds?: number };
      const countdownSeconds = data.countdownSeconds || 5;
      setCountdown(countdownSeconds);

      // 기존 타이머 정리 (중복 실행 방지)
      if (countdownTimerRef.current) {
        clearInterval(countdownTimerRef.current);
        countdownTimerRef.current = null;
      }

      let remaining = countdownSeconds;
      countdownTimerRef.current = setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
          if (countdownTimerRef.current) {
            clearInterval(countdownTimerRef.current);
            countdownTimerRef.current = null;
          }
          setCountdown(null);
        } else {
          setCountdown(remaining);
        }
      }, 1000);
    });

    // HAND_STARTED 핸들러
    const unsubHandStart = wsClient.on('HAND_STARTED', (rawData) => {
      const data = rawData as Parameters<typeof processHandStarted>[0];
      console.log('HAND_STARTED received:', data);

      if (gameState.isShowdownInProgressRef.current) {
        gameState.pendingHandStartedRef.current = data;
        return;
      }
      processHandStarted(data);
    });

    // TURN_PROMPT 핸들러
    const unsubTurnPrompt = wsClient.on('TURN_PROMPT', (rawData) => {
      const data = rawData as Parameters<typeof applyTurnPromptData>[0];
      console.log('🎯 TURN_PROMPT received:', data);

      if (gameState.isShowdownInProgressRef.current) {
        gameState.pendingTurnPromptRef.current = data;
        return;
      }
      applyTurnPromptData(data);
    });

    // TURN_CHANGED 핸들러
    const unsubTurnChanged = wsClient.on('TURN_CHANGED', (rawData) => {
      const data = rawData as { currentBet?: number; currentPlayer?: number | null };
      console.log('TURN_CHANGED received:', data);

      if (data.currentBet !== undefined) {
        gameState.setGameState((prev) => {
          if (!prev) return prev;
          return { ...prev, currentBet: data.currentBet! };
        });
      }

      gameState.setTurnStartTime(null);
      if (data.currentPlayer !== undefined && data.currentPlayer !== null) {
        gameState.setCurrentTurnPosition(data.currentPlayer);
      }
    });

    // TIMEOUT_FOLD 핸들러
    const unsubTimeoutFold = wsClient.on('TIMEOUT_FOLD', (rawData) => {
      const data = rawData as { position?: number; action?: string };
      console.log('⏰ TIMEOUT_FOLD received:', data);

      if (data.position !== undefined) {
        const actionType = data.action === 'check' ? 'timeout_check' : 'timeout_fold';
        gameState.setPlayerActions((prev) => ({
          ...prev,
          [data.position!]: { type: actionType, timestamp: Date.now() },
        }));
      }
    });

    // COMMUNITY_CARDS 핸들러
    const unsubCommunityCards = wsClient.on('COMMUNITY_CARDS', (rawData) => {
      const data = rawData as { cards?: string[]; phase?: string };
      console.log('COMMUNITY_CARDS received:', data);

      if (data.cards) {
        const newCards = parseCards(data.cards);
        const currentCount = gameState.communityCardsRef.current.length;
        const newCardCount = newCards.length;
        const cardsToReveal = newCardCount - currentCount;

        if (cardsToReveal > 0) {
          gameState.setIsRevealingCommunity(true);
          gameState.setGameState((prev) => {
            if (!prev) return prev;
            return { ...prev, phase: (data.phase as GameState['phase']) || prev.phase };
          });

          // 칩 수집 애니메이션
          const currentSeats = gameState.seatsRef.current;
          const chipsToCollect = currentSeats
            .filter(s => s.betAmount > 0)
            .map(s => ({ position: s.position, amount: s.betAmount }));

          const CHIP_COLLECT_DELAY = 700;
          const CARD_REVEAL_START_DELAY = 400;

          if (chipsToCollect.length > 0) {
            const totalCollected = chipsToCollect.reduce((sum, c) => sum + c.amount, 0);
            gameState.setCollectingChips(chipsToCollect);
            chipSoundManager.playCollect();
            setTimeout(() => gameState.setIsCollectingToPot(true), 50);

            setTimeout(() => {
              gameState.setCollectingChips([]);
              gameState.setIsCollectingToPot(false);
              gameState.setPotChips(prev => prev + totalCollected);
              gameState.setSeats(prev => prev.map(s => ({ ...s, betAmount: 0 })));
            }, CHIP_COLLECT_DELAY);
          }

          const cardRevealDelay = chipsToCollect.length > 0
            ? CHIP_COLLECT_DELAY + CARD_REVEAL_START_DELAY
            : 300;

          setTimeout(() => {
            gameState.setGameState((prev) => {
              if (!prev) return prev;
              gameState.communityCardsRef.current = newCards;
              return { ...prev, communityCards: newCards };
            });

            // 카드 뒷면이 먼저 보이도록 초기 딜레이 추가
            const CARD_BACK_SHOW_DELAY = 400; // 뒷면 표시 시간
            const CARD_REVEAL_DELAY = 300; // 카드간 플립 간격
            for (let i = 0; i < cardsToReveal; i++) {
              setTimeout(() => {
                gameState.setRevealedCommunityCount(currentCount + i + 1);
                const cardSound = new Audio('/sounds/community_card.webm');
                cardSound.volume = 0.5;
                cardSound.play().catch(() => {});

                if (i === cardsToReveal - 1) {
                  setTimeout(() => gameState.setIsRevealingCommunity(false), 300);
                }
              }, CARD_BACK_SHOW_DELAY + CARD_REVEAL_DELAY * i);
            }
          }, cardRevealDelay);
        } else {
          gameState.setGameState((prev) => {
            if (!prev) return prev;
            gameState.communityCardsRef.current = newCards;
            return { ...prev, communityCards: newCards, phase: (data.phase as GameState['phase']) || prev.phase };
          });
          gameState.setRevealedCommunityCount(newCardCount);
        }
      }
    });

    // HAND_RESULT 핸들러
    const unsubHandResult = wsClient.on('HAND_RESULT', (rawData) => {
      const data = rawData as {
        showdown?: Array<{ seat?: number; position?: number; holeCards?: string[] }>;
        winners?: Array<{ seat: number; amount: number }>;
        communityCards?: string[];
      };
      console.log('HAND_RESULT received:', data);

      gameState.isShowdownInProgressRef.current = true;
      gameState.setTurnStartTime(null);
      gameState.setCurrentTurnPosition(null);
      actions.setAllowedActions([]);
      actions.setIsActionPending(false);
      isShowingActionEffectRef.current = false;
      gameState.pendingTurnPromptRef.current = null;
      gameState.pendingHandStartedRef.current = null;
      gameState.pendingStackUpdatesRef.current = {};

      const INITIAL_DELAY = 500;
      const CHIP_COLLECT_DURATION = 700;
      const PRE_CHIP_DISTRIBUTE_DELAY = 500;

      setTimeout(() => {
        gameState.setPlayerActions({});

        const currentSeats = gameState.seatsRef.current;
        const chipsToCollect = currentSeats
          .filter(s => s.betAmount > 0)
          .map(s => ({ position: s.position, amount: s.betAmount }));

        const totalChipsAmount = chipsToCollect.reduce((sum, c) => sum + c.amount, 0);

        if (chipsToCollect.length > 0) {
          gameState.setCollectingChips(chipsToCollect);
          chipSoundManager.playCollect();
          setTimeout(() => gameState.setIsCollectingToPot(true), 100);

          setTimeout(() => {
            gameState.setCollectingChips([]);
            gameState.setIsCollectingToPot(false);
            gameState.setPotChips(totalChipsAmount);
            gameState.setSeats(prev => prev.map(s => ({ ...s, betAmount: 0 })));
          }, CHIP_COLLECT_DURATION);
        }

        gameState.setGameState((prev) => {
          if (!prev) return prev;
          const newCommunityCards = data.communityCards
            ? data.communityCards.map((card: string) => ({
                rank: card.slice(0, -1),
                suit: card.slice(-1),
              }))
            : prev.communityCards;
          return { ...prev, phase: 'showdown', communityCards: newCommunityCards };
        });

        // 쇼다운이 아닌 경우 (모두 폴드)
        if (!data.showdown || data.showdown.length === 0) {
          const showWinnerDelay = chipsToCollect.length > 0 ? CHIP_COLLECT_DURATION + 300 : 300;
          setTimeout(() => {
            gameState.setIsShowdownDisplay(true);
            if (data.winners && data.winners.length > 0) {
              const winnerSeats = data.winners.map(w => w.seat);
              gameState.setWinnerPositions(winnerSeats);
              gameState.setShowdownPhase('winner_announced');

              const amounts: Record<number, number> = {};
              let totalWinAmount = 0;
              data.winners.forEach(w => {
                amounts[w.seat] = w.amount;
                totalWinAmount += w.amount;
              });
              gameState.setWinnerAmounts(amounts);

              if (winnerSeats.length > 0 && totalWinAmount > 0) {
                setTimeout(() => {
                  gameState.setPotChips(0);
                  gameState.setDistributingChip({
                    amount: totalWinAmount,
                    toPosition: winnerSeats[0],
                  });
                  chipSoundManager.playWin();

                  const pendingStacks = { ...gameState.pendingStackUpdatesRef.current };
                  if (Object.keys(pendingStacks).length > 0) {
                    gameState.setSeats(prevSeats => prevSeats.map(seat => {
                      if (pendingStacks[seat.position] !== undefined) {
                        return { ...seat, stack: pendingStacks[seat.position] };
                      }
                      return seat;
                    }));
                    gameState.pendingStackUpdatesRef.current = {};
                  }
                }, PRE_CHIP_DISTRIBUTE_DELAY);
              }
            }
            fetchUser();
            setTimeout(() => completeShowdown(), 5000);
          }, showWinnerDelay);
          return;
        }

        // 순차적 쇼다운
        let communityCards: Card[] = [];
        if (data.communityCards && data.communityCards.length > 0) {
          communityCards = data.communityCards.map((card: string) => ({
            rank: card.slice(0, -1),
            suit: card.slice(-1),
          }));
        }
        if (communityCards.length === 0 && gameState.communityCardsRef.current.length > 0) {
          communityCards = gameState.communityCardsRef.current;
        }

        const cardsMap: Record<number, Card[]> = {};
        const handRanksAll: Record<number, string> = {};
        const bestCardsAll: Record<number, Card[]> = {};
        const positions: number[] = [];

        data.showdown.forEach((sd) => {
          const pos = sd.seat ?? sd.position!;
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

        const currentDealer = gameState.dealerPosition ?? 0;
        const maxSeats = 9;
        const sortedPositions = [...positions].sort((a, b) => {
          const aOffset = (a - currentDealer + maxSeats) % maxSeats;
          const bOffset = (b - currentDealer + maxSeats) % maxSeats;
          return aOffset - bOffset;
        });

        const winnerSeats = data.winners?.map(w => w.seat) || [];
        const amounts: Record<number, number> = {};
        data.winners?.forEach(w => {
          amounts[w.seat] = w.amount;
        });

        const winnerHandRanksMap: Record<number, string> = {};
        const winnerBestCardsMap: Record<number, Card[]> = {};
        winnerSeats.forEach((pos: number) => {
          if (handRanksAll[pos]) winnerHandRanksMap[pos] = handRanksAll[pos];
          if (bestCardsAll[pos]) winnerBestCardsMap[pos] = bestCardsAll[pos];
        });

        const INTRO_DURATION = 1500;
        const REVEAL_DELAY = 1500;
        const WINNER_DISPLAY_TIME = 4000;

        const showdownStartDelay = chipsToCollect.length > 0 ? CHIP_COLLECT_DURATION + 300 : 300;
        setTimeout(() => {
          gameState.setShowdownCards(cardsMap);
          gameState.setAllHandRanks(handRanksAll);
          gameState.setIsShowdownDisplay(true);
          gameState.setShowdownPhase('intro');
          gameState.setRevealedPositions(new Set());

          setTimeout(() => {
            gameState.setShowdownPhase('revealing');

            if (sortedPositions.length === 0) {
              gameState.setShowdownPhase('winner_announced');
              gameState.setWinnerPositions(winnerSeats);
              gameState.setWinnerAmounts(amounts);
              gameState.setWinnerHandRanks(winnerHandRanksMap);
              gameState.setWinnerBestCards(winnerBestCardsMap);

              const totalWinAmount = Object.values(amounts).reduce((sum, amt) => sum + amt, 0);
              if (winnerSeats.length > 0 && totalWinAmount > 0) {
                setTimeout(() => {
                  gameState.setPotChips(0);
                  gameState.setDistributingChip({
                    amount: totalWinAmount,
                    toPosition: winnerSeats[0],
                  });
                  chipSoundManager.playWin();
                }, PRE_CHIP_DISTRIBUTE_DELAY);
              }
              setTimeout(() => completeShowdown(), WINNER_DISPLAY_TIME);
              return;
            }

            sortedPositions.forEach((pos, index) => {
              setTimeout(() => {
                gameState.setRevealedPositions(prev => new Set([...prev, pos]));
                const openSound = new Audio('/sounds/opencard.webm');
                openSound.volume = 0.5;
                openSound.play().catch(() => {});

                if (index === sortedPositions.length - 1) {
                  setTimeout(() => {
                    gameState.setShowdownPhase('winner_announced');
                    gameState.setWinnerPositions(winnerSeats);
                    gameState.setWinnerAmounts(amounts);
                    gameState.setWinnerHandRanks(winnerHandRanksMap);
                    gameState.setWinnerBestCards(winnerBestCardsMap);

                    const totalWinAmount = Object.values(amounts).reduce((sum, amt) => sum + amt, 0);
                    if (winnerSeats.length > 0 && totalWinAmount > 0) {
                      setTimeout(() => {
                        gameState.setPotChips(0);
                        gameState.setDistributingChip({
                          amount: totalWinAmount,
                          toPosition: winnerSeats[0],
                        });
                        chipSoundManager.playWin();

                        const pendingStacks = { ...gameState.pendingStackUpdatesRef.current };
                        if (Object.keys(pendingStacks).length > 0) {
                          gameState.setSeats(prevSeats => prevSeats.map(seat => {
                            if (pendingStacks[seat.position] !== undefined) {
                              return { ...seat, stack: pendingStacks[seat.position] };
                            }
                            return seat;
                          }));
                          gameState.pendingStackUpdatesRef.current = {};
                        }
                      }, PRE_CHIP_DISTRIBUTE_DELAY);
                    }
                    setTimeout(() => completeShowdown(), WINNER_DISPLAY_TIME);
                  }, 800);
                }
              }, REVEAL_DELAY * index);
            });
          }, INTRO_DURATION);
        }, showdownStartDelay);

        fetchUser();
      }, INITIAL_DELAY);
    });

    // CONNECTION_STATE 핸들러
    const unsubConnectionState = wsClient.on('CONNECTION_STATE', (rawData) => {
      const data = rawData as { state: string };
      if (data.state === 'connected') {
        setIsConnected(true);
        // 초기 연결 시에만 SUBSCRIBE_TABLE을 보내므로 여기서는 중복 호출하지 않음
      } else {
        setIsConnected(false);
      }
    });

    // SEND_FAILED 핸들러
    const unsubSendFailed = wsClient.on('SEND_FAILED', (rawData) => {
      const data = rawData as { event: string };
      if (data.event !== 'PING') {
        setError('액션 전송 실패: 서버에 연결되지 않았습니다.');
      }
    });

    // CONNECTION_LOST 핸들러
    const unsubConnectionLost = wsClient.on('CONNECTION_LOST', () => {
      setIsConnected(false);
      setError('서버와의 연결이 끊어졌습니다. 페이지를 새로고침해주세요.');
    });

    // STACK_ZERO 핸들러
    const unsubStackZero = wsClient.on('STACK_ZERO', (rawData) => {
      console.log('STACK_ZERO received:', rawData);
      // 쇼다운 중이면 나중에 처리 (모달이 쇼다운 애니메이션을 가리지 않도록)
      if (gameState.isShowdownInProgressRef.current) {
        console.log('🎰 STACK_ZERO: Showdown in progress, storing in pendingStackZeroRef');
        gameState.pendingStackZeroRef.current = true;
      } else {
        // 스택 0 콜백 호출 (리바이 모달 표시)
        if (onStackZeroRef.current) {
          onStackZeroRef.current();
        }
      }
    });

    // REBUY_RESULT 핸들러
    const unsubRebuyResult = wsClient.on('REBUY_RESULT', (rawData) => {
      const data = rawData as {
        success: boolean;
        stack?: number;
        seat?: number;
        errorCode?: string;
        errorMessage?: string;
      };
      console.log('REBUY_RESULT received:', data);
      if (data.success) {
        // 잔액 갱신
        fetchUser();
      } else {
        // 에러 표시
        setError(data.errorMessage || '리바이에 실패했습니다.');
      }
    });

    // ADD_BOT_RESULT 핸들러 (page.tsx에서 상태 관리, 여기서는 SUBSCRIBE_TABLE만)
    const unsubAddBotResult = wsClient.on('ADD_BOT_RESULT', (rawData) => {
      const data = rawData as { success: boolean; errorMessage?: string };
      // 상태 리셋 및 에러 처리는 page.tsx에서 담당
      // 여기서는 로깅만
      if (!data.success) {
        console.log('[ADD_BOT_RESULT] Failed:', data.errorMessage);
      }
    });

    // START_BOT_LOOP_RESULT 핸들러 (page.tsx에서 상태 관리)
    const unsubBotLoopResult = wsClient.on('START_BOT_LOOP_RESULT', (rawData) => {
      const data = rawData as { success: boolean; botsAdded?: number; gameStarted?: boolean; errorMessage?: string };
      // 상태 리셋 및 에러 처리는 page.tsx에서 담당
      // 여기서는 로깅만
      if (!data.success) {
        console.log('[START_BOT_LOOP_RESULT] Failed:', data.errorMessage);
      }
    });

    return () => {
      // 타이머 클린업 (메모리 누수 방지)
      if (countdownTimerRef.current) {
        clearInterval(countdownTimerRef.current);
        countdownTimerRef.current = null;
      }

      unsubTableSnapshot();
      unsubTableUpdate();
      unsubActionResult();
      unsubSeatResult();
      unsubError();
      unsubLeaveResult();
      unsubGameStarting();
      unsubHandStart();
      unsubTurnPrompt();
      unsubTurnChanged();
      unsubTimeoutFold();
      unsubCommunityCards();
      unsubHandResult();
      unsubConnectionState();
      unsubSendFailed();
      unsubConnectionLost();
      unsubStackZero();
      unsubRebuyResult();
      unsubAddBotResult();
      unsubBotLoopResult();
      wsClient.send('UNSUBSCRIBE_TABLE', { tableId });
    };
  // 의도적으로 gameState, actions 등을 의존성에서 제외 - 무한 루프 방지
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tableId, userId, router, fetchUser]);

  return {
    isConnected,
    error,
    setError,
    countdown,
  };
}
