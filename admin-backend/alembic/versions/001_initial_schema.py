"""Initial admin schema

Revision ID: 001
Revises:
Create Date: 2026-01-15

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Admin Users table
    op.create_table(
        "admin_users",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("viewer", "operator", "supervisor", "admin", name="adminrole"),
            nullable=False,
        ),
        sa.Column("two_factor_secret", sa.String(32), nullable=True),
        sa.Column("two_factor_enabled", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )

    # Audit Logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "admin_user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("admin_users.id"),
            nullable=False,
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_id", sa.String(100), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=False, default={}),
        sa.Column("ip_address", sa.String(45), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_target_type", "audit_logs", ["target_type"])

    # Announcements table
    op.create_table(
        "announcements",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "target",
            sa.Enum("all", "vip", "specific_room", name="announcementtarget"),
            nullable=False,
        ),
        sa.Column("target_room_id", sa.String(36), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("broadcasted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("admin_users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Crypto Deposits table
    op.create_table(
        "crypto_deposits",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("tx_hash", sa.String(66), nullable=False),
        sa.Column("from_address", sa.String(42), nullable=False),
        sa.Column("to_address", sa.String(42), nullable=False),
        sa.Column("amount_usdt", sa.Numeric(20, 6), nullable=False),
        sa.Column("amount_krw", sa.Numeric(20, 0), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(10, 2), nullable=False),
        sa.Column("confirmations", sa.Integer(), nullable=False, default=0),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "confirming",
                "confirmed",
                "processing",
                "completed",
                "failed",
                "rejected",
                name="transactionstatus",
            ),
            nullable=False,
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("credited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tx_hash"),
    )
    op.create_index("ix_crypto_deposits_user_id", "crypto_deposits", ["user_id"])
    op.create_index("ix_crypto_deposits_status", "crypto_deposits", ["status"])

    # Crypto Withdrawals table
    op.create_table(
        "crypto_withdrawals",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("to_address", sa.String(42), nullable=False),
        sa.Column("amount_usdt", sa.Numeric(20, 6), nullable=False),
        sa.Column("amount_krw", sa.Numeric(20, 0), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(10, 2), nullable=False),
        sa.Column("network_fee_usdt", sa.Numeric(20, 6), nullable=False),
        sa.Column("network_fee_krw", sa.Numeric(20, 0), nullable=False),
        sa.Column("tx_hash", sa.String(66), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "confirming",
                "confirmed",
                "processing",
                "completed",
                "failed",
                "rejected",
                name="transactionstatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tx_hash"),
    )
    op.create_index("ix_crypto_withdrawals_user_id", "crypto_withdrawals", ["user_id"])
    op.create_index("ix_crypto_withdrawals_status", "crypto_withdrawals", ["status"])

    # Hot Wallet Balances table
    op.create_table(
        "hot_wallet_balances",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("address", sa.String(42), nullable=False),
        sa.Column("balance_usdt", sa.Numeric(20, 6), nullable=False),
        sa.Column("balance_krw", sa.Numeric(20, 0), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(10, 2), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Exchange Rate History table
    op.create_table(
        "exchange_rate_history",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("rate", sa.Numeric(10, 2), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_exchange_rate_history_recorded_at", "exchange_rate_history", ["recorded_at"]
    )

    # Suspicious Cases table
    op.create_table(
        "suspicious_cases",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column(
            "flag_type",
            sa.Enum("same_ip", "chip_dumping", "bot_pattern", "unusual_activity", name="flagtype"),
            nullable=False,
        ),
        sa.Column("flag_details", postgresql.JSONB(), nullable=False, default={}),
        sa.Column("related_user_ids", postgresql.JSONB(), nullable=False, default=[]),
        sa.Column("related_hand_ids", postgresql.JSONB(), nullable=False, default=[]),
        sa.Column(
            "status",
            sa.Enum("pending", "under_review", "cleared", "escalated", name="casestatus"),
            nullable=False,
        ),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("admin_users.id"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_suspicious_cases_user_id", "suspicious_cases", ["user_id"])
    op.create_index("ix_suspicious_cases_flag_type", "suspicious_cases", ["flag_type"])
    op.create_index("ix_suspicious_cases_status", "suspicious_cases", ["status"])


def downgrade() -> None:
    op.drop_table("suspicious_cases")
    op.drop_table("exchange_rate_history")
    op.drop_table("hot_wallet_balances")
    op.drop_table("crypto_withdrawals")
    op.drop_table("crypto_deposits")
    op.drop_table("announcements")
    op.drop_table("audit_logs")
    op.drop_table("admin_users")

    op.execute("DROP TYPE IF EXISTS casestatus")
    op.execute("DROP TYPE IF EXISTS flagtype")
    op.execute("DROP TYPE IF EXISTS transactionstatus")
    op.execute("DROP TYPE IF EXISTS announcementtarget")
    op.execute("DROP TYPE IF EXISTS adminrole")
