"""Admin Partner API endpoints.

어드민 프론트엔드에서 호출하는 파트너(총판) 관리 API입니다.
JWT 인증을 통해 보호됩니다.
"""

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.models.partner import PartnerStatus, SettlementStatus
from app.schemas.partner import (
    PartnerCreateRequest,
    PartnerListResponse,
    PartnerResponse,
    PartnerUpdateRequest,
    ReferralListResponse,
    ReferralResponse,
    SettlementGenerateRequest,
    SettlementListResponse,
    SettlementResponse,
    SettlementUpdateRequest,
)
from app.services.partner import PartnerError, PartnerService
from app.services.partner_settlement import PartnerSettlementService, SettlementError

router = APIRouter(prefix="/admin/partners", tags=["Admin - Partners"])
logger = logging.getLogger(__name__)


# =============================================================================
# Partner CRUD
# =============================================================================


@router.post(
    "",
    response_model=PartnerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="파트너 생성",
    description="새로운 파트너(총판)를 생성합니다.",
)
async def create_partner(
    request: PartnerCreateRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Create a new partner."""
    service = PartnerService(db)
    try:
        partner = await service.create_partner(
            user_id=request.user_id,
            name=request.name,
            commission_type=request.commission_type,
            commission_rate=request.commission_rate,
            contact_info=request.contact_info,
        )
        await db.commit()
        return PartnerResponse.model_validate(partner)
    except PartnerError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": e.message, "details": e.details}},
        )


@router.get(
    "",
    response_model=PartnerListResponse,
    summary="파트너 목록 조회",
    description="전체 파트너 목록을 조회합니다.",
)
async def list_partners(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize", description="페이지 크기"),
    status_filter: PartnerStatus | None = Query(None, alias="status", description="상태 필터"),
    search: str | None = Query(None, description="검색어 (이름, 코드)"),
):
    """List all partners with pagination."""
    service = PartnerService(db)
    partners, total = await service.list_partners(
        page=page,
        page_size=page_size,
        status=status_filter,
        search=search,
    )
    return PartnerListResponse(
        items=[PartnerResponse.model_validate(p) for p in partners],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{partner_id}",
    response_model=PartnerResponse,
    summary="파트너 상세 조회",
    description="특정 파트너의 상세 정보를 조회합니다.",
)
async def get_partner(
    partner_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get partner by ID."""
    service = PartnerService(db)
    partner = await service.get_partner(partner_id)
    if not partner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PARTNER_NOT_FOUND", "message": "파트너를 찾을 수 없습니다"}},
        )
    return PartnerResponse.model_validate(partner)


@router.patch(
    "/{partner_id}",
    response_model=PartnerResponse,
    summary="파트너 수정",
    description="파트너 정보를 수정합니다.",
)
async def update_partner(
    partner_id: str,
    request: PartnerUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Update partner information."""
    service = PartnerService(db)
    try:
        partner = await service.update_partner(
            partner_id=partner_id,
            name=request.name,
            commission_type=request.commission_type,
            commission_rate=request.commission_rate,
            contact_info=request.contact_info,
            status=request.status,
        )
        await db.commit()
        return PartnerResponse.model_validate(partner)
    except PartnerError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": e.message, "details": e.details}},
        )


@router.delete(
    "/{partner_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="파트너 삭제",
    description="파트너를 삭제합니다 (소프트 삭제).",
)
async def delete_partner(
    partner_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """Soft delete partner (set status to TERMINATED)."""
    service = PartnerService(db)
    try:
        await service.delete_partner(partner_id)
        await db.commit()
    except PartnerError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": e.message, "details": e.details}},
        )


@router.post(
    "/{partner_id}/regenerate-code",
    response_model=dict,
    summary="파트너 코드 재생성",
    description="파트너 코드를 새로 생성합니다.",
)
async def regenerate_partner_code(
    partner_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """Regenerate partner code."""
    service = PartnerService(db)
    try:
        new_code = await service.regenerate_code(partner_id)
        await db.commit()
        return {"partnerCode": new_code}
    except PartnerError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": e.message, "details": e.details}},
        )


# =============================================================================
# Partner Referrals
# =============================================================================


@router.get(
    "/{partner_id}/referrals",
    response_model=ReferralListResponse,
    summary="추천 회원 목록 조회",
    description="특정 파트너의 추천 회원 목록을 조회합니다.",
)
async def get_partner_referrals(
    partner_id: str,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize", description="페이지 크기"),
    search: str | None = Query(None, description="검색어 (닉네임, 이메일)"),
):
    """Get referrals for a partner."""
    service = PartnerService(db)
    users, total = await service.get_referrals(
        partner_id=partner_id,
        page=page,
        page_size=page_size,
        search=search,
    )
    return ReferralListResponse(
        items=[ReferralResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


# =============================================================================
# Settlement Management
# =============================================================================


@router.get(
    "/settlements",
    response_model=SettlementListResponse,
    summary="전체 정산 목록 조회",
    description="모든 파트너의 정산 목록을 조회합니다.",
)
async def list_all_settlements(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize", description="페이지 크기"),
    status_filter: SettlementStatus | None = Query(None, alias="status", description="상태 필터"),
):
    """List all settlements with pagination."""
    service = PartnerSettlementService(db)
    settlements, total = await service.list_settlements(
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return SettlementListResponse(
        items=[SettlementResponse.model_validate(s) for s in settlements],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{partner_id}/settlements",
    response_model=SettlementListResponse,
    summary="특정 파트너 정산 목록 조회",
    description="특정 파트너의 정산 목록을 조회합니다.",
)
async def list_partner_settlements(
    partner_id: str,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize", description="페이지 크기"),
    status_filter: SettlementStatus | None = Query(None, alias="status", description="상태 필터"),
):
    """List settlements for a specific partner."""
    service = PartnerSettlementService(db)
    settlements, total = await service.list_settlements(
        partner_id=partner_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return SettlementListResponse(
        items=[SettlementResponse.model_validate(s) for s in settlements],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/settlements/generate",
    response_model=list[SettlementResponse],
    summary="정산 생성",
    description="지정된 기간에 대한 파트너 정산을 생성합니다.",
)
async def generate_settlements(
    request: SettlementGenerateRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Generate settlements for partners."""
    service = PartnerSettlementService(db)
    try:
        settlements = await service.generate_settlements(
            period_type=request.period_type,
            period_start=request.period_start,
            period_end=request.period_end,
            partner_ids=request.partner_ids,
        )
        await db.commit()
        return [SettlementResponse.model_validate(s) for s in settlements]
    except SettlementError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": e.message, "details": e.details}},
        )


@router.patch(
    "/settlements/{settlement_id}",
    response_model=SettlementResponse,
    summary="정산 상태 변경",
    description="정산 상태를 변경합니다 (승인/거부).",
)
async def update_settlement(
    settlement_id: str,
    request: SettlementUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Update settlement status (approve/reject)."""
    service = PartnerSettlementService(db)
    try:
        if request.status == SettlementStatus.APPROVED:
            settlement = await service.approve_settlement(settlement_id, current_user.id)
        elif request.status == SettlementStatus.REJECTED:
            if not request.rejection_reason:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": {"code": "REJECTION_REASON_REQUIRED", "message": "거부 사유가 필요합니다"}},
                )
            settlement = await service.reject_settlement(
                settlement_id, current_user.id, request.rejection_reason
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "INVALID_STATUS", "message": "유효하지 않은 상태입니다"}},
            )
        await db.commit()
        return SettlementResponse.model_validate(settlement)
    except SettlementError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": e.message, "details": e.details}},
        )


@router.post(
    "/settlements/{settlement_id}/pay",
    response_model=SettlementResponse,
    summary="정산 지급",
    description="승인된 정산을 지급 처리합니다.",
)
async def pay_settlement(
    settlement_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """Pay an approved settlement."""
    service = PartnerSettlementService(db)
    try:
        settlement = await service.pay_settlement(settlement_id, current_user.id)
        await db.commit()
        return SettlementResponse.model_validate(settlement)
    except SettlementError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": e.code, "message": e.message, "details": e.details}},
        )
