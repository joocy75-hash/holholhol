import { create } from 'zustand';
import type { Card, HandPhase, SeatState, ValidAction, TableConfig, ShowdownResult } from '@/types/game';
import type {
  TableSnapshotPayload,
  TableStateUpdatePayload,
  TurnPromptPayload,
  ActionResultPayload,
  ShowdownResultPayload,
} from '@/types/websocket';

interface TableState {
  // Table info
  tableId: string | null;
  config: TableConfig | null;
  seats: SeatState[];

  // Hand info
  handId: string | null;
  phase: HandPhase | null;
  communityCards: Card[];
  pot: number;
  sidePots: Array<{ amount: number; eligiblePositions: number[] }>;
  currentBet: number;
  minRaise: number;
  currentPosition: number | null;
  dealerPosition: number | null;
  turnDeadline: Date | null;

  // My info
  myPosition: number | null;
  myHoleCards: [Card, Card] | null;
  isSpectator: boolean;

  // Turn prompt
  allowedActions: ValidAction[];
  isMyTurn: boolean;

  // Showdown result
  showdownResult: ShowdownResult | null;
  nextHandDelay: number;

  // State management
  stateVersion: number;
  isSubscribed: boolean;
  isLoading: boolean;
  pendingAction: string | null;

  // Actions
  handleTableSnapshot: (payload: TableSnapshotPayload) => void;
  handleTableStateUpdate: (payload: TableStateUpdatePayload) => void;
  handleTurnPrompt: (payload: TurnPromptPayload) => void;
  handleActionResult: (payload: ActionResultPayload) => void;
  handleShowdownResult: (payload: ShowdownResultPayload) => void;
  setSubscribed: (isSubscribed: boolean) => void;
  setSpectator: (isSpectator: boolean) => void;
  setPendingAction: (action: string | null) => void;
  clearShowdownResult: () => void;
  reset: () => void;

  // Selectors
  getSeat: (position: number) => SeatState | null;
  getMySeat: () => SeatState | null;
  getCurrentTurnSeat: () => SeatState | null;
}

const initialState = {
  tableId: null,
  config: null,
  seats: [],
  handId: null,
  phase: null,
  communityCards: [],
  pot: 0,
  sidePots: [],
  currentBet: 0,
  minRaise: 0,
  currentPosition: null,
  dealerPosition: null,
  turnDeadline: null,
  myPosition: null,
  myHoleCards: null,
  isSpectator: false,
  allowedActions: [],
  isMyTurn: false,
  showdownResult: null,
  nextHandDelay: 0,
  stateVersion: 0,
  isSubscribed: false,
  isLoading: false,
  pendingAction: null,
};

export const useTableStore = create<TableState>((set, get) => ({
  ...initialState,

  handleTableSnapshot: (payload) => {
    const config: TableConfig = {
      tableId: payload.tableId,
      name: payload.config.name,
      blinds: {
        small: payload.config.smallBlind,
        big: payload.config.bigBlind,
      },
      maxSeats: payload.config.maxSeats as 2 | 6 | 9,
      buyIn: {
        min: payload.config.minBuyIn,
        max: payload.config.maxBuyIn,
      },
    };

    set({
      tableId: payload.tableId,
      config,
      seats: payload.seats,
      handId: payload.hand?.handId ?? null,
      phase: payload.hand?.phase ?? null,
      communityCards: payload.hand?.communityCards ?? [],
      pot: payload.hand?.pot ?? 0,
      sidePots: payload.hand?.sidePots ?? [],
      currentBet: payload.hand?.currentBet ?? 0,
      minRaise: payload.hand?.minRaise ?? 0,
      currentPosition: payload.hand?.currentPosition ?? null,
      dealerPosition: payload.hand?.dealerPosition ?? null,
      turnDeadline: payload.hand?.turnDeadline ? new Date(payload.hand.turnDeadline) : null,
      myPosition: payload.myPosition,
      myHoleCards: payload.myHoleCards,
      stateVersion: payload.stateVersion,
      isLoading: false,
      isMyTurn: payload.myPosition !== null && payload.hand?.currentPosition === payload.myPosition,
    });
  },

  handleTableStateUpdate: (payload) => {
    const { stateVersion } = get();

    // Ignore outdated updates
    if (payload.stateVersion <= stateVersion) {
      return;
    }

    set((state) => {
      const updates: Partial<TableState> = {
        stateVersion: payload.stateVersion,
      };

      if (payload.changes.seats) {
        updates.seats = payload.changes.seats;
      }

      if (payload.changes.hand) {
        updates.handId = payload.changes.hand.handId;
        updates.phase = payload.changes.hand.phase;
        updates.communityCards = payload.changes.hand.communityCards;
        updates.pot = payload.changes.hand.pot;
        updates.sidePots = payload.changes.hand.sidePots;
        updates.currentBet = payload.changes.hand.currentBet;
        updates.minRaise = payload.changes.hand.minRaise;
        updates.currentPosition = payload.changes.hand.currentPosition;
        updates.dealerPosition = payload.changes.hand.dealerPosition;
        updates.turnDeadline = payload.changes.hand.turnDeadline
          ? new Date(payload.changes.hand.turnDeadline)
          : null;

        // Update isMyTurn
        updates.isMyTurn =
          state.myPosition !== null && payload.changes.hand.currentPosition === state.myPosition;
      }

      if (payload.changes.myPosition !== undefined) {
        updates.myPosition = payload.changes.myPosition;
      }

      if (payload.changes.myHoleCards !== undefined) {
        updates.myHoleCards = payload.changes.myHoleCards;
      }

      return updates;
    });
  },

  handleTurnPrompt: (payload) => {
    const { myPosition } = get();

    if (payload.position !== myPosition) {
      set({ isMyTurn: false, allowedActions: [] });
      return;
    }

    set({
      isMyTurn: true,
      allowedActions: payload.allowedActions,
      currentBet: payload.currentBet,
      minRaise: payload.minRaise,
      pot: payload.pot,
      turnDeadline: new Date(payload.deadline),
    });
  },

  handleActionResult: (payload) => {
    set({ pendingAction: null });

    if (!payload.success) {
      // Handle error - UI store will show toast
      console.error('Action failed:', payload.errorMessage);
    }
  },

  handleShowdownResult: (payload) => {
    set({
      showdownResult: {
        winners: payload.winners,
        losers: payload.losers,
      },
      nextHandDelay: payload.nextHandDelay,
      isMyTurn: false,
      allowedActions: [],
    });
  },

  setSubscribed: (isSubscribed) => set({ isSubscribed }),

  setSpectator: (isSpectator) => set({ isSpectator }),

  setPendingAction: (action) => set({ pendingAction: action }),

  clearShowdownResult: () => set({ showdownResult: null }),

  reset: () => set(initialState),

  getSeat: (position) => {
    const { seats } = get();
    return seats.find((s) => s.position === position) ?? null;
  },

  getMySeat: () => {
    const { seats, myPosition } = get();
    if (myPosition === null) return null;
    return seats.find((s) => s.position === myPosition) ?? null;
  },

  getCurrentTurnSeat: () => {
    const { seats, currentPosition } = get();
    if (currentPosition === null) return null;
    return seats.find((s) => s.position === currentPosition) ?? null;
  },
}));
