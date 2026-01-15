'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { buttonHover, buttonTap, scaleIn } from '@/lib/animations';

interface TimeBankButtonProps {
  /** 남은 타임 뱅크 횟수 */
  remaining: number;
  /** 타임 뱅크 사용 가능 여부 (자신의 턴일 때만) */
  isEnabled: boolean;
  /** 타임 뱅크 사용 핸들러 */
  onUseTimeBank: () => void;
  /** 로딩 상태 */
  isLoading?: boolean;
}

/**
 * 타임 뱅크 버튼 컴포넌트
 * 
 * 플레이어가 자신의 턴에 추가 시간(30초)을 요청할 수 있습니다.
 * 핸드당 최대 3회 사용 가능합니다.
 */
export function TimeBankButton({
  remaining,
  isEnabled,
  onUseTimeBank,
  isLoading = false,
}: TimeBankButtonProps) {
  const canUse = isEnabled && remaining > 0 && !isLoading;

  return (
    <AnimatePresence>
      {remaining > 0 && (
        <motion.div
          className="flex items-center gap-2"
          variants={scaleIn}
          initial="initial"
          animate="animate"
          exit="exit"
        >
          <motion.button
            onClick={canUse ? onUseTimeBank : undefined}
            disabled={!canUse}
            className={`
              relative flex items-center gap-1.5 px-3 py-1.5 rounded-lg
              font-bold text-sm transition-all duration-200
              ${canUse 
                ? 'bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-400 hover:to-cyan-400 text-white shadow-lg shadow-blue-500/30' 
                : 'bg-gray-700/50 text-gray-400 cursor-not-allowed'
              }
            `}
            whileHover={canUse ? buttonHover : undefined}
            whileTap={canUse ? buttonTap : undefined}
            data-testid="time-bank-button"
            aria-label={`타임 뱅크 사용 (남은 횟수: ${remaining})`}
          >
            {/* 타이머 아이콘 */}
            <svg 
              className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} 
              fill="none" 
              viewBox="0 0 24 24" 
              stroke="currentColor"
            >
              <path 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth={2} 
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" 
              />
            </svg>
            
            {/* 버튼 텍스트 */}
            <span>+30초</span>
            
            {/* 남은 횟수 표시 */}
            <span 
              className={`
                ml-1 px-1.5 py-0.5 rounded-full text-xs font-bold
                ${canUse ? 'bg-white/20' : 'bg-gray-600/50'}
              `}
              data-testid="time-bank-remaining"
            >
              {remaining}
            </span>
          </motion.button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
