"""
Tournament API Router.

토너먼트 관리 및 관리자 API 엔드포인트.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field

# Tournament models and engine will be instantiated by dependency injection


# =============================================================================
# Request/Response Models
# =============================================================================


class CreateTournamentRequest(BaseModel):
    """토너먼트 생성 요청."""

    name: str = Field(..., min_length=1, max_length=100)
    min_players: int = Field(default=2, ge=2)
    max_players: int = Field(default=300, le=1000)
    players_per_table: int = Field(default=9, ge=2, le=10)
    buy_in: int = Field(default=10000, ge=0)
    starting_chips: int = Field(default=10000, ge=1000)
    allow_rebuy: bool = False
    allow_addon: bool = False
    shotgun_start_enabled: bool = True
    shotgun_countdown_seconds: int = Field(default=10, ge=5, le=60)


class TournamentResponse(BaseModel):
    """토너먼트 응답."""

    tournament_id: str
    name: str
    status: str
    current_blind_level: int
    current_blind: Optional[Dict[str, Any]] = None
    active_players: int
    total_players: int
    table_count: int
    total_prize_pool: int
    started_at: Optional[str] = None
    next_level_at: Optional[str] = None


class RegisterPlayerRequest(BaseModel):
    """플레이어 등록 요청."""

    user_id: str
    nickname: str = Field(..., min_length=1, max_length=50)


class PlayerResponse(BaseModel):
    """플레이어 응답."""

    user_id: str
    nickname: str
    chip_count: int
    table_id: Optional[str] = None
    seat_position: Optional[int] = None
    is_active: bool
    rank: Optional[int] = None


class RankingEntry(BaseModel):
    """랭킹 엔트리."""

    rank: int
    user_id: str
    nickname: str
    chip_count: int
    table_id: Optional[str] = None


class RankingResponse(BaseModel):
    """랭킹 응답."""

    tournament_id: str
    total_players: int
    active_players: int
    average_stack: int
    entries: List[RankingEntry]


class TableMonitorResponse(BaseModel):
    """테이블 모니터링 응답."""

    table_id: str
    table_number: int
    player_count: int
    players: List[Dict[str, Any]]
    hand_in_progress: bool
    current_hand_id: Optional[str] = None


class AdminPauseRequest(BaseModel):
    """관리자 일시정지 요청."""

    reason: str = Field(default="Admin pause", max_length=200)


class AdminKickRequest(BaseModel):
    """관리자 강제 퇴장 요청."""

    user_id: str
    reason: str = Field(..., min_length=1, max_length=200)


class AdminChipsRequest(BaseModel):
    """관리자 칩 조정 요청."""

    user_id: str
    amount: int
    reason: str = Field(..., min_length=1, max_length=200)


class AdminBlindRequest(BaseModel):
    """관리자 블라인드 조정 요청."""

    level: int = Field(..., ge=1)
    reason: str = Field(..., min_length=1, max_length=200)


class HandCompleteRequest(BaseModel):
    """핸드 완료 요청."""

    table_id: str
    winners: List[str] = Field(default_factory=list)
    chip_changes: Dict[str, int] = Field(default_factory=dict)
    eliminated: List[str] = Field(default_factory=list)


# =============================================================================
# API Router
# =============================================================================

router = APIRouter(prefix="/api/v1/tournament", tags=["Tournament"])


# Placeholder for engine instance (in production: use FastAPI dependency injection)
_engine = None


def get_engine():
    """Get tournament engine instance."""
    global _engine
    if _engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tournament engine not initialized",
        )
    return _engine


# =============================================================================
# Tournament Lifecycle Endpoints
# =============================================================================


@router.post("", response_model=TournamentResponse)
async def create_tournament(
    request: CreateTournamentRequest,
):
    """
    새 토너먼트 생성.

    - 최대 300명 동시 접속 지원
    - Shotgun Start로 동시 시작
    """
    from .models import TournamentConfig

    engine = get_engine()

    config = TournamentConfig(
        tournament_id=str(uuid4()),
        name=request.name,
        min_players=request.min_players,
        max_players=request.max_players,
        players_per_table=request.players_per_table,
        buy_in=request.buy_in,
        starting_chips=request.starting_chips,
        allow_rebuy=request.allow_rebuy,
        allow_addon=request.allow_addon,
        shotgun_start_enabled=request.shotgun_start_enabled,
        shotgun_countdown_seconds=request.shotgun_countdown_seconds,
    )

    state = await engine.create_tournament(config)
    return TournamentResponse(**state.to_dict())


@router.get("/{tournament_id}", response_model=TournamentResponse)
async def get_tournament(tournament_id: str):
    """토너먼트 상태 조회."""
    engine = get_engine()
    state = engine.get_state(tournament_id)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found"
        )

    return TournamentResponse(**state.to_dict())


@router.post("/{tournament_id}/register", response_model=PlayerResponse)
async def register_player(
    tournament_id: str,
    request: RegisterPlayerRequest,
):
    """플레이어 등록."""
    engine = get_engine()

    try:
        state, player = await engine.register_player(
            tournament_id,
            request.user_id,
            request.nickname,
        )

        rank = await engine.ranking.get_rank(tournament_id, request.user_id)

        return PlayerResponse(
            user_id=player.user_id,
            nickname=player.nickname,
            chip_count=player.chip_count,
            table_id=player.table_id,
            seat_position=player.seat_position,
            is_active=player.is_active,
            rank=rank if rank > 0 else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{tournament_id}/start", response_model=TournamentResponse)
async def start_tournament(tournament_id: str):
    """
    토너먼트 시작 (Shotgun Start).

    모든 테이블이 카운트다운 후 동시에 시작됩니다.
    """
    engine = get_engine()

    try:
        state = await engine.start_tournament(tournament_id)
        return TournamentResponse(**state.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# Ranking Endpoints
# =============================================================================


@router.get("/{tournament_id}/ranking", response_model=RankingResponse)
async def get_ranking(
    tournament_id: str,
    top: int = Query(default=100, ge=1, le=500),
):
    """
    실시간 순위 조회.

    Redis Sorted Set 기반 O(log n) 성능.
    """
    engine = get_engine()
    state = engine.get_state(tournament_id)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found"
        )

    entries = await engine.get_ranking(tournament_id, top)
    snapshot = await engine.ranking.get_snapshot(tournament_id)

    return RankingResponse(
        tournament_id=tournament_id,
        total_players=snapshot.total_players,
        active_players=snapshot.active_players,
        average_stack=snapshot.average_stack,
        entries=[
            RankingEntry(
                rank=e.rank,
                user_id=e.user_id,
                nickname=e.nickname,
                chip_count=e.chip_count,
                table_id=e.table_id,
            )
            for e in entries
        ],
    )


@router.get("/{tournament_id}/player/{user_id}/rank")
async def get_player_rank(tournament_id: str, user_id: str):
    """개별 플레이어 순위 조회."""
    engine = get_engine()

    rank = await engine.ranking.get_rank(tournament_id, user_id)
    nearby = await engine.ranking.get_nearby_players(tournament_id, user_id)

    return {
        "user_id": user_id,
        "rank": rank if rank > 0 else None,
        "nearby": [e.to_dict() for e in nearby],
    }


# =============================================================================
# Table Endpoints
# =============================================================================


@router.get("/{tournament_id}/tables", response_model=List[TableMonitorResponse])
async def get_all_tables(tournament_id: str):
    """모든 테이블 조회."""
    engine = get_engine()
    state = engine.get_state(tournament_id)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found"
        )

    from .admin import TournamentAdminController

    admin = TournamentAdminController(engine.lock_manager, engine.event_bus)
    monitors = await admin.get_all_tables_monitor(state)

    return [
        TableMonitorResponse(
            table_id=m.table_id,
            table_number=m.table_number,
            player_count=m.player_count,
            players=m.players,
            hand_in_progress=m.hand_in_progress,
            current_hand_id=m.current_hand_id,
        )
        for m in monitors
    ]


@router.get("/{tournament_id}/table/{table_id}", response_model=TableMonitorResponse)
async def get_table(tournament_id: str, table_id: str):
    """특정 테이블 모니터링."""
    engine = get_engine()
    state = engine.get_state(tournament_id)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found"
        )

    from .admin import TournamentAdminController

    admin = TournamentAdminController(engine.lock_manager, engine.event_bus)
    monitor = await admin.get_table_monitor(state, table_id)

    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Table not found"
        )

    return TableMonitorResponse(
        table_id=monitor.table_id,
        table_number=monitor.table_number,
        player_count=monitor.player_count,
        players=monitor.players,
        hand_in_progress=monitor.hand_in_progress,
        current_hand_id=monitor.current_hand_id,
    )


# =============================================================================
# Hand Completion Endpoint
# =============================================================================


@router.post("/{tournament_id}/hand/complete", response_model=TournamentResponse)
async def complete_hand(
    tournament_id: str,
    request: HandCompleteRequest,
):
    """
    핸드 완료 처리.

    - 칩 변경 적용
    - 탈락자 처리
    - 랭킹 업데이트
    - 테이블 밸런싱 트리거
    """
    engine = get_engine()

    try:
        state = await engine.complete_hand(
            tournament_id,
            request.table_id,
            request.winners,
            request.chip_changes,
            request.eliminated,
        )
        return TournamentResponse(**state.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# Admin Endpoints
# =============================================================================

admin_router = APIRouter(prefix="/api/v1/tournament/admin", tags=["Tournament Admin"])


@admin_router.post("/{tournament_id}/pause", response_model=TournamentResponse)
async def admin_pause_tournament(
    tournament_id: str,
    request: AdminPauseRequest,
    admin_id: str = Query(..., description="Admin user ID"),
):
    """
    [관리자] 토너먼트 일시정지.

    - 현재 핸드는 완료 허용
    - 새 핸드 시작 금지
    - 블라인드 타이머 정지
    """
    engine = get_engine()
    state = engine.get_state(tournament_id)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found"
        )

    from .admin import TournamentAdminController

    admin = TournamentAdminController(engine.lock_manager, engine.event_bus)
    new_state = await admin.pause_tournament(state, admin_id, request.reason)

    # Update engine state
    engine._tournaments[tournament_id] = new_state

    return TournamentResponse(**new_state.to_dict())


@admin_router.post("/{tournament_id}/resume", response_model=TournamentResponse)
async def admin_resume_tournament(
    tournament_id: str,
    admin_id: str = Query(..., description="Admin user ID"),
):
    """[관리자] 토너먼트 재개."""
    engine = get_engine()
    state = engine.get_state(tournament_id)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found"
        )

    from .admin import TournamentAdminController

    admin = TournamentAdminController(engine.lock_manager, engine.event_bus)
    new_state = await admin.resume_tournament(state, admin_id)

    engine._tournaments[tournament_id] = new_state

    return TournamentResponse(**new_state.to_dict())


@admin_router.post("/{tournament_id}/kick", response_model=TournamentResponse)
async def admin_kick_player(
    tournament_id: str,
    request: AdminKickRequest,
    admin_id: str = Query(..., description="Admin user ID"),
):
    """
    [관리자] 비정상 유저 강제 퇴장.

    - 즉시 탈락 처리
    - 현재 핸드에서 폴드 처리
    """
    engine = get_engine()
    state = engine.get_state(tournament_id)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found"
        )

    from .admin import TournamentAdminController

    admin = TournamentAdminController(engine.lock_manager, engine.event_bus)
    new_state = await admin.kick_player(
        state, admin_id, request.user_id, request.reason
    )

    engine._tournaments[tournament_id] = new_state

    return TournamentResponse(**new_state.to_dict())


@admin_router.post("/{tournament_id}/add-chips", response_model=TournamentResponse)
async def admin_add_chips(
    tournament_id: str,
    request: AdminChipsRequest,
    admin_id: str = Query(..., description="Admin user ID"),
):
    """[관리자] 칩 추가 (분쟁 해결용)."""
    engine = get_engine()
    state = engine.get_state(tournament_id)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found"
        )

    from .admin import TournamentAdminController

    admin = TournamentAdminController(engine.lock_manager, engine.event_bus)
    new_state = await admin.add_chips(
        state, admin_id, request.user_id, request.amount, request.reason
    )

    engine._tournaments[tournament_id] = new_state

    return TournamentResponse(**new_state.to_dict())


@admin_router.post("/{tournament_id}/set-blind", response_model=TournamentResponse)
async def admin_set_blind_level(
    tournament_id: str,
    request: AdminBlindRequest,
    admin_id: str = Query(..., description="Admin user ID"),
):
    """[관리자] 블라인드 레벨 강제 조정."""
    engine = get_engine()
    state = engine.get_state(tournament_id)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found"
        )

    from .admin import TournamentAdminController

    admin = TournamentAdminController(engine.lock_manager, engine.event_bus)
    new_state = await admin.force_blind_level(
        state, admin_id, request.level, request.reason
    )

    engine._tournaments[tournament_id] = new_state

    return TournamentResponse(**new_state.to_dict())


@admin_router.get("/{tournament_id}/action-log")
async def get_admin_action_log(
    tournament_id: str,
    limit: int = Query(default=100, ge=1, le=500),
):
    """[관리자] 액션 로그 조회."""
    from .admin import TournamentAdminController

    engine = get_engine()
    admin = TournamentAdminController(engine.lock_manager, engine.event_bus)

    logs = admin.get_action_log(tournament_id, limit)
    return {
        "tournament_id": tournament_id,
        "actions": [log.to_dict() for log in logs],
    }


# =============================================================================
# Recovery Endpoint
# =============================================================================


@router.post("/{tournament_id}/recover", response_model=TournamentResponse)
async def recover_tournament(tournament_id: str):
    """
    토너먼트 복구 (서버 재시작 후).

    스냅샷에서 상태를 복원합니다.
    """
    engine = get_engine()

    state = await engine.recover_tournament(tournament_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No snapshot found for recovery",
        )

    return TournamentResponse(**state.to_dict())
