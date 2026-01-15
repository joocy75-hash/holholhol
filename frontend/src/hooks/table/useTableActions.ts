/**
 * @fileoverview 플레이어 액션 핸들러 훅
 * @module hooks/table/useTableActions
 *
 * 포커 게임의 모든 플레이어 액션을 관리하는 커스텀 훅입니다.
 *
 * @description
 * 이 훅은 플레이어가 수행할 수 있는 모든 액션을 처리합니다:
 * - fold: 핸드 포기
 * - check: 체크 (베팅 없이 패스)
 * - call: 콜 (현재 베팅 금액 맞추기)
 * - raise: 레이즈 (베팅 금액 올리기)
 * - all-in: 올인 (전체 스택 베팅)
 *
 * 중복 클릭 방지를 위해 isActionPending 상태를 관리하며,
 * 타이머 만료 시 자동 폴드 기능도 제공합니다.
 *
 * @example
 * ```tsx
 * const actions = useTableActions({
 *   tableId: 'table-123',
 *   raiseAmount: 100,
 *   setRaiseAmount: setRaiseAmount,
 *   setShowRaiseSlider: setShowRaiseSlider,
 * });
 *
 * // 폴드 액션 실행
 * actions.handleFold();
 *
 * // 레이즈 액션 실행
 * actions.handleRaise();
 *
 * // 액션 가능 여부 확인
 * if (!actions.isActionPending) {
 *   // 액션 버튼 활성화
 * }
 * ```
 */

import { useState, useCallback } from 'react';
import { wsClient } from '@/lib/websocket';
import type { AllowedAction } from '@/types/table';

/**
 * useTableActions 훅의 props 인터페이스
 *
 * @interface UseTableActionsProps
 * @property {string} tableId - 테이블 고유 ID
 * @property {number} raiseAmount - 현재 설정된 레이즈 금액
 * @property {Function} setRaiseAmount - 레이즈 금액 설정 함수
 * @property {Function} setShowRaiseSlider - 레이즈 슬라이더 표시 여부 설정 함수
 */
interface UseTableActionsProps {
  tableId: string;
  raiseAmount: number;
  setRaiseAmount: (amount: number) => void;
  setShowRaiseSlider: (show: boolean) => void;
}

/**
 * useTableActions 훅의 반환값 인터페이스
 *
 * @interface UseTableActionsReturn
 * @property {boolean} isActionPending - 액션 처리 중 여부 (중복 클릭 방지)
 * @property {AllowedAction[]} allowedActions - 현재 허용된 액션 목록
 * @property {boolean} hasAutoFolded - 자동 폴드 발생 여부
 * @property {Function} handleFold - 폴드 액션 핸들러
 * @property {Function} handleCheck - 체크 액션 핸들러
 * @property {Function} handleCall - 콜 액션 핸들러
 * @property {Function} handleRaise - 레이즈 액션 핸들러
 * @property {Function} handleAllIn - 올인 액션 핸들러
 * @property {Function} handleAutoFold - 자동 폴드 핸들러
 */
interface UseTableActionsReturn {
  // 상태
  isActionPending: boolean;
  allowedActions: AllowedAction[];
  hasAutoFolded: boolean;

  // 액션 핸들러
  handleFold: () => void;
  handleCheck: () => void;
  handleCall: () => void;
  handleRaise: () => void;
  handleAllIn: () => void;
  handleAutoFold: () => void;

  // 상태 설정
  setIsActionPending: (pending: boolean) => void;
  setAllowedActions: (actions: AllowedAction[]) => void;
  setHasAutoFolded: (folded: boolean) => void;
  clearAllowedActions: () => void;
}

/**
 * 플레이어 액션 핸들러 훅
 *
 * 포커 게임의 모든 플레이어 액션을 관리합니다.
 * WebSocket을 통해 서버에 액션을 전송하고,
 * 중복 클릭 방지 및 자동 폴드 기능을 제공합니다.
 *
 * @param {UseTableActionsProps} props - 훅 설정
 * @returns {UseTableActionsReturn} 액션 핸들러 및 상태
 */
export function useTableActions({
  tableId,
  raiseAmount,
  setRaiseAmount: _setRaiseAmount,
  setShowRaiseSlider,
}: UseTableActionsProps): UseTableActionsReturn {
  const [isActionPending, setIsActionPending] = useState(false);
  const [allowedActions, setAllowedActions] = useState<AllowedAction[]>([]);
  const [hasAutoFolded, setHasAutoFolded] = useState(false);

  const clearAllowedActions = useCallback(() => {
    setAllowedActions([]);
  }, []);

  const handleFold = useCallback(() => {
    if (isActionPending) return;
    setIsActionPending(true);
    setAllowedActions([]);
    setShowRaiseSlider(false);
    wsClient.send('ACTION_REQUEST', {
      tableId,
      actionType: 'fold',
    });
  }, [tableId, isActionPending, setShowRaiseSlider]);

  const handleCheck = useCallback(() => {
    if (isActionPending) return;
    setIsActionPending(true);
    setAllowedActions([]);
    setShowRaiseSlider(false);
    wsClient.send('ACTION_REQUEST', {
      tableId,
      actionType: 'check',
    });
  }, [tableId, isActionPending, setShowRaiseSlider]);

  const handleCall = useCallback(() => {
    if (isActionPending) return;
    setIsActionPending(true);
    setAllowedActions([]);
    setShowRaiseSlider(false);
    wsClient.send('ACTION_REQUEST', {
      tableId,
      actionType: 'call',
    });
  }, [tableId, isActionPending, setShowRaiseSlider]);

  const handleRaise = useCallback(() => {
    if (isActionPending) return;
    setIsActionPending(true);
    setAllowedActions([]);
    setShowRaiseSlider(false);
    wsClient.send('ACTION_REQUEST', {
      tableId,
      actionType: 'raise',
      amount: raiseAmount,
    });
  }, [tableId, raiseAmount, isActionPending, setShowRaiseSlider]);

  const handleAllIn = useCallback(() => {
    if (isActionPending) return;
    setIsActionPending(true);
    setAllowedActions([]);
    setShowRaiseSlider(false);
    wsClient.send('ACTION_REQUEST', {
      tableId,
      actionType: 'all_in',
    });
  }, [tableId, isActionPending, setShowRaiseSlider]);

  const handleAutoFold = useCallback(() => {
    if (hasAutoFolded || isActionPending) return;
    setHasAutoFolded(true);
    setIsActionPending(true);
    setAllowedActions([]);
    setShowRaiseSlider(false);
    console.log('Auto-fold triggered');
    wsClient.send('ACTION_REQUEST', {
      tableId,
      actionType: 'fold',
    });
  }, [tableId, hasAutoFolded, isActionPending, setShowRaiseSlider]);

  return {
    isActionPending,
    allowedActions,
    hasAutoFolded,
    handleFold,
    handleCheck,
    handleCall,
    handleRaise,
    handleAllIn,
    handleAutoFold,
    setIsActionPending,
    setAllowedActions,
    setHasAutoFolded,
    clearAllowedActions,
  };
}
