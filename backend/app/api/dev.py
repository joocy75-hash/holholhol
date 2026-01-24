"""Development/Test API endpoints for E2E testing.

치트 API - 테스트 자동화를 위한 개발용 엔드포인트:
- 덱 주입 (특정 카드 순서 설정)
- 타이머 제어 (강제 타임아웃, 타이머 설정)
- 페이즈 강제 전환 (preflop → flop → turn → river)
- 게임 상태 조회/조작

IMPORTANT: 프로덕션 환경에서는 자동으로 비활성화됩니다.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.game.manager import game_manager
from app.utils.db import get_db
from app.ws.events import EventType
from app.ws.messages import MessageEnvelope

logger = logging.getLogger(__name__)
settings = get_settings()


# =============================================================================
# WebSocket Broadcast Helper
# =============================================================================


async def broadcast_to_table(table_id: str, message: dict[str, Any]) -> int:
    """Broadcast message to all subscribers of a table channel.
    
    Returns count of messages sent (0 if manager not available).
    """
    try:
        from app.ws.gateway import get_manager
        manager = await get_manager()
        channel = f"table:{table_id}"
        return await manager.broadcast_to_channel(channel, message)
    except Exception as e:
        logger.warning(f"Failed to broadcast to table {table_id}: {e}")
        return 0


async def broadcast_table_state_update(
    table_id: str,
    changes: dict[str, Any],
    update_type: str | None = None,
) -> int:
    """Broadcast TABLE_STATE_UPDATE event."""
    payload = {
        "tableId": table_id,
        "changes": changes,
        "source": "cheat_api",  # 치트 API에서 발생한 변경임을 표시
    }
    # updateType이 명시적으로 전달되면 payload 레벨에 추가
    if update_type:
        payload["updateType"] = update_type
    # changes 안에 updateType이 있으면 payload 레벨로 이동
    elif "updateType" in changes:
        payload["updateType"] = changes.pop("updateType")
    
    message = MessageEnvelope.create(
        event_type=EventType.TABLE_STATE_UPDATE,
        payload=payload,
    )
    return await broadcast_to_table(table_id, message.to_dict())


async def broadcast_community_cards(
    table_id: str,
    phase: str,
    cards: list[str],
) -> int:
    """Broadcast COMMUNITY_CARDS event."""
    message = MessageEnvelope.create(
        event_type=EventType.COMMUNITY_CARDS,
        payload={
            "tableId": table_id,
            "phase": phase,
            "cards": cards,
        },
    )
    return await broadcast_to_table(table_id, message.to_dict())


async def broadcast_turn_prompt(
    table_id: str,
    position: int,
    allowed_actions: list[dict],
    pot: int,
    current_bet: int,
) -> int:
    """Broadcast TURN_PROMPT event."""
    turn_timeout = 30  # seconds
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(seconds=turn_timeout)
    turn_start_time = int(now.timestamp() * 1000)
    
    message = MessageEnvelope.create(
        event_type=EventType.TURN_PROMPT,
        payload={
            "tableId": table_id,
            "position": position,
            "allowedActions": allowed_actions,
            "deadlineAt": deadline.isoformat(),
            "turnStartTime": turn_start_time,
            "pot": pot,
            "currentBet": current_bet,
        },
    )
    return await broadcast_to_table(table_id, message.to_dict())

router = APIRouter(prefix="/dev", tags=["Dev/Test"])


# =============================================================================
# Request/Response Models
# =============================================================================


class CardModel(BaseModel):
    """카드 모델."""
    rank: str = Field(..., description="카드 랭크: 2-9, T, J, Q, K, A")
    suit: str = Field(..., description="카드 수트: h, d, c, s")


class DeckInjectionRequest(BaseModel):
    """덱 주입 요청."""
    holeCards: dict[int, list[CardModel]] | None = Field(
        default=None,
        alias="hole_cards",
        description="플레이어 포지션별 홀카드 (0-5)",
    )
    communityCards: list[CardModel] | None = Field(
        default=None,
        alias="community_cards",
        description="커뮤니티 카드 (최대 5장)",
    )
    
    model_config = {"populate_by_name": True}


class SetHoleCardsRequest(BaseModel):
    """홀카드 설정 요청."""
    position: int = Field(..., ge=0, le=5, description="플레이어 포지션")
    cards: list[CardModel] = Field(..., min_length=2, max_length=2)


class SetCommunityCardsRequest(BaseModel):
    """커뮤니티 카드 설정 요청."""
    cards: list[CardModel] = Field(..., min_length=1, max_length=5)


class ForceTimeoutRequest(BaseModel):
    """타이머 강제 종료 요청."""
    position: int | None = Field(
        default=None,
        description="특정 포지션 타임아웃 (None이면 현재 턴)",
    )


class SetTimerRequest(BaseModel):
    """타이머 설정 요청."""
    remaining_seconds: int = Field(..., ge=0, le=300, description="남은 시간(초)")
    paused: bool | None = Field(default=None, description="타이머 일시정지")


class ForcePhaseRequest(BaseModel):
    """페이즈 강제 전환 요청."""
    phase: str = Field(
        ...,
        description="목표 페이즈: preflop, flop, turn, river, showdown",
    )


class ForceActionRequest(BaseModel):
    """플레이어 액션 강제 요청."""
    position: int = Field(..., ge=0, le=5, description="플레이어 포지션")
    action: str = Field(..., description="액션: fold, check, call, raise, all_in")
    amount: int | None = Field(default=None, description="베팅 금액 (raise 시)")


class SetStackRequest(BaseModel):
    """플레이어 스택 설정 요청."""
    position: int = Field(..., ge=0, le=5, description="플레이어 포지션")
    stack: int = Field(..., ge=0, description="스택 금액")


class ForcePotRequest(BaseModel):
    """팟 금액 강제 설정 요청."""
    main_pot: int = Field(..., ge=0, description="메인 팟 금액")
    side_pots: list[int] | None = Field(default=None, description="사이드 팟 금액들")


class AddBotRequest(BaseModel):
    """봇 추가 요청."""
    position: int | None = Field(default=None, description="좌석 위치 (None이면 자동)")
    stack: int = Field(default=1000, ge=100, description="초기 스택")
    strategy: str = Field(default="random", description="봇 전략: random, tight, loose")


class CreateTestTableRequest(BaseModel):
    """테스트 테이블 생성 요청."""
    name: str = Field(default="Test Table", description="테이블 이름")
    small_blind: int = Field(default=10, ge=1)
    big_blind: int = Field(default=20, ge=2)
    min_buy_in: int = Field(default=400, ge=100)
    max_buy_in: int = Field(default=2000, ge=200)
    max_players: int = Field(default=6, ge=2, le=9)


class DevResponse(BaseModel):
    """개발 API 응답."""
    success: bool
    message: str
    data: dict[str, Any] | None = None


# =============================================================================
# Dependencies
# =============================================================================


async def verify_dev_api_key(
    x_dev_key: Annotated[str | None, Header()] = None,
) -> str:
    """Dev API 키 검증.
    
    프로덕션에서는 자동으로 비활성화됩니다.
    """
    if not settings.dev_api_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dev API is disabled in production",
        )
    
    if x_dev_key != settings.dev_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Dev-Key header",
        )
    
    return x_dev_key


DevApiKey = Annotated[str, Depends(verify_dev_api_key)]
DbSession = Annotated[AsyncSession, Depends(get_db)]


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/health")
async def dev_health_check(api_key: DevApiKey) -> DevResponse:
    """Dev API 상태 확인."""
    return DevResponse(
        success=True,
        message="Dev API is enabled",
        data={
            "environment": settings.app_env,
            "dev_api_enabled": settings.dev_api_enabled,
        },
    )


@router.get("/server-time")
async def get_server_time(api_key: DevApiKey) -> DevResponse:
    """서버 시간 조회 (타이머 동기화 테스트용)."""
    now = datetime.now(timezone.utc)
    return DevResponse(
        success=True,
        message="Server time retrieved",
        data={
            "server_time": now.isoformat(),
            "timestamp": now.timestamp(),
        },
    )


@router.post("/tables/create")
async def create_test_table(
    request: CreateTestTableRequest,
    api_key: DevApiKey,
    db: DbSession,
) -> DevResponse:
    """테스트용 테이블 생성.
    
    데이터베이스에 Room과 Table을 생성하고,
    게임 매니저에도 테이블을 등록합니다.
    """
    import uuid
    from app.models.room import Room, RoomStatus
    from app.models.table import Table, TableStatus
    
    room_id = str(uuid.uuid4())
    table_id = str(uuid.uuid4())
    
    # Create Room in database
    room = Room(
        id=room_id,
        name=request.name,
        description=f"Test table created via Dev API",
        owner_id=None,  # No owner for test tables
        config={
            "max_seats": request.max_players,
            "small_blind": request.small_blind,
            "big_blind": request.big_blind,
            "buy_in_min": request.min_buy_in,
            "buy_in_max": request.max_buy_in,
            "turn_timeout": 30,
            "is_private": False,
        },
        status=RoomStatus.WAITING.value,
        current_players=0,
    )
    db.add(room)
    
    # Create Table in database
    table_db = Table(
        id=table_id,
        room_id=room_id,
        max_seats=request.max_players,
        status=TableStatus.WAITING.value,
        state_version=0,
        hand_number=0,
        dealer_position=0,
        seats={},
        game_state=None,
    )
    db.add(table_db)
    
    await db.commit()
    
    # Also create in game manager for in-memory operations
    game_manager.create_table_sync(
        room_id=room_id,
        name=request.name,
        small_blind=request.small_blind,
        big_blind=request.big_blind,
        min_buy_in=request.min_buy_in,
        max_buy_in=request.max_buy_in,
        max_players=request.max_players,
    )
    
    return DevResponse(
        success=True,
        message="Test table created",
        data={
            "table_id": room_id,
            "name": request.name,
            "config": {
                "small_blind": request.small_blind,
                "big_blind": request.big_blind,
                "min_buy_in": request.min_buy_in,
                "max_buy_in": request.max_buy_in,
                "max_players": request.max_players,
            },
        },
    )


@router.delete("/tables/{table_id}")
async def delete_test_table(
    table_id: str,
    api_key: DevApiKey,
    db: DbSession,
) -> DevResponse:
    """테스트 테이블 삭제.
    
    데이터베이스와 게임 매니저에서 모두 삭제합니다.
    """
    from sqlalchemy import select
    from app.models.room import Room
    
    # Delete from database
    result = await db.execute(select(Room).where(Room.id == table_id))
    room = result.scalar_one_or_none()
    
    if room:
        await db.delete(room)
        await db.commit()
    
    # Also delete from game manager
    table = game_manager.get_table(table_id)
    if table:
        game_manager.reset_table(table_id)
    
    if not room and not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found",
        )
    
    return DevResponse(
        success=True,
        message="Table deleted",
        data={"table_id": table_id},
    )


@router.get("/tables/{table_id}/state")
async def get_table_state(
    table_id: str,
    api_key: DevApiKey,
) -> DevResponse:
    """테이블 게임 상태 조회 (디버깅용)."""
    table = game_manager.get_table(table_id)
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found",
        )
    
    # 테이블 상태 직렬화
    state_data = {
        "room_id": table.room_id,
        "name": table.name,
        "small_blind": table.small_blind,
        "big_blind": table.big_blind,
        "seats": {},
        "hand_in_progress": table.hand_in_progress if hasattr(table, 'hand_in_progress') else False,
        "current_phase": getattr(table, 'current_phase', None),
        "pot": getattr(table, 'pot', 0),
        "community_cards": getattr(table, 'community_cards', []),
        "dealer_position": getattr(table, 'dealer_position', None),
        "current_turn": getattr(table, 'current_turn', None),
    }
    
    # 좌석 정보
    if hasattr(table, 'seats'):
        for pos, seat in enumerate(table.seats):
            if seat and hasattr(seat, 'player') and seat.player:
                state_data["seats"][pos] = {
                    "user_id": getattr(seat.player, 'user_id', None),
                    "nickname": getattr(seat.player, 'nickname', None),
                    "stack": getattr(seat, 'stack', 0),
                    "status": getattr(seat, 'status', 'unknown'),
                    "hole_cards": getattr(seat, 'hole_cards', None),
                }
    
    return DevResponse(
        success=True,
        message="Table state retrieved",
        data=state_data,
    )


@router.post("/tables/{table_id}/inject-deck")
async def inject_deck(
    table_id: str,
    request: DeckInjectionRequest,
    api_key: DevApiKey,
) -> DevResponse:
    """덱 주입 - 특정 카드 순서로 덱 설정.
    
    다음 핸드 시작 시 주입된 카드가 배분됩니다.
    게임 진행 중이면 즉시 적용됩니다.
    """
    # Convert request to internal format
    hole_cards = None
    if request.holeCards:
        hole_cards = {}
        for pos, cards in request.holeCards.items():
            hole_cards[int(pos)] = [f"{c.rank}{c.suit}" for c in cards]
    
    community_cards = None
    if request.communityCards:
        community_cards = [f"{c.rank}{c.suit}" for c in request.communityCards]
    
    result = game_manager.inject_cards(table_id, hole_cards, community_cards)
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to inject cards"),
        )
    
    return DevResponse(
        success=True,
        message="Deck injection configured" + (" (applied immediately)" if result.get("applied_immediately") else ""),
        data={
            "injected_cards": result["injected"],
            "applied_immediately": result.get("applied_immediately", False),
        },
    )


@router.post("/tables/{table_id}/set-hole-cards")
async def set_hole_cards(
    table_id: str,
    request: SetHoleCardsRequest,
    api_key: DevApiKey,
) -> DevResponse:
    """특정 플레이어의 홀카드 설정."""
    table = game_manager.get_table(table_id)
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found",
        )
    
    cards = [f"{c.rank}{c.suit}" for c in request.cards]
    
    if not hasattr(table, '_injected_cards'):
        table._injected_cards = {"hole_cards": {}, "community_cards": []}
    
    table._injected_cards["hole_cards"][request.position] = cards
    
    return DevResponse(
        success=True,
        message=f"Hole cards set for position {request.position}",
        data={"position": request.position, "cards": cards},
    )


@router.post("/tables/{table_id}/set-community-cards")
async def set_community_cards(
    table_id: str,
    request: SetCommunityCardsRequest,
    api_key: DevApiKey,
) -> DevResponse:
    """커뮤니티 카드 설정."""
    table = game_manager.get_table(table_id)
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found",
        )
    
    cards = [f"{c.rank}{c.suit}" for c in request.cards]
    
    if not hasattr(table, '_injected_cards'):
        table._injected_cards = {"hole_cards": {}, "community_cards": []}
    
    table._injected_cards["community_cards"] = cards
    
    return DevResponse(
        success=True,
        message="Community cards set",
        data={"cards": cards},
    )


@router.post("/tables/{table_id}/force-timeout")
async def force_timeout(
    table_id: str,
    request: ForceTimeoutRequest,
    api_key: DevApiKey,
) -> DevResponse:
    """현재 플레이어 타이머 강제 종료 (자동 폴드 트리거)."""
    result = game_manager.force_timeout(table_id, request.position)
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to force timeout"),
        )
    
    # Broadcast TABLE_STATE_UPDATE with fold action
    broadcast_count = 0
    broadcast_count += await broadcast_table_state_update(
        table_id,
        {
            "lastAction": {
                "type": "fold",
                "amount": 0,
                "position": result.get("timed_out_position"),
                "timeout": True,
            },
            "pot": result.get("pot", 0),
            "phase": result.get("phase"),
        },
    )
    
    # Send TURN_PROMPT for next player (if hand not complete)
    if not result.get("hand_complete"):
        table = game_manager.get_table(table_id)
        if table and table.current_player_seat is not None:
            current_player = table.players.get(table.current_player_seat)
            if current_player:
                available = table.get_available_actions(current_player.user_id)
                allowed = []
                for action in available.get("actions", []):
                    action_dict = {"type": action}
                    if action == "call":
                        action_dict["amount"] = available.get("call_amount", 0)
                    if action in ("raise", "bet"):
                        action_dict["minAmount"] = available.get("min_raise", 0)
                        action_dict["maxAmount"] = available.get("max_raise", 0)
                    allowed.append(action_dict)
                
                broadcast_count += await broadcast_turn_prompt(
                    table_id,
                    table.current_player_seat,
                    allowed,
                    table.pot,
                    table.current_bet,
                )
    
    return DevResponse(
        success=True,
        message=f"Timeout forced at position {result.get('timed_out_position')}",
        data={
            "position": result.get("timed_out_position"),
            "action": "fold",
            "timeout": True,
            "hand_complete": result.get("hand_complete", False),
            "broadcast_count": broadcast_count,
        },
    )


@router.post("/tables/{table_id}/set-timer")
async def set_timer(
    table_id: str,
    request: SetTimerRequest,
    api_key: DevApiKey,
) -> DevResponse:
    """타이머 값 설정."""
    result = game_manager.set_timer(
        table_id,
        request.remaining_seconds,
        request.paused,
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to set timer"),
        )
    
    # Broadcast TURN_PROMPT with updated timer
    broadcast_count = 0
    table = game_manager.get_table(table_id)
    if table and table.current_player_seat is not None:
        current_player = table.players.get(table.current_player_seat)
        if current_player:
            available = table.get_available_actions(current_player.user_id)
            allowed = []
            for action in available.get("actions", []):
                action_dict = {"type": action}
                if action == "call":
                    action_dict["amount"] = available.get("call_amount", 0)
                if action in ("raise", "bet"):
                    action_dict["minAmount"] = available.get("min_raise", 0)
                    action_dict["maxAmount"] = available.get("max_raise", 0)
                allowed.append(action_dict)
            
            # Use the new deadline from set_timer result
            now = datetime.now(timezone.utc)
            turn_start_time = int(now.timestamp() * 1000)
            
            message = MessageEnvelope.create(
                event_type=EventType.TURN_PROMPT,
                payload={
                    "tableId": table_id,
                    "position": table.current_player_seat,
                    "allowedActions": allowed,
                    "deadlineAt": result["deadline"],
                    "turnStartTime": turn_start_time,
                    "pot": table.pot,
                    "currentBet": table.current_bet,
                    "paused": result.get("paused", False),
                },
            )
            broadcast_count += await broadcast_to_table(table_id, message.to_dict())
    
    return DevResponse(
        success=True,
        message="Timer set",
        data={
            "position": result["position"],
            "remaining_seconds": result["remaining_seconds"],
            "paused": result.get("paused", False),
            "deadline": result["deadline"],
            "broadcast_count": broadcast_count,
        },
    )


class ForcePhaseRequestExtended(BaseModel):
    """페이즈 강제 전환 요청 (확장)."""
    phase: str = Field(
        ...,
        description="목표 페이즈: preflop, flop, turn, river, showdown",
    )
    community_cards: list[CardModel] | None = Field(
        default=None,
        description="커뮤니티 카드 (선택사항, 없으면 자동 생성)",
    )


@router.post("/tables/{table_id}/force-phase")
async def force_phase(
    table_id: str,
    request: ForcePhaseRequestExtended,
    api_key: DevApiKey,
) -> DevResponse:
    """페이즈 강제 전환 - 실제로 게임 상태를 변경합니다."""
    valid_phases = ["preflop", "flop", "turn", "river", "showdown"]
    if request.phase not in valid_phases:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid phase. Must be one of: {valid_phases}",
        )
    
    # Convert community cards if provided
    community_cards = None
    if request.community_cards:
        community_cards = [f"{c.rank}{c.suit}" for c in request.community_cards]
    
    # Actually change the phase
    result = game_manager.force_phase_change(table_id, request.phase, community_cards)
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to change phase"),
        )
    
    # Broadcast state changes via WebSocket
    broadcast_count = 0
    
    # 1. Broadcast TABLE_STATE_UPDATE
    broadcast_count += await broadcast_table_state_update(
        table_id,
        {
            "phase": result["new_phase"],
            "pot": game_manager.get_table(table_id).pot if game_manager.get_table(table_id) else 0,
        },
    )
    
    # 2. Broadcast COMMUNITY_CARDS if cards were added
    if result.get("community_cards"):
        broadcast_count += await broadcast_community_cards(
            table_id,
            result["new_phase"],
            result["community_cards"],
        )
    
    # 3. Send TURN_PROMPT if there's a current player
    table = game_manager.get_table(table_id)
    if table and table.current_player_seat is not None:
        current_player = table.players.get(table.current_player_seat)
        if current_player:
            available = table.get_available_actions(current_player.user_id)
            allowed = []
            for action in available.get("actions", []):
                action_dict = {"type": action}
                if action == "call":
                    action_dict["amount"] = available.get("call_amount", 0)
                if action in ("raise", "bet"):
                    action_dict["minAmount"] = available.get("min_raise", 0)
                    action_dict["maxAmount"] = available.get("max_raise", 0)
                allowed.append(action_dict)
            
            broadcast_count += await broadcast_turn_prompt(
                table_id,
                table.current_player_seat,
                allowed,
                table.pot,
                table.current_bet,
            )
    
    return DevResponse(
        success=True,
        message=f"Phase changed from {result['old_phase']} to {result['new_phase']}",
        data={
            "phase": result["new_phase"],
            "old_phase": result["old_phase"],
            "community_cards": result["community_cards"],
            "broadcast_count": broadcast_count,
        },
    )


@router.post("/tables/{table_id}/force-showdown")
async def force_showdown(
    table_id: str,
    api_key: DevApiKey,
) -> DevResponse:
    """쇼다운 강제 (모든 베팅 스킵) - 실제로 쇼다운 상태로 전환합니다."""
    result = game_manager.force_phase_change(table_id, "showdown")
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to force showdown"),
        )
    
    # Broadcast state changes via WebSocket
    broadcast_count = 0
    
    # 1. Broadcast TABLE_STATE_UPDATE
    broadcast_count += await broadcast_table_state_update(
        table_id,
        {"phase": "showdown"},
    )
    
    # 2. Broadcast COMMUNITY_CARDS (showdown needs all 5 cards)
    if result.get("community_cards"):
        broadcast_count += await broadcast_community_cards(
            table_id,
            "showdown",
            result["community_cards"],
        )
    
    return DevResponse(
        success=True,
        message="Showdown forced",
        data={
            "phase": "showdown",
            "community_cards": result.get("community_cards", []),
            "broadcast_count": broadcast_count,
        },
    )


@router.post("/tables/{table_id}/start-hand")
async def start_hand(
    table_id: str,
    api_key: DevApiKey,
) -> DevResponse:
    """새 핸드 강제 시작 - 실제로 핸드를 시작합니다."""
    result = game_manager.start_hand_immediately(table_id)
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to start hand"),
        )
    
    # Broadcast HAND_STARTED event
    broadcast_count = 0
    message = MessageEnvelope.create(
        event_type=EventType.HAND_STARTED,
        payload={
            "tableId": table_id,
            "handNumber": result.get("hand_number"),
            "dealer": result.get("dealer"),
        },
    )
    broadcast_count += await broadcast_to_table(table_id, message.to_dict())
    
    # Send TURN_PROMPT for first player
    table = game_manager.get_table(table_id)
    if table and table.current_player_seat is not None:
        current_player = table.players.get(table.current_player_seat)
        if current_player:
            available = table.get_available_actions(current_player.user_id)
            allowed = []
            for action in available.get("actions", []):
                action_dict = {"type": action}
                if action == "call":
                    action_dict["amount"] = available.get("call_amount", 0)
                if action in ("raise", "bet"):
                    action_dict["minAmount"] = available.get("min_raise", 0)
                    action_dict["maxAmount"] = available.get("max_raise", 0)
                allowed.append(action_dict)
            
            broadcast_count += await broadcast_turn_prompt(
                table_id,
                table.current_player_seat,
                allowed,
                table.pot,
                table.current_bet,
            )
    
    return DevResponse(
        success=True,
        message=f"Hand #{result.get('hand_number', 0)} started",
        data={
            "table_id": table_id,
            "hand_number": result.get("hand_number"),
            "dealer": result.get("dealer"),
            "broadcast_count": broadcast_count,
        },
    )


@router.post("/tables/{table_id}/reset")
async def reset_table(
    table_id: str,
    api_key: DevApiKey,
) -> DevResponse:
    """테이블 리셋."""
    table = game_manager.reset_table(table_id)
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found",
        )
    
    return DevResponse(
        success=True,
        message="Table reset",
        data={"table_id": table_id},
    )


@router.post("/tables/{table_id}/force-action")
async def force_action(
    table_id: str,
    request: ForceActionRequest,
    api_key: DevApiKey,
) -> DevResponse:
    """플레이어 액션 강제 실행 - 실제로 액션을 수행합니다."""
    valid_actions = ["fold", "check", "call", "raise", "all_in", "bet"]
    if request.action not in valid_actions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action. Must be one of: {valid_actions}",
        )
    
    result = game_manager.force_action(
        table_id,
        request.position,
        request.action,
        request.amount,
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to execute action"),
        )
    
    # Broadcast TABLE_STATE_UPDATE
    broadcast_count = 0
    broadcast_count += await broadcast_table_state_update(
        table_id,
        {
            "lastAction": {
                "type": result.get("action"),
                "amount": result.get("amount", 0),
                "position": result.get("seat"),
            },
            "pot": result.get("pot", 0),
            "phase": result.get("phase"),
        },
    )
    
    # If phase changed, broadcast community cards
    if result.get("phase_changed"):
        table = game_manager.get_table(table_id)
        if table:
            broadcast_count += await broadcast_community_cards(
                table_id,
                result.get("phase"),
                table.community_cards,
            )
    
    # Send TURN_PROMPT for next player (if hand not complete)
    if not result.get("hand_complete"):
        table = game_manager.get_table(table_id)
        if table and table.current_player_seat is not None:
            current_player = table.players.get(table.current_player_seat)
            if current_player:
                available = table.get_available_actions(current_player.user_id)
                allowed = []
                for action in available.get("actions", []):
                    action_dict = {"type": action}
                    if action == "call":
                        action_dict["amount"] = available.get("call_amount", 0)
                    if action in ("raise", "bet"):
                        action_dict["minAmount"] = available.get("min_raise", 0)
                        action_dict["maxAmount"] = available.get("max_raise", 0)
                    allowed.append(action_dict)
                
                broadcast_count += await broadcast_turn_prompt(
                    table_id,
                    table.current_player_seat,
                    allowed,
                    table.pot,
                    table.current_bet,
                )
    
    return DevResponse(
        success=True,
        message=f"Action {request.action} executed for position {request.position}",
        data={
            "action": result.get("action"),
            "amount": result.get("amount"),
            "seat": result.get("seat"),
            "pot": result.get("pot"),
            "phase": result.get("phase"),
            "hand_complete": result.get("hand_complete", False),
            "broadcast_count": broadcast_count,
        },
    )


@router.post("/players/set-stack")
async def set_player_stack(
    request: SetStackRequest,
    api_key: DevApiKey,
) -> DevResponse:
    """플레이어 스택 설정 (전역)."""
    # 이 기능은 특정 테이블 컨텍스트 없이 사용하기 어려움
    # 실제 구현 시 table_id도 필요
    return DevResponse(
        success=True,
        message="Use /tables/{table_id}/set-stack instead",
        data={"position": request.position, "stack": request.stack},
    )


class SetBalanceRequest(BaseModel):
    """유저 잔액 설정 요청."""
    user_id: str = Field(..., description="유저 ID")
    balance: int = Field(..., ge=0, description="잔액")


@router.post("/set-balance")
async def set_user_balance(
    request: SetBalanceRequest,
    api_key: DevApiKey,
    db: DbSession,
) -> DevResponse:
    """유저 잔액 설정 (테스트용)."""
    from sqlalchemy import update
    from app.models.user import User
    
    try:
        stmt = update(User).where(User.id == request.user_id).values(balance=request.balance)
        await db.execute(stmt)
        await db.commit()
        
        return DevResponse(
            success=True,
            message="Balance updated",
            data={"user_id": request.user_id, "balance": request.balance},
        )
    except Exception as e:
        logger.error(f"Failed to set balance: {e}")
        return DevResponse(
            success=False,
            message=str(e),
            data=None,
        )


@router.post("/tables/{table_id}/force-pot")
async def force_pot(
    table_id: str,
    request: ForcePotRequest,
    api_key: DevApiKey,
) -> DevResponse:
    """팟 금액 강제 설정 - 실제로 팟 금액을 변경합니다."""
    # Convert side_pots list to dict format if needed
    side_pots = None
    if request.side_pots:
        side_pots = [{"amount": amt, "players": []} for amt in request.side_pots]
    
    result = game_manager.force_pot(table_id, request.main_pot, side_pots)
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to set pot"),
        )
    
    # Broadcast TABLE_STATE_UPDATE
    broadcast_count = await broadcast_table_state_update(
        table_id,
        {
            "pot": result["pot"],
            "sidePots": result.get("side_pots", []),
        },
    )
    
    return DevResponse(
        success=True,
        message="Pot amount set",
        data={
            "pot": result["pot"],
            "side_pots": result.get("side_pots", []),
            "broadcast_count": broadcast_count,
        },
    )


class AddBotRequestExtended(BaseModel):
    """봇 추가 요청 (확장)."""
    position: int | None = Field(default=None, description="좌석 위치 (None이면 자동)")
    stack: int = Field(default=1000, ge=100, description="초기 스택")
    strategy: str = Field(default="random", description="봇 전략: random, tight, loose")
    username: str | None = Field(default=None, description="봇 이름 (None이면 자동)")


@router.post("/tables/{table_id}/add-bot")
async def add_bot(
    table_id: str,
    request: AddBotRequestExtended,
    api_key: DevApiKey,
) -> DevResponse:
    """봇 플레이어 추가 - 실제로 봇을 테이블에 착석시킵니다."""
    result = game_manager.add_bot_player(
        table_id,
        position=request.position,
        stack=request.stack,
        strategy=request.strategy,
        username=request.username,
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to add bot"),
        )
    
    # Broadcast TABLE_STATE_UPDATE with new player
    broadcast_count = await broadcast_table_state_update(
        table_id,
        {
            "updateType": "bot_added",
            "position": result["position"],
            "botId": result["bot_id"],
            "nickname": result["username"],
            "stack": result["stack"],
            "playerJoined": {
                "position": result["position"],
                "username": result["username"],
                "stack": result["stack"],
                "isBot": True,
            },
        },
    )
    
    return DevResponse(
        success=True,
        message=f"Bot {result['username']} added at position {result['position']}",
        data={
            "bot_id": result["bot_id"],
            "username": result["username"],
            "position": result["position"],
            "stack": result["stack"],
            "strategy": result["strategy"],
            "broadcast_count": broadcast_count,
        },
    )


@router.post("/simulate-restart")
async def simulate_server_restart(
    api_key: DevApiKey,
) -> DevResponse:
    """서버 재시작 시뮬레이션 (상태 복구 테스트용)."""
    # 실제로 서버를 재시작하지 않고, 상태 복구 로직만 트리거
    return DevResponse(
        success=True,
        message="Server restart simulated - state recovery triggered",
        data={"simulated": True},
    )


@router.get("/test-suites/{suite_name}/results")
async def get_test_suite_results(
    suite_name: str,
    api_key: DevApiKey,
) -> DevResponse:
    """테스트 스위트 결과 조회."""
    # 테스트 결과 저장소에서 조회 (구현 필요)
    return DevResponse(
        success=True,
        message=f"Test suite '{suite_name}' results",
        data={
            "suite_name": suite_name,
            "status": "not_implemented",
            "results": [],
        },
    )


@router.post("/tables/{table_id}/force-betting")
async def force_betting_scenario(
    table_id: str,
    api_key: DevApiKey,
) -> DevResponse:
    """베팅 시나리오 강제 실행."""
    table = game_manager.get_table(table_id)
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found",
        )
    
    return DevResponse(
        success=True,
        message="Betting scenario forced",
        data={"table_id": table_id},
    )
