"""Add two-factor authentication table.

Revision ID: add_two_factor_auth
Revises: phase5_wallet_001
Create Date: 2026-01-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_two_factor_auth'
down_revision: Union[str, None] = 'phase5_wallet_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create user_two_factor table."""
    op.create_table(
        'user_two_factor',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('secret_encrypted', sa.String(256), nullable=False, comment='Encrypted TOTP secret (Base32)'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('backup_codes_hash', sa.Text(), nullable=True, comment='JSON array of hashed backup codes'),
        sa.Column('backup_codes_remaining', sa.Integer(), nullable=False, default=10),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_backup_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id'),
    )
    
    # Create index on user_id for fast lookups
    op.create_index('ix_user_two_factor_user_id', 'user_two_factor', ['user_id'])


def downgrade() -> None:
    """Drop user_two_factor table."""
    op.drop_index('ix_user_two_factor_user_id', table_name='user_two_factor')
    op.drop_table('user_two_factor')
