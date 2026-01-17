'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAnnouncementStore } from '@/stores/announcement';

/**
 * 읽지 않은 공지사항 알림 배지
 * - 클릭 시 공지 히스토리 드롭다운 표시
 * - 읽지 않은 개수 표시
 */
export function AnnouncementBadge() {
  const { announcements, unreadCount, markAsRead, markAllAsRead } =
    useAnnouncementStore();
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="relative">
      {/* 벨 아이콘 버튼 */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-gray-400 hover:text-white transition-colors"
        aria-label="공지사항"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-6 w-6"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>

        {/* 읽지 않은 개수 배지 */}
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs font-bold text-white">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* 드롭다운 메뉴 */}
      <AnimatePresence>
        {isOpen && (
          <>
            {/* 배경 클릭 시 닫기 */}
            <div
              className="fixed inset-0 z-40"
              onClick={() => setIsOpen(false)}
            />

            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="absolute right-0 top-full mt-2 w-80 bg-[#1a1a2e] rounded-xl shadow-xl border border-[#4a4a6a]/50 overflow-hidden z-50"
            >
              {/* 헤더 */}
              <div className="px-4 py-3 bg-black/30 border-b border-white/10 flex items-center justify-between">
                <h3 className="font-semibold text-white">공지사항</h3>
                {unreadCount > 0 && (
                  <button
                    onClick={() => markAllAsRead()}
                    className="text-xs text-[var(--accent)] hover:underline"
                  >
                    모두 읽음
                  </button>
                )}
              </div>

              {/* 공지 목록 */}
              <div className="max-h-80 overflow-y-auto">
                {announcements.length === 0 ? (
                  <div className="py-8 text-center text-gray-500">
                    공지사항이 없습니다
                  </div>
                ) : (
                  announcements.map((ann) => (
                    <div
                      key={ann.id}
                      onClick={() => markAsRead(ann.id)}
                      className={`px-4 py-3 border-b border-white/5 cursor-pointer hover:bg-white/5 transition-colors ${
                        !ann.isRead ? 'bg-[var(--accent)]/10' : ''
                      }`}
                    >
                      <div className="flex items-start gap-2">
                        {!ann.isRead && (
                          <span className="mt-1.5 w-2 h-2 rounded-full bg-[var(--accent)] flex-shrink-0" />
                        )}
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-white truncate">
                            {ann.title}
                          </p>
                          <p className="text-sm text-gray-400 line-clamp-2">
                            {ann.content}
                          </p>
                          <p className="text-xs text-gray-500 mt-1">
                            {formatRelativeTime(ann.receivedAt)}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}

function formatRelativeTime(timestamp: number): string {
  const diff = Date.now() - timestamp;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);

  if (minutes < 1) return '방금 전';
  if (minutes < 60) return `${minutes}분 전`;
  if (hours < 24) return `${hours}시간 전`;
  return new Date(timestamp).toLocaleDateString('ko-KR');
}
