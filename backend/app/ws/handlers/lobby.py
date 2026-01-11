"""Lobby event handlers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.room import Room, RoomStatus
from app.services.room import RoomService, RoomError
from app.ws.connection import WebSocketConnection
from app.ws.events import EventType
from app.ws.handlers.base import BaseHandler
from app.ws.messages import MessageEnvelope, create_error_message

if TYPE_CHECKING:
    from app.ws.manager import ConnectionManager

logger = logging.getLogger(__name__)

LOBBY_CHANNEL = "lobby"


class LobbyHandler(BaseHandler):
    """Handles lobby subscription and room operations.

    Events:
    - SUBSCRIBE_LOBBY: Subscribe to lobby updates
    - UNSUBSCRIBE_LOBBY: Unsubscribe from lobby
    - ROOM_CREATE_REQUEST: Create a new room
    - ROOM_JOIN_REQUEST: Join an existing room
    """

    def __init__(self, manager: "ConnectionManager", db: AsyncSession):
        super().__init__(manager)
        self.db = db
        self.room_service = RoomService(db)

    @property
    def handled_events(self) -> tuple[EventType, ...]:
        return (
            EventType.SUBSCRIBE_LOBBY,
            EventType.UNSUBSCRIBE_LOBBY,
            EventType.ROOM_CREATE_REQUEST,
            EventType.ROOM_JOIN_REQUEST,
        )

    async def handle(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope | None:
        match event.type:
            case EventType.SUBSCRIBE_LOBBY:
                return await self._handle_subscribe(conn, event)
            case EventType.UNSUBSCRIBE_LOBBY:
                return await self._handle_unsubscribe(conn, event)
            case EventType.ROOM_CREATE_REQUEST:
                return await self._handle_create_room(conn, event)
            case EventType.ROOM_JOIN_REQUEST:
                return await self._handle_join_room(conn, event)
        return None

    async def _handle_subscribe(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope:
        """Handle SUBSCRIBE_LOBBY event."""
        # Subscribe to lobby channel
        await self.manager.subscribe(conn.connection_id, LOBBY_CHANNEL)

        # Build and return lobby snapshot
        snapshot = await self._build_lobby_snapshot()

        return MessageEnvelope.create(
            event_type=EventType.LOBBY_SNAPSHOT,
            payload=snapshot,
            request_id=event.request_id,
            trace_id=event.trace_id,
        )

    async def _handle_unsubscribe(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope | None:
        """Handle UNSUBSCRIBE_LOBBY event."""
        await self.manager.unsubscribe(conn.connection_id, LOBBY_CHANNEL)
        return None  # No response needed

    async def _handle_create_room(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope:
        """Handle ROOM_CREATE_REQUEST event."""
        payload = event.payload

        try:
            room = await self.room_service.create_room(
                owner_id=conn.user_id,
                name=payload.get("name", "New Room"),
                description=payload.get("description"),
                max_seats=payload.get("maxSeats", 6),
                small_blind=payload.get("smallBlind", 10),
                big_blind=payload.get("bigBlind", 20),
                buy_in_min=payload.get("buyInMin", 400),
                buy_in_max=payload.get("buyInMax", 2000),
                turn_timeout=payload.get("turnTimeout", 30),
                is_private=payload.get("isPrivate", False),
                password=payload.get("password"),
            )
            await self.db.commit()

            # Broadcast lobby update
            await self._broadcast_lobby_update("room_created", room)

            return MessageEnvelope.create(
                event_type=EventType.ROOM_CREATE_RESULT,
                payload={
                    "success": True,
                    "roomId": room.id,
                    "name": room.name,
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

        except RoomError as e:
            return MessageEnvelope.create(
                event_type=EventType.ROOM_CREATE_RESULT,
                payload={
                    "success": False,
                    "errorCode": e.code,
                    "errorMessage": e.message,
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

    async def _handle_join_room(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope:
        """Handle ROOM_JOIN_REQUEST event."""
        payload = event.payload
        room_id = payload.get("roomId")
        password = payload.get("password")
        buy_in = payload.get("buyIn")

        try:
            player = await self.room_service.join_room(
                room_id=room_id,
                user_id=conn.user_id,
                buy_in=buy_in,
                password=password,
            )
            await self.db.commit()

            # Broadcast lobby update
            room = await self.db.get(Room, room_id)
            if room:
                await self._broadcast_lobby_update("player_joined", room)

            return MessageEnvelope.create(
                event_type=EventType.ROOM_JOIN_RESULT,
                payload={
                    "success": True,
                    "roomId": room_id,
                    "tableId": player.table_id,
                    "position": player.position,
                    "stack": player.stack,
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

        except RoomError as e:
            return MessageEnvelope.create(
                event_type=EventType.ROOM_JOIN_RESULT,
                payload={
                    "success": False,
                    "errorCode": e.code,
                    "errorMessage": e.message,
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

    async def _build_lobby_snapshot(self) -> dict[str, Any]:
        """Build LOBBY_SNAPSHOT payload."""
        # Query active rooms
        stmt = (
            select(Room)
            .where(Room.status.in_([RoomStatus.WAITING.value, RoomStatus.PLAYING.value]))
            .order_by(Room.created_at.desc())
            .limit(100)
        )
        result = await self.db.execute(stmt)
        rooms = result.scalars().all()

        return {
            "rooms": [self._serialize_room(r) for r in rooms],
            "announcements": [],
            "stateVersion": 1,
        }

    def _serialize_room(self, room: Room) -> dict[str, Any]:
        """Serialize room for lobby display."""
        config = room.config or {}
        return {
            "roomId": room.id,
            "name": room.name,
            "blinds": f"{config.get('small_blind', 10)}/{config.get('big_blind', 20)}",
            "maxSeats": config.get("max_seats", 6),
            "playerCount": room.current_players,
            "status": room.status,
            "isPrivate": config.get("is_private", False),
        }

    async def _broadcast_lobby_update(
        self,
        update_type: str,
        room: Room,
    ) -> None:
        """Broadcast lobby update to all subscribers."""
        message = MessageEnvelope.create(
            event_type=EventType.LOBBY_UPDATE,
            payload={
                "updateType": update_type,
                "room": self._serialize_room(room),
            },
        )
        await self.manager.broadcast_to_channel(LOBBY_CHANNEL, message.to_dict())
