'use client';

import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { wsClient } from '@/lib/websocket';
import { analyzeHand } from '@/lib/handEvaluator';
import { HandRankingGuide } from '@/components/table/pmang';
import { RebuyModal } from '@/components/table/RebuyModal';
import { DealingAnimation } from '@/components/table/DealingAnimation';
import { DevAdminPanel } from '@/components/table/DevAdminPanel';
import { TableCenter } from '@/components/table/TableCenter';
import { useAnimatedNumber } from '@/components/table/PotDisplay';
import { BuyInModal } from '@/components/table/BuyInModal';
import { GameHeader } from '@/components/table/GameHeader';
import { SeatsRenderer } from '@/components/table/SeatsRenderer';
import { ChipsRenderer } from '@/components/table/ChipsRenderer';
import { ActionPanel } from '@/components/table/ActionPanel';
import { useGameState } from '@/hooks/table/useGameState';
import { useTableActions } from '@/hooks/table/useTableActions';
import { useTableWebSocket } from '@/hooks/table/useTableWebSocket';
import { GAME_SIZE } from '@/constants/tableCoordinates';

// 게임 컨테이너 스케일 계산 훅
function useGameScale() {
  const [scale, setScale] = useState(1);

  useEffect(() => {
    const updateScale = () => {
      const scaleX = window.innerWidth / GAME_SIZE.WIDTH;
      const scaleY = window.innerHeight / GAME_SIZE.HEIGHT;
      setScale(Math.min(scaleX, scaleY));
    };
    updateScale();
    window.addEventListener('resize', updateScale);
    return () => window.removeEventListener('resize', updateScale);
  }, []);

  return scale;
}

export default function TablePage() {
  const params = useParams();
  const router = useRouter();
  const tableId = params.id as string;
  const { user, fetchUser } = useAuthStore();

  // 게임 컨테이너 스케일
  const gameScale = useGameScale();

  // 게임 상태 훅
  const gameState = useGameState();

  // UI 상태 (page.tsx에서만 관리)
  const [raiseAmount, setRaiseAmount] = useState(0);
  const [showRaiseSlider, setShowRaiseSlider] = useState(false);
  const [isLeaving, setIsLeaving] = useState(false);
  const [isJoining, setIsJoining] = useState(false);
  const [showBuyInModal, setShowBuyInModal] = useState(false);
  const [isAddingBot, setIsAddingBot] = useState(false);
  const [isStartingLoop, setIsStartingLoop] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [showRebuyModal, setShowRebuyModal] = useState(false);

  // 테이블 컨테이너 ref
  const tableRef = useRef<HTMLDivElement>(null);

  // 카드 오픈 상태
  const cardRevealTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const CARD_AUTO_REVEAL_DELAY = 10000;

  // 액션 훅
  const actions = useTableActions({
    tableId,
    raiseAmount,
    setRaiseAmount,
    setShowRaiseSlider,
  });

  // WebSocket 훅
  const { isConnected, error, setError, countdown } = useTableWebSocket({
    tableId,
    userId: user?.id,
    gameState,
    actions: {
      setIsActionPending: actions.setIsActionPending,
      setAllowedActions: actions.setAllowedActions,
      setHasAutoFolded: actions.setHasAutoFolded,
    },
    fetchUser,
  });

  // seatsRef 동기화
  useEffect(() => {
    gameState.seatsRef.current = gameState.seats;
  }, [gameState.seats, gameState.seatsRef]);

  // 관전자 여부
  const isSpectator = gameState.myPosition === null;
  const isMyTurn = gameState.currentTurnPosition !== null &&
                   gameState.currentTurnPosition === gameState.myPosition &&
                   gameState.dealingComplete;

  // DEBUG: 버튼 표시 조건 (렌더링 시마다 확인)
  console.log('🔘 [PAGE] isMyTurn calculation:', {
    currentTurnPosition: gameState.currentTurnPosition,
    myPosition: gameState.myPosition,
    dealingComplete: gameState.dealingComplete,
    isMyTurn,
  });

  // 팟 숫자 애니메이션
  const animatedPot = useAnimatedNumber(gameState.gameState?.pot ?? 0, 600);

  // 카드 오픈 핸들러
  const handleRevealCards = useCallback(() => {
    // 이미 오픈된 상태면 무시
    if (gameState.myCardsRevealed) return;

    gameState.setMyCardsRevealed(true);

    // 서버에 카드 오픈 알림
    if (tableId) {
      wsClient.send('REVEAL_CARDS', { tableId });
    }

    const openSound = new Audio('/sounds/opencard.webm');
    openSound.volume = 0.5;
    openSound.play().catch(() => {});
    if (cardRevealTimeoutRef.current) {
      clearTimeout(cardRevealTimeoutRef.current);
      cardRevealTimeoutRef.current = null;
    }
  }, [gameState, tableId]);

  // 카드 자동 오픈 타이머
  useEffect(() => {
    // 이미 오픈된 상태면 스킵
    if (gameState.myCardsRevealed) return;

    if (gameState.myHoleCards.length > 0 && gameState.dealingComplete) {
      cardRevealTimeoutRef.current = setTimeout(() => {
        // 타이머 실행 시점에도 다시 체크
        if (!gameState.myCardsRevealed) {
          handleRevealCards();
        }
      }, CARD_AUTO_REVEAL_DELAY);
      return () => {
        if (cardRevealTimeoutRef.current) clearTimeout(cardRevealTimeoutRef.current);
      };
    }
  }, [gameState.myHoleCards.length, gameState.myCardsRevealed, gameState.dealingComplete, handleRevealCards]);

  // 새 핸드 시작 시 상태 초기화
  // 주의: 카드가 이미 있거나 딜링 완료 상태면 초기화하지 않음 (TABLE_SNAPSHOT에서 phase 누락으로 인한 오류 방지)
  useEffect(() => {
    if (gameState.gameState?.phase === 'waiting' && !gameState.dealingComplete && gameState.myHoleCards.length === 0) {
      gameState.setMyCardsRevealed(false);
      gameState.setIsDealing(false);
      gameState.setDealingSequence([]);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameState.gameState?.phase]);

  // Fallback: 카드를 받았는데 딜링이 시작되지 않았으면 2초 후 dealingComplete
  useEffect(() => {
    if (gameState.myHoleCards.length > 0 && !gameState.isDealing && !gameState.dealingComplete) {
      const timeout = setTimeout(() => {
        console.log('🎴 Fallback: dealingComplete set to true (no dealing started)');
        gameState.setDealingComplete(true);
        gameState.isDealingInProgressRef.current = false;
      }, 2000);
      return () => clearTimeout(timeout);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameState.myHoleCards.length, gameState.isDealing, gameState.dealingComplete]);

  // Fallback: 딜링이 시작됐는데 3초 이상 지나면 강제로 dealingComplete
  useEffect(() => {
    if (gameState.isDealing) {
      const timeout = setTimeout(() => {
        console.log('🎴 Fallback: dealingComplete set to true (dealing timeout)');
        gameState.setIsDealing(false);
        gameState.setDealingComplete(true);
        gameState.isDealingInProgressRef.current = false;
      }, 3000);
      return () => clearTimeout(timeout);
    }
  }, [gameState.isDealing, gameState]);

  // 에러 메시지 자동 해제 (5초 후)
  useEffect(() => {
    if (error) {
      const timeout = setTimeout(() => {
        setError(null);
      }, 5000);
      return () => clearTimeout(timeout);
    }
  }, [error, setError]);

  // 딜링 완료 핸들러
  const handleDealingComplete = useCallback(() => {
    gameState.setIsDealing(false);
    gameState.setDealingComplete(true);
    gameState.isDealingInProgressRef.current = false;
  }, [gameState]);

  // 리바이 모달 핸들러
  const handleRebuy = useCallback((amount: number) => {
    wsClient.send('REBUY', { tableId, amount });
    setShowRebuyModal(false);
  }, [tableId]);

  const handleLeaveTable = useCallback(() => {
    wsClient.send('LEAVE_REQUEST', { tableId });
    setShowRebuyModal(false);
    router.push('/lobby');
  }, [tableId, router]);

  const handleSpectate = useCallback(() => {
    setShowRebuyModal(false);
  }, []);

  // 테이블 퇴장 핸들러
  const handleLeave = useCallback(() => {
    if (isLeaving) return;
    setIsLeaving(true);
    setError(null);
    wsClient.send('LEAVE_REQUEST', { tableId });
  }, [tableId, isLeaving, setError]);

  // 참여하기 버튼 클릭 (좌석 위치 포함)
  const handleSeatClick = useCallback((position: number) => {
    setError(null);
    // 선택한 좌석 위치를 저장 (향후 특정 좌석 요청에 사용 가능)
    console.log('[SEAT] Seat clicked:', position);
    setShowBuyInModal(true);
  }, [setError]);

  // 바이인 확인
  const handleBuyInConfirm = useCallback((buyIn: number) => {
    setIsJoining(true);
    const sent = wsClient.send('SEAT_REQUEST', { tableId, buyInAmount: buyIn });
    if (!sent) {
      setIsJoining(false);
      setError('서버에 연결되지 않았습니다.');
    }
  }, [tableId, setError]);

  // 바이인 취소
  const handleBuyInCancel = useCallback(() => {
    setShowBuyInModal(false);
  }, []);

  // 게임 시작 핸들러
  const handleStartGame = useCallback(() => {
    wsClient.send('START_GAME', { tableId });
  }, [tableId]);

  // 봇 추가 핸들러
  const handleAddBot = useCallback(() => {
    if (isAddingBot) return;
    setIsAddingBot(true);
    setError(null);
    console.log('[DEV] Sending ADD_BOT_REQUEST...', { tableId, buyIn: gameState.tableConfig?.minBuyIn || 1000 });
    const sent = wsClient.send('ADD_BOT_REQUEST', {
      tableId,
      buyIn: gameState.tableConfig?.minBuyIn || 1000,
    });
    console.log('[DEV] ADD_BOT_REQUEST sent:', sent, 'wsClient.isConnected:', wsClient.isConnected);
    if (!sent) {
      setIsAddingBot(false);
      setError('서버에 연결되지 않았습니다.');
    }
  }, [tableId, gameState.tableConfig, isAddingBot, setError]);

  // 봇 자동 루프 시작 핸들러
  const handleStartBotLoop = useCallback(() => {
    if (isStartingLoop) return;
    setIsStartingLoop(true);
    setError(null);
    console.log('[DEV] Sending START_BOT_LOOP_REQUEST...', { tableId, botCount: 4, buyIn: gameState.tableConfig?.minBuyIn || 1000 });
    const sent = wsClient.send('START_BOT_LOOP_REQUEST', {
      tableId,
      botCount: 4,
      buyIn: gameState.tableConfig?.minBuyIn || 1000,
    });
    console.log('[DEV] START_BOT_LOOP_REQUEST sent:', sent, 'wsClient.isConnected:', wsClient.isConnected);
    if (!sent) {
      setIsStartingLoop(false);
      setError('서버에 연결되지 않았습니다.');
    }
  }, [tableId, gameState.tableConfig, isStartingLoop, setError]);

  // ADD_BOT_RESULT, START_BOT_LOOP_RESULT, SEAT_RESULT 이벤트 구독
  // (SEAT_RESULT는 useTableWebSocket에서도 처리하지만, UI 상태는 여기서 관리)
  useEffect(() => {
    console.log('[DEV] Setting up bot/seat event listeners...');
    
    const unsubAddBot = wsClient.on('ADD_BOT_RESULT', (rawData) => {
      console.log('[DEV] ADD_BOT_RESULT received:', rawData);
      const data = rawData as { success: boolean; errorMessage?: string };
      setIsAddingBot(false);
      if (!data.success && data.errorMessage) {
        setError(data.errorMessage);
      }
      // 봇 추가 후 TABLE_STATE_UPDATE로 자동 업데이트됨
    });

    const unsubBotLoop = wsClient.on('START_BOT_LOOP_RESULT', (rawData) => {
      console.log('[DEV] START_BOT_LOOP_RESULT received:', rawData);
      const data = rawData as { success: boolean; botsAdded?: number; gameStarted?: boolean; errorMessage?: string };
      setIsStartingLoop(false);
      if (data.success) {
        console.log(`[BOT-LOOP] ${data.botsAdded}개 봇 추가됨, 게임 시작: ${data.gameStarted}`);
        // 봇 추가 후 TABLE_STATE_UPDATE로 자동 업데이트됨
      } else if (data.errorMessage) {
        setError(data.errorMessage);
      }
    });

    // SEAT_RESULT - UI 상태 관리 (게임 상태는 useTableWebSocket에서 처리)
    const unsubSeatResult = wsClient.on('SEAT_RESULT', (rawData) => {
      console.log('[DEV] SEAT_RESULT received (page.tsx):', rawData);
      const data = rawData as { success: boolean; errorMessage?: string };
      setIsJoining(false);
      setShowBuyInModal(false);
      if (!data.success && data.errorMessage) {
        setError(data.errorMessage);
      }
    });

    return () => {
      console.log('[DEV] Cleaning up bot/seat event listeners...');
      unsubAddBot();
      unsubBotLoop();
      unsubSeatResult();
    };
  }, [tableId, setError]);

  // DEV 전체 리셋 핸들러
  const handleDevReset = useCallback(async () => {
    if (isResetting) return;
    setIsResetting(true);
    setError(null);
    try {
      const token = localStorage.getItem('access_token');
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      await fetch(`${baseUrl}/api/v1/rooms/${tableId}/dev/remove-bots`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const res = await fetch(`${baseUrl}/api/v1/rooms/${tableId}/dev/reset`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const data = await res.json();
      if (data.success) {
        // 리셋 성공 시 페이지 새로고침으로 모든 상태 완전 초기화
        window.location.reload();
      } else {
        setError(data.message || '리셋 실패');
      }
    } catch {
      setError('리셋 중 오류 발생');
    } finally {
      setIsResetting(false);
    }
  }, [tableId, isResetting, setError, gameState, actions]);

  // 내 좌석 정보
  const mySeat = gameState.seats.find((s) => s.player?.userId === user?.id);
  const myStack = mySeat?.stack || 0;

  // 실시간 족보 계산
  const myHandAnalysis = useMemo(() => {
    if (gameState.myHoleCards.length === 0) return { hand: null, draws: [] };
    const communityCards = gameState.gameState?.communityCards || [];
    return analyzeHand(gameState.myHoleCards, communityCards);
  }, [gameState.myHoleCards, gameState.gameState?.communityCards]);

  // communityCardsRef 업데이트
  useEffect(() => {
    if (gameState.gameState?.communityCards) {
      gameState.communityCardsRef.current = gameState.gameState.communityCards;
    }
  }, [gameState.gameState?.communityCards, gameState.communityCardsRef]);

  // 게임 진행 중 여부
  const gameInProgress = gameState.gameState?.phase !== 'waiting' && gameState.gameState?.phase !== undefined;


  return (
    <div className="min-h-screen flex justify-center items-center bg-black overflow-hidden">
      {/* 고정 크기 게임 컨테이너 - CSS scale로 뷰포트에 맞춤 */}
      <div
        ref={tableRef}
        className="bg-cover bg-center bg-no-repeat relative"
        style={{
          width: GAME_SIZE.WIDTH,
          height: GAME_SIZE.HEIGHT,
          transform: `scale(${gameScale})`,
          transformOrigin: 'center center',
          backgroundImage: "url('/assets/images/backgrounds/background_game.webp')",
        }}
      >
      {/* 메인 게임 영역 - 전체 화면 */}
      <main className="absolute inset-0" data-testid="poker-table">
        {/* 상단 UI - 나가기, 테이블 정보, 잔액 */}
        <GameHeader
          tableId={tableId}
          balance={user?.balance || 0}
          onLeave={handleLeave}
          isLeaving={isLeaving}
          isConnected={isConnected}
        />

        {/* 에러 메시지 - 5초 후 자동 해제 */}
        {error && (
          <div className="absolute top-10 left-0 right-0 z-50 bg-red-500/80 text-white px-4 py-2 text-center text-sm flex items-center justify-center gap-2">
            <span>{error}</span>
            <button
              onClick={() => setError(null)}
              className="ml-2 px-2 py-0.5 bg-white/20 hover:bg-white/30 rounded text-xs"
            >
              ✕
            </button>
          </div>
        )}

          {/* 카운트다운 오버레이 */}
          {countdown !== null && (
            <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/50">
              <div className="text-center">
                <div className="text-6xl font-bold text-yellow-400 animate-pulse">
                  {countdown}
                </div>
                <div className="text-white mt-2">게임 시작!</div>
              </div>
            </div>
          )}

          {/* tableConfig 로드 전 로딩 표시 */}
          {!gameState.tableConfig && (
            <div className="absolute inset-0 flex items-center justify-center z-20">
              <div className="w-8 h-8 border-2 border-yellow-400 border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {/* tableConfig 로드 후에만 게임 UI 렌더링 */}
          {gameState.tableConfig && (
            <>
              {/* 딜링 애니메이션 */}
              <DealingAnimation
                isDealing={gameState.isDealing}
                dealingSequence={gameState.dealingSequence}
                onDealingComplete={handleDealingComplete}
                myPosition={gameState.myPosition}
                maxSeats={gameState.tableConfig.maxSeats}
              />

              {/* 플레이어 좌석 */}
              <SeatsRenderer
                maxSeats={gameState.tableConfig.maxSeats}
                seats={gameState.seats}
                myPosition={gameState.myPosition}
                myHoleCards={gameState.myHoleCards}
                myCardsRevealed={gameState.myCardsRevealed}
                dealingComplete={gameState.dealingComplete}
                currentTurnPosition={gameState.currentTurnPosition}
                currentTurnTime={gameState.currentTurnTime}
                turnStartTime={gameState.turnStartTime}
                winnerPositions={gameState.winnerPositions}
                winnerAmounts={gameState.winnerAmounts}
                winnerBestCards={gameState.winnerBestCards}
                showdownCards={gameState.showdownCards}
                revealedPositions={gameState.revealedPositions}
                allHandRanks={gameState.allHandRanks}
                playerActions={gameState.playerActions}
                gameInProgress={gameInProgress}
                isSpectator={isSpectator}
                onAutoFold={actions.handleAutoFold}
                onSeatClick={handleSeatClick}
                onRevealCards={handleRevealCards}
              />

              {/* 중앙 정보 (팟, 커뮤니티 카드) */}
              <TableCenter
                maxSeats={gameState.tableConfig.maxSeats}
                pot={gameState.gameState?.pot ?? 0}
                animatedPot={animatedPot}
                sidePots={gameState.sidePots}
                communityCards={gameState.gameState?.communityCards || []}
                revealedCommunityCount={gameState.revealedCommunityCount}
                winnerPositions={gameState.winnerPositions}
                winnerBestCards={gameState.winnerBestCards}
                myHandAnalysis={gameState.myCardsRevealed ? myHandAnalysis : { hand: null, draws: [] }}
                isSpectator={isSpectator}
              />

              {/* 베팅 칩 */}
              <ChipsRenderer
                maxSeats={gameState.tableConfig.maxSeats}
                seats={gameState.seats}
                myPosition={gameState.myPosition}
                collectingChips={gameState.collectingChips}
                isCollectingToPot={gameState.isCollectingToPot}
                potChips={gameState.potChips}
                distributingChip={gameState.distributingChip}
                onDistributingComplete={() => gameState.setDistributingChip(null)}
              />
            </>
          )}

          {/* 쇼다운 인트로 오버레이 - 간소화 */}
          {gameState.showdownPhase === 'intro' && (
            <div className="absolute inset-0 z-[100] flex items-center justify-center bg-black/50">
              <div className="px-6 py-2 bg-black/60 rounded-lg">
                <span className="text-lg font-bold text-yellow-400">SHOWDOWN</span>
              </div>
            </div>
          )}

          {/* 하단 액션 패널 */}
          <div className="absolute bottom-0 left-0 right-0 px-2 py-2 z-[70]">
            <div className="h-[100px]">
              <ActionPanel
                isSpectator={isSpectator}
                isMyTurn={isMyTurn}
                allowedActions={actions.allowedActions}
                raiseAmount={raiseAmount}
                setRaiseAmount={setRaiseAmount}
                showRaiseSlider={showRaiseSlider}
                setShowRaiseSlider={setShowRaiseSlider}
                myStack={myStack}
                minRaise={gameState.gameState?.minRaise || 0}
                currentTurnPosition={gameState.currentTurnPosition}
                phase={gameState.gameState?.phase}
                seatsCount={gameState.seats.filter(s => s.player && s.status !== 'empty').length}
                onFold={actions.handleFold}
                onCheck={actions.handleCheck}
                onCall={actions.handleCall}
                onRaise={actions.handleRaise}
                onAllIn={actions.handleAllIn}
                onStartGame={handleStartGame}
              />
            </div>
          </div>
        </main>

        {/* 바이인 모달 */}
        {showBuyInModal && user && (
          <BuyInModal
            config={gameState.tableConfig || { maxSeats: 9, smallBlind: 10, bigBlind: 20, minBuyIn: 400, maxBuyIn: 2000, turnTimeoutSeconds: 30 }}
            userBalance={user.balance || 0}
            onConfirm={handleBuyInConfirm}
            onCancel={handleBuyInCancel}
            isLoading={isJoining}
            tableName={gameState.gameState?.tableId || tableId}
          />
        )}

        {/* 족보 가이드 */}
        {!isSpectator && gameState.myHoleCards.length > 0 && (
          <HandRankingGuide
            holeCards={gameState.myHoleCards}
            communityCards={gameState.gameState?.communityCards || []}
            isVisible={true}
            position="right"
          />
        )}
      </div>

      {/* DEV 어드민 패널 */}
      <DevAdminPanel
        tableId={tableId}
        onReset={handleDevReset}
        onAddBot={handleAddBot}
        onStartBotLoop={handleStartBotLoop}
        isResetting={isResetting}
        isAddingBot={isAddingBot}
        isStartingLoop={isStartingLoop}
      />

      {/* 리바이 모달 */}
      <RebuyModal
        isOpen={showRebuyModal}
        onRebuy={handleRebuy}
        onLeave={handleLeaveTable}
        onSpectate={handleSpectate}
        minBuyIn={gameState.tableConfig?.minBuyIn || 1000}
        maxBuyIn={gameState.tableConfig?.maxBuyIn || 10000}
        defaultBuyIn={gameState.tableConfig?.minBuyIn || 1000}
      />
    </div>
  );
}
