/**
 * API Routes - 중앙 관리되는 API 경로 상수
 *
 * 모든 API 호출은 이 파일의 상수를 사용해야 합니다.
 * 직접 문자열로 경로를 작성하지 마세요.
 */
export const API_ROUTES = {
  AUTH: {
    LOGIN: '/api/auth/login',
    LOGOUT: '/api/auth/logout',
    REFRESH: '/api/auth/refresh',
    TWO_FA_VERIFY: '/api/auth/2fa/verify',
    TWO_FA_SETUP: '/api/auth/2fa/setup',
    TWO_FA_ENABLE: '/api/auth/2fa/enable',
    TWO_FA_DISABLE: '/api/auth/2fa/disable',
  },
  USERS: {
    ME: '/api/users/me',
    LIST: '/api/users',
    DETAIL: (id: string) => `/api/users/${id}`,
  },
  DASHBOARD: {
    SUMMARY: '/api/dashboard/summary',
    CCU: '/api/dashboard/ccu',
    CCU_HISTORY: '/api/dashboard/ccu/history',
    DAU: '/api/dashboard/dau',
    DAU_HISTORY: '/api/dashboard/dau/history',
    MAU: '/api/dashboard/mau',
    MAU_HISTORY: '/api/dashboard/mau/history',
    USERS_SUMMARY: '/api/dashboard/users/summary',
    ROOMS: '/api/dashboard/rooms',
    ROOMS_DISTRIBUTION: '/api/dashboard/rooms/distribution',
    SERVER_HEALTH: '/api/dashboard/server/health',
    REVENUE_SUMMARY: '/api/dashboard/revenue/summary',
    REVENUE_DAILY: '/api/dashboard/revenue/daily',
    REVENUE_WEEKLY: '/api/dashboard/revenue/weekly',
    REVENUE_MONTHLY: '/api/dashboard/revenue/monthly',
    REVENUE_TOP_PLAYERS: '/api/dashboard/revenue/top-players',
    GAME_STATISTICS: '/api/dashboard/game/statistics',
    PLAYERS_ACTIVITY: '/api/dashboard/players/activity',
    PLAYERS_HOURLY_ACTIVITY: '/api/dashboard/players/hourly-activity',
    STAKE_LEVELS: '/api/dashboard/stake-levels',
  },
  STATISTICS: {
    REVENUE_SUMMARY: '/api/statistics/revenue/summary',
    REVENUE_DAILY: '/api/statistics/revenue/daily',
    REVENUE_WEEKLY: '/api/statistics/revenue/weekly',
    REVENUE_MONTHLY: '/api/statistics/revenue/monthly',
    GAME: '/api/statistics/game',
  },
  CRYPTO: {
    EXCHANGE_RATE: '/api/crypto/exchange-rate',
  },
  PARTNER: {
    LOGIN: '/api/auth/partner/login',
    ME: '/api/partner-portal/me',
    REFERRALS: '/api/partner-portal/referrals',
    SETTLEMENTS: '/api/partner-portal/settlements',
    STATS_OVERVIEW: '/api/partner-portal/stats/overview',
    STATS_DAILY: '/api/partner-portal/stats/daily',
    STATS_MONTHLY: '/api/partner-portal/stats/monthly',
  },
} as const;
