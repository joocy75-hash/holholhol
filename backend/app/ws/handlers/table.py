"""Table event handlers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.room import Room
from app.models.table import Table
from app.engine.snapshot import SnapshotSerializer
from app.services.room import RoomService, RoomError
from app.ws.connection import WebSocketConnection
from app.ws.events import EventType
from app.ws.handlers.base import BaseHandler
from app.ws.messages import MessageEnvelope

if TYPE_CHECKING:
    from app.ws.manager import ConnectionManager

logger = logging.getLogger(__name__)


class TableHandler(BaseHandler):
    """Handles table subscription and seat management.

    Events:
    - SUBSCRIBE_TABLE: Subscribe to table updates
    - UNSUBSCRIBE_TABLE: Unsubscribe from table
    - SEAT_REQUEST: Request to take a seat
    - LEAVE_REQUEST: Leave the table
    """

    def __init__(self, manager: "ConnectionManager", db: AsyncSession):
        super().__init__(manager)
        self.db = db
        self.room_service = RoomService(db)
        self.serializer = SnapshotSerializer()

    @property
    def handled_events(self) -> tuple[EventType, ...]:
        return (
            EventType.SUBSCRIBE_TABLE,
            EventType.UNSUBSCRIBE_TABLE,
            EventType.SEAT_REQUEST,
            EventType.LEAVE_REQUEST,
        )

    async def handle(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope | None:
        match event.type:
            case EventType.SUBSCRIBE_TABLE:
                return await self._handle_subscribe(conn, event)
            case EventType.UNSUBSCRIBE_TABLE:
                return await self._handle_unsubscribe(conn, event)
            case EventType.SEAT_REQUEST:
                return await self._handle_seat(conn, event)
            case EventType.LEAVE_REQUEST:
                return await self._handle_leave(conn, event)
        return None

    async def _handle_subscribe(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope:
        """Handle SUBSCRIBE_TABLE event."""
        table_id = event.payload.get("tableId")
        mode = event.payload.get("mode", "spectator")

        # Subscribe to table channel
        channel = f"table:{table_id}"
        await self.manager.subscribe(conn.connection_id, channel)

        # Build and return table snapshot
        snapshot = await self._build_table_snapshot(table_id, conn.user_id, mode)

        return MessageEnvelope.create(
            event_type=EventType.TABLE_SNAPSHOT,
            payload=snapshot,
            request_id=event.request_id,
            trace_id=event.trace_id,
        )

    async def _handle_unsubscribe(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope | None:
        """Handle UNSUBSCRIBE_TABLE event."""
        table_id = event.payload.get("tableId")
        channel = f"table:{table_id}"
        await self.manager.unsubscribe(conn.connection_id, channel)
        return None  # No response needed

    async def _handle_seat(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope:
        """Handle SEAT_REQUEST event."""
        payload = event.payload
        table_id = payload.get("tableId")
        position = payload.get("position")
        buy_in = payload.get("buyIn")

        try:
            # Get table and room
            table = await self.db.get(Table, table_id)
            if not table:
                raise RoomError("TABLE_NOT_FOUND", "Table not found")

            result = await self.room_service.join_room(
                room_id=table.room_id,
                user_id=conn.user_id,
                buy_in=buy_in,
                position=position,
            )
            await self.db.commit()

            # Extract position and stack from result
            result_position = result.get("position") if isinstance(result, dict) else position
            result_stack = result.get("stack") if isinstance(result, dict) else buy_in

            # Broadcast table update
            await self._broadcast_table_update(
                table_id,
                "seat_taken",
                {
                    "position": result_position,
                    "userId": conn.user_id,
                    "stack": result_stack,
                },
            )

            return MessageEnvelope.create(
                event_type=EventType.SEAT_RESULT,
                payload={
                    "success": True,
                    "tableId": table_id,
                    "position": result_position,
                    "stack": result_stack,
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

        except RoomError as e:
            return MessageEnvelope.create(
                event_type=EventType.SEAT_RESULT,
                payload={
                    "success": False,
                    "errorCode": e.code,
                    "errorMessage": e.message,
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

    async def _handle_leave(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope:
        """Handle LEAVE_REQUEST event."""
        table_id = event.payload.get("tableId")

        try:
            # Get table
            table = await self.db.get(Table, table_id)
            if not table:
                raise RoomError("TABLE_NOT_FOUND", "Table not found")

            await self.room_service.leave_room(
                room_id=table.room_id,
                user_id=conn.user_id,
            )
            await self.db.commit()

            # Unsubscribe from table channel
            channel = f"table:{table_id}"
            await self.manager.unsubscribe(conn.connection_id, channel)

            # Broadcast table update
            await self._broadcast_table_update(
                table_id,
                "player_left",
                {"userId": conn.user_id},
            )

            return MessageEnvelope.create(
                event_type=EventType.LEAVE_RESULT,
                payload={
                    "success": True,
                    "tableId": table_id,
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

        except RoomError as e:
            return MessageEnvelope.create(
                event_type=EventType.LEAVE_RESULT,
                payload={
                    "success": False,
                    "errorCode": e.code,
                    "errorMessage": e.message,
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

    async def _build_table_snapshot(
        self,
        table_id: str,
        user_id: str,
        mode: str,
    ) -> dict[str, Any]:
        """Build TABLE_SNAPSHOT payload."""
        # Get table
        table = await self.db.get(Table, table_id)

        if not table:
            return {
                "tableId": table_id,
                "error": "TABLE_NOT_FOUND",
            }

        # Get room config
        room = await self.db.get(Room, table.room_id)
        config = room.config if room else {}
        max_seats = config.get("max_seats", 6)

        # Find user's position if they are a player
        my_position = None
        my_hole_cards = None

        # Build seats from table.seats JSONB
        seats = []
        for i in range(max_seats):
            seat_data = table.seats.get(str(i)) if table.seats else None

            if seat_data:
                # Check if this is the current user
                if seat_data.get("user_id") == user_id:
                    my_position = i
                    my_hole_cards = seat_data.get("hole_cards")

                seats.append({
                    "position": i,
                    "player": {
                        "userId": seat_data.get("user_id"),
                        "nickname": seat_data.get("nickname") or f"Player{i+1}",
                        "avatarUrl": seat_data.get("avatar_url"),
                    },
                    "stack": seat_data.get("stack", 0),
                    "status": seat_data.get("status", "active"),
                    "betAmount": seat_data.get("current_bet", 0),
                })
            else:
                seats.append({
                    "position": i,
                    "player": None,
                    "stack": 0,
                    "status": "empty",
                    "betAmount": 0,
                })

        # Build snapshot
        snapshot = {
            "tableId": table_id,
            "config": {
                "maxSeats": max_seats,
                "smallBlind": config.get("small_blind", 10),
                "bigBlind": config.get("big_blind", 20),
                "minBuyIn": config.get("buy_in_min", 400),
                "maxBuyIn": config.get("buy_in_max", 2000),
                "turnTimeoutSeconds": config.get("turn_timeout", 30),
            },
            "seats": seats,
            "hand": None,  # Will be populated from hand state if active
            "dealerPosition": table.dealer_position or 0,
            "myPosition": my_position,
            "myHoleCards": my_hole_cards if mode == "player" else None,
            "stateVersion": table.state_version or 1,
            "updatedAt": table.updated_at.isoformat() if table.updated_at else None,
        }

        return snapshot

    async def _broadcast_table_update(
        self,
        table_id: str,
        update_type: str,
        changes: dict[str, Any],
    ) -> None:
        """Broadcast table update to all subscribers."""
        # Get current state version
        table = await self.db.get(Table, table_id)
        state_version = (table.state_version or 0) + 1 if table else 1

        # Update table state version
        if table:
            table.state_version = state_version
            await self.db.commit()

        message = MessageEnvelope.create(
            event_type=EventType.TABLE_STATE_UPDATE,
            payload={
                "tableId": table_id,
                "updateType": update_type,
                "changes": changes,
                "stateVersion": state_version,
            },
        )

        channel = f"table:{table_id}"
        await self.manager.broadcast_to_channel(channel, message.to_dict())


async def broadcast_turn_prompt(
    manager: "ConnectionManager",
    table_id: str,
    position: int,
    allowed_actions: list[dict[str, Any]],
    deadline_at: str,
    state_version: int,
) -> None:
    """Send TURN_PROMPT to all table subscribers."""
    message = MessageEnvelope.create(
        event_type=EventType.TURN_PROMPT,
        payload={
            "tableId": table_id,
            "position": position,
            "allowedActions": allowed_actions,
            "turnDeadlineAt": deadline_at,
            "stateVersion": state_version,
        },
    )

    channel = f"table:{table_id}"
    await manager.broadcast_to_channel(channel, message.to_dict())
