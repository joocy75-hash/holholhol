"""Connection manager with Redis pub/sub for multi-instance support."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from redis.asyncio import Redis

from app.ws.connection import WebSocketConnection, ConnectionState
from app.ws.events import EventType
from app.ws.messages import MessageEnvelope

logger = logging.getLogger(__name__)

# Constants per spec section 2.3
HEARTBEAT_CHECK_INTERVAL = 5  # Check every 5 seconds
SERVER_TIMEOUT = 60  # Close connection if no PING for 60 seconds


class ConnectionManager:
    """Manages WebSocket connections with Redis pub/sub for multi-instance support."""

    def __init__(self, redis: Redis):
        self.redis = redis

        # Local connection registry (per instance)
        self._connections: dict[str, WebSocketConnection] = {}  # connection_id -> Connection
        self._user_connections: dict[str, set[str]] = {}  # user_id -> set[connection_id]

        # Channel subscriptions (local tracking)
        self._channel_members: dict[str, set[str]] = {}  # channel -> set[connection_id]

        # Background tasks
        self._pubsub_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False
        self._instance_id = str(uuid4())[:8]

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def start(self) -> None:
        """Start background tasks."""
        if self._running:
            return
        self._running = True
        await self._start_pubsub_listener()
        await self._start_heartbeat_monitor()
        logger.info(f"ConnectionManager started (instance: {self._instance_id})")

    async def stop(self) -> None:
        """Stop background tasks and cleanup."""
        self._running = False

        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        for conn_id in list(self._connections.keys()):
            await self.disconnect(conn_id)

        logger.info(f"ConnectionManager stopped (instance: {self._instance_id})")

    # =========================================================================
    # Connection Lifecycle
    # =========================================================================

    async def connect(self, conn: WebSocketConnection) -> None:
        """Register a new connection."""
        self._connections[conn.connection_id] = conn

        if conn.user_id not in self._user_connections:
            self._user_connections[conn.user_id] = set()
        self._user_connections[conn.user_id].add(conn.connection_id)

        # Store in Redis for cross-instance awareness
        await self.redis.hset(
            f"ws:connections:{conn.user_id}",
            conn.connection_id,
            json.dumps({
                "instance": self._instance_id,
                "connected_at": conn.connected_at.isoformat(),
                "session_id": conn.session_id,
            }),
        )

        logger.info(
            f"Connection {conn.connection_id} registered for user {conn.user_id}"
        )

    async def disconnect(self, connection_id: str) -> None:
        """Unregister a connection."""
        conn = self._connections.get(connection_id)
        if not conn:
            return

        # Remove from all channels first (before removing from _connections)
        # Use unsubscribe to also update Redis
        for channel in list(conn.subscribed_channels):
            await self.unsubscribe(connection_id, channel)

        # Now remove from connections
        self._connections.pop(connection_id, None)

        # Remove from user connections
        if conn.user_id in self._user_connections:
            self._user_connections[conn.user_id].discard(connection_id)
            if not self._user_connections[conn.user_id]:
                del self._user_connections[conn.user_id]

        # Remove from Redis
        await self.redis.hdel(f"ws:connections:{conn.user_id}", connection_id)

        logger.info(f"Connection {connection_id} unregistered")

    def get_connection(self, connection_id: str) -> WebSocketConnection | None:
        """Get a connection by ID."""
        return self._connections.get(connection_id)

    def get_user_connections(self, user_id: str) -> list[WebSocketConnection]:
        """Get all connections for a user."""
        conn_ids = self._user_connections.get(user_id, set())
        return [self._connections[cid] for cid in conn_ids if cid in self._connections]

    @property
    def connection_count(self) -> int:
        """Get total number of connections."""
        return len(self._connections)

    # =========================================================================
    # Channel Management
    # =========================================================================

    async def subscribe(self, connection_id: str, channel: str) -> bool:
        """Subscribe connection to a channel."""
        conn = self._connections.get(connection_id)
        if not conn:
            return False

        if channel not in self._channel_members:
            self._channel_members[channel] = set()

        self._channel_members[channel].add(connection_id)
        conn.subscribed_channels.add(channel)

        # Track in Redis for cross-instance broadcast
        await self.redis.sadd(
            f"ws:channel:{channel}",
            f"{self._instance_id}:{connection_id}",
        )

        logger.debug(f"Connection {connection_id} subscribed to {channel}")
        return True

    async def unsubscribe(self, connection_id: str, channel: str) -> bool:
        """Unsubscribe connection from a channel."""
        result = await self._unsubscribe_local(connection_id, channel)
        if result:
            await self.redis.srem(
                f"ws:channel:{channel}",
                f"{self._instance_id}:{connection_id}",
            )
        return result

    async def _unsubscribe_local(self, connection_id: str, channel: str) -> bool:
        """Unsubscribe locally without Redis update."""
        conn = self._connections.get(connection_id)
        if not conn:
            return False

        if channel in self._channel_members:
            self._channel_members[channel].discard(connection_id)
            if not self._channel_members[channel]:
                del self._channel_members[channel]

        conn.subscribed_channels.discard(channel)
        logger.debug(f"Connection {connection_id} unsubscribed from {channel}")
        return True

    def get_channel_subscribers(self, channel: str) -> list[str]:
        """Get local connection IDs subscribed to a channel."""
        return list(self._channel_members.get(channel, set()))

    # =========================================================================
    # Broadcasting
    # =========================================================================

    async def broadcast_to_channel(
        self,
        channel: str,
        message: dict[str, Any],
        exclude_connection: str | None = None,
    ) -> int:
        """Broadcast message to all subscribers of a channel (cross-instance).

        Returns count of messages sent to local subscribers.
        """
        # Publish to Redis for other instances
        await self.redis.publish(
            f"ws:pubsub:{channel}",
            json.dumps({
                "source_instance": self._instance_id,
                "exclude_connection": exclude_connection,
                "message": message,
            }),
        )

        # Also send to local subscribers
        return await self._send_to_local_channel(channel, message, exclude_connection)

    async def send_to_user(
        self,
        user_id: str,
        message: dict[str, Any],
    ) -> int:
        """Send message to all connections of a user. Returns count sent."""
        count = 0
        connection_ids = self._user_connections.get(user_id, set())

        for conn_id in connection_ids:
            conn = self._connections.get(conn_id)
            if conn and await conn.send(message):
                count += 1

        return count

    async def send_to_connection(
        self,
        connection_id: str,
        message: dict[str, Any],
    ) -> bool:
        """Send message to a specific connection."""
        conn = self._connections.get(connection_id)
        if conn:
            return await conn.send(message)
        return False

    async def _send_to_local_channel(
        self,
        channel: str,
        message: dict[str, Any],
        exclude_connection: str | None = None,
    ) -> int:
        """Send to local channel subscribers only."""
        connection_ids = self._channel_members.get(channel, set())
        count = 0

        for conn_id in list(connection_ids):
            if conn_id == exclude_connection:
                continue
            conn = self._connections.get(conn_id)
            if conn and await conn.send(message):
                count += 1

        return count

    # =========================================================================
    # Redis Pub/Sub Listener
    # =========================================================================

    async def _start_pubsub_listener(self) -> None:
        """Start listening to Redis pub/sub for cross-instance messages."""
        pubsub = self.redis.pubsub()
        await pubsub.psubscribe("ws:pubsub:*")

        async def listener() -> None:
            while self._running:
                try:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )
                    if message and message["type"] == "pmessage":
                        await self._handle_pubsub_message(message)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Pub/sub listener error: {e}")
                    await asyncio.sleep(1)

            await pubsub.punsubscribe("ws:pubsub:*")
            await pubsub.close()

        self._pubsub_task = asyncio.create_task(listener())

    async def _handle_pubsub_message(self, message: dict[str, Any]) -> None:
        """Handle incoming pub/sub message."""
        try:
            channel_bytes = message.get("channel", b"")
            if isinstance(channel_bytes, bytes):
                channel = channel_bytes.decode().replace("ws:pubsub:", "")
            else:
                channel = str(channel_bytes).replace("ws:pubsub:", "")

            data_bytes = message.get("data", b"{}")
            if isinstance(data_bytes, bytes):
                data = json.loads(data_bytes.decode())
            else:
                data = json.loads(str(data_bytes))

            # Skip messages from self
            if data.get("source_instance") == self._instance_id:
                return

            exclude = data.get("exclude_connection")
            await self._send_to_local_channel(channel, data["message"], exclude)

        except Exception as e:
            logger.error(f"Error handling pub/sub message: {e}")

    # =========================================================================
    # Heartbeat Management
    # =========================================================================

    async def _start_heartbeat_monitor(self) -> None:
        """Start heartbeat monitoring task."""
        async def monitor() -> None:
            while self._running:
                try:
                    await asyncio.sleep(HEARTBEAT_CHECK_INTERVAL)
                    await self._check_heartbeats()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Heartbeat monitor error: {e}")

        self._heartbeat_task = asyncio.create_task(monitor())

    async def _check_heartbeats(self) -> None:
        """Check for stale connections (no PING for 60s per spec)."""
        now = datetime.utcnow()
        stale_timeout = timedelta(seconds=SERVER_TIMEOUT)

        stale_connections = []
        for conn_id, conn in self._connections.items():
            if conn.last_ping_at is None:
                # Use connected_at if no ping received yet
                if (now - conn.connected_at) > stale_timeout:
                    stale_connections.append(conn_id)
            elif (now - conn.last_ping_at) > stale_timeout:
                stale_connections.append(conn_id)

        for conn_id in stale_connections:
            logger.warning(f"Connection {conn_id} timed out (no PING)")
            conn = self._connections.get(conn_id)
            if conn:
                await conn.close(4000, "Connection timeout")
            await self.disconnect(conn_id)

    # =========================================================================
    # State Recovery (for reconnection)
    # =========================================================================

    async def store_user_state(self, user_id: str, state: dict[str, Any]) -> None:
        """Store user state for reconnection recovery."""
        await self.redis.setex(
            f"ws:user_state:{user_id}",
            300,  # 5 minutes TTL
            json.dumps(state),
        )

    async def get_user_state(self, user_id: str) -> dict[str, Any] | None:
        """Get stored user state for reconnection."""
        data = await self.redis.get(f"ws:user_state:{user_id}")
        if data:
            return json.loads(data)
        return None

    async def get_previous_subscriptions(self, user_id: str) -> list[str]:
        """Get previously subscribed channels for a user."""
        state = await self.get_user_state(user_id)
        if state:
            return state.get("subscribed_channels", [])
        return []
