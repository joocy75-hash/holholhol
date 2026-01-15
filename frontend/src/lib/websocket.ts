/**
 * WebSocket Client for Real-time Poker Game
 *
 * Features:
 * - Singleton pattern with connection management
 * - Duplicate connection prevention
 * - Automatic reconnection with exponential backoff
 * - Proper cleanup on disconnect
 * - Event handler management
 * - Type-safe event handling
 */

import {
  EventType,
  WebSocketMessage,
  EventHandler,
  TypedEventHandlers,
  PayloadFor,
} from '@/types/websocket';

type SendFailureHandler = (event: EventType | string, data: unknown, reason: string) => void;

export enum ConnectionState {
  DISCONNECTED = 'disconnected',
  CONNECTING = 'connecting',
  AUTHENTICATING = 'authenticating',
  CONNECTED = 'connected',
}

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private handlers: Map<string, Set<EventHandler<unknown>>> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private pingInterval: NodeJS.Timeout | null = null;
  private currentToken: string | null = null;
  private sendFailureHandler: SendFailureHandler | null = null;
  private connectionState: ConnectionState = ConnectionState.DISCONNECTED;
  private connectPromise: Promise<void> | null = null;

  constructor(private url: string) {}

  /**
   * Get current connection state
   */
  getState(): ConnectionState {
    return this.connectionState;
  }

  /**
   * Set a handler for send failures
   */
  onSendFailure(handler: SendFailureHandler) {
    this.sendFailureHandler = handler;
  }

  /**
   * Connect to WebSocket server
   * - Prevents duplicate connections
   * - Reuses existing connection if already connected
   */
  connect(token: string): Promise<void> {
    // Already connected with same token - reuse connection
    if (this.connectionState === ConnectionState.CONNECTED && this.currentToken === token) {
      console.log('WebSocket already connected, reusing connection');
      return Promise.resolve();
    }

    // Connection in progress - wait for it
    if (this.connectPromise && (
      this.connectionState === ConnectionState.CONNECTING ||
      this.connectionState === ConnectionState.AUTHENTICATING
    )) {
      console.log('WebSocket connection in progress, waiting...');
      return this.connectPromise;
    }

    // Clean up any existing connection before new one
    if (this.ws) {
      this.cleanup();
    }

    this.currentToken = token;
    this.connectionState = ConnectionState.CONNECTING;

    this.connectPromise = new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url);
      } catch {
        this.connectionState = ConnectionState.DISCONNECTED;
        this.connectPromise = null;
        reject(new Error('Failed to create WebSocket'));
        return;
      }

      const authTimeout = setTimeout(() => {
        if (this.connectionState !== ConnectionState.CONNECTED) {
          console.error('WebSocket auth timeout');
          this.cleanup();
          reject(new Error('Authentication timeout'));
        }
      }, 10000); // 10 second total timeout

      this.ws.onopen = () => {
        console.log('WebSocket connected, sending AUTH message');
        this.connectionState = ConnectionState.AUTHENTICATING;

        // Send AUTH message immediately
        if (this.ws?.readyState === WebSocket.OPEN) {
          this.ws.send(JSON.stringify({
            type: 'AUTH',
            payload: { token }
          }));
        } else {
          clearTimeout(authTimeout);
          this.cleanup();
          reject(new Error('WebSocket not ready after open'));
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);

          // Check for CONNECTION_STATE to confirm successful auth
          if (message.type === 'CONNECTION_STATE') {
            console.log('WebSocket authenticated successfully');
            clearTimeout(authTimeout);
            this.connectionState = ConnectionState.CONNECTED;
            this.reconnectAttempts = 0;
            this.startPing();
            // Emit CONNECTION_STATE event to handlers
            this.handleMessage({ type: 'CONNECTION_STATE', payload: message.payload });
            resolve();
            return;
          }

          // Handle ERROR during auth - use correct field names
          if (message.type === 'ERROR' && this.connectionState === ConnectionState.AUTHENTICATING) {
            console.error('WebSocket auth error:', message.payload);
            clearTimeout(authTimeout);
            const errorMsg = message.payload?.errorMessage || message.payload?.message || 'Authentication failed';
            this.cleanup();
            reject(new Error(errorMsg));
            return;
          }

          // Handle normal messages after connected
          this.handleMessage(message);
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      this.ws.onclose = (event) => {
        console.log('WebSocket disconnected', event.code, event.reason);
        clearTimeout(authTimeout);

        const wasConnected = this.connectionState === ConnectionState.CONNECTED;
        this.connectionState = ConnectionState.DISCONNECTED;
        this.stopPing();
        this.connectPromise = null;

        // Notify handlers about disconnection
        this.emitEvent('DISCONNECTED', { code: event.code, reason: event.reason });

        // Only attempt reconnect if we were previously connected and have a token
        if (wasConnected && this.currentToken) {
          this.attemptReconnect(this.currentToken);
        }
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        // Don't reject here - let onclose handle it
      };
    });

    return this.connectPromise;
  }

  private handleMessage(message: WebSocketMessage) {
    // Support both formats: { event, data } and { type, payload }
    const event = (message as { event?: string }).event || message.type;
    const data = (message as { data?: unknown }).data || message.payload;

    if (!event) return;

    this.emitEvent(event, data);
  }

  private emitEvent(event: string, data: unknown) {
    const handlers = this.handlers.get(event);
    // 게임 관련 중요 이벤트는 항상 로그 (디버깅용)
    if (['TURN_PROMPT', 'TURN_CHANGED', 'COMMUNITY_CARDS', 'HAND_RESULT', 'HAND_STARTED'].includes(event)) {
      console.log(`📨 WS Event [${event}]:`, data, `handlers: ${handlers?.size ?? 0}`);
    }
    if (handlers) {
      handlers.forEach((handler) => {
        try {
          handler(data);
        } catch (e) {
          console.error(`Error in handler for ${event}:`, e);
        }
      });
    }
  }

  private startPing() {
    this.stopPing(); // Clear any existing interval
    this.pingInterval = setInterval(() => {
      if (this.connectionState === ConnectionState.CONNECTED) {
        this.send('PING', {});
      }
    }, 30000);
  }

  private stopPing() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private attemptReconnect(token: string) {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnect attempts reached');
      this.emitEvent('CONNECTION_LOST', { reason: 'Max reconnect attempts reached' });
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000);

    console.log(`Reconnecting in ${delay}ms... attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);

    setTimeout(() => {
      if (this.connectionState === ConnectionState.DISCONNECTED) {
        this.connect(token).catch((err) => {
          console.error('Reconnect failed:', err);
        });
      }
    }, delay);
  }

  /**
   * Subscribe to an event with type-safe handler
   * @returns Unsubscribe function
   */
  on<E extends keyof TypedEventHandlers>(
    event: E,
    handler: TypedEventHandlers[E]
  ): () => void;
  on(event: string, handler: EventHandler<unknown>): () => void;
  on(event: string, handler: EventHandler<unknown>): () => void {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, new Set());
    }
    this.handlers.get(event)!.add(handler);

    return () => {
      this.handlers.get(event)?.delete(handler);
    };
  }

  /**
   * Unsubscribe from an event
   */
  off(event: string, handler: EventHandler<unknown>) {
    this.handlers.get(event)?.delete(handler);
  }

  /**
   * Send a message through WebSocket with type-safe payload
   * @returns true if sent successfully, false if connection is not open
   */
  send<E extends keyof TypedEventHandlers>(
    event: E,
    data: PayloadFor<E>
  ): boolean;
  send(event: EventType | string, data: unknown): boolean;
  send(event: EventType | string, data: unknown): boolean {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: event, payload: data }));
      return true;
    } else {
      const reason = this.ws
        ? `WebSocket state: ${this.ws.readyState} (${this.connectionState})`
        : 'WebSocket not initialized';

      // Don't warn for PING failures (too noisy)
      if (event !== EventType.PING && event !== 'PING') {
        console.warn(`Failed to send message (${event}): ${reason}`);
      }

      // Notify failure handler if set
      if (this.sendFailureHandler) {
        this.sendFailureHandler(event, data, reason);
      }

      // Also emit to SEND_FAILED handlers
      this.emitEvent('SEND_FAILED', { event, data, reason });

      return false;
    }
  }

  /**
   * Clean up resources without triggering reconnect
   */
  private cleanup() {
    this.stopPing();
    this.connectPromise = null;

    if (this.ws) {
      // Remove handlers to prevent onclose from triggering reconnect
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onclose = null;
      this.ws.onerror = null;

      if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
        this.ws.close();
      }
      this.ws = null;
    }

    this.connectionState = ConnectionState.DISCONNECTED;
  }

  /**
   * Disconnect and clean up
   * - Clears all state
   * - Does NOT trigger reconnection
   */
  disconnect() {
    console.log('WebSocket disconnect requested');
    this.currentToken = null;
    this.reconnectAttempts = this.maxReconnectAttempts; // Prevent reconnect
    this.cleanup();
  }

  /**
   * Check if connected
   */
  get isConnected(): boolean {
    return this.connectionState === ConnectionState.CONNECTED &&
           this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Get debug info for troubleshooting
   */
  getDebugInfo() {
    return {
      state: this.connectionState,
      wsReadyState: this.ws?.readyState,
      handlersCount: Array.from(this.handlers.entries()).map(([e, s]) => [e, s.size]),
      reconnectAttempts: this.reconnectAttempts,
      hasToken: !!this.currentToken,
    };
  }
}

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws';
export const wsClient = new WebSocketClient(WS_URL);
