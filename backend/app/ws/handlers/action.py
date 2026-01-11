"""Action event handlers for game actions."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.engine.core import PokerKitWrapper
from app.engine.state import ActionType, ActionRequest
from app.engine.snapshot import SnapshotSerializer
from app.models.table import Table
from app.utils.redis_client import RedisService
from app.ws.connection import WebSocketConnection
from app.ws.events import EventType
from app.ws.handlers.base import BaseHandler
from app.ws.handlers.table import broadcast_turn_prompt
from app.ws.messages import MessageEnvelope

if TYPE_CHECKING:
    from app.ws.manager import ConnectionManager

logger = logging.getLogger(__name__)


class ActionHandler(BaseHandler):
    """Handles game action requests with idempotency.

    Events:
    - ACTION_REQUEST: Player action (fold, check, call, bet, raise, all-in)

    Also broadcasts:
    - ACTION_RESULT: Result of action
    - TABLE_STATE_UPDATE: State changes after action
    - TURN_PROMPT: Next player's turn
    - SHOWDOWN_RESULT: Showdown information
    - HAND_RESULT: Hand completion
    """

    def __init__(
        self,
        manager: "ConnectionManager",
        db: AsyncSession,
        redis: Redis,
    ):
        super().__init__(manager)
        self.db = db
        self.redis = redis
        self.redis_service = RedisService(redis)
        self.engine = PokerKitWrapper()
        self.serializer = SnapshotSerializer()

    @property
    def handled_events(self) -> tuple[EventType, ...]:
        return (EventType.ACTION_REQUEST,)

    async def handle(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope | None:
        if event.type == EventType.ACTION_REQUEST:
            return await self._handle_action(conn, event)
        return None

    async def _handle_action(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope:
        """Handle ACTION_REQUEST event."""
        payload = event.payload
        table_id = payload.get("tableId")
        action_type = payload.get("actionType")
        amount = payload.get("amount")
        request_id = event.request_id

        # 1. Idempotency check
        if request_id:
            is_new = await self.redis_service.check_and_set_idempotency(
                table_id=table_id,
                user_id=conn.user_id,
                request_id=request_id,
            )

            if not is_new:
                # Return cached result if available
                cached = await self.redis_service.get_idempotency_result(
                    table_id, conn.user_id, request_id
                )
                if cached:
                    cached_payload = json.loads(cached)
                    return MessageEnvelope.create(
                        event_type=EventType.ACTION_RESULT,
                        payload=cached_payload,
                        request_id=request_id,
                        trace_id=event.trace_id,
                    )

        try:
            # 2. Get current table state
            table = await self.db.get(Table, table_id)
            if not table:
                return self._create_error_result(
                    table_id, "TABLE_NOT_FOUND", "Table not found",
                    request_id, event.trace_id
                )

            if not table.game_state:
                return self._create_error_result(
                    table_id, "NO_ACTIVE_HAND", "No active hand in progress",
                    request_id, event.trace_id
                )

            # 3. Find player position
            player_position = await self._get_player_position(table_id, conn.user_id)
            if player_position is None:
                return self._create_error_result(
                    table_id, "NOT_A_PLAYER", "You are not seated at this table",
                    request_id, event.trace_id
                )

            # 4. Validate it's player's turn
            current_turn = table.game_state.get("current_turn")
            if current_turn != player_position:
                return self._create_error_result(
                    table_id, "NOT_YOUR_TURN", "It is not your turn",
                    request_id, event.trace_id
                )

            # 5. Apply action via engine
            action_request = ActionRequest(
                request_id=request_id or "",
                action_type=ActionType(action_type.lower()),
                amount=amount,
            )

            # Deserialize current state
            table_state = self.serializer.deserialize(table.game_state)

            new_state, executed_action = self.engine.apply_action(
                table_state=table_state,
                position=player_position,
                action=action_request,
            )

            # 6. Persist new state
            table.game_state = self.serializer.serialize(new_state)
            table.state_version = new_state.state_version
            table.updated_at = datetime.utcnow()
            await self.db.commit()

            # 7. Build and cache result
            result = {
                "success": True,
                "tableId": table_id,
                "action": {
                    "type": action_type,
                    "amount": executed_action.amount if hasattr(executed_action, 'amount') else amount,
                    "position": player_position,
                },
                "newStateVersion": new_state.state_version,
            }

            if request_id:
                await self.redis_service.set_idempotency_result(
                    table_id, conn.user_id, request_id, json.dumps(result)
                )

            # 8. Broadcast table state update
            await self._broadcast_state_update(table_id, new_state, executed_action)

            # 9. Handle hand completion if needed
            if new_state.hand and new_state.hand.phase.value == "showdown":
                await self._broadcast_showdown(table_id, new_state)

            if new_state.hand is None or new_state.hand.phase.value == "complete":
                await self._broadcast_hand_result(table_id, new_state)
            else:
                # 10. Send turn prompt to next player
                await self._send_turn_prompt(table_id, new_state)

            return MessageEnvelope.create(
                event_type=EventType.ACTION_RESULT,
                payload=result,
                request_id=request_id,
                trace_id=event.trace_id,
            )

        except ValueError as e:
            await self.db.rollback()
            error_code = "INVALID_ACTION"
            if "not your turn" in str(e).lower():
                error_code = "NOT_YOUR_TURN"
            elif "invalid" in str(e).lower():
                error_code = "INVALID_ACTION"

            return self._create_error_result(
                table_id, error_code, str(e),
                request_id, event.trace_id
            )

        except Exception as e:
            await self.db.rollback()
            logger.exception(f"Error processing action: {e}")
            return self._create_error_result(
                table_id, "INTERNAL_ERROR", "Failed to process action",
                request_id, event.trace_id
            )

    async def _get_player_position(
        self,
        table_id: str,
        user_id: str,
    ) -> int | None:
        """Get player's position at the table from seats JSONB."""
        table = await self.db.get(Table, table_id)
        if not table or not table.seats:
            return None

        for position_str, seat_data in table.seats.items():
            if seat_data and seat_data.get("user_id") == user_id:
                status = seat_data.get("status", "active")
                if status in ("active", "all_in"):
                    return int(position_str)

        return None

    def _create_error_result(
        self,
        table_id: str,
        error_code: str,
        error_message: str,
        request_id: str | None,
        trace_id: str,
    ) -> MessageEnvelope:
        """Create an error ACTION_RESULT message."""
        return MessageEnvelope.create(
            event_type=EventType.ACTION_RESULT,
            payload={
                "success": False,
                "tableId": table_id,
                "errorCode": error_code,
                "errorMessage": error_message,
            },
            request_id=request_id,
            trace_id=trace_id,
        )

    async def _broadcast_state_update(
        self,
        table_id: str,
        new_state: Any,
        action: Any,
    ) -> None:
        """Broadcast TABLE_STATE_UPDATE to table subscribers."""
        changes = {
            "phase": new_state.hand.phase.value if new_state.hand else None,
            "pot": {
                "mainPot": new_state.hand.pot.main if new_state.hand else 0,
                "sidePots": [],
            },
            "lastAction": {
                "type": action.action_type.value if hasattr(action, 'action_type') else str(action),
                "amount": action.amount if hasattr(action, 'amount') else 0,
                "position": action.position if hasattr(action, 'position') else 0,
            },
        }

        if new_state.hand and new_state.hand.community_cards:
            changes["communityCards"] = [str(c) for c in new_state.hand.community_cards]

        message = MessageEnvelope.create(
            event_type=EventType.TABLE_STATE_UPDATE,
            payload={
                "tableId": table_id,
                "changes": changes,
                "stateVersion": new_state.state_version,
            },
        )

        channel = f"table:{table_id}"
        await self.manager.broadcast_to_channel(channel, message.to_dict())

    async def _send_turn_prompt(
        self,
        table_id: str,
        state: Any,
    ) -> None:
        """Send TURN_PROMPT to table subscribers."""
        if not state.hand or state.hand.current_turn is None:
            return

        position = state.hand.current_turn
        valid_actions = self.engine.get_valid_actions(state, position)

        allowed = []
        for action in valid_actions:
            action_dict = {"type": action.action_type.value}
            if action.min_amount is not None:
                action_dict["minAmount"] = action.min_amount
            if action.max_amount is not None:
                action_dict["maxAmount"] = action.max_amount
            allowed.append(action_dict)

        # Calculate deadline
        turn_timeout = state.config.turn_timeout_seconds
        deadline = datetime.utcnow() + timedelta(seconds=turn_timeout)

        await broadcast_turn_prompt(
            manager=self.manager,
            table_id=table_id,
            position=position,
            allowed_actions=allowed,
            deadline_at=deadline.isoformat(),
            state_version=state.state_version,
        )

    async def _broadcast_showdown(
        self,
        table_id: str,
        state: Any,
    ) -> None:
        """Broadcast SHOWDOWN_RESULT."""
        if not state.hand:
            return

        showdown_hands = []
        for seat in state.seats:
            if seat.player and seat.status.value == "active":
                hand_state = state.hand.player_hands.get(seat.position)
                if hand_state and hand_state.hole_cards:
                    showdown_hands.append({
                        "position": seat.position,
                        "holeCards": [str(c) for c in hand_state.hole_cards],
                        "handRank": hand_state.hand_rank or "unknown",
                        "handDescription": hand_state.hand_description or "",
                    })

        message = MessageEnvelope.create(
            event_type=EventType.SHOWDOWN_RESULT,
            payload={
                "tableId": table_id,
                "handId": state.hand.hand_id,
                "showdownHands": showdown_hands,
                "stateVersion": state.state_version,
            },
        )

        channel = f"table:{table_id}"
        await self.manager.broadcast_to_channel(channel, message.to_dict())

    async def _broadcast_hand_result(
        self,
        table_id: str,
        state: Any,
    ) -> None:
        """Broadcast HAND_RESULT."""
        winners = []
        # Extract winners from state if available
        if hasattr(state, 'last_hand_winners') and state.last_hand_winners:
            for winner in state.last_hand_winners:
                winners.append({
                    "position": winner.position,
                    "amount": winner.amount,
                    "potType": winner.pot_type,
                })

        message = MessageEnvelope.create(
            event_type=EventType.HAND_RESULT,
            payload={
                "tableId": table_id,
                "winners": winners,
                "stateVersion": state.state_version,
            },
        )

        channel = f"table:{table_id}"
        await self.manager.broadcast_to_channel(channel, message.to_dict())
