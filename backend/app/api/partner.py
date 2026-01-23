"""Partner Dashboard API endpoints.

파트너(총판) 대시보드에서 사용하는 API입니다.
JWT 토큰 인증 + 파트너 권한 검증을 거칩니다.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPartner, CurrentUser, DbSession
from app.logging_config import get_logger
from app.models.partner import Partner, PartnerSettlement, SettlementStatus
from app.models.user import User
from app.schemas.partner import (
    DailyStatItem,
    MonthlyStatItem,
    PartnerCodeResponse,
    PartnerDailyStatsResponse,
    PartnerMonthlyStatsResponse,
    PartnerResponse,
    PartnerStatsOverviewResponse,
    ReferralListResponse,
    ReferralResponse,
    ReferralStatsResponse,
    SettlementListResponse,
    SettlementResponse,
    SettlementSummaryResponse,
)
from app.services.partner import PartnerService
from app.services.partner_settlement import PartnerSettlementService

router = APIRouter(prefix="/partner", tags=["Partner Dashboard"])
logger = get_logger(__name__)


# =============================================================================
# Partner Info
# =============================================================================


@router.get(
    "/me",
    response_model=PartnerResponse,
    summary="내 파트너 정보",
    description="현재 로그인한 파트너의 정보를 조회합니다.",
)
async def get_my_partner_info(partner: CurrentPartner):
    """Get current partner's information."""
    logger.info(
        "partner_info_accessed",
        partner_id=partner.id,
        partner_code=partner.partner_code,
    )
    return PartnerResponse.model_validate(partner)


@router.get(
    "/me/code",
    response_model=PartnerCodeResponse,
    summary="내 파트너 코드",
    description="현재 로그인한 파트너의 추천 코드를 조회합니다.",
)
async def get_my_partner_code(partner: CurrentPartner):
    """Get current partner's referral code."""
    return PartnerCodeResponse(partner_code=partner.partner_code)


# =============================================================================
# Referrals (추천 회원)
# =============================================================================


@router.get(
    "/referrals",
    response_model=ReferralListResponse,
    summary="추천 회원 목록",
    description="내 추천 코드로 가입한 회원 목록을 조회합니다.",
)
async def get_my_referrals(
    partner: CurrentPartner,
    db: DbSession,
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize", description="페이지 크기"),
    search: str | None = Query(None, description="검색어 (닉네임, 이메일)"),
):
    """Get referrals for current partner."""
    service = PartnerService(db)
    users, total = await service.get_referrals(
        partner_id=partner.id,
        page=page,
        page_size=page_size,
        search=search,
    )

    logger.info(
        "partner_referrals_accessed",
        partner_id=partner.id,
        total_results=total,
    )

    return ReferralListResponse(
        items=[ReferralResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/referrals/stats",
    response_model=ReferralStatsResponse,
    summary="추천 회원 통계",
    description="추천 회원들의 통계를 조회합니다.",
)
async def get_my_referral_stats(
    partner: CurrentPartner,
    db: DbSession,
    days: int = Query(30, ge=1, le=365, description="조회 기간 (일)"),
):
    """Get referral statistics for current partner."""
    service = PartnerService(db)

    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=days)
    period_end = now

    stats = await service.get_referral_stats(
        partner_id=partner.id,
        period_start=period_start,
        period_end=period_end,
    )

    logger.info(
        "partner_referral_stats_accessed",
        partner_id=partner.id,
        days=days,
    )

    return ReferralStatsResponse(
        total_referrals=stats["total_referrals"],
        new_referrals_this_period=stats["new_referrals_this_period"],
        total_rake=stats["total_rake"],
        total_bet_amount=stats["total_bet_amount"],
        total_net_loss=stats["total_net_loss"],
        period_start=stats["period_start"],
        period_end=stats["period_end"],
    )


# =============================================================================
# Settlements (정산)
# =============================================================================


@router.get(
    "/settlements",
    response_model=SettlementListResponse,
    summary="내 정산 내역",
    description="내 정산 내역을 조회합니다.",
)
async def get_my_settlements(
    partner: CurrentPartner,
    db: DbSession,
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize", description="페이지 크기"),
    status_filter: SettlementStatus | None = Query(None, alias="status", description="상태 필터"),
):
    """Get settlements for current partner."""
    service = PartnerSettlementService(db)
    settlements, total = await service.list_settlements(
        partner_id=partner.id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )

    logger.info(
        "partner_settlements_accessed",
        partner_id=partner.id,
        total_results=total,
    )

    return SettlementListResponse(
        items=[SettlementResponse.model_validate(s) for s in settlements],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/settlements/summary",
    response_model=SettlementSummaryResponse,
    summary="정산 요약",
    description="정산 요약 정보를 조회합니다.",
)
async def get_my_settlement_summary(
    partner: CurrentPartner,
    db: DbSession,
):
    """Get settlement summary for current partner."""
    service = PartnerSettlementService(db)
    summary = await service.get_settlement_summary(partner.id)

    logger.info(
        "partner_settlement_summary_accessed",
        partner_id=partner.id,
    )

    return SettlementSummaryResponse(
        total_earned=summary["total_earned"],
        pending_amount=summary["pending_amount"],
        approved_amount=summary["approved_amount"],
        paid_amount=summary["paid_amount"],
        this_month_amount=summary["this_month_amount"],
    )


# =============================================================================
# Statistics
# =============================================================================


@router.get(
    "/stats/overview",
    response_model=PartnerStatsOverviewResponse,
    summary="전체 개요",
    description="파트너 대시보드 전체 개요를 조회합니다.",
)
async def get_stats_overview(
    partner: CurrentPartner,
    db: DbSession,
):
    """Get partner dashboard overview."""
    # 활성 추천 회원 수 (30일 내 로그인)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    active_query = select(func.count(User.id)).where(
        User.partner_id == partner.id,
        User.updated_at >= thirty_days_ago,  # 최근 활동 기준
    )
    active_result = await db.execute(active_query)
    active_referrals = active_result.scalar() or 0

    # 대기 중인 정산 금액
    pending_query = select(
        func.coalesce(func.sum(PartnerSettlement.commission_amount), 0)
    ).where(
        PartnerSettlement.partner_id == partner.id,
        PartnerSettlement.status.in_([SettlementStatus.PENDING, SettlementStatus.APPROVED]),
    )
    pending_result = await db.execute(pending_query)
    pending_settlement = pending_result.scalar() or 0

    logger.info(
        "partner_stats_overview_accessed",
        partner_id=partner.id,
    )

    return PartnerStatsOverviewResponse(
        total_referrals=partner.total_referrals,
        active_referrals=active_referrals,
        total_commission_earned=partner.total_commission_earned,
        current_month_commission=partner.current_month_commission,
        pending_settlement=pending_settlement,
    )


@router.get(
    "/stats/daily",
    response_model=PartnerDailyStatsResponse,
    summary="일별 통계",
    description="일별 통계를 조회합니다.",
)
async def get_daily_stats(
    partner: CurrentPartner,
    db: DbSession,
    days: int = Query(30, ge=1, le=90, description="조회 기간 (일)"),
):
    """Get daily statistics for current partner.

    Note: 현재는 간단한 구현. 실제 운영 시에는 별도 통계 테이블 사용 권장.
    """
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=days)

    # 일별 신규 가입자 수
    daily_query = (
        select(
            func.date_trunc("day", User.created_at).label("date"),
            func.count(User.id).label("referrals"),
            func.coalesce(func.sum(User.total_rake_paid_krw), 0).label("rake"),
            func.coalesce(func.sum(User.total_bet_amount_krw), 0).label("bet_amount"),
            func.coalesce(
                func.sum(func.greatest(-User.total_net_profit_krw, 0)), 0
            ).label("net_loss"),
        )
        .where(
            User.partner_id == partner.id,
            User.created_at >= period_start,
        )
        .group_by(func.date_trunc("day", User.created_at))
        .order_by(func.date_trunc("day", User.created_at))
    )
    result = await db.execute(daily_query)
    rows = result.all()

    # 수수료 계산 (레이크백 기준)
    rate = float(partner.commission_rate)
    items = []
    for row in rows:
        # 수수료 타입에 따른 계산
        if partner.commission_type.value == "rakeback":
            commission = int(row.rake * rate)
        elif partner.commission_type.value == "revshare":
            commission = int(row.net_loss * rate)
        else:  # turnover
            commission = int(row.bet_amount * rate)

        items.append(
            DailyStatItem(
                date=row.date.strftime("%Y-%m-%d"),
                referrals=row.referrals,
                rake=row.rake,
                bet_amount=row.bet_amount,
                net_loss=row.net_loss,
                commission=commission,
            )
        )

    logger.info(
        "partner_daily_stats_accessed",
        partner_id=partner.id,
        days=days,
    )

    return PartnerDailyStatsResponse(
        items=items,
        period_start=period_start,
        period_end=now,
    )


@router.get(
    "/stats/monthly",
    response_model=PartnerMonthlyStatsResponse,
    summary="월별 통계",
    description="월별 통계를 조회합니다.",
)
async def get_monthly_stats(
    partner: CurrentPartner,
    db: DbSession,
    months: int = Query(12, ge=1, le=24, description="조회 기간 (개월)"),
):
    """Get monthly statistics for current partner."""
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=months * 30)  # 대략적인 계산

    # 월별 통계
    monthly_query = (
        select(
            func.date_trunc("month", User.created_at).label("month"),
            func.count(User.id).label("referrals"),
            func.coalesce(func.sum(User.total_rake_paid_krw), 0).label("rake"),
            func.coalesce(func.sum(User.total_bet_amount_krw), 0).label("bet_amount"),
            func.coalesce(
                func.sum(func.greatest(-User.total_net_profit_krw, 0)), 0
            ).label("net_loss"),
        )
        .where(
            User.partner_id == partner.id,
            User.created_at >= period_start,
        )
        .group_by(func.date_trunc("month", User.created_at))
        .order_by(func.date_trunc("month", User.created_at))
    )
    result = await db.execute(monthly_query)
    rows = result.all()

    rate = float(partner.commission_rate)
    items = []
    for row in rows:
        if partner.commission_type.value == "rakeback":
            commission = int(row.rake * rate)
        elif partner.commission_type.value == "revshare":
            commission = int(row.net_loss * rate)
        else:  # turnover
            commission = int(row.bet_amount * rate)

        items.append(
            MonthlyStatItem(
                month=row.month.strftime("%Y-%m"),
                referrals=row.referrals,
                rake=row.rake,
                bet_amount=row.bet_amount,
                net_loss=row.net_loss,
                commission=commission,
            )
        )

    logger.info(
        "partner_monthly_stats_accessed",
        partner_id=partner.id,
        months=months,
    )

    return PartnerMonthlyStatsResponse(items=items)
