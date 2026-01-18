'use client';

import { useCallback } from 'react';

interface GameHeaderProps {
  tableId: string;
  balance: number;
  onLeave: () => void;
  isLeaving?: boolean;
  isConnected?: boolean;
}

/**
 * 게임방 상단 헤더 UI (고정 크기, 비율 유지)
 * Figma 디자인: https://www.figma.com/design/fMyK6bJyw7bZkHWE1KXbvB
 *
 * 원본 Figma:
 * - 테이블 프레임: 358x74px
 * - 잔액 프레임: 358x74px
 * - 내부 박스: 235x56px
 *
 * 게임 컨테이너(500px) 기준 스케일: 0.65
 * - 프레임: 233x48px
 * - 내부 박스: 153x36px
 */

// Figma → 게임 컨테이너 스케일
const SCALE = 0.65;

// 스케일된 사이즈
const FRAME_W = Math.round(358 * SCALE);  // 233px
const FRAME_H = Math.round(74 * SCALE);   // 48px
const BOX_W = Math.round(235 * SCALE);    // 153px
const BOX_H = Math.round(56 * SCALE);     // 36px
const BOX_OFFSET = Math.round(9 * SCALE); // 6px
const FONT_LARGE = Math.round(24 * SCALE); // 16px
const FONT_MED = Math.round(18 * SCALE);   // 12px
const ICON_SIZE = Math.round(23 * SCALE);  // 15px

export function GameHeader({
  tableId,
  balance,
  onLeave,
  isLeaving = false,
  isConnected = true,
}: GameHeaderProps) {
  const handleLeaveClick = useCallback(() => {
    if (!isLeaving) {
      onLeave();
    }
  }, [isLeaving, onLeave]);

  return (
    <div
      className="absolute"
      style={{
        top: 8,
        left: 10,
        right: 10,
        height: FRAME_H,
      }}
    >
      {/* 왼쪽: 나가기 + 테이블 정보 */}
      <div
        className="absolute"
        style={{
          left: 0,
          top: 0,
          width: FRAME_W,
          height: FRAME_H,
        }}
      >
        {/* 외곽 프레임 */}
        <div
          className="absolute rounded-[7px]"
          style={{
            inset: 0,
            background: 'linear-gradient(180deg, #3A3A3A 0%, #1A1A1A 100%)',
            boxShadow: '0px 3px 3px rgba(0, 0, 0, 0.25), inset 0px 1px 0px rgba(255, 255, 255, 0.1)',
          }}
        />

        {/* 내부 다크 박스 - 오른쪽 정렬 */}
        <div
          className="absolute rounded-[7px]"
          style={{
            right: BOX_OFFSET,
            top: BOX_OFFSET,
            width: BOX_W,
            height: BOX_H,
            backgroundColor: '#0E1614',
          }}
        />

        {/* 나가기 버튼 */}
        <button
          onClick={handleLeaveClick}
          disabled={isLeaving}
          className="absolute flex items-center gap-1 transition-opacity hover:opacity-80 disabled:opacity-50"
          style={{
            left: 8,
            top: 0,
            height: FRAME_H,
          }}
        >
          <svg
            width={Math.round(16 * SCALE)}
            height={Math.round(16 * SCALE)}
            viewBox="0 0 24 24"
            fill="none"
          >
            <path
              d="M15 6L9 12L15 18"
              stroke="#C1C1C1"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span
            className="font-semibold"
            style={{ fontSize: FONT_LARGE, color: '#C1C1C1' }}
          >
            나가기
          </span>
        </button>

        {/* 테이블 이름 */}
        <span
          className="absolute font-medium text-center"
          style={{
            right: BOX_OFFSET,
            top: BOX_OFFSET,
            width: BOX_W,
            height: BOX_H,
            lineHeight: `${BOX_H}px`,
            fontSize: FONT_MED,
            color: '#C1C1C1',
          }}
        >
          테이블 #{tableId.slice(0, 8)}
        </span>

        {/* 연결 끊김 */}
        {!isConnected && (
          <div
            className="absolute bg-red-500 rounded-full animate-pulse"
            style={{ right: -3, top: -3, width: 8, height: 8 }}
          />
        )}
      </div>

      {/* 오른쪽: 잔액 표시 */}
      <div
        className="absolute"
        style={{
          right: 0,
          top: 0,
          width: FRAME_W,
          height: FRAME_H,
        }}
      >
        {/* 외곽 프레임 (초록색 + 글로우) */}
        <div
          className="absolute rounded-[7px]"
          style={{
            inset: 0,
            backgroundColor: '#048565',
            boxShadow: '0px 3px 3px rgba(0, 0, 0, 0.25), inset 0px 0px 4px rgba(0, 255, 200, 0.64)',
          }}
        />

        {/* 내부 다크 박스 - 오른쪽 정렬 */}
        <div
          className="absolute rounded-[7px]"
          style={{
            right: BOX_OFFSET,
            top: BOX_OFFSET,
            width: BOX_W,
            height: BOX_H,
            backgroundColor: '#0E1614',
          }}
        />

        {/* 코인 + 잔액 라벨 */}
        <div
          className="absolute flex items-center gap-1"
          style={{ left: 10, top: 0, height: FRAME_H }}
        >
          <svg
            width={ICON_SIZE}
            height={ICON_SIZE}
            viewBox="0 0 23 23"
            fill="none"
          >
            <ellipse cx="11.5" cy="5" rx="8" ry="3" fill="#FFD700" />
            <ellipse cx="11.5" cy="5" rx="8" ry="3" fill="url(#coinGrad1)" />
            <path d="M3.5 5v4c0 1.657 3.582 3 8 3s8-1.343 8-3V5" stroke="#DAA520" strokeWidth="0.5" fill="#FFD700" />
            <ellipse cx="11.5" cy="9" rx="8" ry="3" fill="#FFD700" />
            <path d="M3.5 9v4c0 1.657 3.582 3 8 3s8-1.343 8-3V9" stroke="#DAA520" strokeWidth="0.5" fill="#FFD700" />
            <ellipse cx="11.5" cy="13" rx="8" ry="3" fill="#FFD700" />
            <path d="M3.5 13v4c0 1.657 3.582 3 8 3s8-1.343 8-3V13" stroke="#DAA520" strokeWidth="0.5" fill="#FFD700" />
            <ellipse cx="11.5" cy="17" rx="8" ry="3" fill="#FFD700" />
            <ellipse cx="11.5" cy="17" rx="8" ry="3" fill="url(#coinGrad2)" />
            <defs>
              <linearGradient id="coinGrad1" x1="11.5" y1="2" x2="11.5" y2="8" gradientUnits="userSpaceOnUse">
                <stop stopColor="#FFF8DC" />
                <stop offset="1" stopColor="#FFD700" />
              </linearGradient>
              <linearGradient id="coinGrad2" x1="11.5" y1="14" x2="11.5" y2="20" gradientUnits="userSpaceOnUse">
                <stop stopColor="#FFF8DC" />
                <stop offset="1" stopColor="#FFD700" />
              </linearGradient>
            </defs>
          </svg>
          <span
            className="font-semibold"
            style={{ fontSize: FONT_LARGE, color: '#EBEBEB' }}
          >
            잔액
          </span>
        </div>

        {/* 금액 */}
        <span
          className="absolute font-semibold text-center"
          style={{
            right: BOX_OFFSET,
            top: BOX_OFFSET,
            width: BOX_W,
            height: BOX_H,
            lineHeight: `${BOX_H}px`,
            fontSize: FONT_LARGE,
            letterSpacing: '0.6px',
            color: '#FFCE2C',
          }}
        >
          {balance.toLocaleString()}
        </span>
      </div>
    </div>
  );
}

export default GameHeader;
