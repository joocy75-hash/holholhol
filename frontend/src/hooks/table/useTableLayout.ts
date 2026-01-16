/**
 * @fileoverview 테이블 레이아웃 계산 훅
 * @module hooks/table/useTableLayout
 *
 * 테이블 중앙 좌표와 플레이어 위치 좌표를 계산하는 커스텀 훅입니다.
 *
 * @description
 * 이 훅은 테이블 UI의 레이아웃 계산을 담당합니다:
 * - 테이블 중앙 좌표 계산 (팟 표시, 칩 애니메이션 기준점)
 * - 각 플레이어 좌석의 화면 좌표 계산
 * - 윈도우 리사이즈 시 자동 재계산
 *
 * 플레이어 좌석은 현재 사용자(myPosition)를 기준으로
 * 상대적인 위치로 표시됩니다.
 *
 * @example
 * ```tsx
 * const tableRef = useRef<HTMLDivElement>(null);
 * const { tableCenter, playerPositions } = useTableLayout({
 *   tableRef,
 *   seats,
 *   myPosition,
 * });
 *
 * // 팟 위치에 칩 표시
 * <PotDisplay position={tableCenter} />
 *
 * // 플레이어 위치에 칩 애니메이션
 * <ChipAnimation
 *   from={playerPositions[fromSeat]}
 *   to={tableCenter}
 * />
 * ```
 */

import { useState, useEffect, RefObject } from 'react';
import { SEAT_POSITIONS } from '@/components/table/PlayerSeat';
import type { SeatInfo } from './useGameState';

/**
 * useTableLayout 훅의 props 인터페이스
 *
 * @interface UseTableLayoutProps
 * @property {RefObject<HTMLDivElement|null>} tableRef - 테이블 컨테이너 ref
 * @property {SeatInfo[]} seats - 현재 좌석 정보 배열
 * @property {number|null} myPosition - 현재 사용자의 좌석 번호
 */
interface UseTableLayoutProps {
  tableRef: RefObject<HTMLDivElement | null>;
  seats: SeatInfo[];
  myPosition: number | null;
}

/**
 * useTableLayout 훅의 반환값 인터페이스
 *
 * @interface UseTableLayoutReturn
 * @property {{ x: number; y: number }} tableCenter - 테이블 중앙 좌표 (픽셀)
 * @property {Record<number, { x: number; y: number }>} playerPositions - 각 좌석별 화면 좌표
 */
interface UseTableLayoutReturn {
  tableCenter: { x: number; y: number };
  playerPositions: Record<number, { x: number; y: number }>;
}

/**
 * 테이블 레이아웃 계산 훅
 *
 * 테이블 중앙 좌표와 각 플레이어 좌석의 화면 좌표를 계산합니다.
 * 윈도우 리사이즈 시 자동으로 재계산됩니다.
 *
 * @param {UseTableLayoutProps} props - 훅 설정
 * @returns {UseTableLayoutReturn} 테이블 중앙 및 플레이어 위치 좌표
 */
export function useTableLayout({
  tableRef,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  seats: _seats, // 호환성을 위해 유지, 실제로는 사용하지 않음
  myPosition,
}: UseTableLayoutProps): UseTableLayoutReturn {
  const [tableCenter, setTableCenter] = useState({ x: 0, y: 0 });
  const [playerPositions, setPlayerPositions] = useState<Record<number, { x: number; y: number }>>({});

  // 테이블 중앙 좌표 계산
  useEffect(() => {
    const updateTableCenter = () => {
      if (tableRef.current) {
        const rect = tableRef.current.getBoundingClientRect();
        setTableCenter({ x: rect.width / 2, y: rect.height * 0.32 }); // POT 위치 (32%)
      }
    };
    updateTableCenter();
    window.addEventListener('resize', updateTableCenter);
    return () => window.removeEventListener('resize', updateTableCenter);
  }, [tableRef]);

  // 플레이어 위치 좌표 계산 - 모든 9개 좌석에 대해 계산 (딜링 애니메이션용)
  useEffect(() => {
    const updatePlayerPositions = () => {
      if (!tableRef.current) return;
      const rect = tableRef.current.getBoundingClientRect();
      const positions: Record<number, { x: number; y: number }> = {};
      
      // 모든 9개 좌석 위치를 미리 계산 (visualIndex 0-8)
      // 딜링 애니메이션에서 visualIndex로 조회하므로 모든 위치가 필요
      for (let visualIndex = 0; visualIndex < SEAT_POSITIONS.length; visualIndex++) {
        const seatPos = SEAT_POSITIONS[visualIndex];
        const topPercent = parseFloat(seatPos.top) / 100;
        const leftPercent = parseFloat(seatPos.left) / 100;
        positions[visualIndex] = {
          x: rect.width * leftPercent,
          y: rect.height * topPercent - 30, // 프로필 위로 조정
        };
      }
      
      console.log('🎯 Player positions updated (all 9 seats):', {
        myPosition,
        positions: Object.keys(positions).map(k => ({ visualIndex: k, ...positions[parseInt(k)] })),
      });
      
      setPlayerPositions(positions);
    };
    updatePlayerPositions();
    window.addEventListener('resize', updatePlayerPositions);
    return () => window.removeEventListener('resize', updatePlayerPositions);
  }, [tableRef, myPosition]);

  return { tableCenter, playerPositions };
}
