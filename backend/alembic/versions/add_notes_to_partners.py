"""Add notes column to partners table.

Revision ID: add_notes_to_partners_001
Revises: d0718f423939
Create Date: 2026-01-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_notes_to_partners_001"
down_revision: Union[str, Sequence[str], None] = "d0718f423939"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add notes column to partners table."""
    op.add_column(
        "partners",
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
            comment="비고 (어드민용 메모)",
        ),
    )


def downgrade() -> None:
    """Remove notes column from partners table."""
    op.drop_column("partners", "notes")
