"""Partner (총판) API schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.partner import (
    CommissionType,
    PartnerStatus,
    SettlementPeriod,
    SettlementStatus,
)


# =============================================================================
# Request Schemas
# =============================================================================


class PartnerCreateRequest(BaseModel):
    """파트너 생성 요청 (어드민용)."""

    user_id: str = Field(..., alias="userId", description="파트너로 등록할 유저 ID")
    name: str = Field(..., min_length=1, max_length=100, description="파트너명")
    contact_info: str | None = Field(
        None, alias="contactInfo", max_length=255, description="연락처"
    )
    commission_type: CommissionType = Field(
        CommissionType.RAKEBACK, alias="commissionType", description="수수료 타입"
    )
    commission_rate: Decimal = Field(
        Decimal("0.30"),
        alias="commissionRate",
        ge=Decimal("0"),
        le=Decimal("1"),
        description="수수료율 (0.30 = 30%)",
    )


class PartnerUpdateRequest(BaseModel):
    """파트너 수정 요청 (어드민용)."""

    name: str | None = Field(None, min_length=1, max_length=100, description="파트너명")
    contact_info: str | None = Field(
        None, alias="contactInfo", max_length=255, description="연락처"
    )
    commission_type: CommissionType | None = Field(
        None, alias="commissionType", description="수수료 타입"
    )
    commission_rate: Decimal | None = Field(
        None,
        alias="commissionRate",
        ge=Decimal("0"),
        le=Decimal("1"),
        description="수수료율",
    )
    status: PartnerStatus | None = Field(None, description="파트너 상태")


class SettlementGenerateRequest(BaseModel):
    """정산 생성 요청 (어드민용)."""

    period_type: SettlementPeriod = Field(
        ..., alias="periodType", description="정산 기간 타입"
    )
    period_start: datetime = Field(..., alias="periodStart", description="정산 시작일")
    period_end: datetime = Field(..., alias="periodEnd", description="정산 종료일")
    partner_ids: list[str] | None = Field(
        None, alias="partnerIds", description="특정 파트너만 정산 (없으면 전체)"
    )


class SettlementUpdateRequest(BaseModel):
    """정산 상태 변경 요청 (어드민용)."""

    status: SettlementStatus = Field(..., description="변경할 상태")
    rejection_reason: str | None = Field(
        None, alias="rejectionReason", max_length=500, description="거부 사유 (거부 시)"
    )


# =============================================================================
# Response Schemas
# =============================================================================


class PartnerResponse(BaseModel):
    """파트너 응답."""

    id: str
    user_id: str = Field(alias="userId")
    partner_code: str = Field(alias="partnerCode")
    name: str
    contact_info: str | None = Field(alias="contactInfo")
    commission_type: CommissionType = Field(alias="commissionType")
    commission_rate: Decimal = Field(alias="commissionRate")
    status: PartnerStatus
    total_referrals: int = Field(alias="totalReferrals")
    total_commission_earned: int = Field(alias="totalCommissionEarned")
    current_month_commission: int = Field(alias="currentMonthCommission")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


class PartnerListResponse(BaseModel):
    """파트너 목록 응답."""

    items: list[PartnerResponse]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")

    model_config = {"populate_by_name": True}


class PartnerCodeResponse(BaseModel):
    """파트너 코드 응답."""

    partner_code: str = Field(alias="partnerCode")

    model_config = {"populate_by_name": True}


class ReferralResponse(BaseModel):
    """추천 회원 응답."""

    id: str
    nickname: str
    email: str
    total_rake_paid_krw: int = Field(alias="totalRakePaidKrw")
    total_bet_amount_krw: int = Field(alias="totalBetAmountKrw")
    total_net_profit_krw: int = Field(alias="totalNetProfitKrw")
    created_at: datetime = Field(alias="createdAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


class ReferralListResponse(BaseModel):
    """추천 회원 목록 응답."""

    items: list[ReferralResponse]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")

    model_config = {"populate_by_name": True}


class ReferralStatsResponse(BaseModel):
    """추천 회원 통계 응답."""

    total_referrals: int = Field(alias="totalReferrals")
    new_referrals_this_period: int = Field(alias="newReferralsThisPeriod")
    total_rake: int = Field(alias="totalRake")
    total_bet_amount: int = Field(alias="totalBetAmount")
    total_net_loss: int = Field(alias="totalNetLoss")  # 손실 합계 (양수)
    period_start: datetime = Field(alias="periodStart")
    period_end: datetime = Field(alias="periodEnd")

    model_config = {"populate_by_name": True}


class SettlementDetailItem(BaseModel):
    """정산 상세 항목 (유저별)."""

    user_id: str = Field(alias="userId")
    nickname: str
    amount: int  # 기준 금액 (레이크/손실/베팅량)

    model_config = {"populate_by_name": True}


class SettlementResponse(BaseModel):
    """정산 응답."""

    id: str
    partner_id: str = Field(alias="partnerId")
    period_type: SettlementPeriod = Field(alias="periodType")
    period_start: datetime = Field(alias="periodStart")
    period_end: datetime = Field(alias="periodEnd")
    commission_type: CommissionType = Field(alias="commissionType")
    commission_rate: Decimal = Field(alias="commissionRate")
    base_amount: int = Field(alias="baseAmount")
    commission_amount: int = Field(alias="commissionAmount")
    status: SettlementStatus
    approved_at: datetime | None = Field(alias="approvedAt")
    paid_at: datetime | None = Field(alias="paidAt")
    rejection_reason: str | None = Field(alias="rejectionReason")
    detail: list[SettlementDetailItem] | None = None
    created_at: datetime = Field(alias="createdAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


class SettlementListResponse(BaseModel):
    """정산 목록 응답."""

    items: list[SettlementResponse]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")

    model_config = {"populate_by_name": True}


class SettlementSummaryResponse(BaseModel):
    """정산 요약 응답."""

    total_earned: int = Field(alias="totalEarned")
    pending_amount: int = Field(alias="pendingAmount")
    approved_amount: int = Field(alias="approvedAmount")
    paid_amount: int = Field(alias="paidAmount")
    this_month_amount: int = Field(alias="thisMonthAmount")

    model_config = {"populate_by_name": True}


class PartnerStatsOverviewResponse(BaseModel):
    """파트너 통계 개요 응답."""

    total_referrals: int = Field(alias="totalReferrals")
    active_referrals: int = Field(alias="activeReferrals")
    total_commission_earned: int = Field(alias="totalCommissionEarned")
    current_month_commission: int = Field(alias="currentMonthCommission")
    pending_settlement: int = Field(alias="pendingSettlement")

    model_config = {"populate_by_name": True}


class DailyStatItem(BaseModel):
    """일별 통계 항목."""

    date: str
    referrals: int
    rake: int
    bet_amount: int = Field(alias="betAmount")
    net_loss: int = Field(alias="netLoss")
    commission: int

    model_config = {"populate_by_name": True}


class PartnerDailyStatsResponse(BaseModel):
    """파트너 일별 통계 응답."""

    items: list[DailyStatItem]
    period_start: datetime = Field(alias="periodStart")
    period_end: datetime = Field(alias="periodEnd")

    model_config = {"populate_by_name": True}


class MonthlyStatItem(BaseModel):
    """월별 통계 항목."""

    month: str  # YYYY-MM format
    referrals: int
    rake: int
    bet_amount: int = Field(alias="betAmount")
    net_loss: int = Field(alias="netLoss")
    commission: int

    model_config = {"populate_by_name": True}


class PartnerMonthlyStatsResponse(BaseModel):
    """파트너 월별 통계 응답."""

    items: list[MonthlyStatItem]

    model_config = {"populate_by_name": True}
