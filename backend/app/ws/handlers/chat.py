"""Chat event handlers.

플레이어/관전자 채팅 구분 지원:
- public: 모든 사용자에게 표시
- players_only: 플레이어에게만 표시 (관전자 제외)
"""

from __future__ import annotations

import html
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.ws.connection import WebSocketConnection
from app.ws.events import EventType
from app.ws.handlers.base import BaseHandler
from app.ws.messages import MessageEnvelope

if TYPE_CHECKING:
    from app.ws.manager import ConnectionManager

logger = logging.getLogger(__name__)

# Chat history settings
CHAT_HISTORY_LIMIT = 50
CHAT_MESSAGE_TTL = 3600  # 1 hour


class ChatType(str, Enum):
    """채팅 타입."""
    
    PUBLIC = "public"           # 전체 채팅 (플레이어 + 관전자)
    PLAYERS_ONLY = "players_only"  # 플레이어 전용 채팅


class ChatHandler(BaseHandler):
    """Handles chat and emoticon events.

    Events:
    - CHAT_MESSAGE: Send/receive chat messages
    - EMOTICON_SEND: Send emoticon

    Also broadcasts:
    - CHAT_HISTORY: Historical messages on subscription
    - EMOTICON_RECEIVED: Emoticon received by table
    """

    def __init__(
        self,
        manager: "ConnectionManager",
        db: AsyncSession,
        redis: Redis | None = None,
    ):
        super().__init__(manager)
        self.db = db
        self.redis = redis

    @property
    def handled_events(self) -> tuple[EventType, ...]:
        return (EventType.CHAT_MESSAGE, EventType.EMOTICON_SEND)

    async def handle(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope | None:
        # 채팅 금지(mute) 상태 확인
        if event.type in (EventType.CHAT_MESSAGE, EventType.EMOTICON_SEND):
            is_muted = await self._is_user_muted(conn.user_id)
            if is_muted:
                return MessageEnvelope.create(
                    event_type=EventType.ERROR,
                    payload={
                        "code": "CHAT_MUTED",
                        "message": "채팅이 제한되어 있습니다.",
                    },
                )

        if event.type == EventType.CHAT_MESSAGE:
            return await self._handle_chat_message(conn, event)
        elif event.type == EventType.EMOTICON_SEND:
            return await self._handle_emoticon_send(conn, event)
        return None

    async def _is_user_muted(self, user_id: str | None) -> bool:
        """사용자가 채팅 금지(mute) 상태인지 확인.

        Redis에 mute 상태를 캐시하여 빠르게 확인합니다.

        보안 정책:
        - Redis 연결이 없는 경우 경고 로그를 남기고 채팅을 허용합니다.
        - 이는 서비스 가용성을 위한 결정이며, 운영 환경에서는
          Redis 연결 상태를 모니터링해야 합니다.
        """
        if not user_id:
            return False

        if not self.redis:
            # Redis 연결 없이는 mute 상태 확인 불가
            # 보안 경고: 제재 우회 가능성 있음
            logger.warning(
                f"Redis 연결 없음 - mute 상태 확인 불가: user={user_id[:8]}... "
                "제재된 사용자가 채팅할 수 있는 위험이 있습니다."
            )
            # fail-open: 서비스 가용성 우선 (운영 환경에서는 모니터링 필수)
            return False

        mute_key = f"user:mute:{user_id}"
        is_muted = await self.redis.exists(mute_key)
        if is_muted:
            logger.info(f"Mute된 사용자 채팅 시도 차단: user={user_id[:8]}...")
            return True

        return False

    async def _handle_emoticon_send(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope | None:
        """Handle EMOTICON_SEND event.
        
        Payload:
            - tableId: 테이블 ID
            - emoticonId: 이모티콘 ID
            - targetUserId: 타겟 사용자 ID (선택적)
        """
        from app.services.emoticon import EmoticonService

        payload = event.payload
        table_id = payload.get("tableId")
        emoticon_id = payload.get("emoticonId")
        target_user_id = payload.get("targetUserId")

        # 이모티콘 ID 검증
        if not emoticon_id or not EmoticonService.is_valid_emoticon_id(emoticon_id):
            return MessageEnvelope.create(
                event_type=EventType.ERROR,
                payload={
                    "code": "INVALID_EMOTICON",
                    "message": "유효하지 않은 이모티콘입니다.",
                },
            )

        emoticon = EmoticonService.get_emoticon_by_id(emoticon_id)
        if not emoticon:
            return None

        # 이모티콘 메시지 생성
        emoticon_message = {
            "messageId": str(uuid4()),
            "tableId": table_id,
            "userId": conn.user_id,
            "nickname": f"User-{conn.user_id[:8]}",
            "emoticonId": emoticon_id,
            "emoji": emoticon.emoji,
            "emoticonName": emoticon.name,
            "imageUrl": emoticon.image_url,
            "soundUrl": emoticon.sound_url,
            "targetUserId": target_user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 테이블에 브로드캐스트
        if table_id:
            channel = f"table:{table_id}"
            broadcast_message = MessageEnvelope.create(
                event_type=EventType.EMOTICON_RECEIVED,
                payload=emoticon_message,
            )
            await self.manager.broadcast_to_channel(channel, broadcast_message.to_dict())

            logger.debug(
                f"Emoticon sent: user={conn.user_id[:8]}... "
                f"emoticon={emoticon_id} table={table_id}"
            )

        return None

    async def _handle_chat_message(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope | None:
        """Handle CHAT_MESSAGE event.
        
        Payload:
            - tableId: 테이블 ID
            - message: 메시지 내용
            - chatType: 채팅 타입 (public/players_only, 기본값: public)
        """
        payload = event.payload
        table_id = payload.get("tableId")
        message_text = payload.get("message", "").strip()
        chat_type_str = payload.get("chatType", ChatType.PUBLIC.value)

        # Validate message
        if not message_text:
            return None

        # Validate chat type
        try:
            chat_type = ChatType(chat_type_str)
        except ValueError:
            chat_type = ChatType.PUBLIC

        # 플레이어 전용 채팅은 플레이어만 가능
        is_player = await self._is_player(conn.user_id, table_id)
        if chat_type == ChatType.PLAYERS_ONLY and not is_player:
            logger.warning(
                f"Non-player tried to send players_only chat: "
                f"user={conn.user_id[:8]}... table={table_id}"
            )
            return MessageEnvelope.create(
                event_type=EventType.ERROR,
                payload={
                    "code": "CHAT_NOT_ALLOWED",
                    "message": "플레이어 전용 채팅은 플레이어만 사용할 수 있습니다.",
                },
            )

        # XSS prevention: escape HTML entities
        message_text = html.escape(message_text)

        # Enforce length limit (after escaping)
        if len(message_text) > 500:
            message_text = message_text[:500]

        # Build chat message
        # Note: Ignore client-provided nickname to prevent impersonation
        # In production, fetch actual nickname from user profile
        chat_message = {
            "messageId": str(uuid4()),
            "tableId": table_id,
            "userId": conn.user_id,
            "nickname": f"User-{conn.user_id[:8]}",  # Server-generated nickname
            "message": message_text,
            "chatType": chat_type.value,
            "isPlayer": is_player,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Store in Redis if available
        if self.redis and table_id:
            await self._store_chat_message(table_id, chat_message)

        # Broadcast to table channel
        if table_id:
            await self._broadcast_chat_message(
                table_id=table_id,
                chat_message=chat_message,
                chat_type=chat_type,
            )

        # No direct response needed (message is broadcast)
        return None

    async def _is_player(self, user_id: str | None, table_id: str | None) -> bool:
        """사용자가 해당 테이블의 플레이어인지 확인.

        보안 정책 (fail-closed):
        - Redis에서 플레이어 목록을 확인할 수 없는 경우 False 반환
        - 관전자가 플레이어 전용 채팅에 접근하는 것을 방지
        """
        if not user_id or not table_id:
            return False

        if not self.redis:
            # Redis 연결 없이는 플레이어 확인 불가 - 보안상 False 반환
            logger.warning(
                f"Redis 연결 없음 - 플레이어 확인 불가: "
                f"user={user_id[:8]}... table={table_id} "
                "플레이어 전용 기능 접근이 거부됩니다."
            )
            return False

        # Redis에서 테이블 플레이어 목록 확인
        player_key = f"table:{table_id}:players"
        is_member = await self.redis.sismember(player_key, user_id)

        if not is_member:
            logger.debug(
                f"플레이어 아님: user={user_id[:8]}... table={table_id}"
            )

        return bool(is_member)

    async def _broadcast_chat_message(
        self,
        table_id: str,
        chat_message: dict[str, Any],
        chat_type: ChatType,
    ) -> None:
        """채팅 메시지 브로드캐스트.
        
        플레이어 전용 채팅은 플레이어에게만 전송.
        """
        broadcast_message = MessageEnvelope.create(
            event_type=EventType.CHAT_MESSAGE,
            payload=chat_message,
        )
        
        if chat_type == ChatType.PUBLIC:
            # 전체 채팅: 모든 구독자에게 전송
            channel = f"table:{table_id}"
            await self.manager.broadcast_to_channel(channel, broadcast_message.to_dict())
        else:
            # 플레이어 전용: 플레이어 채널에만 전송
            players_channel = f"table:{table_id}:players"
            await self.manager.broadcast_to_channel(
                players_channel, 
                broadcast_message.to_dict()
            )
            
            # 일반 채널에는 마스킹된 메시지 전송 (관전자용)
            masked_message = chat_message.copy()
            masked_message["message"] = "[플레이어 전용 채팅]"
            masked_message["masked"] = True
            masked_broadcast = MessageEnvelope.create(
                event_type=EventType.CHAT_MESSAGE,
                payload=masked_message,
            )
            spectator_channel = f"table:{table_id}:spectators"
            await self.manager.broadcast_to_channel(
                spectator_channel, 
                masked_broadcast.to_dict()
            )

    async def _store_chat_message(
        self,
        table_id: str,
        message: dict[str, Any],
    ) -> None:
        """Store chat message in Redis for history."""
        if not self.redis:
            return

        from app.utils.json_utils import json_dumps

        key = f"chat:history:{table_id}"

        # Add to list (newest first)
        await self.redis.lpush(key, json_dumps(message))

        # Trim to limit
        await self.redis.ltrim(key, 0, CHAT_HISTORY_LIMIT - 1)

        # Set TTL
        await self.redis.expire(key, CHAT_MESSAGE_TTL)

    async def get_chat_history(
        self,
        table_id: str,
        limit: int = CHAT_HISTORY_LIMIT,
    ) -> list[dict[str, Any]]:
        """Get chat history for a table."""
        if not self.redis:
            return []

        from app.utils.json_utils import json_loads

        key = f"chat:history:{table_id}"
        messages = await self.redis.lrange(key, 0, limit - 1)

        return [json_loads(m) for m in messages]


async def send_chat_history(
    manager: "ConnectionManager",
    conn: WebSocketConnection,
    chat_handler: ChatHandler,
    table_id: str,
) -> None:
    """Send chat history to a newly subscribed connection."""
    history = await chat_handler.get_chat_history(table_id)

    if history:
        message = MessageEnvelope.create(
            event_type=EventType.CHAT_HISTORY,
            payload={
                "tableId": table_id,
                "messages": history,
            },
        )
        await conn.send(message.to_dict())
