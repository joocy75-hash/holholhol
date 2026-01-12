#!/usr/bin/env python3
"""
Database Migration Verification Script.

Verifies that all migrations have been applied and required database
objects exist (tables, indexes, constraints).

Usage:
    python scripts/verify_migrations.py
    
    # With specific database URL
    DATABASE_URL=postgresql://... python scripts/verify_migrations.py
"""

import asyncio
import os
import sys
from typing import NamedTuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


class VerificationResult(NamedTuple):
    """Result of a verification check."""
    name: str
    passed: bool
    message: str


async def verify_migrations(database_url: str) -> list[VerificationResult]:
    """
    Verify database migrations and schema.
    
    Args:
        database_url: PostgreSQL connection URL
        
    Returns:
        List of verification results
    """
    results = []
    
    # Create async engine
    engine = create_async_engine(database_url)
    
    async with engine.connect() as conn:
        # 1. Check Alembic version table exists
        result = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'alembic_version'
            )
        """))
        alembic_exists = result.scalar()
        results.append(VerificationResult(
            name="Alembic version table",
            passed=alembic_exists,
            message="alembic_version table exists" if alembic_exists else "alembic_version table missing"
        ))
        
        # 2. Check current migration version
        if alembic_exists:
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            version = result.scalar()
            results.append(VerificationResult(
                name="Migration version",
                passed=version is not None,
                message=f"Current version: {version}" if version else "No migration version found"
            ))
        
        # 3. Check required tables exist
        required_tables = [
            "users",
            "sessions",
            "rooms",
            "tables",
            "hands",
            "hand_events",
            "wallet_transactions",
            "crypto_addresses",
            "user_two_factor",
        ]
        
        for table in required_tables:
            result = await conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = '{table}'
                )
            """))
            exists = result.scalar()
            results.append(VerificationResult(
                name=f"Table: {table}",
                passed=exists,
                message=f"Table '{table}' exists" if exists else f"Table '{table}' MISSING"
            ))
        
        # 4. Check required indexes exist
        required_indexes = [
            ("ix_users_email", "users"),
            ("ix_users_nickname", "users"),
            ("ix_rooms_status", "rooms"),
            ("ix_hands_table_id", "hands"),
            ("ix_wallet_transactions_user_id", "wallet_transactions"),
            ("ix_user_two_factor_user_id", "user_two_factor"),
        ]
        
        for index_name, table_name in required_indexes:
            result = await conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT FROM pg_indexes 
                    WHERE indexname = '{index_name}'
                )
            """))
            exists = result.scalar()
            results.append(VerificationResult(
                name=f"Index: {index_name}",
                passed=exists,
                message=f"Index '{index_name}' on '{table_name}' exists" if exists else f"Index '{index_name}' MISSING"
            ))
        
        # 5. Check KRW balance columns exist
        result = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name IN ('krw_balance', 'pending_withdrawal_krw', 'total_rake_paid_krw')
        """))
        columns = [row[0] for row in result.fetchall()]
        
        for col in ['krw_balance', 'pending_withdrawal_krw', 'total_rake_paid_krw']:
            exists = col in columns
            results.append(VerificationResult(
                name=f"Column: users.{col}",
                passed=exists,
                message=f"Column 'users.{col}' exists" if exists else f"Column 'users.{col}' MISSING"
            ))
        
        # 6. Verify index usage on critical queries
        # Check that rooms query uses index
        result = await conn.execute(text("""
            EXPLAIN (FORMAT JSON) 
            SELECT * FROM rooms WHERE status = 'waiting' ORDER BY created_at DESC LIMIT 20
        """))
        plan = result.scalar()
        uses_index = "Index" in str(plan) if plan else False
        results.append(VerificationResult(
            name="Query plan: rooms listing",
            passed=uses_index,
            message="Uses index scan" if uses_index else "WARNING: May use sequential scan"
        ))
    
    await engine.dispose()
    return results


def print_results(results: list[VerificationResult]) -> bool:
    """
    Print verification results.
    
    Args:
        results: List of verification results
        
    Returns:
        True if all checks passed
    """
    print("\n" + "=" * 60)
    print("DATABASE MIGRATION VERIFICATION REPORT")
    print("=" * 60 + "\n")
    
    passed = 0
    failed = 0
    
    for result in results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"{status} | {result.name}")
        print(f"       {result.message}")
        print()
        
        if result.passed:
            passed += 1
        else:
            failed += 1
    
    print("=" * 60)
    print(f"SUMMARY: {passed} passed, {failed} failed")
    print("=" * 60 + "\n")
    
    return failed == 0


async def main():
    """Main entry point."""
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        print("Usage: DATABASE_URL=postgresql://... python scripts/verify_migrations.py")
        sys.exit(1)
    
    # Convert to async URL if needed
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    print(f"Connecting to database...")
    
    try:
        results = await verify_migrations(database_url)
        all_passed = print_results(results)
        
        if not all_passed:
            print("⚠️  Some checks failed. Please review and fix before deployment.")
            sys.exit(1)
        else:
            print("✅ All migration checks passed!")
            sys.exit(0)
            
    except Exception as e:
        print(f"ERROR: Failed to verify migrations: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
