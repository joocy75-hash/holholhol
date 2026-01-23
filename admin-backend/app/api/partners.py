"""
Partners API - 파트너(총판) 관리 엔드포인트
Admin-backend에서 main DB의 partners 테이블을 직접 조회합니다.
"""
import logging
import secrets
import string
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Query, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.database import get_main_db
from app.utils.dependencies import require_operator
from app.models.admin_user import AdminUser

logger = logging.getLogger(__name__)
router = APIRouter()


def generate_partner_code(length: int = 8) -> str:
    """8자리 대문자+숫자 파트너 코드 생성"""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


# =============================================================================
# Request Models
# =============================================================================

class CreatePartnerRequest(BaseModel):
    user_id: str = Field(..., description="파트너로 등록할 유저 ID")
    partner_code: str = Field(..., min_length=1, max_length=20, description="파트너 코드 (관리자 직접 입력)")
    name: str = Field(..., description="파트너명")
    contact_info: Optional[str] = Field(None, description="연락처")
    notes: Optional[str] = Field(None, description="비고")
    commission_type: str = Field("rakeback", description="수수료 타입")
    commission_rate: float = Field(0.30, ge=0, le=1, description="수수료율 (0~1)")


class UpdatePartnerRequest(BaseModel):
    name: Optional[str] = Field(None, description="파트너명")
    contact_info: Optional[str] = Field(None, description="연락처")
    notes: Optional[str] = Field(None, description="비고")
    commission_type: Optional[str] = Field(None, description="수수료 타입")
    commission_rate: Optional[float] = Field(None, ge=0, le=1, description="수수료율")
    status: Optional[str] = Field(None, description="상태")


# =============================================================================
# Response Models
# =============================================================================

class PartnerResponse(BaseModel):
    id: str
    user_id: str = Field(serialization_alias="userId")
    partner_code: str = Field(serialization_alias="partnerCode")
    name: str
    contact_info: Optional[str] = Field(serialization_alias="contactInfo")
    notes: Optional[str] = None
    commission_type: str = Field(serialization_alias="commissionType")
    commission_rate: float = Field(serialization_alias="commissionRate")
    status: str
    total_referrals: int = Field(serialization_alias="totalReferrals")
    total_commission_earned: int = Field(serialization_alias="totalCommissionEarned")
    current_month_commission: int = Field(serialization_alias="currentMonthCommission")
    created_at: str = Field(serialization_alias="createdAt")
    updated_at: str = Field(serialization_alias="updatedAt")

    model_config = {"populate_by_name": True}


class PaginatedPartners(BaseModel):
    items: list[PartnerResponse]
    total: int
    page: int
    page_size: int = Field(serialization_alias="pageSize")

    model_config = {"populate_by_name": True}


class SettlementResponse(BaseModel):
    id: str
    partner_id: str = Field(serialization_alias="partnerId")
    partner_name: Optional[str] = Field(None, serialization_alias="partnerName")
    partner_code: Optional[str] = Field(None, serialization_alias="partnerCode")
    period_type: str = Field(serialization_alias="periodType")
    period_start: str = Field(serialization_alias="periodStart")
    period_end: str = Field(serialization_alias="periodEnd")
    commission_type: str = Field(serialization_alias="commissionType")
    commission_rate: float = Field(serialization_alias="commissionRate")
    base_amount: int = Field(serialization_alias="baseAmount")
    commission_amount: int = Field(serialization_alias="commissionAmount")
    status: str
    approved_at: Optional[str] = Field(None, serialization_alias="approvedAt")
    paid_at: Optional[str] = Field(None, serialization_alias="paidAt")
    rejection_reason: Optional[str] = Field(None, serialization_alias="rejectionReason")
    created_at: str = Field(serialization_alias="createdAt")

    model_config = {"populate_by_name": True}


class PaginatedSettlements(BaseModel):
    items: list[SettlementResponse]
    total: int
    page: int
    page_size: int = Field(serialization_alias="pageSize")

    model_config = {"populate_by_name": True}


class ReferralResponse(BaseModel):
    id: str
    nickname: str
    email: str
    total_rake_paid_krw: int = Field(serialization_alias="totalRakePaidKrw")
    total_bet_amount_krw: int = Field(serialization_alias="totalBetAmountKrw")
    total_net_profit_krw: int = Field(serialization_alias="totalNetProfitKrw")
    created_at: str = Field(serialization_alias="createdAt")

    model_config = {"populate_by_name": True}


class PaginatedReferrals(BaseModel):
    items: list[ReferralResponse]
    total: int
    page: int
    page_size: int = Field(serialization_alias="pageSize")

    model_config = {"populate_by_name": True}


class RegenerateCodeResponse(BaseModel):
    partner_code: str = Field(serialization_alias="partnerCode")

    model_config = {"populate_by_name": True}


# =============================================================================
# Settlement Endpoints (MUST be before /{partner_id} routes!)
# =============================================================================

@router.get("/settlements", response_model=PaginatedSettlements)
async def list_settlements(
    partner_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    period_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="page_size"),
    current_user: AdminUser = Depends(require_operator),
    main_db: AsyncSession = Depends(get_main_db),
):
    """정산 목록 조회"""
    try:
        offset = (page - 1) * page_size
        params = {"limit": page_size, "offset": offset}

        where_clauses = ["1=1"]
        if partner_id:
            where_clauses.append("s.partner_id = :partner_id")
            params["partner_id"] = partner_id
        if status_filter:
            where_clauses.append("s.status = :status")
            params["status"] = status_filter
        if period_type:
            where_clauses.append("s.period_type = :period_type")
            params["period_type"] = period_type

        where_sql = " AND ".join(where_clauses)

        # Count query
        count_query = text(f"SELECT COUNT(*) FROM partner_settlements s WHERE {where_sql}")
        count_result = await main_db.execute(count_query, params)
        total = count_result.scalar() or 0

        # List query with partner info
        list_query = text(f"""
            SELECT s.id, s.partner_id, s.period_type, s.period_start, s.period_end,
                   s.commission_type, s.commission_rate, s.base_amount, s.commission_amount,
                   s.status, s.approved_at, s.paid_at, s.rejection_reason, s.created_at,
                   p.name as partner_name, p.partner_code
            FROM partner_settlements s
            LEFT JOIN partners p ON s.partner_id = p.id
            WHERE {where_sql}
            ORDER BY s.created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        result = await main_db.execute(list_query, params)
        rows = result.fetchall()

        items = [
            SettlementResponse(
                id=str(row.id),
                partner_id=str(row.partner_id),
                partner_name=row.partner_name,
                partner_code=row.partner_code,
                period_type=row.period_type,
                period_start=row.period_start.isoformat() if row.period_start else "",
                period_end=row.period_end.isoformat() if row.period_end else "",
                commission_type=row.commission_type,
                commission_rate=float(row.commission_rate),
                base_amount=row.base_amount,
                commission_amount=row.commission_amount,
                status=row.status,
                approved_at=row.approved_at.isoformat() if row.approved_at else None,
                paid_at=row.paid_at.isoformat() if row.paid_at else None,
                rejection_reason=row.rejection_reason,
                created_at=row.created_at.isoformat() if row.created_at else "",
            )
            for row in rows
        ]

        return PaginatedSettlements(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        error_str = str(e).lower()
        if "does not exist" in error_str or "relation" in error_str:
            logger.warning("partner_settlements 테이블이 없습니다. 빈 목록 반환.")
            return PaginatedSettlements(items=[], total=0, page=page, page_size=page_size)
        logger.error(f"Failed to list settlements: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Partner Endpoints
# =============================================================================

@router.get("", response_model=PaginatedPartners)
async def list_partners(
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="page_size"),
    current_user: AdminUser = Depends(require_operator),
    main_db: AsyncSession = Depends(get_main_db),
):
    """파트너 목록 조회"""
    try:
        offset = (page - 1) * page_size
        params = {"limit": page_size, "offset": offset}

        where_clauses = ["1=1"]
        if status_filter:
            where_clauses.append("p.status = :status")
            params["status"] = status_filter
        if search:
            where_clauses.append("(p.name ILIKE :search OR p.partner_code ILIKE :search)")
            params["search"] = f"%{search}%"

        where_sql = " AND ".join(where_clauses)

        # Count query
        count_query = text(f"SELECT COUNT(*) FROM partners p WHERE {where_sql}")
        count_result = await main_db.execute(count_query, params)
        total = count_result.scalar() or 0

        # List query
        list_query = text(f"""
            SELECT p.id, p.user_id, p.partner_code, p.name, p.contact_info, p.notes,
                   p.commission_type, p.commission_rate, p.status,
                   p.total_referrals, p.total_commission_earned, p.current_month_commission,
                   p.created_at, p.updated_at
            FROM partners p
            WHERE {where_sql}
            ORDER BY p.created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        result = await main_db.execute(list_query, params)
        rows = result.fetchall()

        items = [
            PartnerResponse(
                id=str(row.id),
                user_id=str(row.user_id),
                partner_code=row.partner_code,
                name=row.name,
                contact_info=row.contact_info,
                notes=row.notes,
                commission_type=row.commission_type,
                commission_rate=float(row.commission_rate),
                status=row.status,
                total_referrals=row.total_referrals,
                total_commission_earned=row.total_commission_earned,
                current_month_commission=row.current_month_commission,
                created_at=row.created_at.isoformat() if row.created_at else "",
                updated_at=row.updated_at.isoformat() if row.updated_at else "",
            )
            for row in rows
        ]

        return PaginatedPartners(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        error_str = str(e).lower()
        if "does not exist" in error_str or "relation" in error_str:
            logger.warning("partners 테이블이 없습니다. 빈 목록 반환.")
            return PaginatedPartners(items=[], total=0, page=page, page_size=page_size)
        logger.error(f"Failed to list partners: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{partner_id}", response_model=PartnerResponse)
async def get_partner(
    partner_id: str,
    current_user: AdminUser = Depends(require_operator),
    main_db: AsyncSession = Depends(get_main_db),
):
    """파트너 상세 조회"""
    try:
        query = text("""
            SELECT p.id, p.user_id, p.partner_code, p.name, p.contact_info, p.notes,
                   p.commission_type, p.commission_rate, p.status,
                   p.total_referrals, p.total_commission_earned, p.current_month_commission,
                   p.created_at, p.updated_at
            FROM partners p
            WHERE p.id = :partner_id
        """)
        result = await main_db.execute(query, {"partner_id": partner_id})
        row = result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Partner not found")

        return PartnerResponse(
            id=str(row.id),
            user_id=str(row.user_id),
            partner_code=row.partner_code,
            name=row.name,
            contact_info=row.contact_info,
            notes=row.notes,
            commission_type=row.commission_type,
            commission_rate=float(row.commission_rate),
            status=row.status,
            total_referrals=row.total_referrals,
            total_commission_earned=row.total_commission_earned,
            current_month_commission=row.current_month_commission,
            created_at=row.created_at.isoformat() if row.created_at else "",
            updated_at=row.updated_at.isoformat() if row.updated_at else "",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get partner: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=PartnerResponse, status_code=status.HTTP_201_CREATED)
async def create_partner(
    request: CreatePartnerRequest,
    current_user: AdminUser = Depends(require_operator),
    main_db: AsyncSession = Depends(get_main_db),
):
    """파트너 생성"""
    try:
        # 1. 유저 존재 여부 확인
        user_query = text("SELECT id, nickname, email FROM users WHERE id = :user_id")
        user_result = await main_db.execute(user_query, {"user_id": request.user_id})
        user_row = user_result.fetchone()

        if not user_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="존재하지 않는 유저입니다."
            )

        # 2. 이미 파트너인지 확인
        existing_query = text("SELECT id FROM partners WHERE user_id = :user_id")
        existing_result = await main_db.execute(existing_query, {"user_id": request.user_id})
        if existing_result.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 파트너로 등록된 유저입니다."
            )

        # 3. 파트너 코드 중복 확인
        partner_code = request.partner_code.strip().upper()  # 대문자로 변환
        code_check_query = text("SELECT id FROM partners WHERE partner_code = :code")
        code_check_result = await main_db.execute(code_check_query, {"code": partner_code})
        if code_check_result.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 사용 중인 파트너 코드입니다."
            )

        # 4. 파트너 생성
        partner_id = str(uuid.uuid4())
        now = datetime.utcnow()

        insert_query = text("""
            INSERT INTO partners (
                id, user_id, partner_code, name, contact_info, notes,
                commission_type, commission_rate, status,
                total_referrals, total_commission_earned, current_month_commission,
                created_at, updated_at
            ) VALUES (
                :id, :user_id, :partner_code, :name, :contact_info, :notes,
                :commission_type, :commission_rate, 'active',
                0, 0, 0,
                :created_at, :updated_at
            )
            RETURNING id, user_id, partner_code, name, contact_info, notes,
                      commission_type, commission_rate, status,
                      total_referrals, total_commission_earned, current_month_commission,
                      created_at, updated_at
        """)

        result = await main_db.execute(insert_query, {
            "id": partner_id,
            "user_id": request.user_id,
            "partner_code": partner_code,
            "name": request.name,
            "contact_info": request.contact_info,
            "notes": request.notes,
            "commission_type": request.commission_type,
            "commission_rate": request.commission_rate,
            "created_at": now,
            "updated_at": now,
        })
        row = result.fetchone()
        await main_db.commit()

        return PartnerResponse(
            id=str(row.id),
            user_id=str(row.user_id),
            partner_code=row.partner_code,
            name=row.name,
            contact_info=row.contact_info,
            notes=row.notes,
            commission_type=row.commission_type,
            commission_rate=float(row.commission_rate),
            status=row.status,
            total_referrals=row.total_referrals,
            total_commission_earned=row.total_commission_earned,
            current_month_commission=row.current_month_commission,
            created_at=row.created_at.isoformat() if row.created_at else "",
            updated_at=row.updated_at.isoformat() if row.updated_at else "",
        )
    except HTTPException:
        raise
    except Exception as e:
        await main_db.rollback()
        logger.error(f"Failed to create partner: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{partner_id}", response_model=PartnerResponse)
async def update_partner(
    partner_id: str,
    request: UpdatePartnerRequest,
    current_user: AdminUser = Depends(require_operator),
    main_db: AsyncSession = Depends(get_main_db),
):
    """파트너 정보 수정"""
    try:
        # 파트너 존재 확인
        check_query = text("SELECT id FROM partners WHERE id = :partner_id")
        check_result = await main_db.execute(check_query, {"partner_id": partner_id})
        if not check_result.fetchone():
            raise HTTPException(status_code=404, detail="파트너를 찾을 수 없습니다.")

        # 업데이트할 필드 구성
        updates = []
        params = {"partner_id": partner_id, "updated_at": datetime.utcnow()}

        if request.name is not None:
            updates.append("name = :name")
            params["name"] = request.name
        if request.contact_info is not None:
            updates.append("contact_info = :contact_info")
            params["contact_info"] = request.contact_info
        if request.notes is not None:
            updates.append("notes = :notes")
            params["notes"] = request.notes
        if request.commission_type is not None:
            updates.append("commission_type = :commission_type")
            params["commission_type"] = request.commission_type
        if request.commission_rate is not None:
            updates.append("commission_rate = :commission_rate")
            params["commission_rate"] = request.commission_rate
        if request.status is not None:
            updates.append("status = :status")
            params["status"] = request.status

        updates.append("updated_at = :updated_at")

        if len(updates) == 1:  # 업데이트할 것이 updated_at 뿐
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="수정할 내용이 없습니다."
            )

        update_query = text(f"""
            UPDATE partners
            SET {", ".join(updates)}
            WHERE id = :partner_id
            RETURNING id, user_id, partner_code, name, contact_info, notes,
                      commission_type, commission_rate, status,
                      total_referrals, total_commission_earned, current_month_commission,
                      created_at, updated_at
        """)

        result = await main_db.execute(update_query, params)
        row = result.fetchone()
        await main_db.commit()

        return PartnerResponse(
            id=str(row.id),
            user_id=str(row.user_id),
            partner_code=row.partner_code,
            name=row.name,
            contact_info=row.contact_info,
            notes=row.notes,
            commission_type=row.commission_type,
            commission_rate=float(row.commission_rate),
            status=row.status,
            total_referrals=row.total_referrals,
            total_commission_earned=row.total_commission_earned,
            current_month_commission=row.current_month_commission,
            created_at=row.created_at.isoformat() if row.created_at else "",
            updated_at=row.updated_at.isoformat() if row.updated_at else "",
        )
    except HTTPException:
        raise
    except Exception as e:
        await main_db.rollback()
        logger.error(f"Failed to update partner: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{partner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_partner(
    partner_id: str,
    current_user: AdminUser = Depends(require_operator),
    main_db: AsyncSession = Depends(get_main_db),
):
    """파트너 삭제 (소프트 삭제 - 상태를 terminated로 변경)"""
    try:
        # 파트너 존재 확인
        check_query = text("SELECT id, status FROM partners WHERE id = :partner_id")
        check_result = await main_db.execute(check_query, {"partner_id": partner_id})
        row = check_result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="파트너를 찾을 수 없습니다.")

        if row.status == "terminated":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 해지된 파트너입니다."
            )

        # 소프트 삭제 (상태를 terminated로 변경)
        delete_query = text("""
            UPDATE partners
            SET status = 'terminated', updated_at = :updated_at
            WHERE id = :partner_id
        """)
        await main_db.execute(delete_query, {
            "partner_id": partner_id,
            "updated_at": datetime.utcnow()
        })
        await main_db.commit()

    except HTTPException:
        raise
    except Exception as e:
        await main_db.rollback()
        logger.error(f"Failed to delete partner: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{partner_id}/regenerate-code", response_model=RegenerateCodeResponse)
async def regenerate_partner_code(
    partner_id: str,
    current_user: AdminUser = Depends(require_operator),
    main_db: AsyncSession = Depends(get_main_db),
):
    """파트너 코드 재생성"""
    try:
        # 파트너 존재 확인
        check_query = text("SELECT id FROM partners WHERE id = :partner_id")
        check_result = await main_db.execute(check_query, {"partner_id": partner_id})
        if not check_result.fetchone():
            raise HTTPException(status_code=404, detail="파트너를 찾을 수 없습니다.")

        # 유니크한 파트너 코드 생성 (최대 10회 시도)
        new_code = None
        for _ in range(10):
            candidate = generate_partner_code()
            code_check = text("SELECT id FROM partners WHERE partner_code = :code AND id != :partner_id")
            code_result = await main_db.execute(code_check, {"code": candidate, "partner_id": partner_id})
            if not code_result.fetchone():
                new_code = candidate
                break

        if not new_code:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="파트너 코드 생성에 실패했습니다."
            )

        # 코드 업데이트
        update_query = text("""
            UPDATE partners
            SET partner_code = :new_code, updated_at = :updated_at
            WHERE id = :partner_id
        """)
        await main_db.execute(update_query, {
            "partner_id": partner_id,
            "new_code": new_code,
            "updated_at": datetime.utcnow()
        })
        await main_db.commit()

        return RegenerateCodeResponse(partner_code=new_code)
    except HTTPException:
        raise
    except Exception as e:
        await main_db.rollback()
        logger.error(f"Failed to regenerate partner code: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{partner_id}/referrals", response_model=PaginatedReferrals)
async def get_partner_referrals(
    partner_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="page_size"),
    current_user: AdminUser = Depends(require_operator),
    main_db: AsyncSession = Depends(get_main_db),
):
    """파트너의 추천 회원 목록 조회"""
    try:
        # 파트너 존재 확인
        check_query = text("SELECT id FROM partners WHERE id = :partner_id")
        check_result = await main_db.execute(check_query, {"partner_id": partner_id})
        if not check_result.fetchone():
            raise HTTPException(status_code=404, detail="파트너를 찾을 수 없습니다.")

        offset = (page - 1) * page_size
        params = {"partner_id": partner_id, "limit": page_size, "offset": offset}

        # 파트너에 연결된 사용자 조회 (partner_id 필드로 연결)
        count_query = text("""
            SELECT COUNT(*) FROM users
            WHERE partner_id = :partner_id
        """)
        count_result = await main_db.execute(count_query, params)
        total = count_result.scalar() or 0

        list_query = text("""
            SELECT u.id, u.nickname, u.email,
                   COALESCE(u.total_rake_paid_krw, 0) as total_rake_paid_krw,
                   COALESCE(u.total_bet_amount_krw, 0) as total_bet_amount_krw,
                   COALESCE(u.total_net_profit_krw, 0) as total_net_profit_krw,
                   u.created_at
            FROM users u
            WHERE u.partner_id = :partner_id
            ORDER BY u.created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        result = await main_db.execute(list_query, params)
        rows = result.fetchall()

        items = [
            ReferralResponse(
                id=str(row.id),
                nickname=row.nickname or "",
                email=row.email or "",
                total_rake_paid_krw=row.total_rake_paid_krw,
                total_bet_amount_krw=row.total_bet_amount_krw,
                total_net_profit_krw=row.total_net_profit_krw,
                created_at=row.created_at.isoformat() if row.created_at else "",
            )
            for row in rows
        ]

        return PaginatedReferrals(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e).lower()
        if "column" in error_str and "does not exist" in error_str:
            # partner_id 컬럼이 없으면 빈 목록 반환
            logger.warning("users 테이블에 partner_id 필드가 없습니다. 빈 목록 반환.")
            return PaginatedReferrals(items=[], total=0, page=page, page_size=page_size)
        logger.error(f"Failed to get partner referrals: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{partner_id}/settlements", response_model=PaginatedSettlements)
async def list_partner_settlements(
    partner_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="page_size"),
    current_user: AdminUser = Depends(require_operator),
    main_db: AsyncSession = Depends(get_main_db),
):
    """특정 파트너의 정산 목록 조회"""
    try:
        offset = (page - 1) * page_size
        params = {"partner_id": partner_id, "limit": page_size, "offset": offset}

        where_clauses = ["s.partner_id = :partner_id"]
        if status_filter:
            where_clauses.append("s.status = :status")
            params["status"] = status_filter

        where_sql = " AND ".join(where_clauses)

        # Count query
        count_query = text(f"SELECT COUNT(*) FROM partner_settlements s WHERE {where_sql}")
        count_result = await main_db.execute(count_query, params)
        total = count_result.scalar() or 0

        # List query
        list_query = text(f"""
            SELECT s.id, s.partner_id, s.period_type, s.period_start, s.period_end,
                   s.commission_type, s.commission_rate, s.base_amount, s.commission_amount,
                   s.status, s.approved_at, s.paid_at, s.rejection_reason, s.created_at,
                   p.name as partner_name, p.partner_code
            FROM partner_settlements s
            LEFT JOIN partners p ON s.partner_id = p.id
            WHERE {where_sql}
            ORDER BY s.created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        result = await main_db.execute(list_query, params)
        rows = result.fetchall()

        items = [
            SettlementResponse(
                id=str(row.id),
                partner_id=str(row.partner_id),
                partner_name=row.partner_name,
                partner_code=row.partner_code,
                period_type=row.period_type,
                period_start=row.period_start.isoformat() if row.period_start else "",
                period_end=row.period_end.isoformat() if row.period_end else "",
                commission_type=row.commission_type,
                commission_rate=float(row.commission_rate),
                base_amount=row.base_amount,
                commission_amount=row.commission_amount,
                status=row.status,
                approved_at=row.approved_at.isoformat() if row.approved_at else None,
                paid_at=row.paid_at.isoformat() if row.paid_at else None,
                rejection_reason=row.rejection_reason,
                created_at=row.created_at.isoformat() if row.created_at else "",
            )
            for row in rows
        ]

        return PaginatedSettlements(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        error_str = str(e).lower()
        if "does not exist" in error_str or "relation" in error_str:
            logger.warning("partner_settlements 테이블이 없습니다. 빈 목록 반환.")
            return PaginatedSettlements(items=[], total=0, page=page, page_size=page_size)
        logger.error(f"Failed to list partner settlements: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
