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
import { preloadChipStackImages } from '@/components/table/chips';
import { ActionPanel } from '@/components/table/ActionPanel';
import { useGameState } from '@/hooks/table/useGameState';
import { useTableActions } from '@/hooks/table/useTableActions';
import { useTableWebSocket } from '@/hooks/table/useTableWebSocket';
import { GAME_SIZE } from '@/constants/tableCoordinates';
import EmoticonButton from '@/components/table/EmoticonButton';
import EmoticonPanel from '@/components/table/EmoticonPanel';
import EmoticonDisplay, { SEAT_POSITIONS_6, SEAT_POSITIONS_9 } from '@/components/table/EmoticonDisplay';
import { Emoticon } from '@/constants/emoticons';
import { EmoticonReceivedPayload, WaitlistSeatReadyPayload } from '@/types/websocket';
import WaitlistJoinModal from '@/components/table/WaitlistJoinModal';
import WaitlistStatusCard from '@/components/table/WaitlistStatusCard';
import { WaitingPlayersPanel } from '@/components/table/WaitingPlayersPanel';

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
  const [toast, setToast] = useState<{ message: string; type: 'info' | 'warning' | 'error' } | null>(null);

  // 이모티콘 상태
  const [isEmoticonPanelOpen, setIsEmoticonPanelOpen] = useState(false);
  const [receivedEmoticons, setReceivedEmoticons] = useState<EmoticonReceivedPayload[]>([]);

  // 대기열 상태
  const [isInWaitlist, setIsInWaitlist] = useState(false);
  const [waitlistPosition, setWaitlistPosition] = useState<number | null>(null);
  const [showWaitlistModal, setShowWaitlistModal] = useState(false);
  const [isJoiningWaitlist, setIsJoiningWaitlist] = useState(false);
  const [isCancellingWaitlist, setIsCancellingWaitlist] = useState(false);
  const [seatReadyInfo, setSeatReadyInfo] = useState<WaitlistSeatReadyPayload | null>(null);

  // 중간 입장 옵션 상태 (sitting_out 좌석 추적)
  const [sittingOutPositions, setSittingOutPositions] = useState<Set<number>>(new Set());

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
    onStackZero: () => {
      setToast({ message: '칩이 모두 소진되었습니다', type: 'warning' });
      setShowRebuyModal(true);
    },
  });

  // seatsRef 동기화
  useEffect(() => {
    gameState.seatsRef.current = gameState.seats;
  }, [gameState.seats, gameState.seatsRef]);

  // sittingOutPositions 동기화 (초기 로드 및 좌석 상태 변경 시)
  useEffect(() => {
    const sittingOutSeats = gameState.seats
      .filter(seat => seat.status === 'sitting_out')
      .map(seat => seat.position);

    // 함수형 업데이트로 현재 상태와 비교
    setSittingOutPositions(prev => {
      const prevArray = Array.from(prev).sort();
      const newArray = [...sittingOutSeats].sort();

      // 변경이 없으면 이전 Set 유지 (리렌더 방지)
      if (prevArray.length === newArray.length &&
          prevArray.every((pos, i) => pos === newArray[i])) {
        return prev;
      }
      return new Set(sittingOutSeats);
    });
  }, [gameState.seats]);

  // 칩 스택 이미지 프리로딩 (테이블 진입 시 한 번)
  useEffect(() => {
    preloadChipStackImages();
  }, []);

  // 관전자 여부
  const isSpectator = gameState.myPosition === null;
  const isMyTurn = gameState.currentTurnPosition !== null &&
                   gameState.currentTurnPosition === gameState.myPosition &&
                   gameState.dealingComplete;

  // 테이블 만석 여부
  const isTableFull = useMemo(() => {
    const maxSeats = gameState.tableConfig?.maxSeats || 6;
    const occupiedSeats = gameState.seats.filter(s => s.player && s.status !== 'empty').length;
    return occupiedSeats >= maxSeats;
  }, [gameState.tableConfig?.maxSeats, gameState.seats]);

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

  // Toast 자동 해제 (4초 후)
  useEffect(() => {
    if (toast) {
      const timeout = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(timeout);
    }
  }, [toast]);

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

  // 중간 입장 옵션: 참여 모드 토글 핸들러
  const handleJoinModeToggle = useCallback((wantActive: boolean) => {
    if (!tableId) return;
    if (wantActive) {
      wsClient.send('SIT_IN_REQUEST', { tableId });
    } else {
      wsClient.send('SIT_OUT_REQUEST', { tableId });
    }
  }, [tableId]);

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
    console.log('[SEAT] Seat clicked:', position, 'isTableFull:', isTableFull);

    // 만석일 경우 대기열 모달 표시
    if (isTableFull) {
      setShowWaitlistModal(true);
    } else {
      setShowBuyInModal(true);
    }
  }, [setError, isTableFull]);

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
      const data = rawData as { success: boolean; position?: number; errorMessage?: string };
      setIsJoining(false);
      setShowBuyInModal(false);
      if (data.success && data.position !== undefined) {
        // 중간 입장: 착석 시 기본 상태가 sitting_out이므로 추가
        setSittingOutPositions(prev => new Set([...prev, data.position!]));
      } else if (!data.success && data.errorMessage) {
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

  // 이모티콘 전송 핸들러
  const handleSendEmoticon = useCallback((emoticon: Emoticon) => {
    if (!tableId || isSpectator) return;
    wsClient.send('EMOTICON_SEND', {
      tableId,
      emoticonId: emoticon.id,
    });
    setIsEmoticonPanelOpen(false);
  }, [tableId, isSpectator]);

  // 이모티콘 제거 핸들러
  const handleRemoveEmoticon = useCallback((messageId: string) => {
    setReceivedEmoticons((prev) => prev.filter((e) => e.messageId !== messageId));
  }, []);

  // 대기열 등록 핸들러
  const handleJoinWaitlist = useCallback((buyIn: number) => {
    if (!tableId || isJoiningWaitlist) return;
    setIsJoiningWaitlist(true);
    wsClient.send('WAITLIST_JOIN_REQUEST', { tableId, buyIn });
  }, [tableId, isJoiningWaitlist]);

  // 대기열 취소 핸들러
  const handleCancelWaitlist = useCallback(() => {
    if (!tableId || isCancellingWaitlist) return;
    setIsCancellingWaitlist(true);
    wsClient.send('WAITLIST_CANCEL_REQUEST', { tableId });
  }, [tableId, isCancellingWaitlist]);

  // 좌석 준비 수락 핸들러
  const handleAcceptSeat = useCallback(() => {
    if (!tableId || !seatReadyInfo) return;
    // 대기열 상태 초기화
    setIsInWaitlist(false);
    setWaitlistPosition(null);
    setSeatReadyInfo(null);
    // 좌석 요청
    setIsJoining(true);
    wsClient.send('SEAT_REQUEST', { tableId, buyInAmount: seatReadyInfo.buyIn });
  }, [tableId, seatReadyInfo]);

  // 이모티콘 이벤트 구독
  useEffect(() => {
    const unsubEmoticon = wsClient.on('EMOTICON_RECEIVED', (rawData) => {
      const data = rawData as EmoticonReceivedPayload;
      console.log('[EMOTICON] Received:', data);
      setReceivedEmoticons((prev) => [...prev, data]);
    });

    return () => {
      unsubEmoticon();
    };
  }, []);

  // 대기열 이벤트 구독
  useEffect(() => {
    const unsubWaitlistJoined = wsClient.on('WAITLIST_JOINED', (rawData) => {
      const data = rawData as { success: boolean; tableId: string; position: number; joinedAt: string; alreadyWaiting: boolean };
      console.log('[WAITLIST] Joined:', data);
      setIsJoiningWaitlist(false);
      setShowWaitlistModal(false);
      if (data.success) {
        setIsInWaitlist(true);
        setWaitlistPosition(data.position);
      }
    });

    const unsubWaitlistCancelled = wsClient.on('WAITLIST_CANCELLED', (rawData) => {
      const data = rawData as { tableId: string; reason?: string };
      console.log('[WAITLIST] Cancelled:', data);
      setIsCancellingWaitlist(false);
      setIsInWaitlist(false);
      setWaitlistPosition(null);
      setSeatReadyInfo(null);
    });

    const unsubPositionChanged = wsClient.on('WAITLIST_POSITION_CHANGED', (rawData) => {
      const data = rawData as { tableId: string; position: number };
      console.log('[WAITLIST] Position changed:', data);
      setWaitlistPosition(data.position);
    });

    const unsubSeatReady = wsClient.on('WAITLIST_SEAT_READY', (rawData) => {
      const data = rawData as WaitlistSeatReadyPayload;
      console.log('[WAITLIST] Seat ready:', data);
      setSeatReadyInfo(data);
    });

    // 중간 입장 옵션: PLAYER_SIT_OUT 이벤트
    const unsubSitOut = wsClient.on('PLAYER_SIT_OUT', (rawData) => {
      const data = rawData as { tableId: string; position: number; userId: string };
      console.log('[SIT_OUT] Player sitting out:', data);
      setSittingOutPositions(prev => new Set([...prev, data.position]));
      // 좌석 상태도 업데이트
      gameState.setSeats(prev => prev.map(seat =>
        seat.position === data.position
          ? { ...seat, status: 'sitting_out' }
          : seat
      ));
    });

    // 중간 입장 옵션: PLAYER_SIT_IN 이벤트
    const unsubSitIn = wsClient.on('PLAYER_SIT_IN', (rawData) => {
      const data = rawData as { tableId: string; position: number; userId: string; auto?: boolean; reason?: string };
      console.log('[SIT_IN] Player sitting in:', data);
      setSittingOutPositions(prev => {
        const newSet = new Set(prev);
        newSet.delete(data.position);
        return newSet;
      });
      // 좌석 상태도 업데이트
      gameState.setSeats(prev => prev.map(seat =>
        seat.position === data.position
          ? { ...seat, status: 'active' }
          : seat
      ));
      // 자동 sit_in (BB 도달) 시 토스트
      if (data.auto && data.position === gameState.myPosition) {
        setToast({ message: 'BB 위치 도달! 게임에 참여합니다.', type: 'info' });
      }
    });

    return () => {
      unsubWaitlistJoined();
      unsubWaitlistCancelled();
      unsubPositionChanged();
      unsubSeatReady();
      unsubSitOut();
      unsubSitIn();
    };
  }, [gameState.myPosition]);

  // userId -> seatPosition 매핑 생성
  const userSeatMap = useMemo(() => {
    const map: Record<string, number> = {};
    gameState.seats.forEach((seat, index) => {
      if (seat.player?.userId) {
        map[seat.player.userId] = index;
      }
    });
    return map;
  }, [gameState.seats]);

  // 좌석 위치 (maxSeats에 따라 선택)
  const seatPositions = useMemo(() => {
    const maxSeats = gameState.tableConfig?.maxSeats || 6;
    return maxSeats === 9 ? SEAT_POSITIONS_9 : SEAT_POSITIONS_6;
  }, [gameState.tableConfig?.maxSeats]);

  // 모바일에서 스크롤 완전 차단
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    document.body.style.position = 'fixed';
    document.body.style.width = '100%';
    document.body.style.height = '100%';

    return () => {
      document.body.style.overflow = '';
      document.body.style.position = '';
      document.body.style.width = '';
      document.body.style.height = '';
    };
  }, []);

  return (
    <div className="fixed inset-0 flex justify-center items-start bg-black overflow-hidden">
      {/* Scale Wrapper - 스케일된 실제 크기로 레이아웃 공간 확보 */}
      <div
        style={{
          width: GAME_SIZE.WIDTH * gameScale,
          height: GAME_SIZE.HEIGHT * gameScale,
          position: 'relative',
        }}
      >
        {/* 게임 컨테이너 - 고정 크기, CSS scale로 축소 */}
        <div
          ref={tableRef}
          className="bg-cover bg-center bg-no-repeat absolute top-0 left-0"
          style={{
            width: GAME_SIZE.WIDTH,
            height: GAME_SIZE.HEIGHT,
            transform: `scale(${gameScale})`,
            transformOrigin: 'top left',
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

        {/* Toast 알림 - 4초 후 자동 해제 */}
        {toast && (
          <div className={`absolute top-20 left-1/2 -translate-x-1/2 z-50 px-6 py-3 rounded-lg shadow-lg text-white text-sm font-medium transition-all ${
            toast.type === 'warning' ? 'bg-yellow-600/90' :
            toast.type === 'error' ? 'bg-red-500/90' : 'bg-blue-500/90'
          }`}>
            {toast.message}
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
              {/* 대기 중인 플레이어 패널 */}
              <WaitingPlayersPanel
                seats={gameState.seats}
                sittingOutPositions={sittingOutPositions}
                myPosition={gameState.myPosition}
              />

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
                // 중간 입장 옵션
                sittingOutPositions={sittingOutPositions}
                onJoinModeToggle={handleJoinModeToggle}
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

              {/* 이모티콘 표시 */}
              <EmoticonDisplay
                emoticons={receivedEmoticons}
                userSeatMap={userSeatMap}
                seatPositions={seatPositions}
                onRemove={handleRemoveEmoticon}
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
            {/* 이모티콘 버튼 (좌측 하단) */}
            {!isSpectator && (
              <div className="absolute left-4 bottom-[110px]" style={{ position: 'relative' }}>
                <EmoticonButton
                  onClick={() => setIsEmoticonPanelOpen(!isEmoticonPanelOpen)}
                  isActive={isEmoticonPanelOpen}
                />
                <EmoticonPanel
                  isOpen={isEmoticonPanelOpen}
                  onClose={() => setIsEmoticonPanelOpen(false)}
                  onSelect={handleSendEmoticon}
                />
              </div>
            )}

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
                isTableFull={isTableFull}
                isInWaitlist={isInWaitlist}
                waitlistPosition={waitlistPosition}
                onJoinWaitlist={() => setShowWaitlistModal(true)}
                onCancelWaitlist={handleCancelWaitlist}
                isCancellingWaitlist={isCancellingWaitlist}
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
            tableName={gameState.tableName || tableId}
          />
        )}

        {/* 대기열 등록 모달 */}
        {showWaitlistModal && user && (
          <WaitlistJoinModal
            isOpen={showWaitlistModal}
            onClose={() => setShowWaitlistModal(false)}
            onJoin={handleJoinWaitlist}
            roomName={tableId}
            minBuyIn={gameState.tableConfig?.minBuyIn || 400}
            maxBuyIn={gameState.tableConfig?.maxBuyIn || 2000}
            currentWaitlistCount={0}
            userBalance={user.balance || 0}
            isLoading={isJoiningWaitlist}
          />
        )}

        {/* 대기열 - 자리 준비됨 알림 (카운트다운) */}
        {seatReadyInfo && (
          <WaitlistStatusCard
            position={waitlistPosition || 1}
            onCancel={handleCancelWaitlist}
            isLoading={isCancellingWaitlist}
            seatReadyInfo={seatReadyInfo}
            onAcceptSeat={handleAcceptSeat}
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
