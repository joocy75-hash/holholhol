/**
 * Live Bots API client
 */

import { api } from './api';

export interface BotInfo {
  botId: string;
  nickname: string;
  strategy: string;
  state: string;
  roomId: string | null;
  seat: number | null;
  stack: number;
  handsPlayed: number;
  rebuysCount: number;
  totalWon: number;
  totalLost: number;
  sessionStart: string | null;
  retireRequested: boolean;
}

export interface BotStatus {
  enabled: boolean;
  running: boolean;
  targetCount: number;
  activeCount: number;
  totalCount: number;
  stateCounts: Record<string, number>;
  bots: BotInfo[];
}

export interface BotTargetResponse {
  success: boolean;
  oldTarget: number;
  newTarget: number;
  currentActive: number;
  currentTotal: number;
}

export interface SpawnBotResponse {
  success: boolean;
  message: string;
  activeCount: number;
}

export interface RetireBotResponse {
  success: boolean;
  botId: string;
  nickname: string;
  state: string;
  message: string;
}

export interface ForceRemoveAllResponse {
  success: boolean;
  removedCount: number;
  message: string;
}

function getAuthToken(): string | undefined {
  if (typeof window === 'undefined') return undefined;
  try {
    const stored = localStorage.getItem('admin-auth');
    if (stored) {
      const parsed = JSON.parse(stored);
      return parsed.state?.accessToken;
    }
  } catch {
    // ignore
  }
  return undefined;
}

export const botsApi = {
  getStatus: async (): Promise<BotStatus> => {
    const token = getAuthToken();
    return api.get<BotStatus>('/api/bots/status', { token });
  },

  setTargetCount: async (targetCount: number): Promise<BotTargetResponse> => {
    const token = getAuthToken();
    return api.post<BotTargetResponse>('/api/bots/target', {
      target_count: targetCount,
    }, { token });
  },

  spawnBot: async (): Promise<SpawnBotResponse> => {
    const token = getAuthToken();
    return api.post<SpawnBotResponse>('/api/bots/spawn', undefined, { token });
  },

  retireBot: async (botId: string): Promise<RetireBotResponse> => {
    const token = getAuthToken();
    return api.post<RetireBotResponse>(`/api/bots/retire/${botId}`, undefined, { token });
  },

  forceRemoveAll: async (): Promise<ForceRemoveAllResponse> => {
    const token = getAuthToken();
    return api.delete<ForceRemoveAllResponse>('/api/bots/all', { token });
  },
};
