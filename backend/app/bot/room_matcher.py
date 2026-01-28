"""Room matching algorithm for live bots.

Selects appropriate rooms for bots based on:
- Bot's stack size relative to blinds
- Room size and current occupancy
- Even distribution across all rooms
"""

import random
import logging
from typing import Optional

from app.game.manager import game_manager
from app.game.poker_table import PokerTable

logger = logging.getLogger(__name__)


async def ensure_table_exists(room_id: str) -> Optional[PokerTable]:
    """Ensure a table exists in GameManager for the given room.

    If table doesn't exist, creates it from DB room data.

    Args:
        room_id: Room ID to check/create table for

    Returns:
        PokerTable instance or None if room not found
    """
    # Check if table already exists
    table = game_manager.get_table(room_id)
    if table:
        return table

    # Create table from DB room data
    try:
        from app.utils.db import async_session_factory
        from app.models import Room, Table
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        async with async_session_factory() as db:
            result = await db.execute(
                select(Room)
                .options(selectinload(Room.tables))
                .where(Room.id == room_id)
                .where(Room.status != "closed")
            )
            room = result.scalar_one_or_none()

            if not room:
                return None

            # Skip tournament rooms
            if room.config.get("room_type") == "tournament":
                return None

            # Create PokerTable in GameManager
            table = game_manager.get_or_create_table(
                room_id=str(room.id),
                name=room.name,
                small_blind=room.small_blind,
                big_blind=room.big_blind,
                max_players=room.max_seats,
                min_buy_in=room.config.get("buy_in_min", 400),
                max_buy_in=room.config.get("buy_in_max", 2000),
            )

            logger.info(f"[ROOM_MATCHER] Created table for room {room_id}")
            return table

    except Exception as e:
        logger.error(f"[ROOM_MATCHER] Failed to create table: {e}")
        return None


async def get_available_rooms_from_db() -> list[dict]:
    """Get available rooms from database.

    Returns:
        List of room dictionaries with id, blinds, max_seats, etc.
    """
    try:
        from app.utils.db import async_session_factory
        from app.models import Room
        from sqlalchemy import select

        async with async_session_factory() as db:
            result = await db.execute(
                select(Room)
                .where(Room.status != "closed")
            )
            rooms = result.scalars().all()

            available = []
            for room in rooms:
                # Skip tournament rooms
                if room.config.get("room_type") == "tournament":
                    continue

                available.append({
                    "id": str(room.id),
                    "name": room.name,
                    "small_blind": room.small_blind,
                    "big_blind": room.big_blind,
                    "max_seats": room.max_seats,
                    "current_players": room.current_players,
                    "buy_in_min": room.config.get("buy_in_min", 400),
                    "buy_in_max": room.config.get("buy_in_max", 2000),
                })

            return available

    except Exception as e:
        logger.error(f"[ROOM_MATCHER] Failed to get rooms from DB: {e}")
        return []


# Bot stack sizing preferences (bots have infinite funds, so use buy-in based calculation)
# These are now used for scoring, not filtering
MIN_BB_FOR_PLAY = 40   # Minimum big blinds considered playable
MAX_BB_FOR_PLAY = 500  # Maximum (increased since bots choose their buy-in)
IDEAL_BB_MIN = 80      # Ideal minimum BB
IDEAL_BB_MAX = 150     # Ideal maximum BB


def get_ideal_player_range(max_players: int) -> tuple[int, int]:
    """Get ideal player count range based on table size.

    Args:
        max_players: Maximum players the table can hold

    Returns:
        Tuple of (min_players, max_players) for ideal occupancy

    Examples:
        6-seat table: 3-5 players (50-83% occupancy)
        9-seat table: 5-7 players (55-78% occupancy)
    """
    if max_players <= 4:
        return (2, 3)
    elif max_players <= 6:
        return (3, 5)
    elif max_players <= 9:
        return (5, 7)
    else:
        return (6, 8)


def get_max_bots_for_table(max_players: int) -> int:
    """Get maximum bots allowed per table based on size.

    Args:
        max_players: Maximum players the table can hold

    Returns:
        Maximum number of bots for this table size
    """
    ideal_min, ideal_max = get_ideal_player_range(max_players)
    return ideal_max


def get_available_rooms() -> list[PokerTable]:
    """Get all active rooms that are available for bots to join.

    Returns:
        List of available PokerTable instances
    """
    return game_manager.get_all_tables()


def count_bots_at_table(table: PokerTable) -> int:
    """Count the number of bots currently at a table.

    Args:
        table: The poker table to check

    Returns:
        Number of bots at the table
    """
    count = 0
    for player in table.players.values():
        if player is not None:
            user_id = player.user_id
            if user_id.startswith("bot_") or user_id.startswith("livebot_") or user_id.startswith("test_player_"):
                count += 1
    return count


def count_humans_at_table(table: PokerTable) -> int:
    """Count the number of human players at a table.

    Args:
        table: The poker table to check

    Returns:
        Number of human players at the table
    """
    count = 0
    for player in table.players.values():
        if player is not None:
            user_id = player.user_id
            if not (user_id.startswith("bot_") or user_id.startswith("livebot_") or user_id.startswith("test_player_")):
                count += 1
    return count


def get_empty_seats(table: PokerTable) -> list[int]:
    """Get list of empty seat positions at a table.

    Args:
        table: The poker table to check

    Returns:
        List of empty seat indices
    """
    empty = []
    for seat in range(table.max_players):
        if table.players.get(seat) is None:
            empty.append(seat)
    return empty


def calculate_room_score(
    table: PokerTable,
    bot_stack: int,
) -> float:
    """Calculate a score for how suitable a room is for a bot.

    Higher scores are better. Score factors:
    - BB ratio (how appropriate the blinds are for bot's stack)
    - Player count (prefer some activity but not full)
    - Bot count (avoid bot-heavy tables)
    - Human presence (prefer tables with humans)

    Args:
        table: The poker table to evaluate
        bot_stack: The bot's stack size

    Returns:
        Score between 0.0 and 1.0
    """
    score = 0.0

    # Calculate BB ratio
    bb = table.big_blind
    if bb <= 0:
        return 0.0

    bb_ratio = bot_stack / bb

    # BB ratio scoring (0-0.3 points)
    if MIN_BB_FOR_PLAY <= bb_ratio <= MAX_BB_FOR_PLAY:
        if IDEAL_BB_MIN <= bb_ratio <= IDEAL_BB_MAX:
            score += 0.3
        else:
            score += 0.15
    else:
        return 0.0

    # Player count scoring based on table size (0-0.30 points)
    player_count = sum(1 for p in table.players.values() if p is not None)
    empty_seats = table.max_players - player_count

    if empty_seats == 0:
        return 0.0

    ideal_min, ideal_max = get_ideal_player_range(table.max_players)
    max_bots = get_max_bots_for_table(table.max_players)

    if ideal_min <= player_count <= ideal_max:
        score += 0.30
    elif player_count < ideal_min:
        # 아직 적정 인원 미달 → 높은 점수 (봇 투입 필요)
        score += 0.25
    else:
        # 적정 초과 → 낮은 점수
        score += 0.05

    # Bot count: 적은 방을 강력히 선호 (0-0.30 points)
    bot_count = count_bots_at_table(table)
    if bot_count >= max_bots:
        return 0.0
    # 봇이 적을수록 높은 점수
    bot_ratio = bot_count / max_bots
    score += 0.30 * (1.0 - bot_ratio)

    # Human presence bonus (0-0.10 points)
    human_count = count_humans_at_table(table)
    if human_count > 0:
        score += min(0.10, human_count * 0.05)
    else:
        score += 0.02

    return min(1.0, score)


async def select_room_for_bot(
    bot_stack: int,
    exclude_room_ids: list[str] | None = None,
) -> Optional[tuple[PokerTable, int]]:
    """Select the best room for a bot to join.

    Args:
        bot_stack: The bot's stack size
        exclude_room_ids: Room IDs to exclude from selection

    Returns:
        Tuple of (table, seat_position) or None if no suitable room
    """
    exclude_room_ids = exclude_room_ids or []

    # First try existing tables in GameManager
    rooms = get_available_rooms()

    # If no rooms in GameManager, fetch from DB and create tables
    if not rooms:
        logger.debug("[ROOM_MATCHER] No rooms in GameManager, checking DB...")
        db_rooms = await get_available_rooms_from_db()

        for room_data in db_rooms:
            if room_data["id"] in exclude_room_ids:
                continue

            # Create table in GameManager
            table = await ensure_table_exists(room_data["id"])
            if table:
                rooms.append(table)

    if not rooms:
        logger.debug("[ROOM_MATCHER] No rooms available")
        return None

    # Score each room and sort by bot count (fewest first for even distribution)
    scored_rooms: list[tuple[PokerTable, float, int]] = []
    for table in rooms:
        if table.room_id in exclude_room_ids:
            continue

        empty_seats = get_empty_seats(table)
        if not empty_seats:
            continue

        score = calculate_room_score(table, bot_stack)
        if score > 0:
            bot_count = count_bots_at_table(table)
            scored_rooms.append((table, score, bot_count))

    if not scored_rooms:
        logger.debug("[ROOM_MATCHER] No suitable rooms found")
        return None

    # 1차 정렬: 봇 수 오름차순 (적은 방 우선)
    # 2차 정렬: 점수 내림차순
    scored_rooms.sort(key=lambda x: (x[2], -x[1]))

    # 같은 봇 수를 가진 방들 중에서 랜덤 선택 (자연스러운 분배)
    min_bot_count = scored_rooms[0][2]
    same_count_rooms = [r for r in scored_rooms if r[2] == min_bot_count]
    selected_entry = random.choice(same_count_rooms)
    selected_table = selected_entry[0]

    # Select a random empty seat
    empty_seats = get_empty_seats(selected_table)
    if not empty_seats:
        return None

    selected_seat = random.choice(empty_seats)

    logger.info(
        f"[ROOM_MATCHER] Selected room {selected_table.room_id} "
        f"(seat {selected_seat}, blinds {selected_table.small_blind}/{selected_table.big_blind}, "
        f"players {sum(1 for p in selected_table.players.values() if p)})"
    )

    return (selected_table, selected_seat)


def calculate_buy_in_for_room(
    table: PokerTable,
    target_bb: int = 100,
) -> int:
    """Calculate appropriate buy-in amount for a room.

    Args:
        table: The table to join
        target_bb: Target number of big blinds

    Returns:
        Buy-in amount (clamped to min/max)
    """
    ideal_buy_in = table.big_blind * target_bb

    # Clamp to table limits
    buy_in = max(table.min_buy_in, min(table.max_buy_in, ideal_buy_in))

    # Add some variation (+/- 10%)
    variance = random.uniform(0.9, 1.1)
    buy_in = int(buy_in * variance)

    # Re-clamp after variance
    return max(table.min_buy_in, min(table.max_buy_in, buy_in))


def should_leave_table(
    table: PokerTable,
    bot_user_id: str,
    stack: int,
    initial_stack: int,
    big_win_threshold: float = 2.0,
) -> tuple[bool, str]:
    """Determine if a bot should leave the table.

    Args:
        table: The current table
        bot_user_id: The bot's user ID
        stack: Current stack
        initial_stack: Stack when joined
        big_win_threshold: Multiple of initial stack considered a "big win"

    Returns:
        Tuple of (should_leave, reason)
    """
    bb = table.big_blind

    # Check if stack is too low (below rebuy threshold)
    bb_count = stack / bb if bb > 0 else 0

    # Leave if stack is very low and not worth rebuying
    if bb_count < 10:
        return True, "stack_too_low"

    # Check for big win
    if stack >= initial_stack * big_win_threshold:
        return True, "big_win"

    # 자연스러운 방 이동: 매 핸드 2% 확률로 그냥 떠남 (사람처럼)
    if random.random() < 0.02:
        return True, "wandering"

    return False, ""
