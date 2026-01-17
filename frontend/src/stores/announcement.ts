import { create } from 'zustand';
import { AnnouncementPayload, AnnouncementPriority } from '@/types/websocket';

interface StoredAnnouncement extends AnnouncementPayload {
  receivedAt: number;
  isRead: boolean;
}

interface AnnouncementState {
  // 현재 표시할 공지 (모달/팝업)
  activeAnnouncement: StoredAnnouncement | null;

  // 공지 히스토리 (최근 10개)
  announcements: StoredAnnouncement[];

  // 읽지 않은 공지 개수
  unreadCount: number;

  // Actions
  addAnnouncement: (announcement: AnnouncementPayload) => void;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  dismissActive: () => void;
  clearAnnouncements: () => void;
}

// 우선순위별 자동 닫힘 시간 (ms)
const AUTO_DISMISS_DELAYS: Record<AnnouncementPriority, number | null> = {
  low: 5000,
  normal: 8000,
  high: 15000,
  critical: null, // 수동으로 닫아야 함
};

export const useAnnouncementStore = create<AnnouncementState>((set, get) => ({
  activeAnnouncement: null,
  announcements: [],
  unreadCount: 0,

  addAnnouncement: (announcement) => {
    const stored: StoredAnnouncement = {
      ...announcement,
      receivedAt: Date.now(),
      isRead: false,
    };

    set((state) => {
      // 히스토리에 추가 (최대 10개 유지)
      const newAnnouncements = [stored, ...state.announcements].slice(0, 10);

      return {
        announcements: newAnnouncements,
        unreadCount: state.unreadCount + 1,
        // 현재 활성 공지가 없거나 새 공지가 더 높은 우선순위인 경우 활성화
        activeAnnouncement:
          !state.activeAnnouncement ||
          getPriorityLevel(announcement.priority) >
            getPriorityLevel(state.activeAnnouncement.priority)
            ? stored
            : state.activeAnnouncement,
      };
    });

    // 자동 닫힘 설정
    const delay = AUTO_DISMISS_DELAYS[announcement.priority];
    if (delay) {
      setTimeout(() => {
        const current = get().activeAnnouncement;
        if (current?.id === announcement.id) {
          get().dismissActive();
        }
      }, delay);
    }
  },

  markAsRead: (id) => {
    set((state) => {
      const updated = state.announcements.map((a) =>
        a.id === id ? { ...a, isRead: true } : a
      );
      const unreadCount = updated.filter((a) => !a.isRead).length;
      return { announcements: updated, unreadCount };
    });
  },

  markAllAsRead: () => {
    set((state) => ({
      announcements: state.announcements.map((a) => ({ ...a, isRead: true })),
      unreadCount: 0,
    }));
  },

  dismissActive: () => {
    const { activeAnnouncement, announcements } = get();
    if (activeAnnouncement) {
      // 현재 공지를 읽음 처리
      get().markAsRead(activeAnnouncement.id);

      // 다음 읽지 않은 공지가 있으면 표시
      const nextUnread = announcements.find(
        (a) => !a.isRead && a.id !== activeAnnouncement.id
      );
      set({ activeAnnouncement: nextUnread || null });
    }
  },

  clearAnnouncements: () => {
    set({
      announcements: [],
      activeAnnouncement: null,
      unreadCount: 0,
    });
  },
}));

// 우선순위 레벨 (높을수록 중요)
function getPriorityLevel(priority: AnnouncementPriority): number {
  const levels: Record<AnnouncementPriority, number> = {
    low: 1,
    normal: 2,
    high: 3,
    critical: 4,
  };
  return levels[priority] || 0;
}
