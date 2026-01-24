"""change_partner_total_referrals_to_bigint

Revision ID: b598e7a483f8
Revises: d0718f423939
Create Date: 2026-01-24 13:34:28.662658

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b598e7a483f8'
down_revision: Union[str, Sequence[str], None] = 'd0718f423939'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Change total_referrals from Integer to BigInteger."""
    # Change column type from Integer to BigInteger
    op.alter_column(
        'partners',
        'total_referrals',
        type_=sa.BigInteger(),
        existing_type=sa.Integer(),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema - Revert total_referrals from BigInteger to Integer."""
    # Revert column type from BigInteger to Integer
    op.alter_column(
        'partners',
        'total_referrals',
        type_=sa.Integer(),
        existing_type=sa.BigInteger(),
        existing_nullable=False,
    )
