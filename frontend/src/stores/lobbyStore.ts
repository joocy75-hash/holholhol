import { create } from 'zustand';
import type { LobbyRoom, LobbySnapshotPayload, LobbyUpdatePayload } from '@/types/websocket';
import type { RoomFilters } from '@/types/ui';

interface LobbyState {
  rooms: LobbyRoom[];
  stateVersion: number;
  isSubscribed: boolean;
  filters: RoomFilters;
  isLoading: boolean;

  // Actions
  handleLobbySnapshot: (payload: LobbySnapshotPayload) => void;
  handleLobbyUpdate: (payload: LobbyUpdatePayload) => void;
  setSubscribed: (isSubscribed: boolean) => void;
  setFilters: (filters: Partial<RoomFilters>) => void;
  resetFilters: () => void;
  setLoading: (isLoading: boolean) => void;

  // Selectors
  getFilteredRooms: () => LobbyRoom[];
}

const DEFAULT_FILTERS: RoomFilters = {
  blinds: null,
  seats: null,
  status: null,
  search: '',
};

export const useLobbyStore = create<LobbyState>((set, get) => ({
  rooms: [],
  stateVersion: 0,
  isSubscribed: false,
  filters: DEFAULT_FILTERS,
  isLoading: false,

  handleLobbySnapshot: (payload) => {
    set({
      rooms: payload.rooms,
      stateVersion: payload.stateVersion,
      isLoading: false,
    });
  },

  handleLobbyUpdate: (payload) => {
    const { stateVersion } = get();

    // Ignore outdated updates
    if (payload.stateVersion <= stateVersion) {
      return;
    }

    set((state) => {
      let newRooms = [...state.rooms];

      switch (payload.type) {
        case 'add':
          if (payload.room) {
            newRooms.push(payload.room);
          }
          break;

        case 'update':
          if (payload.room) {
            const index = newRooms.findIndex((r) => r.id === payload.room!.id);
            if (index !== -1) {
              newRooms[index] = payload.room;
            }
          }
          break;

        case 'remove':
          if (payload.roomId) {
            newRooms = newRooms.filter((r) => r.id !== payload.roomId);
          }
          break;
      }

      return {
        rooms: newRooms,
        stateVersion: payload.stateVersion,
      };
    });
  },

  setSubscribed: (isSubscribed) => set({ isSubscribed }),

  setFilters: (filters) =>
    set((state) => ({
      filters: { ...state.filters, ...filters },
    })),

  resetFilters: () => set({ filters: DEFAULT_FILTERS }),

  setLoading: (isLoading) => set({ isLoading }),

  getFilteredRooms: () => {
    const { rooms, filters } = get();

    return rooms.filter((room) => {
      // Search filter
      if (filters.search && !room.name.toLowerCase().includes(filters.search.toLowerCase())) {
        return false;
      }

      // Blinds filter
      if (filters.blinds && room.blinds !== filters.blinds) {
        return false;
      }

      // Seats filter
      if (filters.seats && room.maxSeats !== filters.seats) {
        return false;
      }

      // Status filter
      if (filters.status && room.status !== filters.status) {
        return false;
      }

      return true;
    });
  },
}));
