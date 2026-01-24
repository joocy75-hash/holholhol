"""유저 쪽지 API - 쪽지 조회 및 읽음 처리

Note: Admin Backend API를 통해 쪽지를 조회합니다 (서비스 분리 원칙).
Raw SQL 직접 접근 방식에서 HTTP API 방식으로 리팩토링되었습니다.
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.utils.admin_api_client import call_admin_backend

router = APIRouter(prefix="/messages", tags=["Messages"])
logger = logging.getLogger(__name__)


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
):
    """내 쪽지 목록 조회

    Note: Admin Backend API를 통해 조회 (서비스 분리 원칙 준수)
    """
    try:
        result = await call_admin_backend(
            method="GET",
            path=f"/api/v1/internal/messages/user/{user.id}/messages",
            params={
                "page": page,
                "page_size": page_size,
                "unread_only": unread_only,
            },
        )

        return MessageListResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch messages for user {user.id}: {e}")
        # Graceful degradation: 쪽지 시스템 장애 시 빈 목록 반환
        # 게임은 정상 동작, 쪽지만 일시적으로 안 보임
        return MessageListResponse(
            items=[],
            total=0,
            unread_count=0,
            page=page,
            page_size=page_size,
        )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(user: CurrentUser = None):
    """읽지 않은 쪽지 개수"""
    try:
        result = await call_admin_backend(
            method="GET",
            path=f"/api/v1/internal/messages/user/{user.id}/messages/unread-count",
        )
        return UnreadCountResponse(**result)
    except Exception as e:
        logger.warning(f"Failed to fetch unread count for user {user.id}: {e}")
        # Graceful degradation: 에러 시 0 반환
        return UnreadCountResponse(count=0)


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: str,
    user: CurrentUser = None,
):
    """쪽지 상세 조회 (자동으로 읽음 처리)"""
    result = await call_admin_backend(
        method="GET",
        path=f"/api/v1/internal/messages/user/{user.id}/messages/{message_id}",
    )
    return MessageResponse(**result)


@router.post("/mark-all-read", response_model=MarkReadResponse)
async def mark_all_as_read(user: CurrentUser = None):
    """모든 쪽지 읽음 처리"""
    result = await call_admin_backend(
        method="POST",
        path=f"/api/v1/internal/messages/user/{user.id}/messages/mark-all-read",
    )
    return MarkReadResponse(**result)


@router.delete("/{message_id}")
async def delete_message(
    message_id: str,
    user: CurrentUser = None,
):
    """쪽지 삭제"""
    await call_admin_backend(
        method="DELETE",
        path=f"/api/v1/internal/messages/user/{user.id}/messages/{message_id}",
    )
    return {"success": True}
