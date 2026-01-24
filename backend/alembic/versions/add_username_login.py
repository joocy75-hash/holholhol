"""Add username column for ID-based login.

Revision ID: add_username_login_001
Revises: add_partner_system_001
Create Date: 2026-01-24

This migration:
- Adds username column to users table
- Generates unique usernames for existing users (based on nickname)
- Creates unique index on username
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "add_username_login_001"
down_revision = "add_partner_system_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ===========================================================
    # 1. Add username column (nullable initially)
    # ===========================================================
    op.add_column(
        "users",
        sa.Column(
            "username",
            sa.String(50),
            nullable=True,  # 처음에는 nullable로 추가
            comment="로그인용 아이디 (영문/숫자, 4-20자)",
        ),
    )

    # ===========================================================
    # 2. Generate usernames for existing users
    # ===========================================================
    # nickname에서 특수문자 제거하고 소문자로 변환 + UUID 앞 6자리
    op.execute("""
        UPDATE users
        SET username = LOWER(REGEXP_REPLACE(nickname, '[^a-zA-Z0-9]', '', 'g'))
                       || '_' || SUBSTRING(id::text, 1, 6)
        WHERE username IS NULL
    """)

    # 빈 username 처리 (nickname이 한글만인 경우)
    op.execute("""
        UPDATE users
        SET username = 'user_' || SUBSTRING(id::text, 1, 8)
        WHERE username IS NULL OR username = '' OR LENGTH(username) < 4
    """)

    # ===========================================================
    # 3. Make username NOT NULL and add unique constraint
    # ===========================================================
    op.alter_column(
        "users",
        "username",
        nullable=False,
    )

    op.create_index(
        "ix_users_username",
        "users",
        ["username"],
        unique=True,
        postgresql_using="btree",
    )

    # ===========================================================
    # 4. Add usdt_wallet_address column (for P2)
    # ===========================================================
    op.add_column(
        "users",
        sa.Column(
            "usdt_wallet_address",
            sa.String(100),
            nullable=True,
            comment="USDT 지갑 주소 (TRC20/ERC20)",
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "usdt_wallet_type",
            sa.String(10),
            nullable=True,
            comment="지갑 타입 (TRC20, ERC20)",
        ),
    )


def downgrade() -> None:
    # Drop wallet columns
    op.drop_column("users", "usdt_wallet_type")
    op.drop_column("users", "usdt_wallet_address")

    # Drop username index and column
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")
