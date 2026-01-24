"""Game orchestration service.

Handles starting hands, dealing cards, and managing game flow.
"""

from __future__ import annotations

import asyncio
import logging
import random
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import attributes

from app.engine.core import PokerKitWrapper
from app.engine.state import (
    ActionType,
    ActionRequest,
    Player,
    SeatState,
    SeatStatus,
    TableConfig,
    TableState,
)
from app.models.table import Table, TableStatus
from app.ws.events import EventType
from app.ws.messages import MessageEnvelope

if TYPE_CHECKING:
    from app.ws.manager import ConnectionManager


logger = logging.getLogger(__name__)

# Track pending game starts to prevent duplicate starts
# Uses asyncio.Lock for thread-safe access
_pending_game_starts: set[str] = set()
_pending_lock = asyncio.Lock()


class GameStartAlreadyPendingError(Exception):
    """Raised when a game start is already pending for a table."""
    pass


@asynccontextmanager
async def pending_game_start(table_id: str) -> AsyncGenerator[None, None]:
    """Context manager for safely tracking pending game starts.
    
    Ensures the table_id is removed from pending set even if an error occurs.
    
    Args:
        table_id: The table ID to mark as pending
        
    Raises:
        GameStartAlreadyPendingError: If game start is already pending
        
    Example:
        async with pending_game_start(table_id):
            await start_the_game()
    """
    async with _pending_lock:
        if table_id in _pending_game_starts:
            raise GameStartAlreadyPendingError(f"Game start already pending for {table_id}")
        _pending_game_starts.add(table_id)
    
    try:
        yield
    finally:
        async with _pending_lock:
            _pending_game_starts.discard(table_id)


def is_game_start_pending(table_id: str) -> bool:
    """Check if a game start is pending for a table (without lock)."""
    return table_id in _pending_game_starts


class GameService:
    """Service for game orchestration.

    Responsibilities:
    - Start hands when enough players are seated
    - Deal cards to players
    - Manage dealer button rotation
    - Broadcast game state to clients
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.engine = PokerKitWrapper()

    async def try_start_hand(
        self,
        table: Table,
        manager: "ConnectionManager",
        countdown_seconds: int = 5,
    ) -> bool:
        """Try to start a new hand if conditions are met.

        Conditions:
        - At least 2 active players
        - No hand currently in progress
        - No pending game start for this table

        Args:
            table: Table model
            manager: WebSocket connection manager
            countdown_seconds: Seconds to wait before starting (default 5)

        Returns:
            True if hand start was initiated, False otherwise
        """
        table_id = str(table.id)

        # Check if game start already pending for this table
        if is_game_start_pending(table_id):
            logger.info(f"Game start already pending for table {table_id}")
            return False

        # Count active players
        active_players = []
        seats = table.seats or {}

        for pos_str, seat_data in seats.items():
            if seat_data and seat_data.get("status") == "active":
                active_players.append({
                    "position": int(pos_str),
                    "user_id": seat_data.get("user_id"),
                    "nickname": seat_data.get("nickname"),
                    "stack": seat_data.get("stack", 0),
                    "is_bot": seat_data.get("is_bot", False),
                })

        logger.info(f"try_start_hand: {len(active_players)} active players, table status={table.status}")

        if len(active_players) < 2:
            logger.info(f"Not enough players to start hand: {len(active_players)}")
            return False

        # Check if hand already in progress
        if table.status == TableStatus.PLAYING.value:
            logger.info("Hand already in progress")
            return False

        # Mark as pending using safe async context
        try:
            async with _pending_lock:
                _pending_game_starts.add(table_id)
        except Exception as e:
            logger.error(f"Failed to mark game start as pending: {e}")
            return False

        # Broadcast GAME_STARTING event with countdown
        await self._broadcast_game_starting(
            table=table,
            manager=manager,
            countdown_seconds=countdown_seconds,
        )

        # Schedule actual hand start after countdown
        asyncio.create_task(
            self._delayed_start_hand(
                table_id=table_id,
                room_id=str(table.room_id),
                manager=manager,
                countdown_seconds=countdown_seconds,
            )
        )

        return True

    async def _delayed_start_hand(
        self,
        table_id: str,
        room_id: str,
        manager: "ConnectionManager",
        countdown_seconds: int,
    ) -> None:
        """Actually start the hand after countdown delay."""
        try:
            # Wait for countdown
            await asyncio.sleep(countdown_seconds)

            # Get fresh table data from DB
            from sqlalchemy import select
            from sqlalchemy.orm import joinedload
            result = await self.db.execute(
                select(Table)
                .options(joinedload(Table.room))
                .where(Table.id == table_id)
            )
            table = result.scalar_one_or_none()

            if not table:
                logger.error(f"Table {table_id} not found for delayed start")
                return

            # Re-check conditions
            active_players = []
            seats = table.seats or {}

            for pos_str, seat_data in seats.items():
                if seat_data and seat_data.get("status") == "active":
                    active_players.append({
                        "position": int(pos_str),
                        "user_id": seat_data.get("user_id"),
                        "nickname": seat_data.get("nickname"),
                        "stack": seat_data.get("stack", 0),
                        "is_bot": seat_data.get("is_bot", False),
                    })

            if len(active_players) < 2:
                logger.info(f"Not enough players after countdown: {len(active_players)}")
                return

            if table.status == TableStatus.PLAYING.value:
                logger.info("Hand already in progress after countdown")
                return

            # Build TableState from DB model
            table_state = self._build_table_state(table, active_players)

            # Create new hand using engine
            new_state = self.engine.create_initial_hand(table_state)

            if new_state.hand is None:
                logger.error("Failed to create hand state")
                return

            # Update table in DB
            table.status = TableStatus.PLAYING.value
            table.hand_number = new_state.hand.hand_number
            table.state_version = new_state.state_version

            # Store game state as JSONB (use SnapshotSerializer for consistent format)
            from app.engine.snapshot import SnapshotSerializer
            serializer = SnapshotSerializer()
            game_state_dict = serializer.serialize(new_state)
            # Store pk_snapshot separately for state reconstruction
            if new_state._pk_snapshot:
                game_state_dict["pkSnapshotB64"] = new_state._pk_snapshot.hex()
            table.game_state = game_state_dict
            attributes.flag_modified(table, "game_state")

            await self.db.commit()

            logger.info(
                f"Hand #{new_state.hand.hand_number} started at table {table.id}"
            )

            # Broadcast HAND_START to all players
            await self._broadcast_hand_start(
                table=table,
                table_state=new_state,
                manager=manager,
            )

            # Send TURN_PROMPT to current player
            if new_state.hand.current_turn is not None:
                await self._send_turn_prompt(
                    table=table,
                    table_state=new_state,
                    manager=manager,
                )

        except Exception as e:
            logger.error(f"Failed to start hand after countdown: {e}", exc_info=True)
        finally:
            # Remove from pending set (with lock for thread-safety)
            try:
                async with _pending_lock:
                    _pending_game_starts.discard(table_id)
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup pending state for {table_id}: {cleanup_error}")

    async def _broadcast_game_starting(
        self,
        table: Table,
        manager: "ConnectionManager",
        countdown_seconds: int,
    ) -> None:
        """Broadcast GAME_STARTING event with countdown."""
        channel = f"table:{table.room_id}"

        message = MessageEnvelope.create(
            event_type=EventType.GAME_STARTING,
            payload={
                "tableId": str(table.id),
                "countdownSeconds": countdown_seconds,
                "message": "게임이 곧 시작됩니다!",
            },
        )

        await manager.broadcast_to_channel(channel, message.to_dict())
        logger.info(f"GAME_STARTING broadcast to {channel} with {countdown_seconds}s countdown")

    def _build_table_state(
        self,
        table: Table,
        active_players: list[dict],
    ) -> TableState:
        """Build immutable TableState from DB model."""
        # Get room config
        room = table.room
        config_data = room.config if room else {}

        config = TableConfig(
            max_seats=config_data.get("max_seats", 6),
            small_blind=config_data.get("small_blind", 10),
            big_blind=config_data.get("big_blind", 20),
            min_buy_in=config_data.get("buy_in_min", 400),
            max_buy_in=config_data.get("buy_in_max", 2000),
            turn_timeout_seconds=config_data.get("turn_timeout", 30),
            ante=config_data.get("ante", 0),
        )

        # Build seats
        seats = []
        for player in active_players:
            seats.append(
                SeatState(
                    position=player["position"],
                    player=Player(
                        user_id=player["user_id"],
                        nickname=player["nickname"],
                    ),
                    stack=player["stack"],
                    status=SeatStatus.ACTIVE,
                )
            )

        # Sort by position
        seats.sort(key=lambda s: s.position)

        return TableState(
            table_id=str(table.id),
            config=config,
            seats=tuple(seats),
            hand=None,
            dealer_position=table.dealer_position or 0,
            state_version=table.state_version or 0,
            updated_at=datetime.now(timezone.utc),
        )

    def _serialize_hand_state(self, table_state: TableState) -> dict[str, Any]:
        """Serialize hand state to JSON-compatible dict for DB storage."""
        hand = table_state.hand
        if hand is None:
            return {}

        # Serialize player states with hole cards
        player_states = []
        for ps in hand.player_states:
            hole_cards = None
            if ps.hole_cards:
                hole_cards = [str(c) for c in ps.hole_cards]

            player_states.append({
                "position": ps.position,
                "hole_cards": hole_cards,
                "bet_amount": ps.bet_amount,
                "total_bet": ps.total_bet,
                "status": ps.status.value,
            })

        community_cards = [str(c) for c in hand.community_cards]

        return {
            "hand_id": hand.hand_id,
            "hand_number": hand.hand_number,
            "phase": hand.phase.value,
            "community_cards": community_cards,
            "pot": {
                "main_pot": hand.pot.main_pot,
                "total": hand.pot.total,
            },
            "player_states": player_states,
            "current_turn": hand.current_turn,
            "min_raise": hand.min_raise,
            "started_at": hand.started_at.isoformat(),
            # Store pk_snapshot as base64 for persistence
            "pk_snapshot_b64": (
                table_state._pk_snapshot.hex()
                if table_state._pk_snapshot
                else None
            ),
        }

    async def _broadcast_hand_start(
        self,
        table: Table,
        table_state: TableState,
        manager: "ConnectionManager",
    ) -> None:
        """Broadcast HAND_START event to all table subscribers.

        Each player receives their own hole cards.
        Spectators see no hole cards.
        """
        hand = table_state.hand
        if hand is None:
            return

        # Use room_id for channel since clients subscribe with room_id
        channel = f"table:{table.room_id}"
        logger.info(f"Broadcasting HAND_START to channel: {channel}")

        # Get all connections in this channel
        # We need to send personalized messages per player
        connections = manager.get_channel_connections(channel)

        for conn in connections:
            # Find if this user is a player
            player_state = None
            for ps in hand.player_states:
                seat = table_state.get_seat(ps.position)
                if seat and seat.player and seat.player.user_id == conn.user_id:
                    player_state = ps
                    break

            # Build payload
            payload = self._build_hand_start_payload(
                table=table,
                table_state=table_state,
                player_state=player_state,
            )

            message = MessageEnvelope.create(
                event_type=EventType.HAND_START,
                payload=payload,
            )

            await manager.send_to_connection(conn.connection_id, message.to_dict())

    def _build_hand_start_payload(
        self,
        table: Table,
        table_state: TableState,
        player_state: Any,
    ) -> dict[str, Any]:
        """Build HAND_START payload for a specific viewer."""
        hand = table_state.hand
        if hand is None:
            return {}

        # Build seats with public info only
        seats = []
        for ps in hand.player_states:
            seat = table_state.get_seat(ps.position)
            if seat and seat.player:
                seats.append({
                    "position": ps.position,
                    "userId": seat.player.user_id,
                    "nickname": seat.player.nickname,
                    "stack": seat.stack,
                    "status": ps.status.value,
                    "betAmount": ps.bet_amount,
                })

        # My hole cards (only if player)
        my_hole_cards = None
        my_position = None
        if player_state and player_state.hole_cards:
            my_hole_cards = [
                {"rank": c.rank.symbol, "suit": c.suit.symbol}
                for c in player_state.hole_cards
            ]
            my_position = player_state.position

        return {
            "tableId": str(table.id),
            "handId": hand.hand_id,
            "handNumber": hand.hand_number,
            "phase": hand.phase.value,
            "dealerPosition": table_state.dealer_position,
            "seats": seats,
            "pot": hand.pot.total,
            "communityCards": [],  # Empty at start
            "myPosition": my_position,
            "myHoleCards": my_hole_cards,
            "currentTurn": hand.current_turn,
            "stateVersion": table_state.state_version,
        }

    async def _send_turn_prompt(
        self,
        table: Table,
        table_state: TableState,
        manager: "ConnectionManager",
    ) -> None:
        """Send TURN_PROMPT to the current player.

        If the current player is a bot, automatically execute a bot action.
        """
        hand = table_state.hand
        if hand is None or hand.current_turn is None:
            return

        position = hand.current_turn

        # Get valid actions for current player
        valid_actions = self.engine.get_valid_actions(table_state, position)

        # Convert to payload format
        allowed_actions = []
        for va in valid_actions:
            action = {"type": va.action_type.value}
            if va.min_amount is not None:
                action["minAmount"] = va.min_amount
            if va.max_amount is not None:
                action["maxAmount"] = va.max_amount
            allowed_actions.append(action)

        # Calculate deadline
        config = table_state.config
        from datetime import timedelta
        deadline = datetime.now(timezone.utc) + timedelta(seconds=config.turn_timeout_seconds)

        message = MessageEnvelope.create(
            event_type=EventType.TURN_PROMPT,
            payload={
                "tableId": str(table.id),
                "position": position,
                "allowedActions": allowed_actions,
                "turnDeadlineAt": deadline.isoformat(),
                "stateVersion": table_state.state_version,
            },
        )

        # Broadcast to all subscribers (everyone needs to know whose turn it is)
        # Use room_id for channel since clients subscribe with room_id
        channel = f"table:{table.room_id}"
        await manager.broadcast_to_channel(channel, message.to_dict())

        # Check if current player is a bot
        seats = table.seats or {}
        seat_data = seats.get(str(position))
        if seat_data and seat_data.get("is_bot"):
            logger.info(f"Bot at position {position} needs to act")
            # Schedule bot action with a small delay
            asyncio.create_task(
                self._execute_bot_action(
                    table_id=str(table.id),
                    position=position,
                    valid_actions=valid_actions,
                    manager=manager,
                )
            )

    async def _execute_bot_action(
        self,
        table_id: str,
        position: int,
        valid_actions: list,
        manager: "ConnectionManager",
    ) -> None:
        """Execute a bot action with thinking delay."""
        # Add thinking delay (1-3 seconds)
        delay = random.uniform(1.0, 3.0)
        await asyncio.sleep(delay)

        try:
            # Get fresh table data
            from sqlalchemy import select
            from sqlalchemy.orm import joinedload
            result = await self.db.execute(
                select(Table)
                .options(joinedload(Table.room))
                .where(Table.id == table_id)
            )
            table = result.scalar_one_or_none()

            if not table:
                logger.error(f"Table {table_id} not found for bot action")
                return

            if not table.game_state:
                logger.error(f"No game state for bot action")
                return

            # Deserialize current state
            from app.engine.snapshot import SnapshotSerializer
            serializer = SnapshotSerializer()
            table_state = serializer.deserialize(table.game_state)

            # Restore _pk_snapshot from stored hex string
            pk_snapshot_hex = table.game_state.get("pkSnapshotB64")
            if pk_snapshot_hex:
                table_state = TableState(
                    table_id=table_state.table_id,
                    config=table_state.config,
                    seats=table_state.seats,
                    hand=table_state.hand,
                    dealer_position=table_state.dealer_position,
                    state_version=table_state.state_version,
                    updated_at=table_state.updated_at,
                    _pk_snapshot=bytes.fromhex(pk_snapshot_hex),
                )
            else:
                logger.error(f"No pkSnapshotB64 in game_state for bot action")
                return

            # Verify it's still the bot's turn (use hand.current_turn from deserialized state)
            if table_state.hand is None:
                logger.error(f"No active hand for bot action")
                return

            current_turn = table_state.hand.current_turn
            if current_turn != position:
                logger.info(f"No longer bot's turn (was {position}, now {current_turn})")
                return

            # Decide bot action (simple strategy: check/call if possible, otherwise fold)
            chosen_action = self._decide_bot_action(valid_actions)
            logger.info(f"Bot at position {position} chose action: {chosen_action.action_type.value}")

            # Apply action
            new_state, executed_action = self.engine.apply_action(
                table_state=table_state,
                position=position,
                action=chosen_action,
            )

            # Persist new state (include pkSnapshotB64 for future actions)
            game_state_dict = serializer.serialize(new_state)
            if new_state._pk_snapshot:
                game_state_dict["pkSnapshotB64"] = new_state._pk_snapshot.hex()
            table.game_state = game_state_dict
            table.state_version = new_state.state_version
            table.updated_at = datetime.now(timezone.utc)
            attributes.flag_modified(table, "game_state")
            await self.db.commit()

            # Broadcast state update
            await self._broadcast_action_result(
                table_id=table_id,
                table=table,
                new_state=new_state,
                executed_action=executed_action,
                manager=manager,
            )

            # Check if hand is complete or send next turn prompt
            if new_state.hand and new_state.hand.phase.value == "showdown":
                await self._broadcast_showdown(table_id, new_state, manager)

            if new_state.hand is None or new_state.hand.phase.value == "complete":
                await self._broadcast_hand_result(table_id, new_state, manager)
            else:
                # Send turn prompt to next player
                if new_state.hand.current_turn is not None:
                    await self._send_turn_prompt(
                        table=table,
                        table_state=new_state,
                        manager=manager,
                    )

        except Exception as e:
            logger.error(f"Bot action failed: {e}", exc_info=True)

    def _decide_bot_action(self, valid_actions: list) -> ActionRequest:
        """Simple bot decision logic.

        Strategy:
        - If can check, check
        - If can call and call amount is reasonable, call
        - Otherwise fold
        - Occasionally raise (20% chance)
        """
        action_types = {va.action_type for va in valid_actions}

        # 20% chance to raise if possible
        if random.random() < 0.2:
            for va in valid_actions:
                if va.action_type == ActionType.RAISE:
                    # Raise minimum
                    return ActionRequest(
                        request_id="bot",
                        action_type=ActionType.RAISE,
                        amount=va.min_amount,
                    )
                if va.action_type == ActionType.BET:
                    return ActionRequest(
                        request_id="bot",
                        action_type=ActionType.BET,
                        amount=va.min_amount,
                    )

        # Check if possible
        if ActionType.CHECK in action_types:
            return ActionRequest(
                request_id="bot",
                action_type=ActionType.CHECK,
            )

        # Call if possible
        if ActionType.CALL in action_types:
            return ActionRequest(
                request_id="bot",
                action_type=ActionType.CALL,
            )

        # Fold as last resort
        return ActionRequest(
            request_id="bot",
            action_type=ActionType.FOLD,
        )

    async def _broadcast_action_result(
        self,
        table_id: str,
        table: Table,
        new_state: TableState,
        executed_action: Any,
        manager: "ConnectionManager",
    ) -> None:
        """Broadcast action result and state update."""
        # Broadcast TABLE_STATE_UPDATE
        changes = {
            "phase": new_state.hand.phase.value if new_state.hand else None,
            "pot": {
                "mainPot": new_state.hand.pot.main_pot if new_state.hand else 0,
                "sidePots": [],
            },
            "lastAction": {
                "type": executed_action.action_type.value if hasattr(executed_action, 'action_type') else str(executed_action),
                "amount": executed_action.amount if hasattr(executed_action, 'amount') else 0,
                "position": executed_action.position if hasattr(executed_action, 'position') else 0,
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

        channel = f"table:{table.room_id}"
        await manager.broadcast_to_channel(channel, message.to_dict())

    async def _broadcast_showdown(
        self,
        table_id: str,
        state: TableState,
        manager: "ConnectionManager",
    ) -> None:
        """Broadcast SHOWDOWN_RESULT."""
        if not state.hand:
            return

        # Get table for room_id
        table = await self.db.get(Table, table_id)
        if not table:
            return

        showdown_hands = []
        for seat in state.seats:
            if seat.player and seat.status.value == "active":
                hand_state = state.hand.player_hands.get(seat.position) if hasattr(state.hand, 'player_hands') else None
                if hand_state and hasattr(hand_state, 'hole_cards') and hand_state.hole_cards:
                    showdown_hands.append({
                        "position": seat.position,
                        "holeCards": [str(c) for c in hand_state.hole_cards],
                        "handRank": getattr(hand_state, 'hand_rank', "unknown"),
                        "handDescription": getattr(hand_state, 'hand_description', ""),
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

        channel = f"table:{table.room_id}"
        await manager.broadcast_to_channel(channel, message.to_dict())

    async def _broadcast_hand_result(
        self,
        table_id: str,
        state: TableState,
        manager: "ConnectionManager",
    ) -> None:
        """Broadcast HAND_RESULT."""
        # Get table for room_id
        table = await self.db.get(Table, table_id)
        if not table:
            return

        winners = []
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

        channel = f"table:{table.room_id}"
        await manager.broadcast_to_channel(channel, message.to_dict())
