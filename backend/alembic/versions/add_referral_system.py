"""add referral system for friend invite event

Revision ID: add_referral_system
Revises:
Create Date: 2026-01-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_referral_system'
down_revision = None  # 의존성은 실제 마이그레이션 시 설정
branch_labels = None
depends_on = None


def upgrade() -> None:
    """친구추천 시스템 추가"""

    # 1. users 테이블에 추천 관련 컬럼 추가
    op.add_column(
        'users',
        sa.Column('referral_code', sa.String(20), unique=True, nullable=True, comment='내 추천 코드 (친구 초대용)')
    )
    op.add_column(
        'users',
        sa.Column('referred_by_user_id', postgresql.UUID(as_uuid=False), nullable=True, comment='나를 추천한 유저 ID')
    )

    # 인덱스 추가
    op.create_index('ix_users_referral_code', 'users', ['referral_code'])
    op.create_index('ix_users_referred_by_user_id', 'users', ['referred_by_user_id'])

    # 외래키 추가
    op.create_foreign_key(
        'fk_users_referred_by_user',
        'users', 'users',
        ['referred_by_user_id'], ['id'],
        ondelete='SET NULL'
    )

    # 2. referral_rewards 테이블 생성
    op.create_table(
        'referral_rewards',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='보상 받은 유저 ID'),
        sa.Column('referred_user_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='추천된 유저 (신규 가입자) ID'),
        sa.Column('reward_type', sa.String(20), nullable=False, comment='보상 타입 (referrer/referee)'),
        sa.Column('reward_amount', sa.Integer, nullable=False, comment='보상 금액 (KRW)'),
        sa.Column('rewarded_at', sa.DateTime(timezone=True), nullable=False, comment='보상 지급 시간'),
        sa.Column('note', sa.Text, nullable=True, comment='보상 관련 메모'),
    )

    # 인덱스 추가
    op.create_index('ix_referral_rewards_user_id', 'referral_rewards', ['user_id'])
    op.create_index('ix_referral_rewards_referred_user_id', 'referral_rewards', ['referred_user_id'])


def downgrade() -> None:
    """친구추천 시스템 제거"""

    # referral_rewards 테이블 삭제
    op.drop_index('ix_referral_rewards_referred_user_id')
    op.drop_index('ix_referral_rewards_user_id')
    op.drop_table('referral_rewards')

    # users 테이블 컬럼 제거
    op.drop_constraint('fk_users_referred_by_user', 'users', type_='foreignkey')
    op.drop_index('ix_users_referred_by_user_id')
    op.drop_index('ix_users_referral_code')
    op.drop_column('users', 'referred_by_user_id')
    op.drop_column('users', 'referral_code')
