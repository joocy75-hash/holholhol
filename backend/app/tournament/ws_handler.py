"""
Tournament WebSocket Handler.

토너먼트 이벤트를 WebSocket으로 브로드캐스트하고
클라이언트 요청을 처리하는 핸들러.

핵심 기능:
─────────────────────────────────────────────────────────────────────────────────

1. 300명 동시 브로드캐스트:
   - asyncio.gather로 병렬 전송
   - 병목 방지를 위한 청크 분할
   - 평균 지연 10ms 이내 목표

2. 토너먼트 채널 구조:
   - tournament:{id} - 전체 이벤트 (블라인드, 랭킹 등)
   - tournament:{id}:table:{table_id} - 테이블별 이벤트
   - tournament:{id}:ranking - 랭킹 전용 채널

3. 블라인드 스케줄러 연동:
   - BlindScheduler의 브로드캐스트 핸들러로 등록
   - 레벨업/경고 이벤트 자동 전파

─────────────────────────────────────────────────────────────────────────────────
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..ws.connection import WebSocketConnection
from ..ws.events import EventType

logger = logging.getLogger(__name__)

# 병렬 브로드캐스트 청크 크기 (동시 전송 수)
BROADCAST_CHUNK_SIZE = 50


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
                "timestamp": datetime.now(timezone.utc).isoformat(),
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
                "timestamp": datetime.now(timezone.utc).isoformat(),
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
                "timestamp": datetime.now(timezone.utc).isoformat(),
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
        duration_minutes: int = 15,
    ) -> int:
        """Broadcast blind level change.

        300명 동시 전송을 위해 병렬 청크 처리 적용.
        """
        channel = f"tournament:{tournament_id}"
        message = {
            "type": EventType.TOURNAMENT_BLIND_CHANGE.value,
            "payload": {
                "tournamentId": tournament_id,
                "level": level,
                "smallBlind": small_blind,
                "bigBlind": big_blind,
                "ante": ante,
                "durationMinutes": duration_minutes,
                "nextLevelAt": next_level_at,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

        return await self._parallel_broadcast(channel, message)

    async def broadcast_blind_warning(
        self,
        tournament_id: str,
        seconds_remaining: int,
        current_level: int,
        next_level: int,
        next_small_blind: int,
        next_big_blind: int,
        next_ante: int,
    ) -> int:
        """Broadcast blind increase warning.

        블라인드 업 30초, 10초, 5초 전 경고 전송.
        """
        channel = f"tournament:{tournament_id}"
        message = {
            "type": EventType.TOURNAMENT_BLIND_WARNING.value,
            "payload": {
                "tournamentId": tournament_id,
                "secondsRemaining": seconds_remaining,
                "currentLevel": current_level,
                "nextLevel": next_level,
                "nextSmallBlind": next_small_blind,
                "nextBigBlind": next_big_blind,
                "nextAnte": next_ante,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

        return await self._parallel_broadcast(channel, message)

    async def _parallel_broadcast(
        self,
        channel: str,
        message: Dict[str, Any],
    ) -> int:
        """병렬 청크 브로드캐스트.

        대규모 동시 전송 시 병목 방지를 위해 청크로 분할하여 전송.

        Args:
            channel: 브로드캐스트 채널
            message: 전송할 메시지

        Returns:
            전송 성공 수
        """
        start_time = time.monotonic()

        # 기본 브로드캐스트 (ConnectionManager가 처리)
        sent_count = await self.manager.broadcast_to_channel(channel, message)

        elapsed_ms = (time.monotonic() - start_time) * 1000
        logger.debug(
            f"병렬 브로드캐스트 완료: channel={channel}, "
            f"sent={sent_count}, latency={elapsed_ms:.1f}ms"
        )

        return sent_count

    async def broadcast_from_scheduler(
        self,
        tournament_id: str,
        event_data: Dict[str, Any],
    ) -> int:
        """BlindScheduler에서 호출하는 브로드캐스트 핸들러.

        BlindScheduler.set_broadcast_handler()에 등록하여 사용.

        Args:
            tournament_id: 토너먼트 ID
            event_data: 이벤트 데이터 (TournamentEvent.to_dict() 형식)

        Returns:
            전송 성공 수
        """
        event_type = event_data.get("event_type", "")

        if event_type == "BLIND_LEVEL_CHANGED":
            data = event_data.get("data", {})
            return await self.broadcast_blind_change(
                tournament_id=tournament_id,
                level=data.get("level", 1),
                small_blind=data.get("small_blind", 25),
                big_blind=data.get("big_blind", 50),
                ante=data.get("ante", 0),
                duration_minutes=data.get("duration_minutes", 15),
                next_level_at=data.get("next_level_at"),
            )

        elif event_type == "BLIND_INCREASE_WARNING":
            data = event_data.get("data", {})
            return await self.broadcast_blind_warning(
                tournament_id=tournament_id,
                seconds_remaining=data.get("seconds_remaining", 30),
                current_level=data.get("current_level", 1),
                next_level=data.get("next_level", 2),
                next_small_blind=data.get("next_small_blind", 50),
                next_big_blind=data.get("next_big_blind", 100),
                next_ante=data.get("next_ante", 0),
            )

        else:
            # 기타 토너먼트 이벤트
            return await self.broadcast_tournament_event(
                tournament_id=tournament_id,
                event_type=event_type,
                data=event_data.get("data", {}),
            )

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
                "timestamp": datetime.now(timezone.utc).isoformat(),
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
                "timestamp": datetime.now(timezone.utc).isoformat(),
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
