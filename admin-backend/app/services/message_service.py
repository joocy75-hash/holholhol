"""쪽지 서비스 - 관리자 → 유저 쪽지 발송 및 조회"""

from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message


class MessageService:
    """쪽지 서비스"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def send_message(
        self,
        sender_id: str,
        recipient_id: str,
        title: str,
        content: str,
    ) -> Message:
        """쪽지 발송"""
        message = Message(
            id=str(uuid4()),
            sender_id=sender_id,
            recipient_id=recipient_id,
            title=title,
            content=content,
            is_read=False,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def send_bulk_message(
        self,
        sender_id: str,
        recipient_ids: list[str],
        title: str,
        content: str,
    ) -> list[Message]:
        """여러 유저에게 동일한 쪽지 발송"""
        messages = []
        for recipient_id in recipient_ids:
            message = Message(
                id=str(uuid4()),
                sender_id=sender_id,
                recipient_id=recipient_id,
                title=title,
                content=content,
                is_read=False,
            )
            self.db.add(message)
            messages.append(message)

        await self.db.commit()
        for msg in messages:
            await self.db.refresh(msg)
        return messages

    async def get_messages_for_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        unread_only: bool = False,
    ) -> tuple[list[Message], int]:
        """유저의 쪽지 목록 조회"""
        query = select(Message).where(Message.recipient_id == user_id)

        if unread_only:
            query = query.where(Message.is_read == False)  # noqa: E712

        # 총 개수
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # 페이지네이션 및 정렬
        query = query.order_by(Message.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        messages = list(result.scalars().all())

        return messages, total

    async def get_message_by_id(self, message_id: str) -> Message | None:
        """쪽지 ID로 조회"""
        result = await self.db.execute(
            select(Message).where(Message.id == message_id)
        )
        return result.scalar_one_or_none()

    async def mark_as_read(self, message_id: str, user_id: str) -> bool:
        """쪽지 읽음 처리"""
        result = await self.db.execute(
            update(Message)
            .where(Message.id == message_id, Message.recipient_id == user_id)
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        await self.db.commit()
        return result.rowcount > 0

    async def mark_all_as_read(self, user_id: str) -> int:
        """모든 쪽지 읽음 처리"""
        result = await self.db.execute(
            update(Message)
            .where(Message.recipient_id == user_id, Message.is_read == False)  # noqa: E712
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        await self.db.commit()
        return result.rowcount

    async def get_unread_count(self, user_id: str) -> int:
        """읽지 않은 쪽지 개수"""
        result = await self.db.scalar(
            select(func.count())
            .select_from(Message)
            .where(Message.recipient_id == user_id, Message.is_read == False)  # noqa: E712
        )
        return result or 0

    async def delete_message(self, message_id: str, user_id: str) -> bool:
        """쪽지 삭제 (유저 관점)"""
        message = await self.get_message_by_id(message_id)
        if message and message.recipient_id == user_id:
            await self.db.delete(message)
            await self.db.commit()
            return True
        return False

    async def get_sent_messages(
        self,
        sender_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Message], int]:
        """관리자가 보낸 쪽지 목록 (어드민용)"""
        query = select(Message).where(Message.sender_id == sender_id)

        # 총 개수
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # 페이지네이션 및 정렬
        query = query.order_by(Message.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        messages = list(result.scalars().all())

        return messages, total
