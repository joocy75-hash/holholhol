'use client';

import { useAnnouncementListener } from './useAnnouncementListener';
import { AnnouncementModal } from './AnnouncementModal';

/**
 * 공지사항 Provider 컴포넌트
 * - WebSocket 리스너 등록
 * - 공지사항 모달 렌더링
 *
 * 사용: 레이아웃에 <AnnouncementProvider />를 추가하면
 * 앱 전역에서 실시간 공지를 수신하고 표시합니다.
 */
export function AnnouncementProvider() {
  // WebSocket 이벤트 리스너 등록
  useAnnouncementListener();

  return <AnnouncementModal />;
}
