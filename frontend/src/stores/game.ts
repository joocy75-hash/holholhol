import { create } from 'zustand';
import { tablesApi } from '@/lib/api';
import { extractErrorMessage } from '@/types/errors';

export interface Table {
  id: string;
  name: string;
  blinds: string;
  maxSeats: number;
  playerCount: number;
  status: 'waiting' | 'playing' | 'finished';
  isPrivate: boolean;
  buyInMin: number;
  buyInMax: number;
}

interface GameState {
  tables: Table[];
  currentTable: Table | null;
  seatedRoomIds: string[];
  isLoading: boolean;
  error: string | null;

  fetchTables: () => Promise<void>;
  fetchTable: (tableId: string) => Promise<void>;
  fetchMySeats: () => Promise<string[]>;
  joinTable: (tableId: string, buyIn: number) => Promise<void>;
  leaveTable: (tableId: string) => Promise<void>;
  clearError: () => void;
}

export const useGameStore = create<GameState>((set) => ({
  tables: [],
  currentTable: null,
  seatedRoomIds: [],
  isLoading: false,
  error: null,

  fetchTables: async () => {
    set({ isLoading: true, error: null });
    try {
      const response = await tablesApi.list();
      set({ tables: response.data.rooms || [], isLoading: false });
    } catch (error: unknown) {
      set({
        error: extractErrorMessage(error, '테이블 목록을 불러올 수 없습니다.'),
        isLoading: false,
      });
    }
  },

  fetchTable: async (tableId: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await tablesApi.get(tableId);
      set({ currentTable: response.data, isLoading: false });
    } catch (error: unknown) {
      set({
        error: extractErrorMessage(error, '테이블 정보를 불러올 수 없습니다.'),
        isLoading: false,
      });
    }
  },

  fetchMySeats: async () => {
    try {
      const response = await tablesApi.mySeats();
      const roomIds = response.data.rooms || [];
      set({ seatedRoomIds: roomIds });
      return roomIds;
    } catch {
      set({ seatedRoomIds: [] });
      return [];
    }
  },

  joinTable: async (tableId: string, buyIn: number) => {
    set({ isLoading: true, error: null });
    try {
      const joinResponse = await tablesApi.join(tableId, buyIn);
      // Fetch the full table info after successful join
      const tableResponse = await tablesApi.get(tableId);
      set({ currentTable: tableResponse.data, isLoading: false });
      return joinResponse.data;
    } catch (error: unknown) {
      set({
        error: extractErrorMessage(error, '테이블 참가에 실패했습니다.'),
        isLoading: false,
      });
      throw error;
    }
  },

  leaveTable: async (tableId: string) => {
    set({ isLoading: true, error: null });
    try {
      await tablesApi.leave(tableId);
      set({ currentTable: null, isLoading: false });
    } catch (error: unknown) {
      set({
        error: extractErrorMessage(error, '테이블 퇴장에 실패했습니다.'),
        isLoading: false,
      });
    }
  },

  clearError: () => set({ error: null }),
}));
