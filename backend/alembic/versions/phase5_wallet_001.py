"""Phase 5: KRW Balance + Cryptocurrency Deposit/Withdrawal System.

Revision ID: phase5_wallet_001
Revises: add_perf_indexes_001
Create Date: 2026-01-12

This migration adds:
- KRW balance fields to users table
- wallet_transactions table for all financial transactions
- crypto_addresses table for user deposit addresses
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "phase5_wallet_001"
down_revision = "add_perf_indexes_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ===========================================================
    # 1. Add KRW balance fields to users table
    # ===========================================================

    # KRW Balance - Primary game currency
    op.add_column(
        "users",
        sa.Column(
            "krw_balance",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
            comment="Game balance in KRW (원화) - deposits converted from crypto",
        ),
    )

    # Pending withdrawal amount (locked during 24h withdrawal process)
    op.add_column(
        "users",
        sa.Column(
            "pending_withdrawal_krw",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
            comment="KRW amount locked for pending withdrawals",
        ),
    )

    # Total rake paid (for VIP level calculation - Phase 6)
    op.add_column(
        "users",
        sa.Column(
            "total_rake_paid_krw",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
            comment="Total rake paid in KRW (for VIP level calculation)",
        ),
    )

    # ===========================================================
    # 2. Create wallet_transactions table
    # ===========================================================

    # Create enum types first
    transaction_type_enum = postgresql.ENUM(
        "crypto_deposit",
        "crypto_withdrawal",
        "buy_in",
        "cash_out",
        "win",
        "lose",
        "rake",
        "rakeback",
        "admin_adjust",
        "bonus",
        name="transactiontype",
        create_type=False,
    )
    transaction_type_enum.create(op.get_bind(), checkfirst=True)

    transaction_status_enum = postgresql.ENUM(
        "pending",
        "processing",
        "completed",
        "failed",
        "cancelled",
        name="transactionstatus",
        create_type=False,
    )
    transaction_status_enum.create(op.get_bind(), checkfirst=True)

    crypto_type_enum = postgresql.ENUM(
        "btc", "eth", "usdt", "usdc", name="cryptotype", create_type=False
    )
    crypto_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "wallet_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        # Transaction type and status
        sa.Column("tx_type", transaction_type_enum, nullable=False, index=True),
        sa.Column(
            "status",
            transaction_status_enum,
            nullable=False,
            server_default="completed",
            index=True,
        ),
        # KRW amounts
        sa.Column(
            "krw_amount",
            sa.BigInteger(),
            nullable=False,
            comment="Transaction amount in KRW (+credit/-debit)",
        ),
        sa.Column(
            "krw_balance_before",
            sa.BigInteger(),
            nullable=False,
            comment="User KRW balance before transaction",
        ),
        sa.Column(
            "krw_balance_after",
            sa.BigInteger(),
            nullable=False,
            comment="User KRW balance after transaction",
        ),
        # Cryptocurrency information
        sa.Column("crypto_type", crypto_type_enum, nullable=True),
        sa.Column(
            "crypto_amount",
            sa.String(50),
            nullable=True,
            comment="Crypto amount with full precision",
        ),
        sa.Column(
            "crypto_tx_hash",
            sa.String(100),
            nullable=True,
            index=True,
            comment="Blockchain transaction hash",
        ),
        sa.Column(
            "crypto_address",
            sa.String(100),
            nullable=True,
            comment="Crypto address for this transaction",
        ),
        # Exchange rate
        sa.Column(
            "exchange_rate_krw",
            sa.BigInteger(),
            nullable=True,
            comment="Rate: 1 crypto = X KRW at transaction time",
        ),
        # Game references
        sa.Column(
            "hand_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("hands.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "table_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("tables.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Withdrawal timing
        sa.Column(
            "withdrawal_requested_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When withdrawal was requested (24h pending)",
        ),
        sa.Column(
            "withdrawal_processed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When withdrawal was processed",
        ),
        # Description and notes
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column(
            "admin_note",
            sa.Text(),
            nullable=True,
            comment="Admin notes for manual adjustments",
        ),
        # Integrity
        sa.Column(
            "integrity_hash",
            sa.String(64),
            nullable=False,
            comment="SHA-256 hash for tamper detection",
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

    # Create indexes
    op.create_index(
        "ix_wallet_transactions_user_created",
        "wallet_transactions",
        ["user_id", "created_at"],
        postgresql_using="btree",
    )
    op.create_index(
        "ix_wallet_transactions_type_status",
        "wallet_transactions",
        ["tx_type", "status"],
        postgresql_using="btree",
    )

    # ===========================================================
    # 3. Create crypto_addresses table
    # ===========================================================

    op.create_table(
        "crypto_addresses",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # Crypto type and address
        sa.Column("crypto_type", crypto_type_enum, nullable=False),
        sa.Column("address", sa.String(100), nullable=False, unique=True, index=True),
        # Tracking
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "total_deposits",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Number of deposits received",
        ),
        sa.Column("last_deposit_at", sa.DateTime(timezone=True), nullable=True),
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
        comment="User cryptocurrency deposit addresses",
    )

    # Create unique index for user+crypto_type combination
    op.create_index(
        "ix_crypto_addresses_user_type",
        "crypto_addresses",
        ["user_id", "crypto_type"],
        unique=True,
        postgresql_using="btree",
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("crypto_addresses")
    op.drop_table("wallet_transactions")

    # Drop columns from users
    op.drop_column("users", "total_rake_paid_krw")
    op.drop_column("users", "pending_withdrawal_krw")
    op.drop_column("users", "krw_balance")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS cryptotype")
    op.execute("DROP TYPE IF EXISTS transactionstatus")
    op.execute("DROP TYPE IF EXISTS transactiontype")
