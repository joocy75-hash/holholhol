import { useEffect, useCallback, useState } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Settings, MessageCircle } from 'lucide-react';
import { RootLayout } from '@/components/layout/RootLayout';
import { Table } from '@/components/table/Table';
import { ActionPanel } from '@/components/table/ActionPanel';
import { Chat } from '@/components/table/Chat';
import { ShowdownResult } from '@/components/table/ShowdownResult';
import { Button } from '@/components/common/Button';
import { Loading } from '@/components/common/Loading';
import { useTableStore } from '@/stores/tableStore';
import { useAuthStore } from '@/stores/authStore';
import { toast } from '@/stores/uiStore';
import WebSocketClient from '@/lib/ws/WebSocketClient';
import { WSEventType } from '@/types/websocket';
import type {
  TableSnapshotPayload,
  TableStateUpdatePayload,
  TurnPromptPayload,
  ActionResultPayload,
  ShowdownResultPayload,
  ChatBroadcastPayload,
} from '@/types/websocket';
import type { ActionType } from '@/types/game';
import type { ChatMessage } from '@/types/ui';

export function TablePage() {
  const { tableId } = useParams<{ tableId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const isSpectate = searchParams.get('spectate') === 'true';

  const { isAuthenticated } = useAuthStore();
  const {
    config,
    isLoading,
    isMyTurn,
    allowedActions,
    currentBet,
    pot,
    minRaise,
    turnDeadline,
    myPosition,
    showdownResult,
    nextHandDelay,
    handleTableSnapshot,
    handleTableStateUpdate,
    handleTurnPrompt,
    handleActionResult,
    handleShowdownResult,
    clearShowdownResult,
    setSpectator,
    setPendingAction,
    reset,
    getMySeat,
  } = useTableStore();

  const [showChat, setShowChat] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);

  const mySeat = getMySeat();
  const myBet = mySeat?.betAmount ?? 0;
  const myStack = mySeat?.stack ?? 0;

  // Redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/auth/login');
    }
  }, [isAuthenticated, navigate]);

  // WebSocket subscription
  useEffect(() => {
    if (!tableId) return;

    const ws = WebSocketClient.getInstance();

    // Subscribe to table
    setSpectator(isSpectate);
    ws.send({
      type: WSEventType.SUBSCRIBE_TABLE,
      payload: { tableId, mode: isSpectate ? 'spectator' : 'player' },
    });

    // Register handlers
    ws.on<TableSnapshotPayload>(WSEventType.TABLE_SNAPSHOT, handleTableSnapshot);
    ws.on<TableStateUpdatePayload>(WSEventType.TABLE_STATE_UPDATE, handleTableStateUpdate);
    ws.on<TurnPromptPayload>(WSEventType.TURN_PROMPT, handleTurnPrompt);
    ws.on<ActionResultPayload>(WSEventType.ACTION_RESULT, handleActionResult);
    ws.on<ShowdownResultPayload>(WSEventType.SHOWDOWN_RESULT, handleShowdownResult);
    ws.on<ChatBroadcastPayload>(WSEventType.CHAT_BROADCAST, (payload) => {
      setChatMessages((prev) => [
        ...prev,
        {
          id: `${payload.timestamp}-${payload.senderId}`,
          type: payload.type,
          sender: payload.senderNickname,
          content: payload.message,
          timestamp: new Date(payload.timestamp),
        },
      ]);
    });

    return () => {
      ws.send({ type: WSEventType.UNSUBSCRIBE_TABLE, payload: { tableId } });
      ws.off(WSEventType.TABLE_SNAPSHOT);
      ws.off(WSEventType.TABLE_STATE_UPDATE);
      ws.off(WSEventType.TURN_PROMPT);
      ws.off(WSEventType.ACTION_RESULT);
      ws.off(WSEventType.SHOWDOWN_RESULT);
      ws.off(WSEventType.CHAT_BROADCAST);
      reset();
    };
  }, [
    tableId,
    isSpectate,
    handleTableSnapshot,
    handleTableStateUpdate,
    handleTurnPrompt,
    handleActionResult,
    handleShowdownResult,
    setSpectator,
    reset,
  ]);

  const handleSeatClick = useCallback(
    (position: number) => {
      if (isSpectate || myPosition !== null) return;

      // Open buy-in modal or directly seat
      const ws = WebSocketClient.getInstance();
      ws.send({
        type: WSEventType.SEAT_REQUEST,
        payload: {
          tableId,
          position,
          buyInAmount: config?.buyIn.min ?? 400,
        },
      });

      toast.info('착석 중...');
    },
    [tableId, isSpectate, myPosition, config]
  );

  const handleAction = useCallback(
    (actionType: ActionType, amount?: number) => {
      if (!tableId) return;

      setPendingAction(actionType);

      const ws = WebSocketClient.getInstance();
      ws.send({
        type: WSEventType.ACTION_REQUEST,
        payload: { tableId, actionType, amount },
      });
    },
    [tableId, setPendingAction]
  );

  const handleSendChat = useCallback(
    (message: string) => {
      if (!tableId) return;

      const ws = WebSocketClient.getInstance();
      ws.send({
        type: WSEventType.CHAT_MESSAGE,
        payload: { tableId, message },
      });
    },
    [tableId]
  );

  const handleLeave = useCallback(() => {
    if (tableId) {
      const ws = WebSocketClient.getInstance();
      ws.send({ type: WSEventType.LEAVE_TABLE, payload: { tableId } });
    }
    navigate('/lobby');
  }, [tableId, navigate]);

  if (!isAuthenticated || !tableId) {
    return null;
  }

  if (isLoading) {
    return (
      <RootLayout>
        <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
          <Loading size="lg" text="테이블 로딩 중..." />
        </div>
      </RootLayout>
    );
  }

  return (
    <RootLayout
      title={config?.name ?? '테이블'}
      subtitle={config ? `${config.blinds.small}/${config.blinds.big}` : undefined}
    >
      <div className="h-[calc(100vh-4rem)] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2 bg-bg-dark border-b border-surface">
          <Button variant="ghost" size="sm" onClick={handleLeave}>
            <ArrowLeft className="w-4 h-4 mr-1" />
            로비로
          </Button>

          <div className="flex items-center gap-2">
            {isSpectate && (
              <span className="px-2 py-1 bg-warning/20 text-warning text-xs rounded">
                관전 중
              </span>
            )}
            <Button variant="ghost" size="sm" onClick={() => setShowChat(!showChat)}>
              <MessageCircle className="w-4 h-4" />
            </Button>
            <Button variant="ghost" size="sm">
              <Settings className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Main content */}
        <div className="flex-1 flex">
          {/* Table area */}
          <div className="flex-1 flex flex-col p-4">
            {/* Table */}
            <div className="flex-1 flex items-center justify-center">
              <Table onSeatClick={handleSeatClick} />
            </div>

            {/* Action panel */}
            {!isSpectate && (
              <div className="mt-4 max-w-xl mx-auto w-full">
                <ActionPanel
                  allowedActions={allowedActions}
                  currentBet={currentBet}
                  myBet={myBet}
                  myStack={myStack}
                  pot={pot}
                  minRaise={minRaise}
                  deadline={turnDeadline}
                  disabled={!isMyTurn}
                  onAction={handleAction}
                />
              </div>
            )}
          </div>

          {/* Chat sidebar */}
          {showChat && (
            <div className="w-80 border-l border-surface">
              <Chat messages={chatMessages} onSend={handleSendChat} />
            </div>
          )}
        </div>

        {/* Showdown result overlay */}
        {showdownResult && (
          <ShowdownResult
            result={showdownResult}
            nextHandDelay={nextHandDelay}
            onClose={clearShowdownResult}
          />
        )}
      </div>
    </RootLayout>
  );
}
