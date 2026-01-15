'use client';

import { useCallback } from 'react';
import type { AllowedAction } from '@/types/table';

interface ActionPanelProps {
  isSpectator: boolean;
  isMyTurn: boolean;
  allowedActions: AllowedAction[];
  raiseAmount: number;
  setRaiseAmount: (amount: number) => void;
  showRaiseSlider: boolean;
  setShowRaiseSlider: (show: boolean) => void;
  myStack: number;
  minRaise: number;
  timeBankRemaining: number;
  isTimeBankLoading: boolean;
  currentTurnPosition: number | null;
  phase: string | undefined;
  seatsCount: number;
  onFold: () => void;
  onCheck: () => void;
  onCall: () => void;
  onRaise: () => void;
  onAllIn: () => void;
  onUseTimeBank: () => void;
  onStartGame: () => void;
}

export function ActionPanel({
  isSpectator,
  isMyTurn,
  allowedActions,
  raiseAmount,
  setRaiseAmount,
  showRaiseSlider,
  setShowRaiseSlider,
  myStack,
  minRaise,
  timeBankRemaining,
  isTimeBankLoading,
  currentTurnPosition,
  phase,
  seatsCount,
  onFold,
  onCheck,
  onCall,
  onRaise,
  onAllIn,
  onUseTimeBank,
  onStartGame,
}: ActionPanelProps) {
  const canFold = allowedActions.some(a => a.type === 'fold');
  const canCheck = allowedActions.some(a => a.type === 'check');
  const canCall = allowedActions.some(a => a.type === 'call');
  const canRaise = allowedActions.some(a => a.type === 'raise');
  const canBet = allowedActions.some(a => a.type === 'bet');
  const callAction = allowedActions.find(a => a.type === 'call');
  const callAmount = callAction?.amount || 0;
  const raiseAction = allowedActions.find(a => a.type === 'raise' || a.type === 'bet');
  const minRaiseAmount = raiseAction?.minAmount || minRaise || 0;
  const maxRaiseAmount = raiseAction?.maxAmount || myStack;

  const handleRaiseConfirm = useCallback(() => {
    onRaise();
    setShowRaiseSlider(false);
  }, [onRaise, setShowRaiseSlider]);

  if (isSpectator) {
    return (
      <div className="text-center">
        <p className="text-[var(--text-secondary)] text-sm">
          관전 중 - 위 프로필을 클릭하여 참여하세요
        </p>
      </div>
    );
  }

  if (isMyTurn) {
    return (
      <div className="absolute -top-12 left-0 right-0 flex flex-col items-center gap-2">
        {/* 레이즈 슬라이더 팝업 */}
        {showRaiseSlider && (canBet || canRaise) && (
          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 bg-black/90 border border-white/20 rounded-lg p-4 min-w-[280px] z-[150]">
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-white text-sm">레이즈 금액</span>
                <button onClick={() => setShowRaiseSlider(false)} className="text-white/60 hover:text-white text-xl leading-none">×</button>
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
                  onClick={handleRaiseConfirm}
                  disabled={raiseAmount < minRaiseAmount}
                  className="bg-yellow-500 hover:bg-yellow-400 disabled:bg-gray-500 text-black font-bold px-4 py-2 rounded transition-colors"
                >
                  확인
                </button>
              </div>
              <div className="flex gap-2">
                <button onClick={() => setRaiseAmount(minRaiseAmount)} className="flex-1 bg-white/10 hover:bg-white/20 text-white text-xs py-1 rounded">최소</button>
                <button onClick={() => setRaiseAmount(Math.floor((minRaiseAmount + maxRaiseAmount) / 2))} className="flex-1 bg-white/10 hover:bg-white/20 text-white text-xs py-1 rounded">1/2</button>
                <button onClick={() => setRaiseAmount(Math.floor(maxRaiseAmount * 0.75))} className="flex-1 bg-white/10 hover:bg-white/20 text-white text-xs py-1 rounded">3/4</button>
                <button onClick={() => setRaiseAmount(maxRaiseAmount)} className="flex-1 bg-white/10 hover:bg-white/20 text-white text-xs py-1 rounded">MAX</button>
              </div>
            </div>
          </div>
        )}

        {/* 액션 버튼 */}
        <div className="flex gap-2 justify-center items-center">
          {timeBankRemaining > 0 && (
            <button
              onClick={onUseTimeBank}
              disabled={isTimeBankLoading || timeBankRemaining <= 0}
              className={`relative flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-bold text-sm transition-all duration-200 ${
                !isTimeBankLoading && timeBankRemaining > 0
                  ? 'bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-400 hover:to-cyan-400 text-white shadow-lg shadow-blue-500/30 hover:scale-105 active:scale-95'
                  : 'bg-gray-700/50 text-gray-400 cursor-not-allowed'
              }`}
              data-testid="time-bank-button"
            >
              <svg className={`w-4 h-4 ${isTimeBankLoading ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>+30초</span>
              <span className={`ml-1 px-1.5 py-0.5 rounded-full text-xs font-bold ${!isTimeBankLoading && timeBankRemaining > 0 ? 'bg-white/20' : 'bg-gray-600/50'}`} data-testid="time-bank-remaining">
                {timeBankRemaining}
              </span>
            </button>
          )}
          {canFold && (
            <button onClick={onFold} className="relative hover:scale-105 active:scale-95 transition-transform" data-testid="fold-button">
              <img src="/assets/ui/btn_fold.png?v=3" alt="폴드" className="h-[53px]" />
              <span className="absolute inset-0 flex items-center justify-center text-white font-bold text-sm drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)]">폴드</span>
            </button>
          )}
          {canCheck && (
            <button onClick={onCheck} className="relative hover:scale-105 active:scale-95 transition-transform" data-testid="check-button">
              <img src="/assets/ui/btn_check.png?v=3" alt="체크" className="h-[53px]" />
              <span className="absolute inset-0 flex items-center justify-center text-white font-bold text-sm drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)]">체크</span>
            </button>
          )}
          {canCall && (
            <button onClick={onCall} className="relative hover:scale-105 active:scale-95 transition-transform" data-testid="call-button">
              <img src="/assets/ui/btn_call.png?v=3" alt="콜" className="h-[53px]" />
              <span className="absolute inset-0 flex items-center justify-center text-white font-bold text-sm drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)]">
                콜{callAmount > 0 && <span className="text-yellow-300">({callAmount.toLocaleString()})</span>}
              </span>
            </button>
          )}
          {(canBet || canRaise) && (
            <button onClick={() => setShowRaiseSlider(!showRaiseSlider)} className="relative hover:scale-105 active:scale-95 transition-transform" data-testid="raise-button">
              <img src="/assets/ui/btn_raise.png?v=3" alt="레이즈" className="h-[53px]" />
              <span className="absolute inset-0 flex items-center justify-center text-white font-bold text-sm drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)]">
                레이즈<span className="text-yellow-300">({raiseAmount.toLocaleString()})</span>
              </span>
            </button>
          )}
          {(canRaise || canBet || canCall) && (
            <button onClick={onAllIn} className="relative hover:scale-105 active:scale-95 transition-transform" data-testid="allin-button">
              <img src="/assets/ui/btn_allin.png?v=3" alt="올인" className="h-[53px]" />
              <span className="absolute inset-0 flex items-center justify-center text-white font-bold text-sm drop-shadow-[0_2px_2px_rgba(0,0,0,0.8)]">올인</span>
            </button>
          )}
        </div>
      </div>
    );
  }

  // 내 턴이 아닐 때
  if (currentTurnPosition !== null) {
    return (
      <div className="flex flex-col items-center justify-center h-full">
        <p className="text-[var(--text-secondary)] text-sm">다른 플레이어의 차례를 기다리는 중...</p>
      </div>
    );
  }

  if (phase === 'waiting' || !phase) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2">
        <p className="text-[var(--text-secondary)] text-sm">참가자: {seatsCount}명</p>
        <button
          onClick={onStartGame}
          disabled={seatsCount < 2}
          className="px-6 py-2 rounded-lg font-bold text-black bg-gradient-to-r from-yellow-400 via-yellow-500 to-amber-500 hover:from-yellow-300 hover:via-yellow-400 hover:to-amber-400 disabled:from-gray-500 disabled:via-gray-600 disabled:to-gray-700 disabled:text-gray-400 disabled:cursor-not-allowed shadow-lg transition-all duration-200"
        >
          게임 시작
        </button>
        {seatsCount < 2 && <p className="text-xs text-[var(--text-muted)]">2명 이상이 필요합니다</p>}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center h-full">
      <p className="text-[var(--text-secondary)] text-sm">게임 진행 중...</p>
    </div>
  );
}
