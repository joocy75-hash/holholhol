import { useEffect, useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, RefreshCw } from 'lucide-react';
import { RootLayout } from '@/components/layout/RootLayout';
import { RoomList } from '@/components/lobby/RoomList';
import { RoomFilter } from '@/components/lobby/RoomFilter';
import { CreateRoomModal } from '@/components/lobby/CreateRoomModal';
import { Button } from '@/components/common/Button';
import { useLobbyStore } from '@/stores/lobbyStore';
import { useUIStore } from '@/stores/uiStore';
import { useAuthStore } from '@/stores/authStore';
import { toast } from '@/stores/uiStore';
import WebSocketClient from '@/lib/ws/WebSocketClient';
import { WSEventType } from '@/types/websocket';
import type {
  LobbySnapshotPayload,
  LobbyUpdatePayload,
  RoomCreateResultPayload,
} from '@/types/websocket';

export function LobbyPage() {
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuthStore();
  const { handleLobbySnapshot, handleLobbyUpdate, setSubscribed, setLoading } = useLobbyStore();
  const { openModal, setConnectionStatus } = useUIStore();
  const [isCreating, setIsCreating] = useState(false);

  // Redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/auth/login');
    }
  }, [isAuthenticated, navigate]);

  // WebSocket connection and subscription
  useEffect(() => {
    if (!user) return;

    const ws = WebSocketClient.getInstance();

    // Connect with auth token
    const token = localStorage.getItem('holdem_access_token');
    if (token) {
      ws.connect(`ws://localhost:8000/ws?token=${token}`);
    }

    // Connection state handler
    const handleConnectionState = (payload: { state: string }) => {
      setConnectionStatus(payload.state as 'connected' | 'reconnecting' | 'disconnected');

      if (payload.state === 'connected') {
        // Subscribe to lobby
        setLoading(true);
        ws.send({ type: WSEventType.SUBSCRIBE_LOBBY, payload: {} });
        setSubscribed(true);
      }
    };

    // Register handlers
    ws.on(WSEventType.CONNECTION_STATE, handleConnectionState);
    ws.on<LobbySnapshotPayload>(WSEventType.LOBBY_SNAPSHOT, handleLobbySnapshot);
    ws.on<LobbyUpdatePayload>(WSEventType.LOBBY_UPDATE, handleLobbyUpdate);

    return () => {
      ws.off(WSEventType.CONNECTION_STATE, handleConnectionState);
      ws.off(WSEventType.LOBBY_SNAPSHOT);
      ws.off(WSEventType.LOBBY_UPDATE);
      ws.send({ type: WSEventType.UNSUBSCRIBE_LOBBY, payload: {} });
      setSubscribed(false);
    };
  }, [user, handleLobbySnapshot, handleLobbyUpdate, setSubscribed, setLoading, setConnectionStatus]);

  const handleJoinRoom = useCallback(
    (roomId: string) => {
      navigate(`/table/${roomId}`);
    },
    [navigate]
  );

  const handleSpectateRoom = useCallback(
    (roomId: string) => {
      navigate(`/table/${roomId}?spectate=true`);
    },
    [navigate]
  );

  const handleCreateRoom = useCallback(
    async (data: {
      name: string;
      smallBlind: number;
      bigBlind: number;
      maxSeats: 2 | 6 | 9;
      minBuyIn: number;
      maxBuyIn: number;
    }) => {
      setIsCreating(true);

      const ws = WebSocketClient.getInstance();

      // Create promise for result
      const resultPromise = new Promise<RoomCreateResultPayload>((resolve) => {
        const handler = (payload: RoomCreateResultPayload) => {
          ws.off(WSEventType.ROOM_CREATE_RESULT, handler);
          resolve(payload);
        };
        ws.on(WSEventType.ROOM_CREATE_RESULT, handler);
      });

      // Send create request
      ws.send({
        type: WSEventType.ROOM_CREATE_REQUEST,
        payload: data,
      });

      try {
        const result = await resultPromise;

        if (result.success && result.roomId) {
          toast.success('방이 생성되었습니다!');
          navigate(`/table/${result.roomId}`);
        } else {
          toast.error(result.errorMessage || '방 생성에 실패했습니다');
          throw new Error(result.errorMessage);
        }
      } finally {
        setIsCreating(false);
      }
    },
    [navigate]
  );

  const handleRefresh = useCallback(() => {
    const ws = WebSocketClient.getInstance();
    setLoading(true);
    ws.send({ type: WSEventType.SUBSCRIBE_LOBBY, payload: {} });
  }, [setLoading]);

  if (!isAuthenticated) {
    return null;
  }

  return (
    <RootLayout>
      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-text">로비</h1>
            <p className="text-text-muted">참여할 방을 선택하거나 새로운 방을 만드세요</p>
          </div>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={handleRefresh}>
              <RefreshCw className="w-4 h-4 mr-2" />
              새로고침
            </Button>
            <Button onClick={() => openModal('create-room')}>
              <Plus className="w-4 h-4 mr-2" />
              방 만들기
            </Button>
          </div>
        </div>

        {/* Filter */}
        <div className="mb-6">
          <RoomFilter />
        </div>

        {/* Room List */}
        <RoomList onJoinRoom={handleJoinRoom} onSpectateRoom={handleSpectateRoom} />

        {/* Create Room Modal */}
        <CreateRoomModal onSubmit={handleCreateRoom} isLoading={isCreating} />
      </div>
    </RootLayout>
  );
}
