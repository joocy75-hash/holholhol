"""Table event handlers.

Uses GameManager for in-memory game state (poker project style).
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload, attributes

from app.game import game_manager, Player
from app.models.room import Room
from app.models.table import Table
from app.services.room import RoomService, RoomError
from app.services.player_session_tracker import get_session_tracker
from app.ws.connection import WebSocketConnection
from app.ws.events import EventType
from app.ws.handlers.base import BaseHandler
from app.ws.messages import MessageEnvelope

if TYPE_CHECKING:
    from app.ws.manager import ConnectionManager

logger = logging.getLogger(__name__)


class TableHandler(BaseHandler):
    """Handles table subscription and seat management.

    Uses GameManager for in-memory game state management.

    Events:
    - SUBSCRIBE_TABLE: Subscribe to table updates
    - UNSUBSCRIBE_TABLE: Unsubscribe from table
    - SEAT_REQUEST: Request to take a seat
    - LEAVE_REQUEST: Leave the table
    - ADD_BOT_REQUEST: Add a bot to the table
    """

    def __init__(self, manager: "ConnectionManager", db: AsyncSession):
        super().__init__(manager)
        self.db = db
        self.room_service = RoomService(db)

    @property
    def handled_events(self) -> tuple[EventType, ...]:
        return (
            EventType.SUBSCRIBE_TABLE,
            EventType.UNSUBSCRIBE_TABLE,
            EventType.SEAT_REQUEST,
            EventType.LEAVE_REQUEST,
            EventType.ADD_BOT_REQUEST,
            EventType.START_BOT_LOOP_REQUEST,
            EventType.SIT_OUT_REQUEST,
            EventType.SIT_IN_REQUEST,
            EventType.WAITLIST_JOIN_REQUEST,
            EventType.WAITLIST_CANCEL_REQUEST,
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
            case EventType.ADD_BOT_REQUEST:
                return await self._handle_add_bot(conn, event)
            case EventType.START_BOT_LOOP_REQUEST:
                return await self._handle_start_bot_loop(conn, event)
            case EventType.SIT_OUT_REQUEST:
                return await self._handle_sit_out(conn, event)
            case EventType.SIT_IN_REQUEST:
                return await self._handle_sit_in(conn, event)
            case EventType.WAITLIST_JOIN_REQUEST:
                return await self._handle_waitlist_join(conn, event)
            case EventType.WAITLIST_CANCEL_REQUEST:
                return await self._handle_waitlist_cancel(conn, event)
        return None

    async def _handle_subscribe(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope:
        """Handle SUBSCRIBE_TABLE event."""
        table_id = event.payload.get("tableId")  # Could be roomId
        logger.info(f"[SUBSCRIBE_TABLE] table_id={table_id}, user_id={conn.user_id}")
        # mode는 아래에서 자동 결정 (유저가 테이블에 앉아있으면 player)

        # Get or load table from DB and sync with GameManager
        table = await self._get_table_by_id_or_room(table_id, load_room=True)
        if not table:
            logger.warning(f"[SUBSCRIBE_TABLE] TABLE_NOT_FOUND for table_id={table_id}")
            return MessageEnvelope.create(
                event_type=EventType.TABLE_SNAPSHOT,
                payload={"tableId": table_id, "error": "TABLE_NOT_FOUND"},
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

        # Ensure table exists in GameManager
        await self._ensure_game_table(table)

        # mode 자동 결정: 유저가 테이블에 앉아있으면 player, 아니면 spectator
        room_id = str(table.room_id)
        game_table = game_manager.get_table(room_id)
        mode = "spectator"
        if game_table:
            for player in game_table.players.values():
                if player and player.user_id == conn.user_id:
                    mode = "player"
                    break

        # Phase 4.2: 그룹별 채널 구독
        if mode == "player":
            await self.manager.subscribe_as_player(conn.connection_id, room_id)
        else:
            await self.manager.subscribe_as_spectator(conn.connection_id, room_id)

        logger.info(f"[SUBSCRIBE_TABLE] user_id={conn.user_id}, mode={mode}")

        # Build snapshot using GameManager state
        snapshot = await self._build_table_snapshot(table, conn.user_id, mode)

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

        # Try to get table to find room_id
        table = await self._get_table_by_id_or_room(table_id)
        if table:
            room_id = str(table.room_id)
        else:
            room_id = table_id

        # Phase 4.2: 모든 테이블 관련 채널에서 구독 해제
        await self.manager.unsubscribe_from_table(conn.connection_id, room_id)
        return None

    async def _handle_seat(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope:
        """Handle SEAT_REQUEST event."""
        payload = event.payload
        table_id = payload.get("tableId")
        buy_in = payload.get("buyInAmount") or payload.get("buyIn")
        seat = payload.get("seat")  # Optional specific seat

        try:
            self.db.expire_all()

            table = await self._get_table_by_id_or_room(table_id, load_room=True)
            if not table:
                raise RoomError("TABLE_NOT_FOUND", "Table not found")

            room_id = str(table.room_id)
            config = table.room.config if table.room else {}

            # Join via room service (handles DB)
            result = await self.room_service.join_room(
                room_id=table.room_id,
                user_id=conn.user_id,
                buy_in=buy_in,
            )
            await self.db.commit()

            result_position = result.get("position") if isinstance(result, dict) else 0
            result_stack = result.get("stack") if isinstance(result, dict) else buy_in

            # Get real username from DB
            real_username = conn.user_id
            try:
                from app.models.user import User
                user_result = await self.db.execute(select(User).where(User.id == conn.user_id))
                user = user_result.scalar_one_or_none()
                if user:
                    real_username = user.nickname
            except Exception:
                pass

            # Also seat in GameManager
            game_table = await self._ensure_game_table(table)
            if game_table:
                player = Player(
                    user_id=conn.user_id,
                    username=real_username,
                    seat=result_position,
                    stack=result_stack,
                )
                game_table.seat_player(result_position, player)
                logger.info(f"[SEAT] Player {real_username} ({conn.user_id}) seated at position {result_position} in GameManager")

            # Broadcast table update (use room_id for channel)
            # 중간 입장: 기본 상태가 sitting_out이므로 status 포함
            await self._broadcast_table_update(
                room_id,
                "seat_taken",
                {
                    "position": result_position,
                    "userId": conn.user_id,
                    "nickname": real_username,
                    "stack": result_stack,
                    "status": "sitting_out",  # 착석 시 기본 상태
                },
            )

            # Phase 2.3: 플레이어 세션 시작 (부정 행위 탐지용)
            session_tracker = get_session_tracker()
            if session_tracker:
                session_tracker.start_session(conn.user_id, room_id)
                logger.info(f"[SESSION] Started session for {conn.user_id} in {room_id}")

            # Phase 4.2: 관전자에서 플레이어로 업그레이드
            await self.manager.upgrade_to_player(conn.connection_id, room_id)

            # 자동 시작 제거 - 유저가 START_GAME 버튼을 눌러야 시작

            return MessageEnvelope.create(
                event_type=EventType.SEAT_RESULT,
                payload={
                    "success": True,
                    "tableId": room_id,
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
            table = await self._get_table_by_id_or_room(table_id)
            if not table:
                raise RoomError("TABLE_NOT_FOUND", "Table not found")

            room_id = str(table.room_id)

            # Find player's position and current stack in GameManager
            # 중요: GameManager의 최신 스택을 사용해야 게임 결과가 반영됨
            game_table = game_manager.get_table(room_id)
            player_position = None
            current_stack = None
            if game_table:
                for seat, player in game_table.players.items():
                    if player and player.user_id == conn.user_id:
                        player_position = seat
                        current_stack = player.stack
                        break

            # GameManager에서 현재 스택을 가져왔으면 DB seats도 업데이트
            # 이렇게 해야 leave_room이 올바른 스택을 반환함
            if current_stack is not None and player_position is not None:
                seats = dict(table.seats) if table.seats else {}
                if str(player_position) in seats:
                    seats[str(player_position)]["stack"] = current_stack
                    table.seats = seats
                    attributes.flag_modified(table, "seats")
                    logger.info(f"[LEAVE] Synced stack {current_stack} from GameManager to DB for {conn.user_id}")

            # Leave via room service (handles DB balance return)
            await self.room_service.leave_room(
                room_id=table.room_id,
                user_id=conn.user_id,
            )
            await self.db.commit()

            # Also remove from GameManager
            if game_table and player_position is not None:
                game_table.remove_player(player_position)
                logger.info(f"[LEAVE] Player {conn.user_id} removed from position {player_position} in GameManager (stack: {current_stack})")

            # Phase 2.3: 플레이어 세션 종료 및 통계 이벤트 발행 (부정 행위 탐지용)
            session_tracker = get_session_tracker()
            if session_tracker:
                session = await session_tracker.end_session(conn.user_id, room_id)
                if session:
                    logger.info(
                        f"[SESSION] Ended session for {conn.user_id} in {room_id}: "
                        f"hands={session.hands_played}, bet={session.total_bet}, won={session.total_won}"
                    )

            # Phase 4.2: 플레이어에서 관전자로 다운그레이드 (테이블 구독은 유지)
            await self.manager.downgrade_to_spectator(conn.connection_id, room_id)

            # Broadcast update
            await self._broadcast_table_update(
                room_id,
                "player_left",
                {"userId": conn.user_id, "position": player_position},
            )

            # Phase 4.1: 자리가 비면 대기열 처리
            await self._process_waitlist_on_leave(room_id)

            return MessageEnvelope.create(
                event_type=EventType.LEAVE_RESULT,
                payload={
                    "success": True,
                    "tableId": room_id,
                    "returnedStack": current_stack,  # 반환된 금액 알려주기
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

    async def _handle_add_bot(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope:
        """Handle ADD_BOT_REQUEST event."""
        payload = event.payload
        table_id = payload.get("tableId")
        buy_in = payload.get("buyIn", 1000)
        bot_name = payload.get("name")

        logger.info(f"[ADD_BOT] Received ADD_BOT_REQUEST: tableId={table_id}, buyIn={buy_in}")

        try:
            self.db.expire_all()

            table = await self._get_table_by_id_or_room(table_id, load_room=True)
            if not table:
                raise RoomError("TABLE_NOT_FOUND", "Table not found")

            room_id = str(table.room_id)
            room = table.room
            if not room:
                raise RoomError("ROOM_NOT_FOUND", "Room not found")

            config = room.config or {}
            max_seats = config.get("max_seats", 6)

            # Ensure GameManager table exists
            game_table = await self._ensure_game_table(table)
            if not game_table:
                raise RoomError("GAME_TABLE_ERROR", "Failed to create game table")

            # Find empty position in GameManager
            empty_position = None
            for i in range(max_seats):
                if game_table.players.get(i) is None:
                    empty_position = i
                    break

            if empty_position is None:
                raise RoomError("ROOM_FULL", "No empty seats available")

            # Generate bot ID and name
            bot_id = f"bot_{uuid.uuid4().hex[:8]}"
            bot_nickname = bot_name or f"Bot_{bot_id[-4:]}"

            # Add bot to GameManager
            bot_player = Player(
                user_id=bot_id,
                username=bot_nickname,
                seat=empty_position,
                stack=buy_in,
                is_bot=True,  # 봇임을 명시
            )
            game_table.seat_player(empty_position, bot_player)
            # 봇은 즉시 참여 (sitting_out 기본값 해제)
            game_table.sit_in(empty_position)
            logger.info(f"[BOT] Bot {bot_nickname} added at position {empty_position} in GameManager")

            # Also add to DB seats
            seats = dict(table.seats) if table.seats else {}
            seats[str(empty_position)] = {
                "user_id": bot_id,
                "nickname": bot_nickname,
                "stack": buy_in,
                "status": "active",
                "is_bot": True,
            }
            table.seats = seats
            attributes.flag_modified(table, "seats")
            room.current_players = len(seats)
            await self.db.commit()

            # Broadcast update
            await self._broadcast_table_update(
                room_id,
                "bot_added",
                {
                    "position": empty_position,
                    "botId": bot_id,
                    "nickname": bot_nickname,
                    "stack": buy_in,
                },
            )

            # 자동 시작 제거 - 유저가 START_GAME 버튼을 눌러야 시작

            return MessageEnvelope.create(
                event_type=EventType.ADD_BOT_RESULT,
                payload={
                    "success": True,
                    "tableId": room_id,
                    "botId": bot_id,
                    "nickname": bot_nickname,
                    "position": empty_position,
                    "stack": buy_in,
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

        except RoomError as e:
            return MessageEnvelope.create(
                event_type=EventType.ADD_BOT_RESULT,
                payload={
                    "success": False,
                    "errorCode": e.code,
                    "errorMessage": e.message,
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )
        except Exception as e:
            logger.error(f"Add bot failed: {e}", exc_info=True)
            return MessageEnvelope.create(
                event_type=EventType.ADD_BOT_RESULT,
                payload={
                    "success": False,
                    "errorCode": "ADD_BOT_FAILED",
                    "errorMessage": str(e),
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

    async def _handle_start_bot_loop(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope:
        """Handle START_BOT_LOOP_REQUEST event.

        봇 여러 개를 하나씩 자리에 앉히고 자동으로 게임을 시작합니다.
        """
        import asyncio
        import random

        payload = event.payload
        table_id = payload.get("tableId")
        bot_count = payload.get("botCount", 4)
        buy_in = payload.get("buyIn")

        logger.info(f"[BOT-LOOP] Received START_BOT_LOOP_REQUEST: tableId={table_id}, botCount={bot_count}, buyIn={buy_in}")

        try:
            self.db.expire_all()

            table = await self._get_table_by_id_or_room(table_id, load_room=True)
            if not table:
                raise RoomError("TABLE_NOT_FOUND", "Table not found")

            room_id = str(table.room_id)
            room = table.room
            if not room:
                raise RoomError("ROOM_NOT_FOUND", "Room not found")

            config = room.config or {}
            max_seats = config.get("max_seats", 6)
            default_buy_in = buy_in or config.get("buy_in_min", 1000)

            # Ensure GameManager table exists
            game_table = await self._ensure_game_table(table)
            if not game_table:
                raise RoomError("GAME_TABLE_ERROR", "Failed to create game table")

            # 게임이 진행 중이면 중단
            if game_table.phase.value != "waiting":
                raise RoomError("GAME_IN_PROGRESS", "게임이 진행 중입니다. 리셋 후 다시 시도하세요.")

            # 봇을 하나씩 추가 (실제처럼 보이게)
            bots_added = []
            seats = dict(table.seats) if table.seats else {}

            for i in range(bot_count):
                # Find empty position
                empty_position = None
                for pos in range(max_seats):
                    if game_table.players.get(pos) is None:
                        empty_position = pos
                        break

                if empty_position is None:
                    break  # 더 이상 빈 자리 없음

                # Generate bot ID and name
                bot_id = f"bot_{uuid.uuid4().hex[:8]}"
                bot_nickname = f"Bot_{bot_id[-4:]}"

                # Add bot to GameManager
                bot_player = Player(
                    user_id=bot_id,
                    username=bot_nickname,
                    seat=empty_position,
                    stack=default_buy_in,
                    is_bot=True,
                )
                game_table.seat_player(empty_position, bot_player)
                # 봇은 즉시 참여 (sitting_out 기본값 해제)
                game_table.sit_in(empty_position)

                # Add to DB seats
                seats[str(empty_position)] = {
                    "user_id": bot_id,
                    "nickname": bot_nickname,
                    "stack": default_buy_in,
                    "status": "active",
                    "is_bot": True,
                }

                bots_added.append({
                    "botId": bot_id,
                    "nickname": bot_nickname,
                    "position": empty_position,
                    "stack": default_buy_in,
                })

                logger.info(f"[BOT-LOOP] Bot {bot_nickname} joined at position {empty_position}")

                # Save to DB (매번 저장)
                table.seats = seats
                attributes.flag_modified(table, "seats")
                room.current_players = len(seats)
                await self.db.commit()

                # 봇이 자리에 앉은 것을 브로드캐스트 (하나씩!)
                await self._broadcast_table_update(
                    room_id,
                    "bot_added",
                    {
                        "position": empty_position,
                        "botId": bot_id,
                        "nickname": bot_nickname,
                        "stack": default_buy_in,
                    },
                )

                # 봇 착석은 빠르게 (0.3초)
                if i < bot_count - 1:
                    await asyncio.sleep(0.3)

            # 모든 봇이 앉은 후 게임 시작 전 대기 (2초)
            await asyncio.sleep(2.0)

            # 2명 이상이면 ActionHandler를 통해 게임 시작
            if game_table.can_start_hand():
                logger.info(f"[BOT-LOOP] Auto-starting game with {len(bots_added)} bots")
                # ActionHandler의 기존 로직 사용 (봇 딜레이, 브로드캐스트 등 포함)
                from app.ws.handlers.action import ActionHandler
                from app.utils.redis_client import get_redis

                action_handler = ActionHandler(self.manager, get_redis())
                start_event = MessageEnvelope.create(
                    event_type=EventType.START_GAME,
                    payload={"tableId": room_id},
                )
                await action_handler._handle_start_game(conn, start_event)

            return MessageEnvelope.create(
                event_type=EventType.START_BOT_LOOP_RESULT,
                payload={
                    "success": True,
                    "tableId": room_id,
                    "botsAdded": len(bots_added),
                    "bots": bots_added,
                    "gameStarted": game_table.phase.value != "waiting",
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

        except RoomError as e:
            return MessageEnvelope.create(
                event_type=EventType.START_BOT_LOOP_RESULT,
                payload={
                    "success": False,
                    "errorCode": e.code,
                    "errorMessage": e.message,
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )
        except Exception as e:
            logger.error(f"Start bot loop failed: {e}", exc_info=True)
            return MessageEnvelope.create(
                event_type=EventType.START_BOT_LOOP_RESULT,
                payload={
                    "success": False,
                    "errorCode": "BOT_LOOP_FAILED",
                    "errorMessage": str(e),
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

    async def _ensure_game_table(self, table: Table):
        """Ensure table exists in GameManager and sync from DB if needed."""
        room_id = str(table.room_id)
        room = table.room

        game_table = game_manager.get_table(room_id)
        if game_table:
            return game_table

        # Create new game table from DB config
        config = room.config if room else {}
        game_table = game_manager.get_or_create_table(
            room_id=room_id,
            name=room.name if room else "Table",
            small_blind=config.get("small_blind", 10),
            big_blind=config.get("big_blind", 20),
            min_buy_in=config.get("buy_in_min", 400),
            max_buy_in=config.get("buy_in_max", 2000),
            max_players=config.get("max_seats", 6),
        )

        # Sync existing players from DB
        if table.seats:
            for seat_str, seat_data in table.seats.items():
                if seat_data:
                    seat = int(seat_str)
                    player = Player(
                        user_id=seat_data.get("user_id"),
                        username=seat_data.get("nickname") or f"Player_{seat}",
                        seat=seat,
                        stack=seat_data.get("stack", 0),
                        is_bot=seat_data.get("is_bot", False),
                    )
                    game_table.seat_player(seat, player)

                    # DB에서 저장된 status 복원 (기본값: active)
                    db_status = seat_data.get("status", "active")
                    if db_status == "active":
                        game_table.sit_in(seat)
                        logger.debug(f"[SYNC] Player {player.user_id} synced to seat {seat} (active)")
                    else:
                        logger.debug(f"[SYNC] Player {player.user_id} synced to seat {seat} (sitting_out)")

        logger.info(f"[GAME] Created GameManager table for room {room_id} with {len(game_table.players)} players")
        return game_table

    def _is_valid_uuid(self, value: str | None) -> bool:
        """Check if a string is a valid UUID."""
        if not value or value == "undefined" or value == "null":
            return False
        try:
            from uuid import UUID
            UUID(value)
            return True
        except (ValueError, AttributeError):
            return False

    async def _get_table_by_id_or_room(
        self,
        table_or_room_id: str | None,
        load_room: bool = False,
    ) -> Table | None:
        """Get table by table ID or room ID."""
        if not self._is_valid_uuid(table_or_room_id):
            logger.warning(f"Invalid table/room ID format: {table_or_room_id}")
            return None

        query = select(Table)
        if load_room:
            query = query.options(joinedload(Table.room))

        # First try direct table lookup
        result = await self.db.execute(
            query.where(Table.id == table_or_room_id)
        )
        table = result.scalar_one_or_none()
        if table:
            return table

        # If not found, try to find table by room_id
        result = await self.db.execute(
            query.where(Table.room_id == table_or_room_id)
        )
        return result.scalar_one_or_none()

    async def _build_table_snapshot(
        self,
        table: Table,
        user_id: str,
        mode: str,
    ) -> dict[str, Any]:
        """Build TABLE_SNAPSHOT payload using GameManager state.

        Returns format expected by frontend:
        {
            tableId, roomId, config,
            seats: [{ position, player: { userId, nickname }, stack, status, betAmount }, ...],
            myPosition, myHoleCards, hand, dealerPosition, ...
        }
        """
        room_id = str(table.room_id)
        game_table = game_manager.get_table(room_id)

        config = table.room.config if table.room else {}
        max_seats = config.get("max_seats", 6)

        # Build seats in frontend format
        my_position = None
        my_hole_cards = None
        seats = []

        if game_table:
            # Use GameManager state
            logger.info(f"[TABLE_SNAPSHOT] game_table exists, phase={game_table.phase}, pot={game_table.pot}")
            for i in range(max_seats):
                player = game_table.players.get(i)
                if player:
                    if player.user_id == user_id:
                        my_position = i
                        my_hole_cards = player.hole_cards
                        logger.info(f"[TABLE_SNAPSHOT] Found my player at seat {i}, hole_cards={my_hole_cards}")
                    seats.append({
                        "position": i,
                        "player": {
                            "userId": player.user_id,
                            "nickname": player.username,
                            "avatarUrl": None,
                        },
                        "stack": player.stack,
                        "status": player.status,
                        "betAmount": player.current_bet,
                        "totalBet": player.total_bet_this_hand,  # 핸드 전체 누적 베팅
                        "isDealer": i == game_table.dealer_seat,
                        "isCurrent": i == game_table.current_player_seat,
                        "isCardsRevealed": player.is_cards_revealed,  # 카드 오픈 상태
                    })
                else:
                    seats.append({
                        "position": i,
                        "player": None,
                        "stack": 0,
                        "status": "empty",
                        "betAmount": 0,
                        "totalBet": 0,
                    })

            # Build hand info with action history for mid-game sync
            hand = None
            action_history = []
            if game_table.phase.value != "waiting":
                # 액션 히스토리 - 중간 입장자도 지금까지의 베팅 흐름을 볼 수 있음
                action_history = [
                    {
                        "seat": a["seat"],
                        "action": a["action"],
                        "amount": a.get("amount", 0),
                        "phase": a["phase"],
                    }
                    for a in game_table._hand_actions
                ]

                hand = {
                    "handNumber": game_table.hand_number,
                    "phase": game_table.phase.value,
                    "pot": game_table.pot,
                    "communityCards": game_table.community_cards,
                    "currentTurn": game_table.current_player_seat,
                    "currentBet": game_table.current_bet,
                    "actionHistory": action_history,  # 중간 입장 동기화용
                }

            # 현재 턴인 플레이어에게 allowedActions 제공 (새로고침 시 복원용)
            allowed_actions = None
            if mode == "player" and my_position == game_table.current_player_seat:
                actions_data = game_table.get_available_actions(user_id)
                if actions_data.get("actions"):
                    allowed_actions = []
                    for action in actions_data["actions"]:
                        action_obj = {"type": action}
                        if action == "call":
                            action_obj["amount"] = actions_data.get("call_amount", 0)
                        elif action in ("raise", "bet"):
                            action_obj["minAmount"] = actions_data.get("min_raise", 0)
                            action_obj["maxAmount"] = actions_data.get("max_raise", 0)
                        allowed_actions.append(action_obj)

            # 턴 정보 - 중간 입장 시 남은 시간 계산용
            turn_info = None
            if game_table.current_player_seat is not None and game_table._turn_started_at:
                from datetime import datetime, timezone, timedelta

                base_timeout = config.get("turn_timeout", 15)  # 고정 15초 턴 타임
                deadline = game_table._turn_started_at + timedelta(seconds=base_timeout)

                # 남은 시간 계산
                now = datetime.now(timezone.utc)
                remaining_seconds = max(0, (deadline - now).total_seconds())

                turn_info = {
                    "currentSeat": game_table.current_player_seat,
                    "startedAt": game_table._turn_started_at.isoformat(),
                    "deadlineAt": deadline.isoformat(),
                    "remainingSeconds": round(remaining_seconds, 1),
                }

            return {
                "tableId": room_id,
                "roomId": room_id,
                "config": {
                    "maxSeats": max_seats,
                    "smallBlind": config.get("small_blind", 10),
                    "bigBlind": config.get("big_blind", 20),
                    "minBuyIn": config.get("buy_in_min", 400),
                    "maxBuyIn": config.get("buy_in_max", 2000),
                    "turnTimeoutSeconds": config.get("turn_timeout", 30),
                },
                "seats": seats,
                "hand": hand,
                "dealerPosition": game_table.dealer_seat,
                "myPosition": my_position,
                "myHoleCards": my_hole_cards if mode == "player" else None,
                "allowedActions": allowed_actions,  # 새로고침 시 복원용
                "turnInfo": turn_info,  # 중간 입장 시 턴 타이머 동기화용
                "stateVersion": table.state_version or 1,
                "updatedAt": table.updated_at.isoformat() if table.updated_at else None,
                "isStateRestore": True,  # 상태 복원 플래그 (새로고침/재접속 구분용)
            }

        # Fallback: build from DB seats
        for i in range(max_seats):
            seat_data = table.seats.get(str(i)) if table.seats else None
            if seat_data:
                if seat_data.get("user_id") == user_id:
                    my_position = i
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

        return {
            "tableId": room_id,
            "roomId": room_id,
            "config": {
                "maxSeats": max_seats,
                "smallBlind": config.get("small_blind", 10),
                "bigBlind": config.get("big_blind", 20),
                "minBuyIn": config.get("buy_in_min", 400),
                "maxBuyIn": config.get("buy_in_max", 2000),
                "turnTimeoutSeconds": config.get("turn_timeout", 30),
            },
            "seats": seats,
            "hand": None,
            "dealerPosition": table.dealer_position or 0,
            "myPosition": my_position,
            "stateVersion": table.state_version or 1,
            "updatedAt": table.updated_at.isoformat() if table.updated_at else None,
            "isStateRestore": True,  # 상태 복원 플래그
        }

    async def _try_auto_start_game(self, room_id: str, game_table) -> None:
        """Try to auto-start game if enough players (2+)."""
        # 먼저 BB 위치 대기자 활성화 시도 (can_start_hand() 전에!)
        pre_activated = game_table.try_activate_bb_waiter_for_next_hand()
        if pre_activated:
            for seat in pre_activated:
                player = game_table.players.get(seat)
                if player:
                    sit_in_msg = MessageEnvelope.create(
                        event_type=EventType.PLAYER_SIT_IN,
                        payload={
                            "tableId": room_id,
                            "position": seat,
                            "userId": player.user_id,
                            "auto": True,
                            "reason": "bb_reached",
                        },
                    )
                    channel = f"table:{room_id}"
                    await self.manager.broadcast_to_channel(channel, sit_in_msg.to_dict())
                    logger.info(
                        f"[PRE_HAND_ACTIVATE] 브로드캐스트: seat={seat}, user={player.user_id}, room={room_id}"
                    )

        if not game_table.can_start_hand():
            # 상세 디버그 로그
            active_players = game_table.get_active_players()
            all_players = game_table.get_all_seated_players()
            logger.info(
                f"[AUTO-START] Cannot start: "
                f"active={len(active_players)}, all_seated={len(all_players)}, "
                f"phase={game_table.phase.value}, "
                f"status={[(s, p.status if p else None) for s, p in all_players]}"
            )
            return

        logger.info(f"[AUTO-START] Starting game for room {room_id}")

        result = game_table.start_new_hand()
        if not result.get("success"):
            logger.error(f"[AUTO-START] Failed: {result.get('error')}")
            return

        # Broadcast hand started (with seats/blinds data)
        # seats 데이터 구성 (블라인드 칩 포함)
        seats_data = []
        for seat in range(game_table.max_players):
            player = game_table.players.get(seat)
            if player:
                seats_data.append({
                    "position": seat,
                    "userId": player.user_id,
                    "nickname": player.username,
                    "stack": player.stack,
                    "status": player.status,
                    "betAmount": player.current_bet,  # 블라인드 칩
                })
            else:
                seats_data.append(None)

        # SB/BB 좌석 계산
        sb_seat, bb_seat = game_table.get_blind_seats()

        message = MessageEnvelope.create(
            event_type=EventType.HAND_STARTED,
            payload={
                "tableId": room_id,
                "handNumber": result.get("hand_number"),
                "dealer": result.get("dealer"),
                "smallBlindSeat": sb_seat,
                "bigBlindSeat": bb_seat,
                "seats": seats_data,  # 블라인드 칩 포함된 seats
                "phase": "preflop",
                "pot": game_table.pot,
            },
        )
        channel = f"table:{room_id}"
        await self.manager.broadcast_to_channel(channel, message.to_dict())

        # Send personalized states to all players
        for seat, player in game_table.players.items():
            if player:
                state = game_table.get_state_for_player(player.user_id)
                state_msg = MessageEnvelope.create(
                    event_type=EventType.TABLE_SNAPSHOT,
                    payload={"tableId": room_id, "state": state},
                )
                await self.manager.send_to_user(player.user_id, state_msg.to_dict())

        # Process first turn (with bot loop)
        await self._process_next_turn(room_id, game_table)

    async def _process_next_turn(self, room_id: str, game_table) -> None:
        """Process next turn - with bot loop."""
        import asyncio
        import random
        from datetime import datetime, timedelta

        MAX_ITERATIONS = 50

        for iteration in range(MAX_ITERATIONS):
            if game_table.current_player_seat is None:
                return

            current_player = game_table.players.get(game_table.current_player_seat)
            if not current_player:
                return

            # Check if bot
            is_bot = current_player.user_id.startswith("bot_")

            if not is_bot:
                # Human player - send TURN_PROMPT and exit
                available = game_table.get_available_actions(current_player.user_id)
                allowed = []
                for action in available.get("actions", []):
                    action_dict = {"type": action}
                    if action == "call":
                        action_dict["amount"] = available.get("call_amount", 0)
                    if action == "raise":
                        action_dict["minAmount"] = available.get("min_raise", 0)
                        action_dict["maxAmount"] = available.get("max_raise", 0)
                    if action == "bet":
                        # bet도 min_raise/max_raise 사용 (같은 값)
                        action_dict["minAmount"] = available.get("min_raise", 0)
                        action_dict["maxAmount"] = available.get("max_raise", 0)
                    allowed.append(action_dict)

                deadline = datetime.now(timezone.utc) + timedelta(seconds=30)
                message = MessageEnvelope.create(
                    event_type=EventType.TURN_PROMPT,
                    payload={
                        "tableId": room_id,
                        "position": game_table.current_player_seat,
                        "allowedActions": allowed,
                        "deadlineAt": deadline.isoformat(),
                        "pot": game_table.pot,
                        "currentBet": game_table.current_bet,
                    },
                )
                channel = f"table:{room_id}"
                await self.manager.broadcast_to_channel(channel, message.to_dict())
                return

            # Bot auto-play
            await asyncio.sleep(0.5)

            available = game_table.get_available_actions(current_player.user_id)
            actions = available.get("actions", [])
            call_amount = available.get("call_amount", 0)

            logger.info(f"[BOT] {current_player.username} actions: {actions}")

            if not actions:
                return

            # Bot decision (conservative)
            roll = random.random()
            if "check" in actions:
                action, amount = "check", 0
            elif "call" in actions and (call_amount <= current_player.stack * 0.3 or roll < 0.8):
                action, amount = "call", call_amount
            elif "fold" in actions:
                action, amount = "fold", 0
            else:
                action, amount = actions[0], call_amount if actions[0] == "call" else 0

            logger.info(f"[BOT] {current_player.username} chose: {action} {amount}")

            result = game_table.process_action(current_player.user_id, action, amount)

            if not result.get("success"):
                logger.error(f"[BOT] Action failed: {result.get('error')}")
                return

            # Broadcast action
            action_msg = MessageEnvelope.create(
                event_type=EventType.TABLE_STATE_UPDATE,
                payload={
                    "tableId": room_id,
                    "changes": {
                        "lastAction": {
                            "type": result.get("action"),
                            "amount": result.get("amount", 0),
                            "position": result.get("seat"),
                        },
                        "pot": result.get("pot", 0),
                        "phase": result.get("phase"),
                    },
                },
            )
            channel = f"table:{room_id}"
            await self.manager.broadcast_to_channel(channel, action_msg.to_dict())

            # Phase changed
            if result.get("phase_changed"):
                cards_msg = MessageEnvelope.create(
                    event_type=EventType.COMMUNITY_CARDS,
                    payload={
                        "tableId": room_id,
                        "phase": game_table.phase.value,
                        "cards": game_table.community_cards,
                    },
                )
                await self.manager.broadcast_to_channel(channel, cards_msg.to_dict())

            # Hand complete
            if result.get("hand_complete"):
                hand_result = result.get("hand_result")
                result_msg = MessageEnvelope.create(
                    event_type=EventType.HAND_RESULT,
                    payload={
                        "tableId": room_id,
                        "winners": hand_result.get("winners", []) if hand_result else [],
                        "pot": hand_result.get("pot", 0) if hand_result else 0,
                        "showdown": hand_result.get("showdown", []) if hand_result else [],
                    },
                )
                await self.manager.broadcast_to_channel(channel, result_msg.to_dict())

                # Auto-start next hand after delay
                await asyncio.sleep(3.0)
                await self._try_auto_start_game(room_id, game_table)
                return

    async def _handle_sit_out(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope:
        """Handle SIT_OUT_REQUEST event.
        
        Marks the player as sitting out. They will be skipped in future hands
        until they sit back in.
        """
        table_id = event.payload.get("tableId")

        try:
            table = await self._get_table_by_id_or_room(table_id)
            if not table:
                return MessageEnvelope.create(
                    event_type=EventType.PLAYER_SIT_OUT,
                    payload={
                        "success": False,
                        "errorCode": "TABLE_NOT_FOUND",
                        "errorMessage": "Table not found",
                    },
                    request_id=event.request_id,
                    trace_id=event.trace_id,
                )

            room_id = str(table.room_id)
            game_table = game_manager.get_table(room_id)
            
            if not game_table:
                return MessageEnvelope.create(
                    event_type=EventType.PLAYER_SIT_OUT,
                    payload={
                        "success": False,
                        "errorCode": "GAME_TABLE_NOT_FOUND",
                        "errorMessage": "Game table not found",
                    },
                    request_id=event.request_id,
                    trace_id=event.trace_id,
                )

            # Find player's seat
            player_seat = None
            for seat, player in game_table.players.items():
                if player and player.user_id == conn.user_id:
                    player_seat = seat
                    break

            if player_seat is None:
                return MessageEnvelope.create(
                    event_type=EventType.PLAYER_SIT_OUT,
                    payload={
                        "success": False,
                        "errorCode": "NOT_SEATED",
                        "errorMessage": "You are not seated at this table",
                    },
                    request_id=event.request_id,
                    trace_id=event.trace_id,
                )

            # Mark player as sitting out
            success = game_table.sit_out(player_seat)
            
            if not success:
                return MessageEnvelope.create(
                    event_type=EventType.PLAYER_SIT_OUT,
                    payload={
                        "success": False,
                        "errorCode": "ALREADY_SITTING_OUT",
                        "errorMessage": "You are already sitting out",
                    },
                    request_id=event.request_id,
                    trace_id=event.trace_id,
                )

            # Broadcast to all table subscribers
            await self._broadcast_table_update(
                room_id,
                "player_sit_out",
                {
                    "position": player_seat,
                    "userId": conn.user_id,
                },
            )

            return MessageEnvelope.create(
                event_type=EventType.PLAYER_SIT_OUT,
                payload={
                    "success": True,
                    "tableId": room_id,
                    "position": player_seat,
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

        except Exception as e:
            logger.exception(f"Error handling sit out request: {e}")
            return MessageEnvelope.create(
                event_type=EventType.PLAYER_SIT_OUT,
                payload={
                    "success": False,
                    "errorCode": "INTERNAL_ERROR",
                    "errorMessage": str(e),
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

    async def _handle_sit_in(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope:
        """Handle SIT_IN_REQUEST event.
        
        Marks the player as active again. They will be dealt into the next hand.
        """
        table_id = event.payload.get("tableId")

        try:
            table = await self._get_table_by_id_or_room(table_id)
            if not table:
                return MessageEnvelope.create(
                    event_type=EventType.PLAYER_SIT_IN,
                    payload={
                        "success": False,
                        "errorCode": "TABLE_NOT_FOUND",
                        "errorMessage": "Table not found",
                    },
                    request_id=event.request_id,
                    trace_id=event.trace_id,
                )

            room_id = str(table.room_id)
            game_table = game_manager.get_table(room_id)
            
            if not game_table:
                return MessageEnvelope.create(
                    event_type=EventType.PLAYER_SIT_IN,
                    payload={
                        "success": False,
                        "errorCode": "GAME_TABLE_NOT_FOUND",
                        "errorMessage": "Game table not found",
                    },
                    request_id=event.request_id,
                    trace_id=event.trace_id,
                )

            # Find player's seat
            player_seat = None
            for seat, player in game_table.players.items():
                if player and player.user_id == conn.user_id:
                    player_seat = seat
                    break

            if player_seat is None:
                return MessageEnvelope.create(
                    event_type=EventType.PLAYER_SIT_IN,
                    payload={
                        "success": False,
                        "errorCode": "NOT_SEATED",
                        "errorMessage": "You are not seated at this table",
                    },
                    request_id=event.request_id,
                    trace_id=event.trace_id,
                )

            # Mark player as active
            success = game_table.sit_in(player_seat)
            
            if not success:
                return MessageEnvelope.create(
                    event_type=EventType.PLAYER_SIT_IN,
                    payload={
                        "success": False,
                        "errorCode": "NOT_SITTING_OUT",
                        "errorMessage": "You are not sitting out",
                    },
                    request_id=event.request_id,
                    trace_id=event.trace_id,
                )

            # Broadcast to all table subscribers
            await self._broadcast_table_update(
                room_id,
                "player_sit_in",
                {
                    "position": player_seat,
                    "userId": conn.user_id,
                },
            )

            return MessageEnvelope.create(
                event_type=EventType.PLAYER_SIT_IN,
                payload={
                    "success": True,
                    "tableId": room_id,
                    "position": player_seat,
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

        except Exception as e:
            logger.exception(f"Error handling sit in request: {e}")
            return MessageEnvelope.create(
                event_type=EventType.PLAYER_SIT_IN,
                payload={
                    "success": False,
                    "errorCode": "INTERNAL_ERROR",
                    "errorMessage": str(e),
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

    # =========================================================================
    # Waitlist Handlers (Phase 4.1)
    # =========================================================================

    async def _handle_waitlist_join(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope:
        """Handle WAITLIST_JOIN_REQUEST event - 대기열 등록."""
        payload = event.payload
        table_id = payload.get("tableId")
        buy_in = payload.get("buyIn", 1000)

        try:
            table = await self._get_table_by_id_or_room(table_id)
            if not table:
                raise RoomError("TABLE_NOT_FOUND", "Table not found")

            room_id = str(table.room_id)

            # 대기열에 추가
            result = await self.room_service.add_to_waitlist(
                room_id=room_id,
                user_id=conn.user_id,
                buy_in=buy_in,
            )

            logger.info(
                f"[WAITLIST] User {conn.user_id} joined waitlist for {room_id} "
                f"at position {result['position']}"
            )

            return MessageEnvelope.create(
                event_type=EventType.WAITLIST_JOINED,
                payload={
                    "success": True,
                    "tableId": room_id,
                    "position": result["position"],
                    "joinedAt": result["joined_at"],
                    "alreadyWaiting": result.get("already_waiting", False),
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

        except RoomError as e:
            return MessageEnvelope.create(
                event_type=EventType.WAITLIST_JOINED,
                payload={
                    "success": False,
                    "errorCode": e.code,
                    "errorMessage": e.message,
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

    async def _handle_waitlist_cancel(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope:
        """Handle WAITLIST_CANCEL_REQUEST event - 대기열 취소."""
        payload = event.payload
        table_id = payload.get("tableId")

        try:
            table = await self._get_table_by_id_or_room(table_id)
            if not table:
                raise RoomError("TABLE_NOT_FOUND", "Table not found")

            room_id = str(table.room_id)

            # 대기열에서 제거
            removed = await self.room_service.cancel_waitlist(
                room_id=room_id,
                user_id=conn.user_id,
            )

            if not removed:
                return MessageEnvelope.create(
                    event_type=EventType.WAITLIST_CANCELLED,
                    payload={
                        "success": False,
                        "errorCode": "NOT_IN_WAITLIST",
                        "errorMessage": "대기열에 등록되어 있지 않습니다",
                    },
                    request_id=event.request_id,
                    trace_id=event.trace_id,
                )

            logger.info(f"[WAITLIST] User {conn.user_id} cancelled waitlist for {room_id}")

            return MessageEnvelope.create(
                event_type=EventType.WAITLIST_CANCELLED,
                payload={
                    "success": True,
                    "tableId": room_id,
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

        except RoomError as e:
            return MessageEnvelope.create(
                event_type=EventType.WAITLIST_CANCELLED,
                payload={
                    "success": False,
                    "errorCode": e.code,
                    "errorMessage": e.message,
                },
                request_id=event.request_id,
                trace_id=event.trace_id,
            )

    async def _process_waitlist_on_leave(
        self,
        room_id: str,
    ) -> None:
        """자리가 비었을 때 대기열에서 첫 번째 사용자에게 알림.

        플레이어가 퇴장하면 대기열 첫 번째 사용자에게 WAITLIST_SEAT_READY 이벤트를 보냅니다.
        """
        from app.utils.redis_client import get_redis_context, RedisService

        try:
            async with get_redis_context() as redis:
                redis_service = RedisService(redis)

                # 대기열 첫 번째 사용자 조회
                first_waiter = await redis_service.get_first_in_waitlist(room_id)

                if not first_waiter:
                    return

                user_id = first_waiter["user_id"]
                buy_in = first_waiter["buy_in"]

                logger.info(
                    f"[WAITLIST] Seat available in {room_id}, "
                    f"notifying waitlist user {user_id}"
                )

                # 대기열 첫 번째 사용자에게 자리 났음 알림
                # 해당 사용자의 WebSocket 연결을 찾아 전송
                notification = MessageEnvelope.create(
                    event_type=EventType.WAITLIST_SEAT_READY,
                    payload={
                        "tableId": room_id,
                        "buyIn": buy_in,
                        "message": "자리가 났습니다! 착석 가능합니다.",
                        "expiresInSeconds": 30,  # 30초 내 응답 필요
                    },
                )

                # 사용자에게 직접 전송
                await self.manager.send_to_user(user_id, notification.to_dict())

                # 대기열의 다른 사용자들에게 위치 변경 알림
                waitlist = await redis_service.get_waitlist(room_id)
                for waiter in waitlist[1:]:  # 첫 번째 제외
                    position_notification = MessageEnvelope.create(
                        event_type=EventType.WAITLIST_POSITION_CHANGED,
                        payload={
                            "tableId": room_id,
                            "position": waiter["position"] - 1,  # 위치 한 칸 상승
                        },
                    )
                    await self.manager.send_to_user(
                        waiter["user_id"],
                        position_notification.to_dict()
                    )

        except Exception as e:
            logger.exception(f"Error processing waitlist on leave: {e}")

    async def _broadcast_table_update(
        self,
        room_id: str,
        update_type: str,
        changes: dict[str, Any],
    ) -> None:
        """Broadcast table update to all subscribers."""
        message = MessageEnvelope.create(
            event_type=EventType.TABLE_STATE_UPDATE,
            payload={
                "tableId": room_id,
                "updateType": update_type,
                "changes": changes,
            },
        )

        channel = f"table:{room_id}"
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
