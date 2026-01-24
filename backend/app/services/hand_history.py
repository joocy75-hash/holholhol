"""Hand history storage and retrieval service.

This service handles:
- Saving completed hand results with participant details
- Retrieving user hand history
- Getting hand details for replay
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.hand import Hand, HandEvent, HandParticipant

logger = logging.getLogger(__name__)


class HandHistoryService:
    """Hand history storage and retrieval service.

    Usage:
        service = HandHistoryService(db_session)

        # Save completed hand
        hand_id = await service.save_hand_result(hand_result)

        # Get user's hand history
        hands = await service.get_user_hand_history(user_id, limit=50)

        # Get hand details for replay
        details = await service.get_hand_detail(hand_id)
    """

    def __init__(self, db: AsyncSession):
        """Initialize service with database session.

        Args:
            db: Async SQLAlchemy session
        """
        self._db = db

    async def save_hand_result(self, hand_result: dict) -> str:
        """Save completed hand result with participant details.

        Args:
            hand_result: Hand result dictionary containing:
                - hand_id: Existing hand ID (optional, creates new if not provided)
                - table_id: Table ID
                - hand_number: Hand number within table
                - pot_size: Total pot size
                - community_cards: List of community cards
                - participants: List of participant details

        Returns:
            Hand ID (UUID string)

        Raises:
            ValueError: If required fields are missing
        """
        # Validate required fields
        required_fields = ["table_id", "hand_number", "participants"]
        for field in required_fields:
            if field not in hand_result:
                raise ValueError(f"Missing required field: {field}")

        hand_id = hand_result.get("hand_id") or str(uuid4())
        table_id = hand_result["table_id"]
        hand_number = hand_result["hand_number"]
        participants = hand_result["participants"]
        pot_size = hand_result.get("pot_size", 0)
        community_cards = hand_result.get("community_cards", [])

        # Check if hand already exists
        existing_hand = await self._db.get(Hand, hand_id)

        if existing_hand:
            # Update existing hand with result
            existing_hand.ended_at = datetime.now(timezone.utc)
            existing_hand.result = {
                "pot_total": pot_size,
                "community_cards": community_cards,
                "winners": [
                    p for p in participants if p.get("won_amount", 0) > 0
                ],
            }
            hand = existing_hand
        else:
            # Create new hand record
            hand = Hand(
                id=hand_id,
                table_id=table_id,
                hand_number=hand_number,
                started_at=hand_result.get("started_at", datetime.now(timezone.utc)),
                ended_at=datetime.now(timezone.utc),
                initial_state={
                    "participants": [
                        {"user_id": p["user_id"], "seat": p["seat"]}
                        for p in participants
                        if p.get("user_id")
                    ],
                },
                result={
                    "pot_total": pot_size,
                    "community_cards": community_cards,
                    "winners": [
                        p for p in participants if p.get("won_amount", 0) > 0
                    ],
                },
            )
            self._db.add(hand)

        # Save participant details
        for participant in participants:
            user_id = participant.get("user_id")
            if not user_id:
                continue

            # Convert hole_cards list to JSON string
            hole_cards = participant.get("hole_cards")
            hole_cards_str = json.dumps(hole_cards) if hole_cards else None

            hand_participant = HandParticipant(
                id=str(uuid4()),
                hand_id=hand_id,
                user_id=user_id,
                seat=participant.get("seat", 0),
                hole_cards=hole_cards_str,
                bet_amount=participant.get("bet_amount", 0),
                won_amount=participant.get("won_amount", 0),
                final_action=participant.get("final_action", "fold"),
            )
            self._db.add(hand_participant)

        await self._db.commit()

        logger.info(
            f"Saved hand {hand_id} with {len(participants)} participants"
        )

        return hand_id

    async def get_user_hand_history(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get user's hand history.

        Args:
            user_id: User ID
            limit: Maximum number of hands to return
            offset: Number of hands to skip

        Returns:
            List of hand summaries
        """
        # Query hand participants for this user
        query = (
            select(HandParticipant)
            .where(HandParticipant.user_id == user_id)
            .options(selectinload(HandParticipant.hand))
            .order_by(desc(HandParticipant.created_at))
            .limit(limit)
            .offset(offset)
        )

        result = await self._db.execute(query)
        participants = result.scalars().all()

        hands = []
        for participant in participants:
            hand = participant.hand
            if not hand:
                continue

            # Parse hole cards from JSON string
            hole_cards = None
            if participant.hole_cards:
                try:
                    hole_cards = json.loads(participant.hole_cards)
                except json.JSONDecodeError:
                    hole_cards = None

            hands.append({
                "hand_id": hand.id,
                "table_id": hand.table_id,
                "hand_number": hand.hand_number,
                "started_at": hand.started_at.isoformat() if hand.started_at else None,
                "ended_at": hand.ended_at.isoformat() if hand.ended_at else None,
                "pot_size": hand.result.get("pot_total", 0) if hand.result else 0,
                "community_cards": hand.result.get("community_cards", []) if hand.result else [],
                "user_seat": participant.seat,
                "user_hole_cards": hole_cards,
                "user_bet_amount": participant.bet_amount,
                "user_won_amount": participant.won_amount,
                "user_final_action": participant.final_action,
                "net_result": participant.won_amount - participant.bet_amount,
            })

        return hands

    async def get_hand_detail(self, hand_id: str) -> dict[str, Any] | None:
        """Get detailed hand information for replay.

        Args:
            hand_id: Hand ID

        Returns:
            Hand details including all participants and events, or None if not found
        """
        # Query hand with participants and events
        query = (
            select(Hand)
            .where(Hand.id == hand_id)
            .options(
                selectinload(Hand.participants),
                selectinload(Hand.events),
            )
        )

        result = await self._db.execute(query)
        hand = result.scalar_one_or_none()

        if not hand:
            return None

        # Build participant list
        participants = []
        for p in hand.participants:
            hole_cards = None
            if p.hole_cards:
                try:
                    hole_cards = json.loads(p.hole_cards)
                except json.JSONDecodeError:
                    hole_cards = None

            participants.append({
                "user_id": p.user_id,
                "seat": p.seat,
                "hole_cards": hole_cards,
                "bet_amount": p.bet_amount,
                "won_amount": p.won_amount,
                "final_action": p.final_action,
            })

        # Build event list
        events = []
        for e in sorted(hand.events, key=lambda x: x.seq_no):
            events.append({
                "seq_no": e.seq_no,
                "event_type": e.event_type,
                "payload": e.payload,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            })

        return {
            "hand_id": hand.id,
            "table_id": hand.table_id,
            "hand_number": hand.hand_number,
            "started_at": hand.started_at.isoformat() if hand.started_at else None,
            "ended_at": hand.ended_at.isoformat() if hand.ended_at else None,
            "initial_state": hand.initial_state,
            "result": hand.result,
            "participants": participants,
            "events": events,
        }

    async def get_hands_for_fraud_analysis(
        self,
        user_ids: list[str],
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        """Get recent hands involving specific users for fraud analysis.

        Args:
            user_ids: List of user IDs to analyze
            hours: Number of hours to look back

        Returns:
            List of hand summaries with participant details
        """
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Query hand participants for these users
        query = (
            select(HandParticipant)
            .where(
                HandParticipant.user_id.in_(user_ids),
                HandParticipant.created_at >= cutoff,
            )
            .options(selectinload(HandParticipant.hand))
            .order_by(desc(HandParticipant.created_at))
        )

        result = await self._db.execute(query)
        participants = result.scalars().all()

        # Group by hand_id
        hands_map: dict[str, dict] = {}
        for p in participants:
            hand = p.hand
            if not hand:
                continue

            if hand.id not in hands_map:
                hands_map[hand.id] = {
                    "hand_id": hand.id,
                    "table_id": hand.table_id,
                    "hand_number": hand.hand_number,
                    "ended_at": hand.ended_at.isoformat() if hand.ended_at else None,
                    "pot_size": hand.result.get("pot_total", 0) if hand.result else 0,
                    "participants": [],
                }

            hole_cards = None
            if p.hole_cards:
                try:
                    hole_cards = json.loads(p.hole_cards)
                except json.JSONDecodeError:
                    hole_cards = None

            hands_map[hand.id]["participants"].append({
                "user_id": p.user_id,
                "seat": p.seat,
                "hole_cards": hole_cards,
                "bet_amount": p.bet_amount,
                "won_amount": p.won_amount,
                "final_action": p.final_action,
            })

        return list(hands_map.values())
