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
from app.services.partner_stats import PartnerStatsService

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

    사전 집계된 통계 테이블에서 빠르게 조회합니다.

    Note:
        - partner_daily_stats 테이블에서 조회 (O(1) 성능)
        - 통계가 없는 날짜는 자동으로 집계 시도 (fallback)
    """
    stats_service = PartnerStatsService(db)

    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=days)
    start_date = period_start.date()
    end_date = now.date()

    # 사전 집계된 통계 조회
    daily_stats = await stats_service.get_daily_stats(
        partner_id=str(partner.id),
        start_date=start_date,
        end_date=end_date,
    )

    # 응답 포맷 변환
    items = []
    for stat in daily_stats:
        items.append(
            DailyStatItem(
                date=stat.date.strftime("%Y-%m-%d"),
                referrals=stat.new_referrals,
                rake=stat.total_rake,
                bet_amount=stat.total_bet_amount,
                net_loss=stat.total_net_loss,
                commission=stat.commission_amount,
            )
        )

    logger.info(
        "partner_daily_stats_accessed",
        partner_id=partner.id,
        days=days,
        stats_count=len(items),
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
    """Get monthly statistics for current partner.

    사전 집계된 일일 통계를 월별로 합산하여 반환합니다.
    """
    stats_service = PartnerStatsService(db)
    now = datetime.now(timezone.utc)

    items = []

    # 최근 N개월의 통계 조회
    for i in range(months):
        # 현재 월부터 과거로 역순 계산
        target_date = now - timedelta(days=i * 30)
        year = target_date.year
        month = target_date.month

        # 월간 통계 조회 (일일 통계 합산)
        monthly_stat = await stats_service.get_monthly_stats(
            partner_id=str(partner.id),
            year=year,
            month=month,
        )

        # 통계가 있는 월만 포함
        if monthly_stat["days_count"] > 0:
            items.append(
                MonthlyStatItem(
                    month=f"{year}-{month:02d}",
                    referrals=monthly_stat["new_referrals"],
                    rake=monthly_stat["total_rake"],
                    bet_amount=monthly_stat["total_bet_amount"],
                    net_loss=monthly_stat["total_net_loss"],
                    commission=monthly_stat["commission_amount"],
                )
            )

    # 날짜순 정렬 (오래된 것부터)
    items.reverse()

    logger.info(
        "partner_monthly_stats_accessed",
        partner_id=partner.id,
        months=months,
        stats_count=len(items),
    )

    return PartnerMonthlyStatsResponse(items=items)
