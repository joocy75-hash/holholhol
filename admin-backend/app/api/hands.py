"""Hand History API for Admin Dashboard.

Provides endpoints for:
- Searching and listing hands
- Hand detail view for replay
- Hand export functionality

**Phase 3.4**: 핸드 리플레이 기능 구현
"""

import json
import logging
from datetime import datetime
from math import ceil
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_main_db
from app.models.admin_user import AdminUser
from app.models.main_db import Hand, HandEvent, HandParticipant, User, Table
from app.utils.dependencies import get_current_user
from app.utils.permissions import Permission, has_permission

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Request/Response Models
# ============================================================================


class HandSummary(BaseModel):
    """핸드 요약 정보"""
    id: str
    table_id: str
    table_name: str | None = None
    hand_number: int
    pot_size: int
    player_count: int
    started_at: datetime | None
    ended_at: datetime | None


class PaginatedHands(BaseModel):
    """핸드 목록 페이지네이션 응답"""
    items: list[HandSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class TimelineAction(BaseModel):
    """타임라인 액션 정보"""
    seq_no: int
    event_type: str
    player_id: str | None = None
    player_seat: int | None = None
    player_nickname: str | None = None
    amount: int | None = None
    cards: list[str] | None = None
    timestamp: datetime | None = None
    phase: str | None = None


class ParticipantInfo(BaseModel):
    """참가자 정보"""
    user_id: str
    nickname: str | None = None
    seat: int
    hole_cards: list[str] | None = None
    bet_amount: int
    won_amount: int
    final_action: str
    net_result: int


class InitialState(BaseModel):
    """핸드 시작 상태"""
    dealer_position: int | None = None
    small_blind: int
    big_blind: int
    players: list[dict]


class HandResult(BaseModel):
    """핸드 결과"""
    pot_total: int
    community_cards: list[str]
    winners: list[dict]


class HandDetail(BaseModel):
    """핸드 상세 정보 (리플레이용)"""
    id: str
    table_id: str
    table_name: str | None = None
    hand_number: int
    started_at: datetime | None
    ended_at: datetime | None
    initial_state: InitialState | None = None
    result: HandResult | None = None
    participants: list[ParticipantInfo]
    timeline: list[TimelineAction]
    pot_size: int
    community_cards: list[str]


class HandExport(BaseModel):
    """핸드 내보내기 응답"""
    hand_id: str
    format: str
    data: dict


# ============================================================================
# Helper Functions
# ============================================================================


def _parse_hole_cards(hole_cards_str: str | None) -> list[str] | None:
    """Parse hole cards from JSON string."""
    if not hole_cards_str:
        return None
    try:
        return json.loads(hole_cards_str)
    except json.JSONDecodeError:
        return None


def _extract_phase(event_type: str) -> str | None:
    """Extract phase from event type."""
    phase_map = {
        "deal_hole_cards": "preflop",
        "deal_flop": "flop",
        "deal_turn": "turn",
        "deal_river": "river",
        "showdown": "showdown",
        "hand_end": "finished",
    }
    return phase_map.get(event_type)


async def _get_user_nicknames(
    db: AsyncSession,
    user_ids: list[str],
) -> dict[str, str]:
    """Get user nicknames by user IDs."""
    if not user_ids:
        return {}

    query = select(User).where(User.id.in_(user_ids))
    result = await db.execute(query)
    users = result.scalars().all()

    return {user.id: user.nickname for user in users}


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("", response_model=PaginatedHands)
async def search_hands(
    hand_id: Optional[str] = Query(None, description="핸드 ID로 검색"),
    user_id: Optional[str] = Query(None, description="유저 ID로 검색"),
    table_id: Optional[str] = Query(None, description="테이블 ID로 검색"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_main_db),
):
    """핸드 검색 및 목록 조회.

    필터 조건:
    - hand_id: 특정 핸드 ID 검색
    - user_id: 특정 유저가 참가한 핸드 검색
    - table_id: 특정 테이블의 핸드 검색
    """
    if not has_permission(current_user.role, Permission.VIEW_HANDS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="VIEW_HANDS 권한이 필요합니다",
        )

    # Base query
    query = select(Hand).options(
        selectinload(Hand.participants)
    )

    # Apply filters
    if hand_id:
        query = query.where(Hand.id == hand_id)
    if table_id:
        query = query.where(Hand.table_id == table_id)
    if user_id:
        # Subquery for hands with this user
        subquery = (
            select(HandParticipant.hand_id)
            .where(HandParticipant.user_id == user_id)
            .distinct()
        )
        query = query.where(Hand.id.in_(subquery))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    offset = (page - 1) * page_size
    query = (
        query
        .order_by(desc(Hand.started_at))
        .limit(page_size)
        .offset(offset)
    )

    result = await db.execute(query)
    hands = result.scalars().all()

    # Get table names
    table_ids = list(set(h.table_id for h in hands))
    table_names = {}
    if table_ids:
        table_query = select(Table).where(Table.id.in_(table_ids))
        table_result = await db.execute(table_query)
        tables = table_result.scalars().all()
        table_names = {t.id: t.name for t in tables}

    # Build response
    items = []
    for hand in hands:
        pot_size = 0
        if hand.result:
            pot_size = hand.result.get("pot_total", 0)

        items.append(HandSummary(
            id=hand.id,
            table_id=hand.table_id,
            table_name=table_names.get(hand.table_id),
            hand_number=hand.hand_number,
            pot_size=pot_size,
            player_count=len(hand.participants),
            started_at=hand.started_at,
            ended_at=hand.ended_at,
        ))

    total_pages = ceil(total / page_size) if total > 0 else 1

    return PaginatedHands(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{hand_id}", response_model=HandDetail)
async def get_hand(
    hand_id: str,
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_main_db),
):
    """핸드 상세 조회 (리플레이용).

    관리자는 모든 핸드의 상세 정보를 조회할 수 있습니다.
    타임라인에는 모든 액션과 카드 딜링 이벤트가 포함됩니다.
    """
    if not has_permission(current_user.role, Permission.VIEW_HANDS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="VIEW_HANDS 권한이 필요합니다",
        )

    # Query hand with all related data
    query = (
        select(Hand)
        .where(Hand.id == hand_id)
        .options(
            selectinload(Hand.participants),
            selectinload(Hand.events),
        )
    )

    result = await db.execute(query)
    hand = result.scalar_one_or_none()

    if not hand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="핸드를 찾을 수 없습니다",
        )

    # Get table name
    table_name = None
    if hand.table_id:
        table_query = select(Table).where(Table.id == hand.table_id)
        table_result = await db.execute(table_query)
        table = table_result.scalar_one_or_none()
        if table:
            table_name = table.name

    # Get user nicknames
    user_ids = [p.user_id for p in hand.participants]
    nicknames = await _get_user_nicknames(db, user_ids)

    # Build participants list
    participants = []
    seat_to_user = {}  # For timeline lookup
    for p in hand.participants:
        hole_cards = _parse_hole_cards(p.hole_cards)
        seat_to_user[p.seat] = {
            "user_id": p.user_id,
            "nickname": nicknames.get(p.user_id, "Unknown"),
        }
        participants.append(ParticipantInfo(
            user_id=p.user_id,
            nickname=nicknames.get(p.user_id),
            seat=p.seat,
            hole_cards=hole_cards,
            bet_amount=p.bet_amount,
            won_amount=p.won_amount,
            final_action=p.final_action,
            net_result=p.won_amount - p.bet_amount,
        ))

    # Build timeline from events
    timeline = []
    current_phase = "preflop"
    for event in sorted(hand.events, key=lambda e: e.seq_no):
        payload = event.payload or {}

        # Determine phase from event type
        phase = _extract_phase(event.event_type)
        if phase:
            current_phase = phase

        # Get player info from payload
        player_id = payload.get("user_id")
        player_seat = payload.get("seat")
        player_nickname = None
        if player_seat is not None and player_seat in seat_to_user:
            player_id = seat_to_user[player_seat]["user_id"]
            player_nickname = seat_to_user[player_seat]["nickname"]

        # Get cards for deal events
        cards = None
        if "cards" in payload:
            cards = payload["cards"]
        elif "card" in payload:
            cards = [payload["card"]]

        timeline.append(TimelineAction(
            seq_no=event.seq_no,
            event_type=event.event_type,
            player_id=player_id,
            player_seat=player_seat,
            player_nickname=player_nickname,
            amount=payload.get("amount") or payload.get("total_bet"),
            cards=cards,
            timestamp=event.created_at,
            phase=current_phase,
        ))

    # Parse initial state
    initial_state = None
    if hand.initial_state:
        initial_state = InitialState(
            dealer_position=hand.initial_state.get("dealer_position"),
            small_blind=hand.initial_state.get("small_blind", 0),
            big_blind=hand.initial_state.get("big_blind", 0),
            players=hand.initial_state.get("players", []),
        )

    # Parse result
    hand_result = None
    community_cards = []
    pot_size = 0
    if hand.result:
        pot_size = hand.result.get("pot_total", 0)
        community_cards = hand.result.get("community_cards", [])
        hand_result = HandResult(
            pot_total=pot_size,
            community_cards=community_cards,
            winners=hand.result.get("winners", []),
        )

    return HandDetail(
        id=hand.id,
        table_id=hand.table_id,
        table_name=table_name,
        hand_number=hand.hand_number,
        started_at=hand.started_at,
        ended_at=hand.ended_at,
        initial_state=initial_state,
        result=hand_result,
        participants=participants,
        timeline=timeline,
        pot_size=pot_size,
        community_cards=community_cards,
    )


@router.get("/{hand_id}/export", response_model=HandExport)
async def export_hand(
    hand_id: str,
    format: str = Query("json", description="내보내기 형식"),
    current_user: AdminUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_main_db),
):
    """핸드 히스토리 내보내기.

    지원 형식:
    - json: 전체 핸드 데이터 JSON
    - text: 텍스트 형식 핸드 히스토리
    """
    if not has_permission(current_user.role, Permission.EXPORT_HANDS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="EXPORT_HANDS 권한이 필요합니다",
        )

    # Get hand detail
    query = (
        select(Hand)
        .where(Hand.id == hand_id)
        .options(
            selectinload(Hand.participants),
            selectinload(Hand.events),
        )
    )

    result = await db.execute(query)
    hand = result.scalar_one_or_none()

    if not hand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="핸드를 찾을 수 없습니다",
        )

    # Get table info
    table_query = select(Table).where(Table.id == hand.table_id)
    table_result = await db.execute(table_query)
    table = table_result.scalar_one_or_none()

    # Get user nicknames
    user_ids = [p.user_id for p in hand.participants]
    nicknames = await _get_user_nicknames(db, user_ids)

    if format == "json":
        # Full JSON export
        export_data = {
            "hand_id": hand.id,
            "table_id": hand.table_id,
            "table_name": table.name if table else None,
            "hand_number": hand.hand_number,
            "started_at": hand.started_at.isoformat() if hand.started_at else None,
            "ended_at": hand.ended_at.isoformat() if hand.ended_at else None,
            "initial_state": hand.initial_state,
            "result": hand.result,
            "participants": [
                {
                    "user_id": p.user_id,
                    "nickname": nicknames.get(p.user_id),
                    "seat": p.seat,
                    "hole_cards": _parse_hole_cards(p.hole_cards),
                    "bet_amount": p.bet_amount,
                    "won_amount": p.won_amount,
                    "final_action": p.final_action,
                }
                for p in hand.participants
            ],
            "events": [
                {
                    "seq_no": e.seq_no,
                    "event_type": e.event_type,
                    "payload": e.payload,
                    "timestamp": e.created_at.isoformat() if e.created_at else None,
                }
                for e in sorted(hand.events, key=lambda x: x.seq_no)
            ],
        }
    else:
        # Text format export (PokerStars-like format)
        lines = []
        lines.append(f"Hand #{hand.hand_number}")
        lines.append(f"Table: {table.name if table else 'Unknown'}")
        if hand.initial_state:
            sb = hand.initial_state.get("small_blind", 0)
            bb = hand.initial_state.get("big_blind", 0)
            lines.append(f"Blinds: {sb}/{bb}")
        lines.append("")

        # Participants
        lines.append("*** PLAYERS ***")
        for p in sorted(hand.participants, key=lambda x: x.seat):
            nickname = nicknames.get(p.user_id, "Unknown")
            lines.append(f"Seat {p.seat}: {nickname}")
        lines.append("")

        # Events
        lines.append("*** ACTIONS ***")
        for e in sorted(hand.events, key=lambda x: x.seq_no):
            payload = e.payload or {}
            seat = payload.get("seat")
            player_name = "Unknown"
            if seat is not None:
                for p in hand.participants:
                    if p.seat == seat:
                        player_name = nicknames.get(p.user_id, "Unknown")
                        break

            if e.event_type in ("fold", "check", "call", "bet", "raise", "all_in"):
                amount = payload.get("amount", "")
                if amount:
                    lines.append(f"{player_name}: {e.event_type} {amount}")
                else:
                    lines.append(f"{player_name}: {e.event_type}")
            elif e.event_type == "deal_flop":
                cards = payload.get("cards", [])
                lines.append(f"*** FLOP *** [{' '.join(cards)}]")
            elif e.event_type == "deal_turn":
                card = payload.get("card") or (payload.get("cards", [None])[0])
                lines.append(f"*** TURN *** [{card}]")
            elif e.event_type == "deal_river":
                card = payload.get("card") or (payload.get("cards", [None])[0])
                lines.append(f"*** RIVER *** [{card}]")
            elif e.event_type == "pot_won":
                amount = payload.get("amount", 0)
                lines.append(f"{player_name} wins pot ({amount})")

        export_data = {"text": "\n".join(lines)}

    return HandExport(
        hand_id=hand_id,
        format=format,
        data=export_data,
    )
