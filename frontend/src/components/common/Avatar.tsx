'use client';

import { getAvatarById, DEFAULT_AVATAR_ID, DEFAULT_AVATARS } from '@/constants/avatars';
import { VIPBadge, type VIPLevel, type VIPBadgeSize } from './VIPBadge';

/**
 * 아바타 크기 정의
 */
const SIZES = {
  xs: { width: 24, height: 24, iconSize: 12, vipSize: 'xs' as VIPBadgeSize },
  sm: { width: 32, height: 32, iconSize: 16, vipSize: 'xs' as VIPBadgeSize },
  md: { width: 40, height: 40, iconSize: 20, vipSize: 'sm' as VIPBadgeSize },
  lg: { width: 56, height: 56, iconSize: 28, vipSize: 'sm' as VIPBadgeSize },
  xl: { width: 80, height: 80, iconSize: 40, vipSize: 'md' as VIPBadgeSize },
} as const;

export type AvatarSize = keyof typeof SIZES;

export interface AvatarProps {
  /** 아바타 ID (1-10) 또는 null */
  avatarId: string | number | null;
  /** 크기 */
  size?: AvatarSize;
  /** 닉네임 (alt 텍스트용) */
  nickname?: string;
  /** 현재 사용자 여부 (테두리 강조) */
  isCurrentUser?: boolean;
  /** 폴드 상태 (흐리게 표시) */
  isFolded?: boolean;
  /** 승리자 상태 (애니메이션) */
  isWinner?: boolean;
  /** 활성 상태 (턴) */
  isActive?: boolean;
  /** VIP 레벨 (표시할 경우) */
  vipLevel?: VIPLevel | string | null;
  /** VIP 배지 표시 여부 */
  showVIPBadge?: boolean;
  /** 추가 className */
  className?: string;
  /** 클릭 핸들러 */
  onClick?: () => void;
}

/**
 * 통합 아바타 컴포넌트
 *
 * 프로필, 게임 테이블 등 모든 곳에서 일관된 아바타 표시
 */
export function Avatar({
  avatarId,
  size = 'md',
  nickname,
  isCurrentUser = false,
  isFolded = false,
  isWinner = false,
  isActive = false,
  vipLevel,
  showVIPBadge = true,
  className = '',
  onClick,
}: AvatarProps) {
  const avatar = getAvatarById(avatarId) ?? getAvatarById(DEFAULT_AVATAR_ID);
  const sizeConfig = SIZES[size];

  const baseStyles: React.CSSProperties = {
    width: sizeConfig.width,
    height: sizeConfig.height,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: avatar?.gradient ?? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    border: isCurrentUser ? '2px solid var(--primary, #22c55e)' : '2px solid transparent',
    opacity: isFolded ? 0.5 : 1,
    transition: 'all 0.2s ease',
    cursor: onClick ? 'pointer' : 'default',
    position: 'relative',
    overflow: 'hidden',
    flexShrink: 0,
  };

  // 승리자 애니메이션 스타일
  const winnerStyles: React.CSSProperties = isWinner ? {
    boxShadow: '0 0 20px rgba(255, 215, 0, 0.8)',
    animation: 'winner-pulse 1s ease-in-out infinite',
  } : {};

  // 활성 상태 스타일
  const activeStyles: React.CSSProperties = isActive ? {
    boxShadow: '0 0 10px rgba(34, 197, 94, 0.6)',
  } : {};

  // VIP 배지 표시 여부 결정
  const shouldShowVIP = showVIPBadge && vipLevel;

  return (
    <>
      <style jsx global>{`
        @keyframes winner-pulse {
          0%, 100% { transform: scale(1); box-shadow: 0 0 20px rgba(255, 215, 0, 0.8); }
          50% { transform: scale(1.05); box-shadow: 0 0 30px rgba(255, 215, 0, 1); }
        }
      `}</style>
      <div
        style={{ position: 'relative', display: 'inline-block' }}
      >
        <div
          className={className}
          style={{ ...baseStyles, ...winnerStyles, ...activeStyles }}
          onClick={onClick}
          title={nickname}
          role={onClick ? 'button' : undefined}
          tabIndex={onClick ? 0 : undefined}
          onKeyDown={onClick ? (e) => e.key === 'Enter' && onClick() : undefined}
        >
          <svg
            width={sizeConfig.iconSize}
            height={sizeConfig.iconSize}
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <circle cx="12" cy="8" r="3.5" fill="rgba(255,255,255,0.8)" />
            <path
              d="M6 20C6 16.6863 8.68629 14 12 14C15.3137 14 18 16.6863 18 20"
              stroke="rgba(255,255,255,0.8)"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </div>
        {shouldShowVIP && (
          <VIPBadge
            level={vipLevel}
            size={sizeConfig.vipSize}
            overlay
          />
        )}
      </div>
    </>
  );
}

/**
 * 아바타 선택 그리드
 *
 * 프로필 수정 시 10가지 아바타 중 선택
 */
export interface AvatarSelectorProps {
  /** 선택된 아바타 ID */
  selectedId: number | null;
  /** 선택 변경 핸들러 */
  onSelect: (id: number) => void;
  /** 비활성화 */
  disabled?: boolean;
}

export function AvatarSelector({
  selectedId,
  onSelect,
  disabled = false,
}: AvatarSelectorProps) {
  // ES6 import 사용 (상단에서 import됨) - require() 제거로 타입 안전성 확보
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(5, 1fr)',
        gap: '12px',
        padding: '8px',
      }}
    >
      {DEFAULT_AVATARS.map((avatar) => (
        <button
          key={avatar.id}
          type="button"
          onClick={() => !disabled && onSelect(avatar.id)}
          disabled={disabled}
          style={{
            width: 48,
            height: 48,
            borderRadius: '50%',
            background: avatar.gradient,
            border: selectedId === avatar.id
              ? '3px solid var(--primary, #22c55e)'
              : '3px solid transparent',
            cursor: disabled ? 'not-allowed' : 'pointer',
            opacity: disabled ? 0.5 : 1,
            transition: 'all 0.2s ease',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 0,
          }}
          title={avatar.name}
        >
          <svg
            width={20}
            height={20}
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <circle cx="12" cy="8" r="3.5" fill="rgba(255,255,255,0.8)" />
            <path
              d="M6 20C6 16.6863 8.68629 14 12 14C15.3137 14 18 16.6863 18 20"
              stroke="rgba(255,255,255,0.8)"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </button>
      ))}
    </div>
  );
}

export default Avatar;
