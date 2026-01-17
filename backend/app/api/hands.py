"""Hand history API endpoints.

Phase 2.5: 핸드 히스토리 조회 API
- GET /hands/{hand_id} - 핸드 상세 조회 (리플레이용)
- GET /hands/me - 현재 사용자의 핸드 히스토리
"""

from datetime import datetime
from math import ceil

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas import (
    ErrorResponse,
    HandDetailResponse,
    HandEventResponse,
    HandHistoryListResponse,
    HandParticipantResponse,
    HandSummaryResponse,
    PaginationMeta,
)
from app.services.hand_history import HandHistoryService

router = APIRouter(prefix="/hands", tags=["Hands"])


@router.get(
    "/me",
    response_model=HandHistoryListResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def get_my_hand_history(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(default=1, ge=1, description="페이지 번호"),
    page_size: int = Query(
        default=20, ge=1, le=100, alias="pageSize", description="페이지 크기"
    ),
):
    """현재 사용자의 핸드 히스토리 조회.

    최근 플레이한 핸드 목록을 페이지네이션과 함께 반환합니다.
    각 핸드에 대한 요약 정보와 사용자의 결과를 포함합니다.
    """
    offset = (page - 1) * page_size

    hand_service = HandHistoryService(db)
    hands = await hand_service.get_user_hand_history(
        user_id=current_user.id,
        limit=page_size + 1,  # 다음 페이지 존재 여부 확인용
        offset=offset,
    )

    # 다음 페이지 존재 여부 확인
    has_more = len(hands) > page_size
    if has_more:
        hands = hands[:page_size]

    # 응답 형식으로 변환
    hand_responses = []
    for hand in hands:
        hand_responses.append(
            HandSummaryResponse(
                hand_id=hand["hand_id"],
                table_id=hand["table_id"],
                hand_number=hand["hand_number"],
                started_at=_parse_datetime(hand.get("started_at")),
                ended_at=_parse_datetime(hand.get("ended_at")),
                pot_size=hand.get("pot_size", 0),
                community_cards=hand.get("community_cards", []),
                user_seat=hand.get("user_seat", 0),
                user_hole_cards=hand.get("user_hole_cards"),
                user_bet_amount=hand.get("user_bet_amount", 0),
                user_won_amount=hand.get("user_won_amount", 0),
                user_final_action=hand.get("user_final_action", "fold"),
                net_result=hand.get("net_result", 0),
            )
        )

    # 전체 개수 추정 (정확한 count 쿼리 대신 추정값 사용)
    # 실제 total count가 필요하면 별도 쿼리 추가
    total_estimate = offset + len(hands) + (1 if has_more else 0)

    return HandHistoryListResponse(
        hands=hand_responses,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total_items=total_estimate,
            total_pages=ceil(total_estimate / page_size) if total_estimate > 0 else 1,
        ),
    )


@router.get(
    "/{hand_id}",
    response_model=HandDetailResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "Hand not found"},
    },
)
async def get_hand_detail(
    hand_id: str,
    current_user: CurrentUser,
    db: DbSession,
):
    """핸드 상세 정보 조회.

    핸드 리플레이를 위한 상세 정보를 반환합니다.
    참가자 정보, 커뮤니티 카드, 이벤트 시퀀스를 포함합니다.

    Note: 사용자가 참가한 핸드만 조회할 수 있습니다.
    """
    hand_service = HandHistoryService(db)
    hand = await hand_service.get_hand_detail(hand_id)

    if not hand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "HAND_NOT_FOUND",
                    "message": "핸드를 찾을 수 없습니다.",
                    "details": {"hand_id": hand_id},
                }
            },
        )

    # 사용자가 이 핸드에 참가했는지 확인
    user_participated = any(
        p.get("user_id") == current_user.id for p in hand.get("participants", [])
    )

    if not user_participated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "HAND_NOT_FOUND",
                    "message": "핸드를 찾을 수 없습니다.",
                    "details": {"hand_id": hand_id},
                }
            },
        )

    # 참가자 정보 변환
    participants = []
    for p in hand.get("participants", []):
        participants.append(
            HandParticipantResponse(
                user_id=p["user_id"],
                seat=p.get("seat", 0),
                hole_cards=p.get("hole_cards"),
                bet_amount=p.get("bet_amount", 0),
                won_amount=p.get("won_amount", 0),
                final_action=p.get("final_action", "fold"),
                net_result=p.get("won_amount", 0) - p.get("bet_amount", 0),
            )
        )

    # 이벤트 정보 변환
    events = []
    for e in hand.get("events", []):
        events.append(
            HandEventResponse(
                seq_no=e.get("seq_no", 0),
                event_type=e.get("event_type", ""),
                payload=e.get("payload", {}),
                created_at=_parse_datetime(e.get("created_at")),
            )
        )

    return HandDetailResponse(
        hand_id=hand["hand_id"],
        table_id=hand["table_id"],
        hand_number=hand["hand_number"],
        started_at=_parse_datetime(hand.get("started_at")),
        ended_at=_parse_datetime(hand.get("ended_at")),
        initial_state=hand.get("initial_state"),
        result=hand.get("result"),
        participants=participants,
        events=events,
    )


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    """datetime 문자열을 datetime 객체로 변환."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
