'use client';

import { motion } from 'framer-motion';

interface JoinModeToggleProps {
  /** true면 active 상태 (바로 참여), false면 sitting_out (BB 대기) */
  isActive: boolean;
  /** 상태 전환 콜백 */
  onToggle: (wantActive: boolean) => void;
  /** 비활성화 여부 (게임 중 폴드 전에는 전환 불가) */
  disabled?: boolean;
}

/**
 * 중간 입장 옵션 토글 버튼
 * - "BB 대기": sitting_out 상태, BB 위치까지 대기
 * - "바로 참여": active 상태, 다음 핸드부터 즉시 참여
 */
export function JoinModeToggle({ isActive, onToggle, disabled }: JoinModeToggleProps) {
  return (
    <div className="flex items-center gap-0.5 bg-black/80 rounded-full p-0.5 border border-white/20 shadow-lg">
      {/* BB 대기 버튼 */}
      <motion.button
        onClick={() => !disabled && onToggle(false)}
        disabled={disabled}
        whileHover={!disabled ? { scale: 1.02 } : undefined}
        whileTap={!disabled ? { scale: 0.98 } : undefined}
        className={`
          px-2.5 py-1 rounded-full text-[10px] font-bold transition-all whitespace-nowrap
          ${!isActive
            ? 'bg-gradient-to-r from-amber-500 to-amber-600 text-black shadow-md'
            : 'bg-transparent text-white/50 hover:text-white/70'}
          ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}
        `}
      >
        BB 대기
      </motion.button>

      {/* 바로 참여 버튼 */}
      <motion.button
        onClick={() => !disabled && onToggle(true)}
        disabled={disabled}
        whileHover={!disabled ? { scale: 1.02 } : undefined}
        whileTap={!disabled ? { scale: 0.98 } : undefined}
        className={`
          px-2.5 py-1 rounded-full text-[10px] font-bold transition-all whitespace-nowrap
          ${isActive
            ? 'bg-gradient-to-r from-green-500 to-green-600 text-black shadow-md'
            : 'bg-transparent text-white/50 hover:text-white/70'}
          ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}
        `}
      >
        바로 참여
      </motion.button>
    </div>
  );
}
