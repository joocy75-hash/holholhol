"""Add ban fields to users table.

Revision ID: add_ban_fields_to_users_001
Revises: add_notes_to_partners_001
Create Date: 2026-01-29

This migration adds:
- is_banned: 계정 정지 여부
- ban_reason: 정지 사유
- ban_expires_at: 정지 해제 일시 (null이면 영구 정지)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_ban_fields_to_users_001"
down_revision: Union[str, Sequence[str], None] = "add_notes_to_partners_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ban fields to users table."""
    op.add_column(
        "users",
        sa.Column(
            "is_banned",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="계정 정지 여부",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "ban_reason",
            sa.Text(),
            nullable=True,
            comment="정지 사유",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "ban_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="정지 해제 일시 (null이면 영구 정지)",
        ),
    )


def downgrade() -> None:
    """Remove ban fields from users table."""
    op.drop_column("users", "ban_expires_at")
    op.drop_column("users", "ban_reason")
    op.drop_column("users", "is_banned")
