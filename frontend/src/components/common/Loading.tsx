'use client';

import { ReactNode } from 'react';

/**
 * 스켈레톤 로딩 컴포넌트
 * 
 * 콘텐츠 로딩 중 표시되는 플레이스홀더 UI입니다.
 */

interface SkeletonProps {
  /** 너비 (Tailwind 클래스 또는 픽셀) */
  width?: string;
  /** 높이 (Tailwind 클래스 또는 픽셀) */
  height?: string;
  /** 원형 여부 */
  circle?: boolean;
  /** 추가 클래스 */
  className?: string;
}

/**
 * 기본 스켈레톤 (박스/원형)
 */
export function Skeleton({ 
  width = 'w-full', 
  height = 'h-4', 
  circle = false,
  className = '' 
}: SkeletonProps) {
  return (
    <div
      className={`
        bg-gradient-to-r from-surface via-surface-hover to-surface
        animate-pulse
        ${circle ? 'rounded-full' : 'rounded-md'}
        ${width} ${height} ${className}
      `}
      style={{
        backgroundSize: '200% 100%',
      }}
    />
  );
}

/**
 * 텍스트 스켈레톤 (여러 줄)
 */
export function TextSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton 
          key={i} 
          width={i === lines - 1 ? 'w-3/4' : 'w-full'} 
          height="h-4" 
        />
      ))}
    </div>
  );
}

/**
 * 카드 스켈레톤
 */
export function CardSkeleton() {
  return (
    <div className="card animate-pulse">
      <div className="flex items-center gap-4 mb-4">
        <Skeleton width="w-12" height="h-12" circle />
        <div className="flex-1 space-y-2">
          <Skeleton width="w-1/2" height="h-4" />
          <Skeleton width="w-1/3" height="h-3" />
        </div>
      </div>
      <TextSkeleton lines={2} />
    </div>
  );
}

/**
 * 테이블 카드 스켈레톤 (로비용)
 */
export function RoomCardSkeleton() {
  return (
    <div className="card p-4 animate-pulse">
      {/* 헤더 */}
      <div className="flex justify-between items-start mb-3">
        <Skeleton width="w-32" height="h-5" />
        <Skeleton width="w-16" height="h-5" />
      </div>
      
      {/* 정보 */}
      <div className="flex gap-4 mb-4">
        <Skeleton width="w-20" height="h-4" />
        <Skeleton width="w-20" height="h-4" />
        <Skeleton width="w-24" height="h-4" />
      </div>
      
      {/* 버튼 */}
      <div className="flex gap-2">
        <Skeleton width="w-20" height="h-10" />
        <Skeleton width="w-20" height="h-10" />
      </div>
    </div>
  );
}

/**
 * 플레이어 좌석 스켈레톤
 */
export function SeatSkeleton() {
  return (
    <div className="flex flex-col items-center gap-1 animate-pulse">
      <Skeleton width="w-12" height="h-12" circle />
      <Skeleton width="w-16" height="h-3" />
      <Skeleton width="w-12" height="h-3" />
    </div>
  );
}

/**
 * 포커 테이블 로딩 화면
 */
export function TableLoadingSkeleton() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-black p-4">
      {/* 테이블 영역 */}
      <div className="w-full max-w-[500px] h-[600px] relative">
        {/* 상단 좌석들 */}
        <div className="absolute top-4 left-1/2 -translate-x-1/2 flex gap-16">
          <SeatSkeleton />
          <SeatSkeleton />
        </div>
        
        {/* 좌측 좌석들 */}
        <div className="absolute left-4 top-1/2 -translate-y-1/2 flex flex-col gap-16">
          <SeatSkeleton />
          <SeatSkeleton />
        </div>
        
        {/* 우측 좌석들 */}
        <div className="absolute right-4 top-1/2 -translate-y-1/2 flex flex-col gap-16">
          <SeatSkeleton />
          <SeatSkeleton />
        </div>
        
        {/* 중앙 팟 */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
          <div className="text-center">
            <Skeleton width="w-24" height="h-6" className="mx-auto mb-2" />
            <div className="flex gap-2 justify-center">
              <Skeleton width="w-10" height="h-14" />
              <Skeleton width="w-10" height="h-14" />
              <Skeleton width="w-10" height="h-14" />
            </div>
          </div>
        </div>
        
        {/* 하단 (내 좌석) */}
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2">
          <SeatSkeleton />
        </div>
      </div>
      
      {/* 로딩 메시지 */}
      <div className="mt-8 text-center">
        <div className="flex items-center justify-center gap-2 text-text-secondary">
          <LoadingSpinner size="sm" />
          <span>테이블 연결 중...</span>
        </div>
      </div>
    </div>
  );
}

/**
 * 로딩 스피너
 */
interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  color?: string;
}

export function LoadingSpinner({ 
  size = 'md', 
  color = 'text-primary' 
}: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-10 h-10',
  };

  return (
    <svg
      className={`animate-spin ${sizeClasses[size]} ${color}`}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

/**
 * 전체 화면 로딩 오버레이
 */
interface LoadingOverlayProps {
  message?: string;
  children?: ReactNode;
}

export function LoadingOverlay({ 
  message = '로딩 중...', 
  children 
}: LoadingOverlayProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="text-center">
        <LoadingSpinner size="lg" />
        <p className="mt-4 text-text-secondary">{message}</p>
        {children}
      </div>
    </div>
  );
}

/**
 * 인라인 로딩 (버튼 내부 등)
 */
export function InlineLoading({ text = '처리 중...' }: { text?: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      <LoadingSpinner size="sm" />
      <span>{text}</span>
    </span>
  );
}

export default Skeleton;
