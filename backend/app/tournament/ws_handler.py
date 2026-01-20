"""
Tournament WebSocket Handler.

토너먼트 이벤트를 WebSocket으로 브로드캐스트하고
클라이언트 요청을 처리하는 핸들러.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..ws.connection import WebSocketConnection
from ..ws.events import EventType

logger = logging.getLogger(__name__)


@dataclass
class TournamentSubscription:
    """Tournament channel subscription."""

    tournament_id: str
    connection_id: str
    user_id: str
    subscribed_at: datetime = field(default_factory=datetime.utcnow)


class TournamentWebSocketHandler:
    """
    토너먼트 WebSocket 핸들러.

    채널 구조:
    - tournament:{id} - 토너먼트 전체 이벤트
    - tournament:{id}:table:{table_id} - 테이블 이벤트
    - tournament:{id}:ranking - 랭킹 업데이트
    """

    HANDLED_EVENTS = [
        EventType.SUBSCRIBE,
        EventType.UNSUBSCRIBE,
    ]

    def __init__(self, manager):
        self.manager = manager
        self._subscriptions: dict[str, set[str]] = {}  # tournament_id -> connection_ids
        self._table_subs: dict[str, set[str]] = {}  # table_channel -> connection_ids

    async def handle(
        self,
        event_type: EventType,
        payload: dict[str, Any],
        connection: WebSocketConnection,
    ) -> dict[str, Any] | None:
        """Handle tournament-related WebSocket events."""
        channel = payload.get("channel", "")

        if not channel.startswith("tournament:"):
            return None

        if event_type == EventType.SUBSCRIBE:
            return await self._handle_subscribe(channel, connection)
        elif event_type == EventType.UNSUBSCRIBE:
            return await self._handle_unsubscribe(channel, connection)

        return None

    async def _handle_subscribe(
        self,
        channel: str,
        connection: WebSocketConnection,
    ) -> dict[str, Any]:
        """Handle subscription to tournament channel."""
        parts = channel.split(":")

        if len(parts) < 2:
            return {
                "type": "ERROR",
                "payload": {
                    "code": "INVALID_CHANNEL",
                    "message": "Invalid channel format",
                },
            }

        tournament_id = parts[1]

        # Subscribe to manager
        await self.manager.subscribe(connection.connection_id, channel)

        # Track subscription
        if tournament_id not in self._subscriptions:
            self._subscriptions[tournament_id] = set()
        self._subscriptions[tournament_id].add(connection.connection_id)

        logger.info(f"Connection {connection.connection_id} subscribed to {channel}")

        return {
            "type": "SUBSCRIBED",
            "payload": {"channel": channel},
        }

    async def _handle_unsubscribe(
        self,
        channel: str,
        connection: WebSocketConnection,
    ) -> dict[str, Any]:
        """Handle unsubscription from tournament channel."""
        parts = channel.split(":")

        if len(parts) < 2:
            return {
                "type": "ERROR",
                "payload": {
                    "code": "INVALID_CHANNEL",
                    "message": "Invalid channel format",
                },
            }

        tournament_id = parts[1]

        # Unsubscribe from manager
        await self.manager.unsubscribe(connection.connection_id, channel)

        # Remove from tracking
        if tournament_id in self._subscriptions:
            self._subscriptions[tournament_id].discard(connection.connection_id)

        return {
            "type": "UNSUBSCRIBED",
            "payload": {"channel": channel},
        }

    async def broadcast_tournament_event(
        self,
        tournament_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> int:
        """
        Broadcast event to all tournament subscribers.

        Returns count of messages sent.
        """
        channel = f"tournament:{tournament_id}"
        message = {
            "type": "TOURNAMENT_EVENT",
            "payload": {
                "event_type": event_type,
                "tournament_id": tournament_id,
                "data": data,
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

        return await self.manager.broadcast_to_channel(channel, message)

    async def broadcast_table_event(
        self,
        tournament_id: str,
        table_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> int:
        """Broadcast event to table subscribers."""
        channel = f"tournament:{tournament_id}:table:{table_id}"
        message = {
            "type": "TABLE_EVENT",
            "payload": {
                "event_type": event_type,
                "tournament_id": tournament_id,
                "table_id": table_id,
                "data": data,
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

        return await self.manager.broadcast_to_channel(channel, message)

    async def broadcast_ranking_update(
        self,
        tournament_id: str,
        ranking: list[dict[str, Any]],
    ) -> int:
        """Broadcast ranking update to tournament subscribers."""
        channel = f"tournament:{tournament_id}"
        message = {
            "type": "RANKING_UPDATE",
            "payload": {
                "tournament_id": tournament_id,
                "ranking": ranking[:100],  # Top 100
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

        return await self.manager.broadcast_to_channel(channel, message)

    async def broadcast_blind_change(
        self,
        tournament_id: str,
        level: int,
        small_blind: int,
        big_blind: int,
        ante: int,
        next_level_at: str | None = None,
    ) -> int:
        """Broadcast blind level change."""
        channel = f"tournament:{tournament_id}"
        message = {
            "type": "BLIND_CHANGE",
            "payload": {
                "tournament_id": tournament_id,
                "level": level,
                "small_blind": small_blind,
                "big_blind": big_blind,
                "ante": ante,
                "next_level_at": next_level_at,
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

        return await self.manager.broadcast_to_channel(channel, message)

    async def send_player_move_notification(
        self,
        tournament_id: str,
        user_id: str,
        from_table_id: str,
        to_table_id: str,
        to_seat: int,
    ) -> int:
        """Send move notification to specific player."""
        message = {
            "type": "PLAYER_MOVE",
            "payload": {
                "tournament_id": tournament_id,
                "from_table_id": from_table_id,
                "to_table_id": to_table_id,
                "to_seat": to_seat,
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

        return await self.manager.send_to_user(user_id, message)

    async def broadcast_shotgun_countdown(
        self,
        tournament_id: str,
        seconds_remaining: int,
        target_start_time: str,
    ) -> int:
        """Broadcast shotgun start countdown."""
        channel = f"tournament:{tournament_id}"
        message = {
            "type": "SHOTGUN_COUNTDOWN",
            "payload": {
                "tournament_id": tournament_id,
                "seconds_remaining": seconds_remaining,
                "target_start_time": target_start_time,
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

        return await self.manager.broadcast_to_channel(channel, message)

    def get_subscriber_count(self, tournament_id: str) -> int:
        """Get subscriber count for a tournament."""
        return len(self._subscriptions.get(tournament_id, set()))

    async def cleanup_connection(self, connection_id: str) -> None:
        """Cleanup subscriptions when connection closes."""
        for tournament_id in list(self._subscriptions.keys()):
            self._subscriptions[tournament_id].discard(connection_id)
            if not self._subscriptions[tournament_id]:
                del self._subscriptions[tournament_id]
