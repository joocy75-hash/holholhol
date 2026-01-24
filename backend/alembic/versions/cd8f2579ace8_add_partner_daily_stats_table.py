"""add_partner_daily_stats_table

Revision ID: cd8f2579ace8
Revises: 8d10a4ea3fac
Create Date: 2026-01-24 15:34:12.489410

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'cd8f2579ace8'
down_revision: Union[str, Sequence[str], None] = '8d10a4ea3fac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create partner_daily_stats table
    op.create_table(
        'partner_daily_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('partner_id', UUID(as_uuid=True), nullable=False),
        sa.Column('date', sa.Date(), nullable=False, comment='통계 날짜 (UTC 기준)'),
        sa.Column('new_referrals', sa.BigInteger(), nullable=False, server_default='0', comment='해당 날짜 신규 추천 회원 수'),
        sa.Column('total_bet_amount', sa.BigInteger(), nullable=False, server_default='0', comment='총 베팅 금액 (KRW)'),
        sa.Column('total_rake', sa.BigInteger(), nullable=False, server_default='0', comment='총 레이크 (하우스 수수료) (KRW)'),
        sa.Column('total_net_loss', sa.BigInteger(), nullable=False, server_default='0', comment='총 순손실 (유저 관점) (KRW)'),
        sa.Column('commission_amount', sa.BigInteger(), nullable=False, server_default='0', comment='수수료 금액 (commission_type에 따라 계산됨) (KRW)'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['partner_id'], ['partners.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('partner_id', 'date', name='uq_partner_daily_stats_partner_date')
    )

    # Create indexes
    op.create_index('ix_partner_daily_stats_partner_date', 'partner_daily_stats', ['partner_id', 'date'], unique=False)
    op.create_index('ix_partner_daily_stats_partner_id', 'partner_daily_stats', ['partner_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_partner_daily_stats_partner_id', table_name='partner_daily_stats')
    op.drop_index('ix_partner_daily_stats_partner_date', table_name='partner_daily_stats')
    op.drop_table('partner_daily_stats')
