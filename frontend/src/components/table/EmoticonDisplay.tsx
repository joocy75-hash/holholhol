'use client';

import { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { EmoticonReceivedPayload } from '@/types/websocket';

interface DisplayedEmoticon extends EmoticonReceivedPayload {
  displayId: string; // 고유 표시 ID (같은 이모티콘 여러번 표시용)
}

interface EmoticonDisplayProps {
  emoticons: EmoticonReceivedPayload[];
  userSeatMap: Record<string, number>; // userId -> seat position mapping
  seatPositions: { x: number; y: number }[]; // 좌석별 화면 위치
  onRemove: (messageId: string) => void;
}

const DISPLAY_DURATION = 3000; // 3초 표시

export default function EmoticonDisplay({
  emoticons,
  userSeatMap,
  seatPositions,
  onRemove,
}: EmoticonDisplayProps) {
  const [displayedEmoticons, setDisplayedEmoticons] = useState<DisplayedEmoticon[]>([]);

  // 새 이모티콘 추가
  useEffect(() => {
    emoticons.forEach((emoticon) => {
      const displayId = `${emoticon.messageId}-${Date.now()}`;

      setDisplayedEmoticons((prev) => {
        // 이미 표시 중인지 확인
        if (prev.some((e) => e.messageId === emoticon.messageId)) {
          return prev;
        }
        return [...prev, { ...emoticon, displayId }];
      });

      // 일정 시간 후 제거
      setTimeout(() => {
        setDisplayedEmoticons((prev) => prev.filter((e) => e.displayId !== displayId));
        onRemove(emoticon.messageId);
      }, DISPLAY_DURATION);
    });
  }, [emoticons, onRemove]);

  // 사운드 재생
  const playSound = useCallback((soundUrl: string | null) => {
    if (!soundUrl) return;
    try {
      const audio = new Audio(soundUrl);
      audio.volume = 0.5;
      audio.play().catch(() => {
        // 사운드 재생 실패 무시 (자동 재생 정책)
      });
    } catch {
      // 오디오 생성 실패 무시
    }
  }, []);

  // 새 이모티콘 사운드 재생
  // NOTE: displayedEmoticons.length만 의존하는 것은 의도적 설계
  // 전체 배열을 의존성으로 추가하면 이모티콘마다 중복 재생됨
  useEffect(() => {
    displayedEmoticons.forEach((emoticon) => {
      if (emoticon.soundUrl) {
        playSound(emoticon.soundUrl);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [displayedEmoticons.length, playSound]);

  return (
    <AnimatePresence>
      {displayedEmoticons.map((emoticon) => {
        const seatIndex = userSeatMap[emoticon.userId];
        const position = seatPositions[seatIndex];

        if (position === undefined) return null;

        return (
          <motion.div
            key={emoticon.displayId}
            initial={{ opacity: 0, scale: 0.5, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.8, y: -20 }}
            transition={{ type: 'spring', stiffness: 400, damping: 20 }}
            style={{
              position: 'absolute',
              left: `${position.x}%`,
              top: `${position.y - 12}%`,
              transform: 'translate(-50%, -100%)',
              zIndex: 200,
              pointerEvents: 'none',
            }}
          >
            <motion.div
              animate={{
                y: [0, -8, 0],
                scale: [1, 1.1, 1],
              }}
              transition={{
                duration: 0.8,
                repeat: 2,
                ease: 'easeInOut',
              }}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              {/* 이모티콘 */}
              <div
                style={{
                  width: '56px',
                  height: '56px',
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.9) 100%)',
                  border: '2px solid rgba(245, 158, 11, 0.5)',
                  boxShadow: '0 4px 20px rgba(245, 158, 11, 0.3), 0 0 30px rgba(245, 158, 11, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '32px',
                }}
              >
                {emoticon.emoji}
              </div>

              {/* 닉네임 */}
              <div
                style={{
                  padding: '3px 8px',
                  borderRadius: '8px',
                  background: 'rgba(0,0,0,0.7)',
                  backdropFilter: 'blur(4px)',
                }}
              >
                <span
                  style={{
                    fontSize: '10px',
                    color: 'rgba(255,255,255,0.8)',
                    fontWeight: 500,
                    whiteSpace: 'nowrap',
                  }}
                >
                  {emoticon.nickname}
                </span>
              </div>
            </motion.div>
          </motion.div>
        );
      })}
    </AnimatePresence>
  );
}

// =============================================================================
// 테이블 레이아웃별 좌석 위치 (퍼센트)
// =============================================================================

export const SEAT_POSITIONS_6: { x: number; y: number }[] = [
  { x: 50, y: 85 },   // 0: 하단 중앙 (플레이어)
  { x: 15, y: 65 },   // 1: 좌측 하단
  { x: 15, y: 35 },   // 2: 좌측 상단
  { x: 50, y: 15 },   // 3: 상단 중앙
  { x: 85, y: 35 },   // 4: 우측 상단
  { x: 85, y: 65 },   // 5: 우측 하단
];

export const SEAT_POSITIONS_9: { x: number; y: number }[] = [
  { x: 50, y: 88 },   // 0: 하단 중앙
  { x: 22, y: 80 },   // 1: 좌측 하단
  { x: 8, y: 55 },    // 2: 좌측 중앙
  { x: 15, y: 28 },   // 3: 좌측 상단
  { x: 35, y: 12 },   // 4: 상단 좌측
  { x: 65, y: 12 },   // 5: 상단 우측
  { x: 85, y: 28 },   // 6: 우측 상단
  { x: 92, y: 55 },   // 7: 우측 중앙
  { x: 78, y: 80 },   // 8: 우측 하단
];
