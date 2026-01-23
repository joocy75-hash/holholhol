"""파트너 포털 API

파트너가 자신의 데이터를 조회할 수 있는 API 엔드포인트입니다.
모든 엔드포인트는 partner 역할로 인증된 사용자만 접근 가능합니다.
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_admin_db, get_main_db
from app.models.admin_user import AdminUser, AdminRole
from app.utils.dependencies import get_current_user

router = APIRouter()


# ============ Response Models ============

class PartnerInfoResponse(BaseModel):
    id: str
    partner_code: str
    name: str
    contact_info: str | None
    commission_type: str
    commission_rate: float
    status: str
    total_referrals: int
    total_commission_earned: int
    current_month_commission: int
    created_at: str


class ReferralItem(BaseModel):
    user_id: str = Field(serialization_alias="userId")
    nickname: str
    email: str
    joined_at: str = Field(serialization_alias="joinedAt")
    total_rake: int = Field(serialization_alias="totalRake")
    total_bet_amount: int = Field(serialization_alias="totalBetAmount")
    net_loss: int = Field(serialization_alias="netLoss")
    last_active_at: str | None = Field(serialization_alias="lastActiveAt")
    is_active: bool = Field(serialization_alias="isActive")

    model_config = {"populate_by_name": True}


class ReferralListResponse(BaseModel):
    items: list[ReferralItem]
    total: int
    page: int
    page_size: int = Field(serialization_alias="pageSize")

    model_config = {"populate_by_name": True}


class SettlementItem(BaseModel):
    id: str
    period_type: str
    period_start: str
    period_end: str
    commission_type: str
    commission_rate: float
    base_amount: int
    commission_amount: int
    status: str
    created_at: str
    approved_at: str | None
    paid_at: str | None


class SettlementListResponse(BaseModel):
    items: list[SettlementItem]
    total: int
    page: int
    page_size: int


class OverviewStatsResponse(BaseModel):
    total_referrals: int
    total_commission_earned: int
    current_month_commission: int
    pending_settlements: int
    pending_amount: int
    active_users_today: int
    new_referrals_this_month: int


class DailyStatItem(BaseModel):
    date: str
    referrals: int
    rake: int
    bet_amount: int
    net_loss: int
    commission: int


class MonthlyStatItem(BaseModel):
    month: str
    referrals: int
    rake: int
    bet_amount: int
    net_loss: int
    commission: int


# ============ Helper Functions ============

async def get_partner_user(
    current_user: AdminUser = Depends(get_current_user),
) -> AdminUser:
    """파트너 역할 확인"""
    if current_user.role != AdminRole.partner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="파트너 전용 API입니다.",
        )
    if not current_user.partner_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="파트너 ID가 설정되지 않았습니다.",
        )
    return current_user


# ============ Endpoints ============

@router.get("/me", response_model=PartnerInfoResponse)
async def get_my_partner_info(
    current_user: AdminUser = Depends(get_partner_user),
    main_db: AsyncSession = Depends(get_main_db),
):
    """내 파트너 정보 조회"""
    query = text("""
        SELECT
            id, partner_code, name, contact_info,
            commission_type, commission_rate, status,
            total_referrals, total_commission_earned, current_month_commission,
            created_at
        FROM partners
        WHERE id = :partner_id
    """)
    result = await main_db.execute(query, {"partner_id": str(current_user.partner_id)})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="파트너 정보를 찾을 수 없습니다.",
        )

    return PartnerInfoResponse(
        id=str(row.id),
        partner_code=row.partner_code,
        name=row.name,
        contact_info=row.contact_info,
        commission_type=row.commission_type,
        commission_rate=float(row.commission_rate),
        status=row.status,
        total_referrals=row.total_referrals,
        total_commission_earned=row.total_commission_earned,
        current_month_commission=row.current_month_commission,
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


@router.get("/referrals", response_model=ReferralListResponse)
async def get_my_referrals(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    current_user: AdminUser = Depends(get_partner_user),
    main_db: AsyncSession = Depends(get_main_db),
):
    """내 추천 회원 목록 조회"""
    partner_id = str(current_user.partner_id)
    offset = (page - 1) * page_size

    # 검색 조건
    search_condition = ""
    params = {"partner_id": partner_id, "offset": offset, "limit": page_size}
    if search:
        search_condition = "AND (u.nickname ILIKE :search OR u.email ILIKE :search)"
        params["search"] = f"%{search}%"

    # 총 개수
    count_query = text(f"""
        SELECT COUNT(*)
        FROM users u
        WHERE u.partner_id = CAST(:partner_id AS uuid)
        {search_condition}
    """)
    count_result = await main_db.execute(count_query, params)
    total = count_result.scalar() or 0

    # 데이터 조회 (users 테이블에서 직접 통계 필드 조회)
    query = text(f"""
        SELECT
            u.id as user_id,
            u.nickname,
            u.email,
            u.created_at as joined_at,
            COALESCE(u.total_rake_paid_krw, 0) as total_rake,
            COALESCE(u.total_bet_amount_krw, 0) as total_bet_amount,
            COALESCE(-u.total_net_profit_krw, 0) as net_loss,
            u.updated_at as last_active_at,
            CASE WHEN u.status = 'active' THEN true ELSE false END as is_active
        FROM users u
        WHERE u.partner_id = CAST(:partner_id AS uuid)
        {search_condition}
        ORDER BY u.created_at DESC
        OFFSET :offset LIMIT :limit
    """)
    result = await main_db.execute(query, params)
    rows = result.fetchall()

    items = [
        ReferralItem(
            user_id=str(row.user_id),
            nickname=row.nickname or "",
            email=row.email or "",
            joined_at=row.joined_at.isoformat() if row.joined_at else "",
            total_rake=row.total_rake or 0,
            total_bet_amount=row.total_bet_amount or 0,
            net_loss=row.net_loss or 0,
            last_active_at=row.last_active_at.isoformat() if row.last_active_at else None,
            is_active=row.is_active,
        )
        for row in rows
    ]

    return ReferralListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/settlements", response_model=SettlementListResponse)
async def get_my_settlements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: AdminUser = Depends(get_partner_user),
    main_db: AsyncSession = Depends(get_main_db),
):
    """내 정산 내역 조회"""
    partner_id = str(current_user.partner_id)
    offset = (page - 1) * page_size

    # 상태 필터
    status_condition = ""
    params = {"partner_id": partner_id, "offset": offset, "limit": page_size}
    if status_filter:
        status_condition = "AND ps.status = :status_filter"
        params["status_filter"] = status_filter

    # 총 개수
    count_query = text(f"""
        SELECT COUNT(*)
        FROM partner_settlements ps
        WHERE ps.partner_id = :partner_id
        {status_condition}
    """)
    count_result = await main_db.execute(count_query, params)
    total = count_result.scalar() or 0

    # 데이터 조회
    query = text(f"""
        SELECT
            ps.id,
            ps.period_type,
            ps.period_start,
            ps.period_end,
            ps.commission_type,
            ps.commission_rate,
            ps.base_amount,
            ps.commission_amount,
            ps.status,
            ps.created_at,
            ps.approved_at,
            ps.paid_at
        FROM partner_settlements ps
        WHERE ps.partner_id = :partner_id
        {status_condition}
        ORDER BY ps.created_at DESC
        OFFSET :offset LIMIT :limit
    """)
    result = await main_db.execute(query, params)
    rows = result.fetchall()

    items = [
        SettlementItem(
            id=str(row.id),
            period_type=row.period_type,
            period_start=row.period_start.isoformat() if row.period_start else "",
            period_end=row.period_end.isoformat() if row.period_end else "",
            commission_type=row.commission_type,
            commission_rate=float(row.commission_rate),
            base_amount=row.base_amount,
            commission_amount=row.commission_amount,
            status=row.status,
            created_at=row.created_at.isoformat() if row.created_at else "",
            approved_at=row.approved_at.isoformat() if row.approved_at else None,
            paid_at=row.paid_at.isoformat() if row.paid_at else None,
        )
        for row in rows
    ]

    return SettlementListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/stats/overview", response_model=OverviewStatsResponse)
async def get_my_stats_overview(
    current_user: AdminUser = Depends(get_partner_user),
    main_db: AsyncSession = Depends(get_main_db),
):
    """내 통계 개요 조회"""
    partner_id = str(current_user.partner_id)

    # 파트너 기본 통계
    partner_query = text("""
        SELECT
            total_referrals,
            total_commission_earned,
            current_month_commission
        FROM partners
        WHERE id = :partner_id
    """)
    partner_result = await main_db.execute(partner_query, {"partner_id": partner_id})
    partner_row = partner_result.fetchone()

    if not partner_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="파트너 정보를 찾을 수 없습니다.",
        )

    # 대기 중인 정산
    pending_query = text("""
        SELECT COUNT(*), COALESCE(SUM(commission_amount), 0)
        FROM partner_settlements
        WHERE partner_id = :partner_id AND status = 'pending'
    """)
    pending_result = await main_db.execute(pending_query, {"partner_id": partner_id})
    pending_row = pending_result.fetchone()
    pending_count = pending_row[0] if pending_row else 0
    pending_amount = pending_row[1] if pending_row else 0

    # 오늘 활성 유저 (updated_at 기준)
    today = datetime.utcnow().date()
    active_query = text("""
        SELECT COUNT(DISTINCT u.id)
        FROM users u
        WHERE u.partner_id = CAST(:partner_id AS uuid)
          AND DATE(u.updated_at) = :today
    """)
    active_result = await main_db.execute(
        active_query, {"partner_id": partner_id, "today": today}
    )
    active_today = active_result.scalar() or 0

    # 이번 달 신규 추천
    first_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_referrals_query = text("""
        SELECT COUNT(*)
        FROM users
        WHERE partner_id = CAST(:partner_id AS uuid)
          AND created_at >= :first_of_month
    """)
    new_result = await main_db.execute(
        new_referrals_query, {"partner_id": partner_id, "first_of_month": first_of_month}
    )
    new_referrals = new_result.scalar() or 0

    return OverviewStatsResponse(
        total_referrals=partner_row.total_referrals,
        total_commission_earned=partner_row.total_commission_earned,
        current_month_commission=partner_row.current_month_commission,
        pending_settlements=pending_count,
        pending_amount=pending_amount,
        active_users_today=active_today,
        new_referrals_this_month=new_referrals,
    )


@router.get("/stats/daily", response_model=list[DailyStatItem])
async def get_my_daily_stats(
    days: int = Query(30, ge=1, le=90),
    current_user: AdminUser = Depends(get_partner_user),
    main_db: AsyncSession = Depends(get_main_db),
):
    """일별 통계 조회"""
    partner_id = str(current_user.partner_id)
    start_date = datetime.utcnow() - timedelta(days=days)

    query = text("""
        WITH daily_referrals AS (
            SELECT
                DATE(created_at) as date,
                COUNT(*) as referrals
            FROM users
            WHERE partner_id = CAST(:partner_id AS uuid)
              AND created_at >= :start_date
            GROUP BY DATE(created_at)
        ),
        daily_stats AS (
            SELECT
                DATE(h.ended_at) as date,
                0 as rake,
                SUM(hp.bet_amount) as bet_amount,
                SUM(hp.won_amount - hp.bet_amount) as net_won
            FROM hand_participants hp
            JOIN hands h ON h.id = hp.hand_id
            JOIN users u ON u.id = hp.user_id
            WHERE u.partner_id = CAST(:partner_id AS uuid)
              AND h.ended_at >= :start_date
            GROUP BY DATE(h.ended_at)
        )
        SELECT
            COALESCE(dr.date, ds.date) as date,
            COALESCE(dr.referrals, 0) as referrals,
            COALESCE(ds.rake, 0) as rake,
            COALESCE(ds.bet_amount, 0) as bet_amount,
            COALESCE(-ds.net_won, 0) as net_loss
        FROM daily_referrals dr
        FULL OUTER JOIN daily_stats ds ON dr.date = ds.date
        WHERE COALESCE(dr.date, ds.date) IS NOT NULL
        ORDER BY date DESC
    """)

    result = await main_db.execute(
        query, {"partner_id": partner_id, "start_date": start_date}
    )
    rows = result.fetchall()

    # 파트너의 수수료율 조회
    rate_query = text("""
        SELECT commission_type, commission_rate FROM partners WHERE id = :partner_id
    """)
    rate_result = await main_db.execute(rate_query, {"partner_id": partner_id})
    rate_row = rate_result.fetchone()
    commission_type = rate_row.commission_type if rate_row else "rakeback"
    commission_rate = float(rate_row.commission_rate) if rate_row else 0.3

    items = []
    for row in rows:
        # 수수료 계산
        base_amount = 0
        if commission_type == "rakeback":
            base_amount = row.rake or 0
        elif commission_type == "revshare":
            base_amount = row.net_loss or 0
        elif commission_type == "turnover":
            base_amount = row.bet_amount or 0

        commission = int(base_amount * commission_rate)

        items.append(DailyStatItem(
            date=row.date.isoformat() if row.date else "",
            referrals=row.referrals or 0,
            rake=row.rake or 0,
            bet_amount=row.bet_amount or 0,
            net_loss=row.net_loss or 0,
            commission=commission,
        ))

    return items


@router.get("/stats/monthly", response_model=list[MonthlyStatItem])
async def get_my_monthly_stats(
    months: int = Query(12, ge=1, le=24),
    current_user: AdminUser = Depends(get_partner_user),
    main_db: AsyncSession = Depends(get_main_db),
):
    """월별 통계 조회"""
    partner_id = str(current_user.partner_id)
    start_date = datetime.utcnow() - timedelta(days=months * 31)

    query = text("""
        WITH monthly_referrals AS (
            SELECT
                TO_CHAR(created_at, 'YYYY-MM') as month,
                COUNT(*) as referrals
            FROM users
            WHERE partner_id = CAST(:partner_id AS uuid)
              AND created_at >= :start_date
            GROUP BY TO_CHAR(created_at, 'YYYY-MM')
        ),
        monthly_stats AS (
            SELECT
                TO_CHAR(h.ended_at, 'YYYY-MM') as month,
                0 as rake,
                SUM(hp.bet_amount) as bet_amount,
                SUM(hp.won_amount - hp.bet_amount) as net_won
            FROM hand_participants hp
            JOIN hands h ON h.id = hp.hand_id
            JOIN users u ON u.id = hp.user_id
            WHERE u.partner_id = CAST(:partner_id AS uuid)
              AND h.ended_at >= :start_date
            GROUP BY TO_CHAR(h.ended_at, 'YYYY-MM')
        )
        SELECT
            COALESCE(mr.month, ms.month) as month,
            COALESCE(mr.referrals, 0) as referrals,
            COALESCE(ms.rake, 0) as rake,
            COALESCE(ms.bet_amount, 0) as bet_amount,
            COALESCE(-ms.net_won, 0) as net_loss
        FROM monthly_referrals mr
        FULL OUTER JOIN monthly_stats ms ON mr.month = ms.month
        WHERE COALESCE(mr.month, ms.month) IS NOT NULL
        ORDER BY month DESC
    """)

    result = await main_db.execute(
        query, {"partner_id": partner_id, "start_date": start_date}
    )
    rows = result.fetchall()

    # 파트너의 수수료율 조회
    rate_query = text("""
        SELECT commission_type, commission_rate FROM partners WHERE id = :partner_id
    """)
    rate_result = await main_db.execute(rate_query, {"partner_id": partner_id})
    rate_row = rate_result.fetchone()
    commission_type = rate_row.commission_type if rate_row else "rakeback"
    commission_rate = float(rate_row.commission_rate) if rate_row else 0.3

    items = []
    for row in rows:
        # 수수료 계산
        base_amount = 0
        if commission_type == "rakeback":
            base_amount = row.rake or 0
        elif commission_type == "revshare":
            base_amount = row.net_loss or 0
        elif commission_type == "turnover":
            base_amount = row.bet_amount or 0

        commission = int(base_amount * commission_rate)

        items.append(MonthlyStatItem(
            month=row.month or "",
            referrals=row.referrals or 0,
            rake=row.rake or 0,
            bet_amount=row.bet_amount or 0,
            net_loss=row.net_loss or 0,
            commission=commission,
        ))

    return items
