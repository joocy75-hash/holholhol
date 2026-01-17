'use client';

import { useEffect, useRef } from 'react';
import { wsClient } from '@/lib/websocket';
import { EventType, AnnouncementPayload } from '@/types/websocket';
import { useAnnouncementStore } from '@/stores/announcement';

/**
 * WebSocket에서 공지사항 이벤트를 수신하는 훅
 * - ANNOUNCEMENT 이벤트 수신 시 store에 추가
 * - 컴포넌트 언마운트 시 자동 정리
 */
export function useAnnouncementListener() {
  const addAnnouncement = useAnnouncementStore((state) => state.addAnnouncement);
  const listenerRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    // 이벤트 핸들러 등록
    const unsubscribe = wsClient.on(
      EventType.ANNOUNCEMENT,
      (payload: AnnouncementPayload) => {
        console.log('📢 공지사항 수신:', payload.title);
        addAnnouncement(payload);
      }
    );

    listenerRef.current = unsubscribe;

    // 클린업
    return () => {
      if (listenerRef.current) {
        listenerRef.current();
        listenerRef.current = null;
      }
    };
  }, [addAnnouncement]);
}
