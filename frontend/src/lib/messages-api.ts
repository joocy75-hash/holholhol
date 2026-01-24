/**
 * 쪽지 API 클라이언트
 */

import { api } from './api';

// Types
export interface Message {
  id: string;
  title: string;
  content: string;
  isRead: boolean;
  readAt: string | null;
  createdAt: string | null;
}

export interface MessageListResponse {
  items: Message[];
  total: number;
  unreadCount: number;
  page: number;
  pageSize: number;
}

export interface UnreadCountResponse {
  count: number;
}

// API 함수들
export const messagesApi = {
  /**
   * 쪽지 목록 조회
   */
  getMessages: async (
    page: number = 1,
    pageSize: number = 20,
    unreadOnly: boolean = false
  ): Promise<MessageListResponse> => {
    const response = await api.get('/messages', {
      params: { page, page_size: pageSize, unread_only: unreadOnly },
    });
    // snake_case → camelCase 변환
    return {
      items: response.data.items.map((item: Record<string, unknown>) => ({
        id: item.id,
        title: item.title,
        content: item.content,
        isRead: item.is_read,
        readAt: item.read_at,
        createdAt: item.created_at,
      })),
      total: response.data.total,
      unreadCount: response.data.unread_count,
      page: response.data.page,
      pageSize: response.data.page_size,
    };
  },

  /**
   * 읽지 않은 쪽지 개수
   */
  getUnreadCount: async (): Promise<number> => {
    const response = await api.get('/messages/unread-count');
    return response.data.count;
  },

  /**
   * 쪽지 상세 조회 (읽음 처리 포함)
   */
  getMessage: async (messageId: string): Promise<Message> => {
    const response = await api.get(`/messages/${messageId}`);
    const item = response.data;
    return {
      id: item.id,
      title: item.title,
      content: item.content,
      isRead: item.is_read,
      readAt: item.read_at,
      createdAt: item.created_at,
    };
  },

  /**
   * 모든 쪽지 읽음 처리
   */
  markAllAsRead: async (): Promise<{ success: boolean; markedCount: number }> => {
    const response = await api.post('/messages/mark-all-read');
    return {
      success: response.data.success,
      markedCount: response.data.marked_count,
    };
  },

  /**
   * 쪽지 삭제
   */
  deleteMessage: async (messageId: string): Promise<void> => {
    await api.delete(`/messages/${messageId}`);
  },
};
