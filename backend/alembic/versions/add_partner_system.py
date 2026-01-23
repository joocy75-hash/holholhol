"""Partner (총판) system.

Revision ID: add_partner_system_001
Revises: 1723deb5781e
Create Date: 2026-01-22

This migration adds:
- partners table for partner accounts
- partner_settlements table for settlement records
- partner_id and stats columns to users table
- PARTNER_COMMISSION to transaction type enum
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "add_partner_system_001"
down_revision = "1723deb5781e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ===========================================================
    # 1. Create enum types
    # ===========================================================

    # PartnerStatus enum
    partner_status_enum = postgresql.ENUM(
        "active",
        "suspended",
        "terminated",
        name="partnerstatus",
        create_type=False,
    )
    partner_status_enum.create(op.get_bind(), checkfirst=True)

    # CommissionType enum
    commission_type_enum = postgresql.ENUM(
        "rakeback",
        "revshare",
        "turnover",
        name="commissiontype",
        create_type=False,
    )
    commission_type_enum.create(op.get_bind(), checkfirst=True)

    # SettlementStatus enum
    settlement_status_enum = postgresql.ENUM(
        "pending",
        "approved",
        "paid",
        "rejected",
        name="settlementstatus",
        create_type=False,
    )
    settlement_status_enum.create(op.get_bind(), checkfirst=True)

    # SettlementPeriod enum
    settlement_period_enum = postgresql.ENUM(
        "daily",
        "weekly",
        "monthly",
        name="settlementperiod",
        create_type=False,
    )
    settlement_period_enum.create(op.get_bind(), checkfirst=True)

    # ===========================================================
    # 2. Create partners table
    # ===========================================================

    op.create_table(
        "partners",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        # User reference
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            unique=True,
            nullable=False,
            index=True,
        ),
        # Partner code
        sa.Column(
            "partner_code",
            sa.String(20),
            unique=True,
            nullable=False,
            index=True,
        ),
        # Partner info
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("contact_info", sa.String(255), nullable=True),
        # Commission settings
        sa.Column(
            "commission_type",
            commission_type_enum,
            nullable=False,
            server_default="rakeback",
        ),
        sa.Column(
            "commission_rate",
            sa.Numeric(5, 4),
            nullable=False,
            server_default="0.3000",
        ),
        # Status
        sa.Column(
            "status",
            partner_status_enum,
            nullable=False,
            server_default="active",
        ),
        # Statistics (denormalized)
        sa.Column(
            "total_referrals",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="총 추천 회원 수",
        ),
        sa.Column(
            "total_commission_earned",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
            comment="누적 수수료 (KRW)",
        ),
        sa.Column(
            "current_month_commission",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
            comment="이번 달 수수료 (KRW)",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # ===========================================================
    # 3. Create partner_settlements table
    # ===========================================================

    op.create_table(
        "partner_settlements",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        # Partner reference
        sa.Column(
            "partner_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("partners.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        # Period
        sa.Column("period_type", settlement_period_enum, nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        # Snapshot of commission settings
        sa.Column("commission_type", commission_type_enum, nullable=False),
        sa.Column("commission_rate", sa.Numeric(5, 4), nullable=False),
        # Amounts
        sa.Column(
            "base_amount",
            sa.BigInteger(),
            nullable=False,
            comment="기준 금액 (레이크/순손실/베팅량)",
        ),
        sa.Column(
            "commission_amount",
            sa.BigInteger(),
            nullable=False,
            comment="수수료 금액 (KRW)",
        ),
        # Status
        sa.Column(
            "status",
            settlement_status_enum,
            nullable=False,
            server_default="pending",
            index=True,
        ),
        # Approval info
        sa.Column(
            "approved_by",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        # Detail (JSON breakdown by user)
        sa.Column(
            "detail",
            postgresql.JSONB(),
            nullable=True,
            comment="하위 유저별 정산 상세",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    # Create index for settlement queries
    op.create_index(
        "ix_partner_settlements_partner_status",
        "partner_settlements",
        ["partner_id", "status"],
        postgresql_using="btree",
    )
    op.create_index(
        "ix_partner_settlements_period",
        "partner_settlements",
        ["period_start", "period_end"],
        postgresql_using="btree",
    )

    # ===========================================================
    # 4. Add columns to users table
    # ===========================================================

    # Partner reference
    op.add_column(
        "users",
        sa.Column(
            "partner_id",
            postgresql.UUID(as_uuid=False),
            nullable=True,
            comment="추천 파트너 ID",
        ),
    )
    op.create_foreign_key(
        "fk_users_partner_id",
        "users",
        "partners",
        ["partner_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_users_partner_id",
        "users",
        ["partner_id"],
        postgresql_using="btree",
    )

    # Partner settlement statistics
    op.add_column(
        "users",
        sa.Column(
            "total_bet_amount_krw",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
            comment="누적 베팅량 (KRW) - 턴오버 정산용",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "total_net_profit_krw",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
            comment="누적 순손익 (KRW, 승리-베팅) - 레브쉐어 정산용",
        ),
    )

    # ===========================================================
    # 5. Add PARTNER_COMMISSION to TransactionType enum
    # ===========================================================

    # Add new value to existing enum
    op.execute("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'partner_commission'")


def downgrade() -> None:
    # Drop foreign key and index from users
    op.drop_index("ix_users_partner_id", table_name="users")
    op.drop_constraint("fk_users_partner_id", "users", type_="foreignkey")

    # Drop columns from users
    op.drop_column("users", "total_net_profit_krw")
    op.drop_column("users", "total_bet_amount_krw")
    op.drop_column("users", "partner_id")

    # Drop tables
    op.drop_table("partner_settlements")
    op.drop_table("partners")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS settlementperiod")
    op.execute("DROP TYPE IF EXISTS settlementstatus")
    op.execute("DROP TYPE IF EXISTS commissiontype")
    op.execute("DROP TYPE IF EXISTS partnerstatus")

    # Note: Cannot remove PARTNER_COMMISSION from enum in PostgreSQL
    # It would require recreating the enum type
