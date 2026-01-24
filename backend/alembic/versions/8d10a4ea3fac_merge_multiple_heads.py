"""merge_multiple_heads

Revision ID: 8d10a4ea3fac
Revises: add_daily_checkins_table, add_messages_table, add_referral_system, b598e7a483f8
Create Date: 2026-01-24 15:34:08.765762

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d10a4ea3fac'
down_revision: Union[str, Sequence[str], None] = ('add_daily_checkins_table', 'add_messages_table', 'add_referral_system', 'b598e7a483f8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
