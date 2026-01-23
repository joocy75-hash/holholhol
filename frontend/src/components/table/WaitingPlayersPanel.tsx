'use client';

import { motion, AnimatePresence } from 'framer-motion';
import type { SeatInfo } from '@/hooks/table/useGameState';
import { getAvatarById, DEFAULT_AVATAR_ID } from '@/constants/avatars';

interface WaitingPlayersPanelProps {
  /** 모든 좌석 정보 */
  seats: SeatInfo[];
  /** sitting_out 상태인 좌석 번호들 */
  sittingOutPositions: Set<number>;
  /** 현재 사용자 포지션 */
  myPosition: number | null;
}

/**
 * 대기 중인 플레이어(sitting_out)를 작은 아이콘으로 표시하는 패널
 */
export function WaitingPlayersPanel({
  seats,
  sittingOutPositions,
  myPosition,
}: WaitingPlayersPanelProps) {
  // sitting_out 상태인 플레이어만 필터링 (본인 제외 - 본인은 좌석에서 직접 확인 가능)
  const waitingPlayers = seats.filter(
    (seat) =>
      seat.player &&
      seat.position !== myPosition &&  // 본인 제외
      (seat.status === 'sitting_out' || sittingOutPositions.has(seat.position))
  );

  // 대기 중인 다른 플레이어가 없으면 패널 숨김
  if (waitingPlayers.length === 0) {
    return null;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="absolute top-2 left-2 z-20"
    >
      <div className="bg-black/70 backdrop-blur-sm rounded-lg px-3 py-2 border border-white/10">
        {/* 헤더 */}
        <div className="flex items-center gap-1.5 mb-2">
          <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
          <span className="text-[10px] text-amber-400 font-medium">
            대기 중 ({waitingPlayers.length})
          </span>
        </div>

        {/* 대기 중인 플레이어 목록 (본인 제외) */}
        <div className="flex flex-wrap gap-2">
          <AnimatePresence mode="popLayout">
            {waitingPlayers.map((seat) => {
              const player = seat.player!;

              return (
                <motion.div
                  key={seat.position}
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-white/10"
                >
                  {/* 아바타 */}
                  {(() => {
                    const avatarId = player.avatarUrl ? parseInt(player.avatarUrl, 10) : null;
                    const avatar = getAvatarById(avatarId) ?? getAvatarById(DEFAULT_AVATAR_ID);
                    return (
                      <div
                        className="relative w-5 h-5 rounded-full overflow-hidden flex-shrink-0 flex items-center justify-center"
                        style={{ background: avatar?.gradient || 'linear-gradient(135deg, #374151, #1f2937)' }}
                      >
                        <span className="text-[8px] text-white/90 font-medium">
                          {player.nickname.charAt(0).toUpperCase()}
                        </span>
                      </div>
                    );
                  })()}

                  {/* 이름 */}
                  <span className="text-[10px] truncate max-w-[60px] text-white/70">
                    {player.nickname}
                  </span>

                  {/* 좌석 번호 */}
                  <span className="text-[8px] text-white/40">
                    #{seat.position + 1}
                  </span>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>

        {/* 안내 텍스트 */}
        <div className="mt-2 text-[8px] text-white/40">
          BB 위치 도달 시 자동 참여
        </div>
      </div>
    </motion.div>
  );
}
