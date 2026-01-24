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


# =============================================================================
# Recovery Management Endpoints (Admin)
# =============================================================================


class RecoverableTournamentInfo(BaseModel):
    """복구 가능한 토너먼트 정보."""

    tournament_id: str
    status: str
    active_players: int
    total_players: int
    table_count: int
    blind_level: int
    can_recover: bool


class RecoveryListResponse(BaseModel):
    """복구 가능 목록 응답."""

    recoverable_count: int
    tournaments: List[RecoverableTournamentInfo]


class RecoveryResult(BaseModel):
    """복구 결과."""

    tournament_id: str
    success: bool
    status: Optional[str] = None
    error: Optional[str] = None


class BatchRecoveryResponse(BaseModel):
    """일괄 복구 응답."""

    total: int
    success_count: int
    failed_count: int
    results: List[RecoveryResult]


@admin_router.get("/recovery/list", response_model=RecoveryListResponse)
async def list_recoverable_tournaments():
    """
    [관리자] 복구 가능한 토너먼트 목록 조회.

    Redis에 저장된 스냅샷을 기반으로 복구 가능한 토너먼트를 나열합니다.
    서버 재시작 시 자동 복구되지 않은 토너먼트를 확인할 수 있습니다.
    """
    engine = get_engine()

    # 이미 메모리에 로드된 토너먼트
    loaded_ids = set(engine._tournaments.keys())

    # Redis에서 복구 가능한 토너먼트 조회
    snapshot_ids = await engine.snapshot.list_recoverable_tournaments()

    tournaments = []
    for tid in snapshot_ids:
        # 이미 로드된 경우
        if tid in loaded_ids:
            state = engine._tournaments[tid]
            tournaments.append(
                RecoverableTournamentInfo(
                    tournament_id=tid,
                    status=state.status.value,
                    active_players=state.active_player_count,
                    total_players=len(state.players),
                    table_count=len(state.tables),
                    blind_level=state.current_blind_level,
                    can_recover=False,  # 이미 로드됨
                )
            )
        else:
            # 스냅샷에서 정보 로드
            state = await engine.snapshot.load_latest(tid)
            if state:
                # 이미 종료된 토너먼트인지 확인
                from .models import TournamentStatus

                can_recover = state.status not in (
                    TournamentStatus.COMPLETED,
                    TournamentStatus.CANCELLED,
                )
                tournaments.append(
                    RecoverableTournamentInfo(
                        tournament_id=tid,
                        status=state.status.value,
                        active_players=state.active_player_count,
                        total_players=len(state.players),
                        table_count=len(state.tables),
                        blind_level=state.current_blind_level,
                        can_recover=can_recover,
                    )
                )

    return RecoveryListResponse(
        recoverable_count=sum(1 for t in tournaments if t.can_recover),
        tournaments=tournaments,
    )


@admin_router.post("/recovery/batch", response_model=BatchRecoveryResponse)
async def batch_recover_tournaments(
    tournament_ids: Optional[List[str]] = None,
):
    """
    [관리자] 토너먼트 일괄 복구.

    tournament_ids가 제공되지 않으면 모든 복구 가능한 토너먼트를 복구합니다.

    Args:
        tournament_ids: 복구할 토너먼트 ID 목록 (선택)
    """
    engine = get_engine()

    # 복구할 토너먼트 목록 결정
    if tournament_ids:
        target_ids = tournament_ids
    else:
        target_ids = await engine.snapshot.list_recoverable_tournaments()

    results = []
    success_count = 0

    for tid in target_ids:
        # 이미 로드된 경우 스킵
        if tid in engine._tournaments:
            results.append(
                RecoveryResult(
                    tournament_id=tid,
                    success=True,
                    status="already_loaded",
                    error=None,
                )
            )
            success_count += 1
            continue

        try:
            state = await engine.recover_tournament(tid)
            if state:
                from .models import TournamentStatus

                # 종료된 토너먼트 스냅샷 정리
                if state.status in (
                    TournamentStatus.COMPLETED,
                    TournamentStatus.CANCELLED,
                ):
                    await engine.snapshot.delete_snapshot(tid)
                    results.append(
                        RecoveryResult(
                            tournament_id=tid,
                            success=True,
                            status="cleaned_up",
                            error=None,
                        )
                    )
                else:
                    results.append(
                        RecoveryResult(
                            tournament_id=tid,
                            success=True,
                            status=state.status.value,
                            error=None,
                        )
                    )
                success_count += 1
            else:
                results.append(
                    RecoveryResult(
                        tournament_id=tid,
                        success=False,
                        status=None,
                        error="Snapshot not found",
                    )
                )
        except Exception as e:
            results.append(
                RecoveryResult(
                    tournament_id=tid,
                    success=False,
                    status=None,
                    error=str(e),
                )
            )

    return BatchRecoveryResponse(
        total=len(results),
        success_count=success_count,
        failed_count=len(results) - success_count,
        results=results,
    )


@admin_router.delete("/recovery/{tournament_id}/snapshot")
async def delete_tournament_snapshot(
    tournament_id: str,
    admin_id: str = Query(..., description="Admin user ID"),
):
    """
    [관리자] 토너먼트 스냅샷 삭제.

    종료된 토너먼트의 스냅샷을 수동으로 정리합니다.
    """
    engine = get_engine()

    deleted = await engine.snapshot.delete_snapshot(tournament_id)

    return {
        "tournament_id": tournament_id,
        "deleted": deleted,
        "admin_id": admin_id,
    }


# =============================================================================
# Settlement Endpoints (Admin)
# =============================================================================


class EstimatedPayoutEntry(BaseModel):
    """예상 상금 엔트리."""

    rank: int
    percentage: float
    estimated_prize: int


class EstimatedPayoutsResponse(BaseModel):
    """예상 상금 응답."""

    tournament_id: str
    player_count: int
    total_prize_pool: int
    itm_count: int
    payouts: List[EstimatedPayoutEntry]


class PayoutResultResponse(BaseModel):
    """정산 결과 응답."""

    payout_id: str
    user_id: str
    nickname: str
    rank: int
    prize_amount: int
    prize_percentage: float
    transaction_id: Optional[str] = None
    success: bool
    error_message: Optional[str] = None
    paid_at: str


class SettlementResponse(BaseModel):
    """정산 요약 응답."""

    settlement_id: str
    tournament_id: str
    tournament_name: str
    total_prize_pool: int
    total_paid: int
    successful_payouts: int
    failed_payouts: int
    payouts: List[PayoutResultResponse]
    settled_at: str


@router.get(
    "/{tournament_id}/payouts/estimate", response_model=EstimatedPayoutsResponse
)
async def estimate_payouts(
    tournament_id: str,
):
    """
    토너먼트 예상 상금 조회.

    현재 등록된 플레이어 수를 기반으로 예상 상금을 계산합니다.
    """
    engine = get_engine()
    state = engine.get_state(tournament_id)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found"
        )

    from .settlement import TournamentSettlement

    # WalletService 없이 예상 상금만 계산
    settlement = TournamentSettlement(wallet_service=None)  # type: ignore
    estimates = settlement.estimate_payouts(state.config, len(state.players))

    # ITM 플레이어 수 계산
    itm_count = settlement.calculate_itm_players(state)

    return EstimatedPayoutsResponse(
        tournament_id=tournament_id,
        player_count=len(state.players),
        total_prize_pool=state.total_prize_pool,
        itm_count=itm_count,
        payouts=[
            EstimatedPayoutEntry(
                rank=e["rank"],
                percentage=e["percentage"],
                estimated_prize=e["estimated_prize"],
            )
            for e in estimates
        ],
    )


@admin_router.post("/{tournament_id}/settle", response_model=SettlementResponse)
async def settle_tournament(
    tournament_id: str,
    admin_id: str = Query(..., description="Admin user ID"),
):
    """
    [관리자] 토너먼트 상금 정산.

    토너먼트가 종료되면 순위별로 상금을 자동 지급합니다.
    - ITM (In The Money) 플레이어에게만 상금 지급
    - 분산 락으로 중복 정산 방지
    - 실패한 지급은 retry 가능

    Requirements:
        - 토너먼트 상태가 COMPLETED 또는 HEADS_UP (1인 남음)
    """
    engine = get_engine()
    state = engine.get_state(tournament_id)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found"
        )

    from .models import TournamentStatus

    # 토너먼트가 종료된 상태인지 확인
    if state.status not in (TournamentStatus.COMPLETED, TournamentStatus.HEADS_UP):
        # HEADS_UP에서 1인만 남은 경우도 정산 가능
        if state.status == TournamentStatus.HEADS_UP and state.active_player_count == 1:
            pass  # 정산 진행
        elif state.active_player_count <= 1:
            pass  # 1인 이하면 정산 가능
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tournament is not completed. Status: {state.status.value}, Active players: {state.active_player_count}",
            )

    # WalletService 및 Settlement 초기화
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.core.database import get_async_session
    from app.services.wallet import WalletService
    from .settlement import TournamentSettlement

    # 실제 환경에서는 의존성 주입 사용
    # 여기서는 간단히 직접 생성
    try:
        async for session in get_async_session():
            wallet_service = WalletService(session)
            settlement = TournamentSettlement(
                wallet_service=wallet_service,
                event_bus=engine.event_bus,
            )

            summary = await settlement.settle_tournament(tournament_id, state)

            return SettlementResponse(
                settlement_id=summary.settlement_id,
                tournament_id=summary.tournament_id,
                tournament_name=summary.tournament_name,
                total_prize_pool=summary.total_prize_pool,
                total_paid=summary.total_paid,
                successful_payouts=summary.successful_payouts,
                failed_payouts=summary.failed_payouts,
                payouts=[
                    PayoutResultResponse(
                        payout_id=p.payout_id,
                        user_id=p.user_id,
                        nickname=p.nickname,
                        rank=p.rank,
                        prize_amount=p.prize_amount,
                        prize_percentage=p.prize_percentage,
                        transaction_id=p.transaction_id,
                        success=p.success,
                        error_message=p.error_message,
                        paid_at=p.paid_at.isoformat(),
                    )
                    for p in summary.payouts
                ],
                settled_at=summary.settled_at.isoformat(),
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Settlement failed: {str(e)}",
        )


@admin_router.get("/{tournament_id}/settlement/status")
async def get_settlement_status(
    tournament_id: str,
):
    """
    [관리자] 정산 상태 조회.

    토너먼트의 정산 가능 여부와 예상 지급 내역을 반환합니다.
    """
    engine = get_engine()
    state = engine.get_state(tournament_id)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found"
        )

    from .models import TournamentStatus
    from .settlement import TournamentSettlement

    settlement = TournamentSettlement(wallet_service=None)  # type: ignore
    payouts = settlement.calculate_payouts(state)
    itm_count = settlement.calculate_itm_players(state)

    can_settle = (
        state.status == TournamentStatus.COMPLETED or state.active_player_count <= 1
    )

    return {
        "tournament_id": tournament_id,
        "status": state.status.value,
        "can_settle": can_settle,
        "total_prize_pool": state.total_prize_pool,
        "active_players": state.active_player_count,
        "total_players": len(state.players),
        "itm_count": itm_count,
        "estimated_payouts": [
            {
                "user_id": uid,
                "rank": data[0],
                "amount": data[1],
                "percentage": data[2] * 100,
            }
            for uid, data in sorted(payouts.items(), key=lambda x: x[1][0])
        ],
    }
