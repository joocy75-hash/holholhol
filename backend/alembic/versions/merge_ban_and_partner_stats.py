"""Merge ban fields and partner stats heads.

Revision ID: merge_ban_and_partner_stats_001
Revises: add_ban_fields_to_users_001, cd8f2579ace8
Create Date: 2026-01-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "merge_ban_and_partner_stats_001"
down_revision: Union[str, Sequence[str], None] = ("add_ban_fields_to_users_001", "cd8f2579ace8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge migration - no changes needed."""
    pass


def downgrade() -> None:
    """Merge migration - no changes needed."""
    pass
