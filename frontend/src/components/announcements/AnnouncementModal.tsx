'use client';

import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAnnouncementStore } from '@/stores/announcement';
import { AnnouncementPriority, AnnouncementType } from '@/types/websocket';

// 우선순위별 스타일
const priorityStyles: Record<
  AnnouncementPriority,
  { headerBg: string; icon: string; iconColor: string }
> = {
  low: {
    headerBg: 'from-gray-600/20 to-gray-700/20',
    icon: 'ℹ️',
    iconColor: 'text-gray-400',
  },
  normal: {
    headerBg: 'from-blue-600/20 to-blue-700/20',
    icon: '📢',
    iconColor: 'text-blue-400',
  },
  high: {
    headerBg: 'from-orange-600/20 to-orange-700/20',
    icon: '⚠️',
    iconColor: 'text-orange-400',
  },
  critical: {
    headerBg: 'from-red-600/30 to-red-700/30',
    icon: '🚨',
    iconColor: 'text-red-400',
  },
};

// 공지 유형별 라벨
const typeLabels: Record<AnnouncementType, string> = {
  notice: '공지사항',
  event: '이벤트',
  maintenance: '점검 안내',
  urgent: '긴급 공지',
};

export function AnnouncementModal() {
  const { activeAnnouncement, dismissActive } = useAnnouncementStore();

  // ESC 키로 닫기
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && activeAnnouncement) {
        dismissActive();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeAnnouncement, dismissActive]);

  return (
    <AnimatePresence>
      {activeAnnouncement && (
        <>
          {/* 배경 오버레이 */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm"
            onClick={dismissActive}
          />

          {/* 모달 */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            transition={{ type: 'spring', duration: 0.3 }}
            className="fixed inset-0 z-[101] flex items-center justify-center p-4 pointer-events-none"
          >
            <div className="w-full max-w-md bg-gradient-to-b from-[#1a1a2e] to-[#16213e] rounded-2xl shadow-2xl border border-[#4a4a6a]/50 overflow-hidden pointer-events-auto">
              {/* 헤더 */}
              <div
                className={`px-6 py-4 bg-gradient-to-r ${priorityStyles[activeAnnouncement.priority].headerBg} border-b border-white/10`}
              >
                <div className="flex items-center gap-3">
                  <span className="text-2xl">
                    {priorityStyles[activeAnnouncement.priority].icon}
                  </span>
                  <div>
                    <span
                      className={`text-xs font-medium ${priorityStyles[activeAnnouncement.priority].iconColor}`}
                    >
                      {typeLabels[activeAnnouncement.type]}
                    </span>
                    <h2 className="text-xl font-bold text-white">
                      {activeAnnouncement.title}
                    </h2>
                  </div>
                </div>
              </div>

              {/* 본문 */}
              <div className="p-6">
                <div className="text-gray-300 whitespace-pre-wrap leading-relaxed">
                  {activeAnnouncement.content}
                </div>
              </div>

              {/* 푸터 */}
              <div className="px-6 py-4 bg-black/30 border-t border-white/5 flex justify-end gap-3">
                <button
                  onClick={dismissActive}
                  className="px-6 py-2.5 bg-gradient-to-r from-[var(--accent)] to-[#3a8f6a] hover:from-[#3a8f6a] hover:to-[var(--accent)] text-white font-medium rounded-xl transition-all duration-200"
                >
                  확인
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
