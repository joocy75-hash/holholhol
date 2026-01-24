'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { messagesApi, Message } from '@/lib/messages-api';
import { useAuthStore } from '@/stores/auth';

export default function MessagesPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const [messages, setMessages] = useState<Message[]>([]);
  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedMessage, setSelectedMessage] = useState<Message | null>(null);
  const [showUnreadOnly, setShowUnreadOnly] = useState(false);

  const pageSize = 10;

  // 인증 체크
  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  // 쪽지 목록 로드
  const loadMessages = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await messagesApi.getMessages(page, pageSize, showUnreadOnly);
      setMessages(response.items);
      setTotal(response.total);
      setUnreadCount(response.unreadCount);
    } catch (error) {
      console.error('쪽지 목록 조회 실패:', error);
    } finally {
      setIsLoading(false);
    }
  }, [page, showUnreadOnly]);

  useEffect(() => {
    if (isAuthenticated) {
      loadMessages();
    }
  }, [isAuthenticated, loadMessages]);

  // 쪽지 상세 조회
  const openMessage = async (message: Message) => {
    try {
      const detail = await messagesApi.getMessage(message.id);
      setSelectedMessage(detail);
      // 읽음 처리 후 목록 갱신
      if (!message.isRead) {
        setMessages(prev =>
          prev.map(m => (m.id === message.id ? { ...m, isRead: true } : m))
        );
        setUnreadCount(prev => Math.max(0, prev - 1));
      }
    } catch (error) {
      console.error('쪽지 조회 실패:', error);
    }
  };

  // 모든 쪽지 읽음 처리
  const handleMarkAllRead = async () => {
    try {
      await messagesApi.markAllAsRead();
      setMessages(prev => prev.map(m => ({ ...m, isRead: true })));
      setUnreadCount(0);
    } catch (error) {
      console.error('읽음 처리 실패:', error);
    }
  };

  // 쪽지 삭제
  const handleDelete = async (messageId: string) => {
    try {
      await messagesApi.deleteMessage(messageId);
      setMessages(prev => prev.filter(m => m.id !== messageId));
      setTotal(prev => prev - 1);
      if (selectedMessage?.id === messageId) {
        setSelectedMessage(null);
      }
    } catch (error) {
      console.error('쪽지 삭제 실패:', error);
    }
  };

  // 날짜 포맷팅
  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) {
      return date.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
    } else if (days < 7) {
      return `${days}일 전`;
    } else {
      return date.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' });
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="page-bg-gradient min-h-screen p-4 md:p-8">
      <div className="noise-overlay" />

      <div className="max-w-4xl mx-auto relative z-10">
        {/* 헤더 */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.back()}
              className="glass-btn p-2"
            >
              ← 뒤로
            </button>
            <h1 className="text-2xl font-bold text-white">
              쪽지함
              {unreadCount > 0 && (
                <span className="ml-2 px-2 py-0.5 bg-red-500 text-white text-sm rounded-full">
                  {unreadCount}
                </span>
              )}
            </h1>
          </div>

          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
              <input
                type="checkbox"
                checked={showUnreadOnly}
                onChange={e => {
                  setShowUnreadOnly(e.target.checked);
                  setPage(1);
                }}
                className="w-4 h-4 accent-blue-500"
              />
              안읽은 쪽지만
            </label>

            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="glass-btn text-sm"
              >
                모두 읽음
              </button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* 쪽지 목록 */}
          <div className="glass-card p-4">
            <h2 className="text-lg font-semibold text-white mb-4">
              전체 {total}개
            </h2>

            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                  className="w-8 h-8 border-2 border-white/30 border-t-white rounded-full"
                />
              </div>
            ) : messages.length === 0 ? (
              <div className="text-center py-12 text-gray-400">
                쪽지가 없습니다
              </div>
            ) : (
              <div className="space-y-2">
                {messages.map(message => (
                  <motion.div
                    key={message.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className={`p-3 rounded-xl cursor-pointer transition-all ${
                      selectedMessage?.id === message.id
                        ? 'bg-blue-500/20 border border-blue-500/50'
                        : 'bg-white/5 hover:bg-white/10 border border-transparent'
                    } ${!message.isRead ? 'border-l-4 border-l-blue-500' : ''}`}
                    onClick={() => openMessage(message)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <h3 className={`font-medium truncate ${
                          message.isRead ? 'text-gray-300' : 'text-white'
                        }`}>
                          {!message.isRead && (
                            <span className="inline-block w-2 h-2 bg-blue-500 rounded-full mr-2" />
                          )}
                          {message.title}
                        </h3>
                        <p className="text-sm text-gray-500 truncate mt-1">
                          {message.content.substring(0, 50)}...
                        </p>
                      </div>
                      <span className="text-xs text-gray-500 ml-2 flex-shrink-0">
                        {formatDate(message.createdAt)}
                      </span>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}

            {/* 페이지네이션 */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-4 pt-4 border-t border-white/10">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="glass-btn px-3 py-1 text-sm disabled:opacity-50"
                >
                  이전
                </button>
                <span className="text-sm text-gray-400">
                  {page} / {totalPages}
                </span>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="glass-btn px-3 py-1 text-sm disabled:opacity-50"
                >
                  다음
                </button>
              </div>
            )}
          </div>

          {/* 쪽지 상세 */}
          <AnimatePresence mode="wait">
            {selectedMessage ? (
              <motion.div
                key={selectedMessage.id}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="glass-card p-4"
              >
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-white">
                    {selectedMessage.title}
                  </h2>
                  <button
                    onClick={() => handleDelete(selectedMessage.id)}
                    className="text-red-400 hover:text-red-300 text-sm"
                  >
                    삭제
                  </button>
                </div>

                <div className="text-xs text-gray-500 mb-4">
                  {selectedMessage.createdAt &&
                    new Date(selectedMessage.createdAt).toLocaleString('ko-KR')}
                </div>

                <div className="prose prose-invert prose-sm max-w-none">
                  <p className="text-gray-300 whitespace-pre-wrap leading-relaxed">
                    {selectedMessage.content}
                  </p>
                </div>
              </motion.div>
            ) : (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="glass-card p-4 flex items-center justify-center min-h-[300px]"
              >
                <p className="text-gray-500">쪽지를 선택하세요</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
