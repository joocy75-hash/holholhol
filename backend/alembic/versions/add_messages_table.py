"""add messages table for user inbox

Revision ID: add_messages_table
Revises:
Create Date: 2026-01-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision = 'add_messages_table'
down_revision = None  # 의존성은 실제 마이그레이션 시 설정
branch_labels = None
depends_on = None


def upgrade() -> None:
    """messages 테이블 생성 - 관리자 → 유저 쪽지"""
    op.create_table(
        'messages',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('sender_id', UUID(as_uuid=True), nullable=False, comment='발신자 (관리자) ID'),
        sa.Column('recipient_id', UUID(as_uuid=True), nullable=False, index=True, comment='수신자 (유저) ID'),
        sa.Column('title', sa.String(200), nullable=False, comment='쪽지 제목'),
        sa.Column('content', sa.Text, nullable=False, comment='쪽지 내용'),
        sa.Column('is_read', sa.Boolean, default=False, nullable=False, comment='읽음 여부'),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True, comment='읽은 시간'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
    )

    # 인덱스 생성
    op.create_index('ix_messages_recipient_created', 'messages', ['recipient_id', 'created_at'])
    op.create_index('ix_messages_recipient_unread', 'messages', ['recipient_id', 'is_read'])


def downgrade() -> None:
    """messages 테이블 삭제"""
    op.drop_index('ix_messages_recipient_unread')
    op.drop_index('ix_messages_recipient_created')
    op.drop_table('messages')
