from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()


class AuditLogResponse(BaseModel):
    id: str
    admin_user_id: str
    admin_username: str
    action: str
    target_type: str
    target_id: str
    details: dict
    ip_address: str
    created_at: str


class PaginatedAuditLogs(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


@router.get("", response_model=PaginatedAuditLogs)
async def list_audit_logs(
    action: str | None = Query(None, description="Filter by action type"),
    admin_user_id: str | None = Query(None, description="Filter by admin user"),
    target_type: str | None = Query(None, description="Filter by target type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List audit logs"""
    # TODO: Implement actual audit log listing
    return PaginatedAuditLogs(
        items=[],
        total=0,
        page=page,
        page_size=page_size,
        total_pages=0,
    )
