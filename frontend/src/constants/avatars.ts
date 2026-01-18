/**
 * 기본 프로필 아바타 상수
 * 10가지 그래디언트 색상 기반 아바타
 */

export interface DefaultAvatar {
  id: number;
  gradient: string;
  name: string;
}

export const DEFAULT_AVATARS: readonly DefaultAvatar[] = [
  { id: 1, gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', name: '보라' },
  { id: 2, gradient: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)', name: '핑크' },
  { id: 3, gradient: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)', name: '하늘' },
  { id: 4, gradient: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)', name: '민트' },
  { id: 5, gradient: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)', name: '선셋' },
  { id: 6, gradient: 'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)', name: '파스텔' },
  { id: 7, gradient: 'linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)', name: '로즈' },
  { id: 8, gradient: 'linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%)', name: '피치' },
  { id: 9, gradient: 'linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%)', name: '스카이' },
  { id: 10, gradient: 'linear-gradient(135deg, #d299c2 0%, #fef9d7 100%)', name: '라벤더' },
] as const;

/**
 * ID로 아바타 찾기
 */
export function getAvatarById(id: number | string | null): DefaultAvatar | null {
  if (id === null || id === undefined) return null;
  const numId = typeof id === 'string' ? parseInt(id, 10) : id;
  if (isNaN(numId)) return null;
  return DEFAULT_AVATARS.find(avatar => avatar.id === numId) ?? null;
}

/**
 * avatar_url 값이 유효한 아바타 ID인지 확인
 */
export function isValidAvatarId(value: string | null): boolean {
  if (!value) return false;
  const num = parseInt(value, 10);
  return !isNaN(num) && num >= 1 && num <= 10;
}

/**
 * 기본 아바타 ID (새 사용자용)
 */
export const DEFAULT_AVATAR_ID = 1;
