/**
 * 공통 컴포넌트 모듈
 * 
 * 재사용 가능한 UI 컴포넌트들을 export합니다.
 */

// 에러 처리
export { ErrorBoundary, TableErrorBoundary } from './ErrorBoundary';

// 로딩 상태
export {
  Skeleton,
  TextSkeleton,
  CardSkeleton,
  RoomCardSkeleton,
  SeatSkeleton,
  TableLoadingSkeleton,
  LoadingSpinner,
  LoadingOverlay,
  InlineLoading,
} from './Loading';

// 아바타
export { Avatar, AvatarSelector } from './Avatar';
export type { AvatarProps, AvatarSelectorProps, AvatarSize } from './Avatar';
