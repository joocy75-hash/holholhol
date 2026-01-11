import { useState, useCallback } from 'react';
import { Button } from '@/components/common/Button';
import { Timer } from './Timer';
import type { ValidAction, ActionType } from '@/types/game';
import { formatDollars } from '@/lib/utils/currencyFormatter';

interface ActionPanelProps {
  allowedActions: ValidAction[];
  currentBet: number;
  myBet: number;
  myStack: number;
  pot: number;
  minRaise: number;
  deadline: Date | null;
  disabled: boolean;
  onAction: (actionType: ActionType, amount?: number) => void;
}

export function ActionPanel({
  allowedActions,
  currentBet,
  myBet,
  myStack,
  pot,
  minRaise,
  deadline,
  disabled,
  onAction,
}: ActionPanelProps) {
  const [showRaiseSlider, setShowRaiseSlider] = useState(false);
  const [raiseAmount, setRaiseAmount] = useState(minRaise);

  const callAmount = currentBet - myBet;
  const canCheck = allowedActions.some((a) => a.type === 'check');
  const canCall = allowedActions.some((a) => a.type === 'call');
  const canBet = allowedActions.some((a) => a.type === 'bet');
  const canRaise = allowedActions.some((a) => a.type === 'raise');
  const raiseAction = allowedActions.find((a) => a.type === 'raise' || a.type === 'bet');
  const maxRaise = raiseAction?.maxAmount ?? myStack;

  const handleAction = useCallback(
    (type: ActionType, amount?: number) => {
      setShowRaiseSlider(false);
      onAction(type, amount);
    },
    [onAction]
  );

  const handleRaiseConfirm = useCallback(() => {
    handleAction(canBet ? 'bet' : 'raise', raiseAmount);
  }, [handleAction, canBet, raiseAmount]);

  // Quick bet amounts
  const halfPot = Math.floor(pot / 2);
  const fullPot = pot;
  const doublePot = pot * 2;

  if (disabled || allowedActions.length === 0) {
    return (
      <div className="bg-surface/80 backdrop-blur rounded-lg p-4">
        <p className="text-center text-text-muted">다른 플레이어의 차례입니다...</p>
      </div>
    );
  }

  return (
    <div className="bg-surface/80 backdrop-blur rounded-lg p-4">
      {/* Timer */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm text-text-muted">남은 시간</span>
        <Timer deadline={deadline} />
      </div>

      {/* Raise slider */}
      {showRaiseSlider ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-text-muted">
              {canBet ? '베팅 금액' : '레이즈 금액'}
            </span>
            <span className="text-lg font-bold text-text">{formatDollars(raiseAmount)}</span>
          </div>

          {/* Slider */}
          <input
            type="range"
            min={minRaise}
            max={maxRaise}
            value={raiseAmount}
            onChange={(e) => setRaiseAmount(parseInt(e.target.value))}
            className="w-full h-2 bg-bg rounded-lg appearance-none cursor-pointer accent-primary"
          />

          <div className="flex justify-between text-xs text-text-muted">
            <span>Min: {formatDollars(minRaise)}</span>
            <span>Max: {formatDollars(maxRaise)}</span>
          </div>

          {/* Quick bet buttons */}
          <div className="flex gap-2">
            {halfPot >= minRaise && halfPot <= maxRaise && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setRaiseAmount(halfPot)}
                className="flex-1"
              >
                1/2 팟
              </Button>
            )}
            {fullPot >= minRaise && fullPot <= maxRaise && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setRaiseAmount(fullPot)}
                className="flex-1"
              >
                팟
              </Button>
            )}
            {doublePot >= minRaise && doublePot <= maxRaise && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setRaiseAmount(doublePot)}
                className="flex-1"
              >
                2x 팟
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setRaiseAmount(maxRaise)}
              className="flex-1"
            >
              올인
            </Button>
          </div>

          {/* Confirm/Cancel */}
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => setShowRaiseSlider(false)} className="flex-1">
              취소
            </Button>
            <Button onClick={handleRaiseConfirm} className="flex-1">
              {canBet ? '베팅' : '레이즈'} {formatDollars(raiseAmount)}
            </Button>
          </div>
        </div>
      ) : (
        /* Main action buttons */
        <div className="flex gap-2">
          {/* Fold */}
          <Button
            variant="danger"
            onClick={() => handleAction('fold')}
            className="flex-1"
          >
            폴드
          </Button>

          {/* Check/Call */}
          {canCheck && (
            <Button
              variant="secondary"
              onClick={() => handleAction('check')}
              className="flex-1"
            >
              체크
            </Button>
          )}

          {canCall && (
            <Button
              variant="secondary"
              onClick={() => handleAction('call')}
              className="flex-1"
            >
              콜 {formatDollars(callAmount)}
            </Button>
          )}

          {/* Bet/Raise */}
          {(canBet || canRaise) && (
            <Button
              variant="primary"
              onClick={() => setShowRaiseSlider(true)}
              className="flex-1"
            >
              {canBet ? '베팅' : '레이즈'}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
