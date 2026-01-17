"""merge heads

Revision ID: 1723deb5781e
Revises: add_game_state_001, add_hand_participants_001
Create Date: 2026-01-17 12:13:18.033448

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1723deb5781e'
down_revision: Union[str, Sequence[str], None] = ('add_game_state_001', 'add_hand_participants_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
