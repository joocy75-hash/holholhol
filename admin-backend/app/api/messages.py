"""쪽지 관리 API - 어드민용"""

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_admin_db
from app.utils.dependencies import require_admin
from app.models.admin_user import AdminUser
from app.services.message_service import MessageService
from app.config import get_settings

router = APIRouter()
settings = get_settings()


# ============================================================================
# Request/Response Models
# ============================================================================


class SendMessageRequest(BaseModel):
    """쪽지 발송 요청"""
    recipient_id: str = Field(..., description="수신자 ID")
    title: str = Field(..., min_length=1, max_length=200, description="제목")
    content: str = Field(..., min_length=1, description="내용")


class SendBulkMessageRequest(BaseModel):
    """대량 쪽지 발송 요청"""
    recipient_ids: list[str] = Field(..., min_items=1, description="수신자 ID 목록")
    title: str = Field(..., min_length=1, max_length=200, description="제목")
    content: str = Field(..., min_length=1, description="내용")


class MessageResponse(BaseModel):
    """쪽지 응답"""
    id: str
    sender_id: str
    recipient_id: str
    title: str
    content: str
    is_read: bool
    read_at: str | None
    created_at: str | None

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    """쪽지 목록 응답"""
    items: list[MessageResponse]
    total: int
    page: int
    page_size: int


class SendResultResponse(BaseModel):
    """발송 결과 응답"""
    success: bool
    message_id: str | None = None
    sent_count: int = 0


class UnreadCountResponse(BaseModel):
    """읽지 않은 쪽지 개수"""
    count: int


class MarkReadResponse(BaseModel):
    """읽음 처리 결과"""
    success: bool
    marked_count: int


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/send", response_model=SendResultResponse)
async def send_message(
    request: SendMessageRequest,
    admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_admin_db),
):
    """개별 유저에게 쪽지 발송"""
    service = MessageService(db)
    message = await service.send_message(
        sender_id=admin.id,
        recipient_id=request.recipient_id,
        title=request.title,
        content=request.content,
    )
    return SendResultResponse(
        success=True,
        message_id=message.id,
        sent_count=1,
    )


@router.post("/send-bulk", response_model=SendResultResponse)
async def send_bulk_message(
    request: SendBulkMessageRequest,
    admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_admin_db),
):
    """여러 유저에게 동일한 쪽지 발송"""
    service = MessageService(db)
    messages = await service.send_bulk_message(
        sender_id=admin.id,
        recipient_ids=request.recipient_ids,
        title=request.title,
        content=request.content,
    )
    return SendResultResponse(
        success=True,
        sent_count=len(messages),
    )


@router.get("/sent", response_model=MessageListResponse)
async def get_sent_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_admin_db),
):
    """내가 보낸 쪽지 목록"""
    service = MessageService(db)
    skip = (page - 1) * page_size
    messages, total = await service.get_sent_messages(
        sender_id=admin.id,
        skip=skip,
        limit=page_size,
    )

    return MessageListResponse(
        items=[
            MessageResponse(
                id=m.id,
                sender_id=m.sender_id,
                recipient_id=m.recipient_id,
                title=m.title,
                content=m.content,
                is_read=m.is_read,
                read_at=m.read_at.isoformat() if m.read_at else None,
                created_at=m.created_at.isoformat() if m.created_at else None,
            )
            for m in messages
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: str,
    admin: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_admin_db),
):
    """쪽지 상세 조회"""
    service = MessageService(db)
    message = await service.get_message_by_id(message_id)
    if not message:
        raise HTTPException(status_code=404, detail="쪽지를 찾을 수 없습니다")

    return MessageResponse(
        id=message.id,
        sender_id=message.sender_id,
        recipient_id=message.recipient_id,
        title=message.title,
        content=message.content,
        is_read=message.is_read,
        read_at=message.read_at.isoformat() if message.read_at else None,
        created_at=message.created_at.isoformat() if message.created_at else None,
    )


# ============================================================================
# Internal API Endpoints (Game Backend 전용)
# ============================================================================


def verify_internal_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """내부 API Key 검증 (Game Backend 인증용)"""
    if x_api_key != settings.main_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


@router.get("/user/{user_id}/messages", response_model=MessageListResponse)
async def get_user_messages_internal(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    _: bool = Depends(verify_internal_api_key),
    db: AsyncSession = Depends(get_admin_db),
):
    """[내부 API] 유저 쪽지 목록 조회 (Game Backend 전용)

    Note: X-API-Key 헤더로 인증 필요
    """
    service = MessageService(db)
    skip = (page - 1) * page_size
    messages, total = await service.get_messages_for_user(
        user_id=user_id,
        skip=skip,
        limit=page_size,
        unread_only=unread_only,
    )

    unread_count = await service.get_unread_count(user_id)

    return MessageListResponse(
        items=[
            MessageResponse(
                id=m.id,
                sender_id=m.sender_id,
                recipient_id=m.recipient_id,
                title=m.title,
                content=m.content,
                is_read=m.is_read,
                read_at=m.read_at.isoformat() if m.read_at else None,
                created_at=m.created_at.isoformat() if m.created_at else None,
            )
            for m in messages
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/user/{user_id}/messages/unread-count", response_model=UnreadCountResponse)
async def get_unread_count_internal(
    user_id: str,
    _: bool = Depends(verify_internal_api_key),
    db: AsyncSession = Depends(get_admin_db),
):
    """[내부 API] 읽지 않은 쪽지 개수 (Game Backend 전용)"""
    service = MessageService(db)
    count = await service.get_unread_count(user_id)
    return UnreadCountResponse(count=count)


@router.get("/user/{user_id}/messages/{message_id}", response_model=MessageResponse)
async def get_user_message_internal(
    user_id: str,
    message_id: str,
    _: bool = Depends(verify_internal_api_key),
    db: AsyncSession = Depends(get_admin_db),
):
    """[내부 API] 쪽지 상세 조회 (자동 읽음 처리, Game Backend 전용)"""
    service = MessageService(db)
    message = await service.get_message_by_id(message_id)

    if not message or message.recipient_id != user_id:
        raise HTTPException(status_code=404, detail="쪽지를 찾을 수 없습니다")

    # 읽음 처리
    if not message.is_read:
        await service.mark_as_read(message_id, user_id)
        # 읽음 처리 후 다시 조회 (read_at 갱신)
        message = await service.get_message_by_id(message_id)

    return MessageResponse(
        id=message.id,
        sender_id=message.sender_id,
        recipient_id=message.recipient_id,
        title=message.title,
        content=message.content,
        is_read=message.is_read,
        read_at=message.read_at.isoformat() if message.read_at else None,
        created_at=message.created_at.isoformat() if message.created_at else None,
    )


@router.post("/user/{user_id}/messages/mark-all-read", response_model=MarkReadResponse)
async def mark_all_read_internal(
    user_id: str,
    _: bool = Depends(verify_internal_api_key),
    db: AsyncSession = Depends(get_admin_db),
):
    """[내부 API] 모든 쪽지 읽음 처리 (Game Backend 전용)"""
    service = MessageService(db)
    marked_count = await service.mark_all_as_read(user_id)
    return MarkReadResponse(success=True, marked_count=marked_count)


@router.delete("/user/{user_id}/messages/{message_id}")
async def delete_message_internal(
    user_id: str,
    message_id: str,
    _: bool = Depends(verify_internal_api_key),
    db: AsyncSession = Depends(get_admin_db),
):
    """[내부 API] 쪽지 삭제 (Game Backend 전용)"""
    service = MessageService(db)
    deleted = await service.delete_message(message_id, user_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="쪽지를 찾을 수 없습니다")

    return {"success": True}
