"""Connection manager with Redis pub/sub for multi-instance support."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from redis.asyncio import Redis

from app.config import get_settings
from app.ws.connection import WebSocketConnection, ConnectionState
from app.ws.events import EventType
from app.ws.messages import MessageEnvelope
from app.ws.worker_health import WorkerHealthManager

logger = logging.getLogger(__name__)

# CCU/DAU 트래킹 상수
CCU_SNAPSHOT_INTERVAL = 60  # 매 분마다 CCU 스냅샷 저장
CCU_HISTORY_TTL = 86400 * 7  # 7일 보관
DAU_TTL = 86400 * 31  # 31일 보관 (월간 집계용)

# Constants per spec section 2.3
HEARTBEAT_CHECK_INTERVAL = 5  # Check every 5 seconds
SERVER_TIMEOUT = 60  # Close connection if no PING for 60 seconds


class ConnectionLimitExceeded(Exception):
    """Raised when connection limits are exceeded."""
    pass


class ConnectionManager:
    """Manages WebSocket connections with Redis pub/sub for multi-instance support."""

    def __init__(self, redis: Redis):
        self.redis = redis
        self._settings = get_settings()

        # Local connection registry (per instance)
        self._connections: dict[str, WebSocketConnection] = {}  # connection_id -> Connection
        self._user_connections: dict[str, set[str]] = {}  # user_id -> set[connection_id]

        # Channel subscriptions (local tracking)
        self._channel_members: dict[str, set[str]] = {}  # channel -> set[connection_id]

        # Connection limits (Phase 2.5)
        self._max_connections = self._settings.ws_max_connections
        self._max_connections_per_user = self._settings.ws_max_connections_per_user

        # Background tasks
        self._pubsub_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._ccu_snapshot_task: asyncio.Task | None = None  # Phase 5.1: CCU 스냅샷
        self._running = False
        self._instance_id = str(uuid4())[:8]

        # Worker health management (Phase 2.7)
        self._worker_health = WorkerHealthManager(redis, self._instance_id)

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
        await self._start_ccu_snapshot_task()  # Phase 5.1: CCU 스냅샷

        # Start worker health management (Phase 2.7)
        await self._worker_health.start(on_worker_dead=self._on_worker_dead)

        logger.info(f"ConnectionManager started (instance: {self._instance_id})")

    async def _on_worker_dead(self, worker_id: str) -> None:
        """Handle dead worker notification (Phase 2.7)."""
        logger.warning(
            f"Worker {worker_id} died. Connections have been cleaned up from Redis."
        )
        # 추가 로직이 필요하면 여기에 구현
        # 예: 재연결 알림 전송, 모니터링 메트릭 업데이트 등

    async def stop(self) -> None:
        """Stop background tasks and cleanup."""
        self._running = False
        logger.info(f"Stopping ConnectionManager (instance: {self._instance_id})")

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

        if self._ccu_snapshot_task:
            self._ccu_snapshot_task.cancel()
            try:
                await self._ccu_snapshot_task
            except asyncio.CancelledError:
                pass

        # Stop worker health management (Phase 2.7)
        await self._worker_health.stop()

        # Close all connections (don't save state on shutdown)
        connection_count = len(self._connections)
        for conn_id in list(self._connections.keys()):
            try:
                await self.disconnect(conn_id, save_state=False)
            except Exception as e:
                logger.error(f"Error disconnecting {conn_id} during shutdown: {e}")

        logger.info(
            f"ConnectionManager stopped (instance: {self._instance_id}, "
            f"connections closed: {connection_count})"
        )

    # =========================================================================
    # Connection Lifecycle
    # =========================================================================

    async def connect(self, conn: WebSocketConnection) -> None:
        """Register a new connection with connection limit enforcement."""
        # Check global connection limit
        if len(self._connections) >= self._max_connections:
            logger.warning(
                f"Global connection limit reached ({self._max_connections}). "
                f"Rejecting connection for user {conn.user_id}"
            )
            raise ConnectionLimitExceeded(
                f"Maximum connections ({self._max_connections}) reached"
            )

        # Check per-user connection limit and close oldest if exceeded
        user_conn_ids = self._user_connections.get(conn.user_id, set())
        if len(user_conn_ids) >= self._max_connections_per_user:
            # Find and close the oldest connection for this user
            oldest_conn_id = await self._get_oldest_user_connection(conn.user_id)
            if oldest_conn_id:
                logger.info(
                    f"User {conn.user_id} exceeded connection limit "
                    f"({self._max_connections_per_user}). Closing oldest: {oldest_conn_id}"
                )
                old_conn = self._connections.get(oldest_conn_id)
                if old_conn:
                    await old_conn.close(4001, "New connection opened, closing old session")
                await self.disconnect(oldest_conn_id)

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

        # Phase 5.1: CCU/DAU 트래킹
        await self._track_user_online(conn.user_id)

        logger.info(
            f"Connection {conn.connection_id} registered for user {conn.user_id} "
            f"(total: {len(self._connections)}/{self._max_connections}, "
            f"user: {len(self._user_connections.get(conn.user_id, set()))}/{self._max_connections_per_user})"
        )

    async def _get_oldest_user_connection(self, user_id: str) -> str | None:
        """Get the oldest connection ID for a user."""
        conn_ids = self._user_connections.get(user_id, set())
        if not conn_ids:
            return None

        oldest_id = None
        oldest_time = None

        for conn_id in conn_ids:
            conn = self._connections.get(conn_id)
            if conn:
                if oldest_time is None or conn.connected_at < oldest_time:
                    oldest_time = conn.connected_at
                    oldest_id = conn_id

        return oldest_id

    async def disconnect(self, connection_id: str, save_state: bool = True) -> None:
        """Unregister a connection and cleanup all associated resources.
        
        Args:
            connection_id: The connection ID to disconnect
            save_state: If True, save user state for reconnection recovery
                       when this is the user's last connection
        """
        conn = self._connections.get(connection_id)
        if not conn:
            logger.debug(f"Connection {connection_id} not found, skipping disconnect")
            return

        user_id = conn.user_id
        channels_cleaned = 0
        redis_cleaned = False
        
        logger.info(
            f"Disconnecting connection {connection_id} for user {user_id} "
            f"(subscribed channels: {len(conn.subscribed_channels)})"
        )

        # Step 1: Update connection state
        try:
            conn.state = ConnectionState.DISCONNECTED
        except Exception as e:
            logger.warning(f"Failed to update connection state for {connection_id}: {e}")

        # Step 2: Remove from all channels (before removing from _connections)
        # Use unsubscribe to also update Redis
        channels_to_unsubscribe = list(conn.subscribed_channels)
        for channel in channels_to_unsubscribe:
            try:
                await self.unsubscribe(connection_id, channel)
                channels_cleaned += 1
            except Exception as e:
                logger.error(
                    f"Failed to unsubscribe {connection_id} from channel {channel}: {e}"
                )
                # Continue with other channels even if one fails
                # Also try to clean up local state directly
                try:
                    await self._unsubscribe_local(connection_id, channel)
                except Exception:
                    pass

        # Step 3: Remove from local connections registry
        try:
            self._connections.pop(connection_id, None)
        except Exception as e:
            logger.error(f"Failed to remove connection {connection_id} from registry: {e}")

        # Step 4: Remove from user connections
        is_last_connection = False
        try:
            if user_id in self._user_connections:
                self._user_connections[user_id].discard(connection_id)
                if not self._user_connections[user_id]:
                    del self._user_connections[user_id]
                    is_last_connection = True
                    # Phase 5.1: 마지막 연결 해제 시 offline 트래킹
                    await self._track_user_offline(user_id)
        except Exception as e:
            logger.error(
                f"Failed to remove connection {connection_id} from user connections: {e}"
            )

        # Step 5: Remove from Redis connection registry
        try:
            await self.redis.hdel(f"ws:connections:{user_id}", connection_id)
            redis_cleaned = True
        except Exception as e:
            logger.error(
                f"Failed to remove connection {connection_id} from Redis: {e}"
            )

        # Step 6: Save user state for reconnection if this is the last connection
        if save_state and is_last_connection and channels_to_unsubscribe:
            try:
                await self.store_user_state(user_id, {
                    "subscribed_channels": channels_to_unsubscribe,
                    "last_seen_versions": conn.last_seen_versions,
                    "disconnected_at": datetime.utcnow().isoformat(),
                })
                logger.debug(
                    f"Saved reconnection state for user {user_id} "
                    f"(channels: {channels_to_unsubscribe})"
                )
            except Exception as e:
                logger.warning(f"Failed to save user state for {user_id}: {e}")

        # Step 7: Clean up any orphaned Redis channel entries
        # This handles cases where unsubscribe might have partially failed
        for channel in channels_to_unsubscribe:
            try:
                await self.redis.srem(
                    f"ws:channel:{channel}",
                    f"{self._instance_id}:{connection_id}",
                )
            except Exception as e:
                logger.debug(
                    f"Failed to clean orphaned Redis channel entry for {channel}: {e}"
                )

        logger.info(
            f"Connection {connection_id} disconnected - "
            f"channels cleaned: {channels_cleaned}/{len(channels_to_unsubscribe)}, "
            f"redis cleaned: {redis_cleaned}, "
            f"remaining connections: {len(self._connections)}"
        )

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

    def get_channel_connections(self, channel: str) -> list[WebSocketConnection]:
        """Get local WebSocketConnection objects subscribed to a channel."""
        conn_ids = self._channel_members.get(channel, set())
        return [
            self._connections[cid]
            for cid in conn_ids
            if cid in self._connections
        ]

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
    # Group Broadcasting (Phase 4.2)
    # =========================================================================

    async def broadcast_to_players(
        self,
        room_id: str,
        message: dict[str, Any],
        exclude_connection: str | None = None,
    ) -> int:
        """Broadcast message only to players (not spectators).

        Uses the table:{room_id}:players subchannel.
        """
        channel = f"table:{room_id}:players"
        return await self.broadcast_to_channel(channel, message, exclude_connection)

    async def broadcast_to_spectators(
        self,
        room_id: str,
        message: dict[str, Any],
        exclude_connection: str | None = None,
    ) -> int:
        """Broadcast message only to spectators (not players).

        Uses the table:{room_id}:spectators subchannel.
        """
        channel = f"table:{room_id}:spectators"
        return await self.broadcast_to_channel(channel, message, exclude_connection)

    async def broadcast_to_table(
        self,
        room_id: str,
        message: dict[str, Any],
        exclude_connection: str | None = None,
    ) -> int:
        """Broadcast message to all table subscribers (players + spectators).

        Uses the main table:{room_id} channel.
        """
        channel = f"table:{room_id}"
        return await self.broadcast_to_channel(channel, message, exclude_connection)

    async def subscribe_as_player(
        self,
        connection_id: str,
        room_id: str,
    ) -> bool:
        """Subscribe connection to table as a player.

        Subscribes to both main channel and players subchannel.
        """
        main_channel = f"table:{room_id}"
        players_channel = f"table:{room_id}:players"

        # Subscribe to main channel
        result1 = await self.subscribe(connection_id, main_channel)

        # Subscribe to players subchannel
        result2 = await self.subscribe(connection_id, players_channel)

        # Unsubscribe from spectators if previously subscribed
        spectators_channel = f"table:{room_id}:spectators"
        if spectators_channel in self._channel_members:
            conn = self._connections.get(connection_id)
            if conn and spectators_channel in conn.subscribed_channels:
                await self.unsubscribe(connection_id, spectators_channel)

        logger.debug(f"Connection {connection_id} subscribed as player to {room_id}")
        return result1 and result2

    async def subscribe_as_spectator(
        self,
        connection_id: str,
        room_id: str,
    ) -> bool:
        """Subscribe connection to table as a spectator.

        Subscribes to both main channel and spectators subchannel.
        """
        main_channel = f"table:{room_id}"
        spectators_channel = f"table:{room_id}:spectators"

        # Subscribe to main channel
        result1 = await self.subscribe(connection_id, main_channel)

        # Subscribe to spectators subchannel
        result2 = await self.subscribe(connection_id, spectators_channel)

        logger.debug(f"Connection {connection_id} subscribed as spectator to {room_id}")
        return result1 and result2

    async def upgrade_to_player(
        self,
        connection_id: str,
        room_id: str,
    ) -> bool:
        """Upgrade a spectator to player status.

        Moves from spectators subchannel to players subchannel.
        """
        spectators_channel = f"table:{room_id}:spectators"
        players_channel = f"table:{room_id}:players"

        # Unsubscribe from spectators
        await self.unsubscribe(connection_id, spectators_channel)

        # Subscribe to players
        result = await self.subscribe(connection_id, players_channel)

        logger.debug(f"Connection {connection_id} upgraded to player in {room_id}")
        return result

    async def downgrade_to_spectator(
        self,
        connection_id: str,
        room_id: str,
    ) -> bool:
        """Downgrade a player to spectator status.

        Moves from players subchannel to spectators subchannel.
        """
        players_channel = f"table:{room_id}:players"
        spectators_channel = f"table:{room_id}:spectators"

        # Unsubscribe from players
        await self.unsubscribe(connection_id, players_channel)

        # Subscribe to spectators
        result = await self.subscribe(connection_id, spectators_channel)

        logger.debug(f"Connection {connection_id} downgraded to spectator in {room_id}")
        return result

    async def unsubscribe_from_table(
        self,
        connection_id: str,
        room_id: str,
    ) -> bool:
        """Unsubscribe connection from all table channels.

        Removes from main channel and any subchannels.
        """
        main_channel = f"table:{room_id}"
        players_channel = f"table:{room_id}:players"
        spectators_channel = f"table:{room_id}:spectators"

        # Unsubscribe from all
        await self.unsubscribe(connection_id, main_channel)
        await self.unsubscribe(connection_id, players_channel)
        await self.unsubscribe(connection_id, spectators_channel)

        logger.debug(f"Connection {connection_id} unsubscribed from table {room_id}")
        return True

    def get_player_count(self, room_id: str) -> int:
        """Get count of players subscribed to a table."""
        players_channel = f"table:{room_id}:players"
        return len(self._channel_members.get(players_channel, set()))

    def get_spectator_count(self, room_id: str) -> int:
        """Get count of spectators subscribed to a table."""
        spectators_channel = f"table:{room_id}:spectators"
        return len(self._channel_members.get(spectators_channel, set()))

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
            logger.warning(f"Connection {conn_id} timed out (no PING for {SERVER_TIMEOUT}s)")
            conn = self._connections.get(conn_id)
            if conn:
                try:
                    await conn.close(4000, "Connection timeout")
                except Exception as e:
                    logger.debug(f"Error closing timed out connection {conn_id}: {e}")
            # Save state for reconnection on timeout (user might reconnect)
            await self.disconnect(conn_id, save_state=True)

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

    # =========================================================================
    # CCU/DAU Tracking (Phase 5.1)
    # =========================================================================

    async def _track_user_online(self, user_id: str) -> None:
        """사용자 온라인 상태 추적.

        - online_users SET에 user_id 추가 (CCU 계산용)
        - DAU HyperLogLog에 user_id 추가 (DAU 계산용)
        - MAU HyperLogLog에 user_id 추가 (MAU 계산용)
        """
        try:
            now = datetime.utcnow()
            today = now.strftime("%Y-%m-%d")
            month = now.strftime("%Y-%m")

            pipe = self.redis.pipeline()

            # CCU: online_users SET에 추가
            pipe.sadd("online_users", user_id)

            # DAU: 일별 HyperLogLog에 추가
            dau_key = f"dau:{today}"
            pipe.pfadd(dau_key, user_id)
            pipe.expire(dau_key, DAU_TTL)

            # MAU: 월별 HyperLogLog에 추가
            mau_key = f"mau:{month}"
            pipe.pfadd(mau_key, user_id)
            pipe.expire(mau_key, DAU_TTL)

            await pipe.execute()

            logger.debug(f"User {user_id} tracked as online (DAU: {today}, MAU: {month})")
        except Exception as e:
            logger.warning(f"Failed to track user online: {e}")

    async def _track_user_offline(self, user_id: str) -> None:
        """사용자 오프라인 상태 추적.

        - online_users SET에서 user_id 제거 (CCU 계산용)
        """
        try:
            await self.redis.srem("online_users", user_id)
            logger.debug(f"User {user_id} tracked as offline")
        except Exception as e:
            logger.warning(f"Failed to track user offline: {e}")

    async def _start_ccu_snapshot_task(self) -> None:
        """CCU 스냅샷 태스크 시작 (매 분마다 현재 CCU를 기록)."""

        async def snapshot_loop() -> None:
            while self._running:
                try:
                    await asyncio.sleep(CCU_SNAPSHOT_INTERVAL)
                    await self._save_ccu_snapshot()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"CCU snapshot error: {e}")

        self._ccu_snapshot_task = asyncio.create_task(snapshot_loop())
        logger.info("CCU snapshot task started")

    async def _save_ccu_snapshot(self) -> None:
        """현재 CCU를 시간별 키에 저장."""
        try:
            now = datetime.utcnow()
            hour_key = now.strftime("%Y-%m-%d:%H")

            # 현재 CCU 조회
            ccu = await self.redis.scard("online_users")

            # 시간별 CCU 저장 (더 높은 값 유지)
            ccu_key = f"ccu_hourly:{hour_key}"
            current = await self.redis.get(ccu_key)

            if current is None or int(ccu) > int(current):
                await self.redis.setex(ccu_key, CCU_HISTORY_TTL, str(ccu))

            # 분별 세부 CCU도 저장 (선택적)
            minute_key = now.strftime("%Y-%m-%d:%H:%M")
            await self.redis.setex(
                f"ccu_minute:{minute_key}",
                86400,  # 1일 보관
                str(ccu),
            )

            logger.debug(f"CCU snapshot saved: {ccu} users at {hour_key}")
        except Exception as e:
            logger.warning(f"Failed to save CCU snapshot: {e}")

    async def get_current_ccu(self) -> int:
        """현재 CCU 조회."""
        try:
            return await self.redis.scard("online_users")
        except Exception:
            return 0

    async def get_online_users(self) -> list[str]:
        """현재 온라인 사용자 목록 조회."""
        try:
            users = await self.redis.smembers("online_users")
            return list(users)
        except Exception:
            return []
