"""add_is_admin_to_users

Revision ID: d0718f423939
Revises: add_username_login_001
Create Date: 2026-01-24 13:20:50.024507

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0718f423939'
down_revision: Union[str, Sequence[str], None] = 'add_username_login_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add is_admin column to users table
    op.add_column(
        'users',
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.false(), comment='관리자 권한 여부')
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove is_admin column from users table
    op.drop_column('users', 'is_admin')
