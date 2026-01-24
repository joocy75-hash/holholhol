"""add daily_checkins table for attendance event

Revision ID: add_daily_checkins_table
Revises:
Create Date: 2026-01-24

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'add_daily_checkins_table'
down_revision = None  # 의존성은 실제 마이그레이션 시 설정
branch_labels = None
depends_on = None


def upgrade() -> None:
    """daily_checkins 테이블 생성 - 일일 출석체크"""
    op.create_table(
        'daily_checkins',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('checkin_date', sa.Date, nullable=False, comment='출석 날짜 (KST)'),
        sa.Column('streak_days', sa.Integer, default=1, nullable=False, comment='연속 출석 일수'),
        sa.Column('reward_amount', sa.Integer, default=0, nullable=False, comment='지급 보상 금액'),
        sa.Column('reward_type', sa.String(20), default='daily', nullable=False, comment='보상 타입'),
        sa.Column('checked_at', sa.DateTime(timezone=True), nullable=False, comment='출석 시간'),
    )

    # 유저당 하루 1회 출석 제약
    op.create_unique_constraint('uq_user_checkin_date', 'daily_checkins', ['user_id', 'checkin_date'])

    # 조회 성능을 위한 복합 인덱스
    op.create_index('ix_checkin_user_date', 'daily_checkins', ['user_id', 'checkin_date'])


def downgrade() -> None:
    """daily_checkins 테이블 삭제"""
    op.drop_index('ix_checkin_user_date')
    op.drop_constraint('uq_user_checkin_date', 'daily_checkins')
    op.drop_table('daily_checkins')
