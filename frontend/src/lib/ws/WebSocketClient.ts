import { WSEventType, type WSMessage } from '@/types/websocket';

type EventCallback<T = unknown> = (payload: T) => void;

interface ReconnectConfig {
  maxRetries: number;
  baseDelay: number;
  maxDelay: number;
}

const DEFAULT_RECONNECT_CONFIG: ReconnectConfig = {
  maxRetries: 10,
  baseDelay: 1000,
  maxDelay: 30000,
};

export class WebSocketClient {
  private static instance: WebSocketClient | null = null;
  private ws: WebSocket | null = null;
  private url: string = '';
  private eventHandlers: Map<string, Set<EventCallback>> = new Map();
  private reconnectConfig: ReconnectConfig;
  private reconnectAttempts: number = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingInterval: ReturnType<typeof setInterval> | null = null;
  private messageQueue: WSMessage[] = [];
  private isConnecting: boolean = false;

  private constructor(config?: Partial<ReconnectConfig>) {
    this.reconnectConfig = { ...DEFAULT_RECONNECT_CONFIG, ...config };
  }

  static getInstance(config?: Partial<ReconnectConfig>): WebSocketClient {
    if (!WebSocketClient.instance) {
      WebSocketClient.instance = new WebSocketClient(config);
    }
    return WebSocketClient.instance;
  }

  connect(url: string): void {
    if (this.ws?.readyState === WebSocket.OPEN || this.isConnecting) {
      return;
    }

    this.url = url;
    this.isConnecting = true;

    try {
      this.ws = new WebSocket(url);
      this.setupEventListeners();
    } catch (error) {
      console.error('WebSocket connection error:', error);
      this.isConnecting = false;
      this.scheduleReconnect();
    }
  }

  private setupEventListeners(): void {
    if (!this.ws) return;

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.isConnecting = false;
      this.reconnectAttempts = 0;
      this.startPingInterval();
      this.flushMessageQueue();
      this.emit(WSEventType.CONNECTION_STATE, { state: 'connected' });
    };

    this.ws.onclose = (event) => {
      console.log('WebSocket closed:', event.code, event.reason);
      this.stopPingInterval();
      this.isConnecting = false;

      if (!event.wasClean) {
        this.emit(WSEventType.CONNECTION_STATE, { state: 'reconnecting' });
        this.scheduleReconnect();
      } else {
        this.emit(WSEventType.CONNECTION_STATE, { state: 'disconnected' });
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    this.ws.onmessage = (event) => {
      try {
        const message: WSMessage = JSON.parse(event.data);
        this.handleMessage(message);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };
  }

  private handleMessage(message: WSMessage): void {
    // Handle PONG internally
    if (message.type === WSEventType.PONG) {
      return;
    }

    // Emit to registered handlers
    this.emit(message.type, message.payload);
  }

  private startPingInterval(): void {
    this.stopPingInterval();
    this.pingInterval = setInterval(() => {
      this.send({ type: WSEventType.PING, payload: {} });
    }, 15000);
  }

  private stopPingInterval(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.reconnectConfig.maxRetries) {
      console.error('Max reconnection attempts reached');
      this.emit(WSEventType.CONNECTION_STATE, { state: 'disconnected' });
      return;
    }

    const delay = Math.min(
      this.reconnectConfig.baseDelay * Math.pow(2, this.reconnectAttempts),
      this.reconnectConfig.maxDelay
    );

    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1})`);

    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempts++;
      this.connect(this.url);
    }, delay);
  }

  private flushMessageQueue(): void {
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift();
      if (message) {
        this.sendRaw(message);
      }
    }
  }

  private sendRaw(message: WSMessage): boolean {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      return false;
    }

    try {
      this.ws.send(JSON.stringify(message));
      return true;
    } catch (error) {
      console.error('Failed to send WebSocket message:', error);
      return false;
    }
  }

  send<T>(data: { type: string; payload: T; requestId?: string }): void {
    const message: WSMessage<T> = {
      type: data.type as WSEventType,
      ts: Date.now(),
      traceId: crypto.randomUUID(),
      requestId: data.requestId,
      payload: data.payload,
      version: 1,
    };

    if (this.ws?.readyState === WebSocket.OPEN) {
      this.sendRaw(message);
    } else {
      // Queue message for sending after reconnect
      this.messageQueue.push(message as WSMessage);
    }
  }

  on<T>(eventType: string, callback: EventCallback<T>): void {
    if (!this.eventHandlers.has(eventType)) {
      this.eventHandlers.set(eventType, new Set());
    }
    this.eventHandlers.get(eventType)!.add(callback as EventCallback);
  }

  off<T>(eventType: string, callback?: EventCallback<T>): void {
    if (!callback) {
      this.eventHandlers.delete(eventType);
    } else {
      this.eventHandlers.get(eventType)?.delete(callback as EventCallback);
    }
  }

  private emit<T>(eventType: string, payload: T): void {
    const handlers = this.eventHandlers.get(eventType);
    if (handlers) {
      handlers.forEach((handler) => handler(payload));
    }
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.stopPingInterval();

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this.messageQueue = [];
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  getReadyState(): number {
    return this.ws?.readyState ?? WebSocket.CLOSED;
  }
}

export default WebSocketClient;
