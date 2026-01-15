"""Room matching service for Quick Join functionality.

Provides intelligent room matching based on user preferences and room availability.
"""

from __future__ import annotations

import random
import logging
from typing import TYPE_CHECKING

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.room import Room, RoomStatus
from app.models.table import Table
from app.utils.errors import (
    NoAvailableRoomError,
    InsufficientBalanceError,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# Blind level ranges
BLIND_LEVELS = {
    "low": {"min_sb": 5, "max_sb": 25},      # 5/10 ~ 25/50
    "medium": {"min_sb": 25, "max_sb": 100},  # 25/50 ~ 100/200
    "high": {"min_sb": 100, "max_sb": 1000},  # 100/200+
}


def calculate_room_score(room: Room) -> int:
    """Calculate priority score for room selection.
    
    Higher score = higher priority.
    
    Scoring:
    - Playing status: +100 (prefer active games)
    - Player count: +10 per player (prefer fuller tables)
    - Fewer empty seats: +5 per occupied seat (prefer active tables)
    
    Args:
        room: Room to score
        
    Returns:
        Priority score (higher is better)
    """
    score = 0
    
    # 1. Prefer rooms with active games (+100)
    if room.status == RoomStatus.PLAYING.value:
        score += 100
    elif room.status == RoomStatus.WAITING.value:
        score += 50
    
    # 2. Prefer rooms with more players (+10 per player)
    score += room.current_players * 10
    
    # 3. Prefer rooms with fewer empty seats (more active)
    max_seats = room.config.get("max_seats", 6)
    occupied_ratio = room.current_players / max_seats if max_seats > 0 else 0
    score += int(occupied_ratio * 20)
    
    return score


def calculate_default_buy_in(
    buy_in_min: int,
    buy_in_max: int,
    user_balance: int,
) -> int:
    """Calculate default buy-in amount.
    
    Default is 50% of max buy-in, capped by user balance.
    
    Args:
        buy_in_min: Minimum buy-in for the room
        buy_in_max: Maximum buy-in for the room
        user_balance: User's current balance
        
    Returns:
        Calculated buy-in amount
        
    Raises:
        InsufficientBalanceError: If balance < min buy-in
    """
    if user_balance < buy_in_min:
        raise InsufficientBalanceError(balance=user_balance, min_buy_in=buy_in_min)
    
    # Default: 50% of max buy-in
    default_buy_in = buy_in_max // 2
    
    # Cap by user balance
    if user_balance < default_buy_in:
        default_buy_in = user_balance
    
    # Ensure at least min buy-in
    if default_buy_in < buy_in_min:
        default_buy_in = buy_in_min
    
    # Cap at max buy-in
    if default_buy_in > buy_in_max:
        default_buy_in = buy_in_max
    
    return default_buy_in


class RoomMatcher:
    """Matches users to optimal rooms based on criteria.
    
    Provides intelligent room selection for Quick Join functionality.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def find_best_room(
        self,
        user_id: str,
        user_balance: int,
        blind_level: str | None = None,
        exclude_room_ids: list[str] | None = None,
    ) -> Room | None:
        """Find the best available room for the user.
        
        Args:
            user_id: User ID (to exclude rooms they're already in)
            user_balance: User's current balance
            blind_level: Optional blind level filter ('low', 'medium', 'high', or '10/20')
            exclude_room_ids: Room IDs to exclude (e.g., rooms user is already in)
            
        Returns:
            Best matching Room or None if no suitable room found
        """
        # Build query for available rooms
        query = select(Room).options(
            selectinload(Room.tables)
        ).where(
            and_(
                Room.status.in_([RoomStatus.WAITING.value, RoomStatus.PLAYING.value]),
                Room.current_players < Room.max_seats,  # Has empty seats
            )
        )
        
        # Exclude rooms user is already in
        if exclude_room_ids:
            query = query.where(Room.id.notin_(exclude_room_ids))
        
        result = await self.db.execute(query)
        rooms = list(result.scalars().all())
        
        if not rooms:
            return None
        
        # Filter by user balance (must afford min buy-in)
        affordable_rooms = [
            room for room in rooms
            if room.config.get("buy_in_min", 400) <= user_balance
        ]
        
        if not affordable_rooms:
            return None
        
        # Filter by blind level if specified
        if blind_level:
            affordable_rooms = self._filter_by_blind_level(affordable_rooms, blind_level)
            if not affordable_rooms:
                return None
        
        # Score and sort rooms
        scored_rooms = [
            (room, calculate_room_score(room))
            for room in affordable_rooms
        ]
        scored_rooms.sort(key=lambda x: x[1], reverse=True)
        
        # Get rooms with the highest score
        if not scored_rooms:
            return None
        
        max_score = scored_rooms[0][1]
        top_rooms = [room for room, score in scored_rooms if score == max_score]
        
        # Random selection among top rooms (for fairness)
        return random.choice(top_rooms)
    
    def _filter_by_blind_level(
        self,
        rooms: list[Room],
        blind_level: str,
    ) -> list[Room]:
        """Filter rooms by blind level.
        
        Args:
            rooms: List of rooms to filter
            blind_level: 'low', 'medium', 'high', or specific like '10/20'
            
        Returns:
            Filtered list of rooms
        """
        if "/" in blind_level:
            # Specific blind level like "10/20"
            parts = blind_level.split("/")
            try:
                target_sb = int(parts[0])
                target_bb = int(parts[1])
                return [
                    room for room in rooms
                    if room.small_blind == target_sb and room.big_blind == target_bb
                ]
            except (ValueError, IndexError):
                return rooms
        
        # Named level
        level_config = BLIND_LEVELS.get(blind_level.lower())
        if not level_config:
            return rooms
        
        min_sb = level_config["min_sb"]
        max_sb = level_config["max_sb"]
        
        return [
            room for room in rooms
            if min_sb <= room.small_blind <= max_sb
        ]
    
    def get_available_seat(self, room: Room) -> int | None:
        """Find an available seat in the room.
        
        Args:
            room: Room to check
            
        Returns:
            Available seat number or None if full
        """
        if not room.tables:
            return None
        
        table = room.tables[0]  # Assume one table per room
        seats = table.seats or {}
        max_seats = room.config.get("max_seats", 6)
        
        # Find first empty seat
        for seat_num in range(max_seats):
            seat_key = str(seat_num)
            if seat_key not in seats or seats[seat_key] is None:
                return seat_num
        
        return None
    
    async def get_user_room_ids(self, user_id: str) -> list[str]:
        """Get room IDs where user is currently seated.
        
        Args:
            user_id: User ID to check
            
        Returns:
            List of room IDs where user is seated
        """
        # Query tables where user is seated
        query = select(Table).where(
            Table.seats.contains({user_id: {}})  # JSON contains check
        )
        
        # Alternative: Check each table's seats
        all_tables_query = select(Table)
        result = await self.db.execute(all_tables_query)
        tables = result.scalars().all()
        
        room_ids = []
        for table in tables:
            if table.seats:
                for seat_key, seat_data in table.seats.items():
                    if seat_data and seat_data.get("user_id") == user_id:
                        room_ids.append(str(table.room_id))
                        break
        
        return room_ids
