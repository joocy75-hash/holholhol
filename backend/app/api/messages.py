"""유저 쪽지 API - 쪽지 조회 및 읽음 처리"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, update, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.utils.db import get_db

router = APIRouter(prefix="/messages", tags=["Messages"])


# ============================================================================
# Response Models
# ============================================================================


class MessageResponse(BaseModel):
    """쪽지 응답"""
    id: str
    title: str
    content: str
    is_read: bool
    read_at: str | None
    created_at: str | None


class MessageListResponse(BaseModel):
    """쪽지 목록 응답"""
    items: list[MessageResponse]
    total: int
    unread_count: int
    page: int
    page_size: int


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


@router.get("", response_model=MessageListResponse)
async def get_my_messages(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False, description="읽지 않은 쪽지만"),
    user: CurrentUser = None,
    db: AsyncSession = Depends(get_db),
):
    """내 쪽지 목록 조회

    Note: messages 테이블은 admin-backend DB에 있으므로
    여기서는 admin DB에 직접 쿼리합니다.
    """
    # Admin DB 연결 정보 (환경변수에서 가져오거나 하드코딩)
    # 실제로는 admin DB에 연결해야 하지만, 간단히 구현
    from app.config import get_settings
    settings = get_settings()

    # Raw SQL로 admin DB의 messages 테이블 조회
    # 실제 프로덕션에서는 별도의 admin DB 세션이 필요
    skip = (page - 1) * page_size
    user_id = str(user.id)

    # 기본 쿼리
    base_query = """
        SELECT id, title, content, is_read, read_at, created_at
        FROM messages
        WHERE recipient_id = :user_id
    """

    if unread_only:
        base_query += " AND is_read = false"

    # 총 개수
    count_query = f"SELECT COUNT(*) FROM ({base_query}) sub"
    result = await db.execute(text(count_query), {"user_id": user_id})
    total = result.scalar() or 0

    # 읽지 않은 개수
    unread_query = """
        SELECT COUNT(*) FROM messages
        WHERE recipient_id = :user_id AND is_read = false
    """
    result = await db.execute(text(unread_query), {"user_id": user_id})
    unread_count = result.scalar() or 0

    # 페이지네이션
    query = base_query + """
        ORDER BY created_at DESC
        OFFSET :skip LIMIT :limit
    """
    result = await db.execute(
        text(query),
        {"user_id": user_id, "skip": skip, "limit": page_size}
    )
    rows = result.fetchall()

    items = [
        MessageResponse(
            id=str(row.id),
            title=row.title,
            content=row.content,
            is_read=row.is_read,
            read_at=row.read_at.isoformat() if row.read_at else None,
            created_at=row.created_at.isoformat() if row.created_at else None,
        )
        for row in rows
    ]

    return MessageListResponse(
        items=items,
        total=total,
        unread_count=unread_count,
        page=page,
        page_size=page_size,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    user: CurrentUser = None,
    db: AsyncSession = Depends(get_db),
):
    """읽지 않은 쪽지 개수"""
    user_id = str(user.id)

    query = """
        SELECT COUNT(*) FROM messages
        WHERE recipient_id = :user_id AND is_read = false
    """
    result = await db.execute(text(query), {"user_id": user_id})
    count = result.scalar() or 0

    return UnreadCountResponse(count=count)


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: str,
    user: CurrentUser = None,
    db: AsyncSession = Depends(get_db),
):
    """쪽지 상세 조회 (자동으로 읽음 처리)"""
    user_id = str(user.id)

    # 쪽지 조회
    query = """
        SELECT id, title, content, is_read, read_at, created_at
        FROM messages
        WHERE id = :message_id AND recipient_id = :user_id
    """
    result = await db.execute(
        text(query),
        {"message_id": message_id, "user_id": user_id}
    )
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="쪽지를 찾을 수 없습니다")

    # 읽음 처리
    if not row.is_read:
        update_query = """
            UPDATE messages
            SET is_read = true, read_at = :now
            WHERE id = :message_id
        """
        await db.execute(
            text(update_query),
            {"message_id": message_id, "now": datetime.now(timezone.utc)}
        )
        await db.commit()

    return MessageResponse(
        id=str(row.id),
        title=row.title,
        content=row.content,
        is_read=True,  # 방금 읽음 처리됨
        read_at=row.read_at.isoformat() if row.read_at else datetime.now(timezone.utc).isoformat(),
        created_at=row.created_at.isoformat() if row.created_at else None,
    )


@router.post("/mark-all-read", response_model=MarkReadResponse)
async def mark_all_as_read(
    user: CurrentUser = None,
    db: AsyncSession = Depends(get_db),
):
    """모든 쪽지 읽음 처리"""
    user_id = str(user.id)

    query = """
        UPDATE messages
        SET is_read = true, read_at = :now
        WHERE recipient_id = :user_id AND is_read = false
    """
    result = await db.execute(
        text(query),
        {"user_id": user_id, "now": datetime.now(timezone.utc)}
    )
    await db.commit()

    return MarkReadResponse(success=True, marked_count=result.rowcount)


@router.delete("/{message_id}")
async def delete_message(
    message_id: str,
    user: CurrentUser = None,
    db: AsyncSession = Depends(get_db),
):
    """쪽지 삭제"""
    user_id = str(user.id)

    query = """
        DELETE FROM messages
        WHERE id = :message_id AND recipient_id = :user_id
    """
    result = await db.execute(
        text(query),
        {"message_id": message_id, "user_id": user_id}
    )
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="쪽지를 찾을 수 없습니다")

    return {"success": True}
