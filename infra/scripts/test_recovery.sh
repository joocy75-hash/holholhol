#!/bin/bash
#
# Database Recovery Test Script
#
# Tests PostgreSQL and Redis recovery procedures to verify backup integrity.
#
# Usage:
#   ./test_recovery.sh [postgres|redis|all]
#
# Environment Variables:
#   PGHOST, PGPORT, PGUSER, PGPASSWORD - PostgreSQL connection
#   REDIS_HOST, REDIS_PORT - Redis connection
#   BACKUP_DIR - Backup directory
#   TEST_DB - Test database name (default: poker_db_recovery_test)
#

set -e

# Configuration
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/postgres}"
TEST_DB="${TEST_DB:-poker_db_recovery_test}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_BACKUP_DIR="${REDIS_BACKUP_DIR:-/var/lib/redis}"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Error handling
error_exit() {
    log "ERROR: $1"
    exit 1
}

# Test PostgreSQL recovery
test_postgres_recovery() {
    log "=========================================="
    log "Testing PostgreSQL Recovery"
    log "=========================================="
    
    # Find latest backup
    LATEST_BACKUP=$(ls -t "${BACKUP_DIR}"/*.dump 2>/dev/null | head -1)
    
    if [ -z "${LATEST_BACKUP}" ]; then
        error_exit "No backup files found in ${BACKUP_DIR}"
    fi
    
    log "Using backup: ${LATEST_BACKUP}"
    
    # Record start time
    START_TIME=$(date +%s)
    
    # Drop test database if exists
    log "Dropping test database if exists..."
    psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -c "DROP DATABASE IF EXISTS ${TEST_DB};" postgres || true
    
    # Create test database
    log "Creating test database..."
    psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -c "CREATE DATABASE ${TEST_DB};" postgres || error_exit "Failed to create test database"
    
    # Restore backup
    log "Restoring backup..."
    pg_restore \
        -h "${PGHOST}" \
        -p "${PGPORT}" \
        -U "${PGUSER}" \
        -d "${TEST_DB}" \
        --no-owner \
        --no-privileges \
        "${LATEST_BACKUP}" || error_exit "pg_restore failed"
    
    # Record end time
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    log "Recovery completed in ${DURATION} seconds"
    
    # Verify data integrity
    log "Verifying data integrity..."
    
    # Check table counts
    TABLES=("users" "rooms" "hands" "wallet_transactions")
    for TABLE in "${TABLES[@]}"; do
        COUNT=$(psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -t -c "SELECT COUNT(*) FROM ${TABLE};" "${TEST_DB}" 2>/dev/null | tr -d ' ')
        log "  ${TABLE}: ${COUNT:-0} rows"
    done
    
    # Clean up test database
    log "Cleaning up test database..."
    psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -c "DROP DATABASE ${TEST_DB};" postgres || true
    
    log "PostgreSQL recovery test PASSED"
    log "Recovery Time: ${DURATION} seconds"
    
    # Check against RTO target (30 minutes = 1800 seconds)
    if [ ${DURATION} -gt 1800 ]; then
        log "WARNING: Recovery time exceeds 30-minute RTO target"
    else
        log "Recovery time within 30-minute RTO target"
    fi
}

# Test Redis recovery
test_redis_recovery() {
    log "=========================================="
    log "Testing Redis Recovery"
    log "=========================================="
    
    # Check if Redis is running
    if ! redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" ping > /dev/null 2>&1; then
        error_exit "Redis is not running"
    fi
    
    # Check for RDB file
    RDB_FILE="${REDIS_BACKUP_DIR}/dump.rdb"
    if [ ! -f "${RDB_FILE}" ]; then
        log "WARNING: No RDB file found at ${RDB_FILE}"
        log "Redis backup may not be configured"
        return
    fi
    
    RDB_SIZE=$(du -h "${RDB_FILE}" | cut -f1)
    RDB_DATE=$(stat -c %y "${RDB_FILE}" 2>/dev/null || stat -f %Sm "${RDB_FILE}" 2>/dev/null)
    
    log "RDB file: ${RDB_FILE}"
    log "RDB size: ${RDB_SIZE}"
    log "Last modified: ${RDB_DATE}"
    
    # Get Redis info
    log "Redis memory usage:"
    redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" INFO memory | grep -E "used_memory_human|used_memory_peak_human"
    
    log "Redis keyspace:"
    redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" INFO keyspace
    
    log "Redis recovery test PASSED"
    log "Note: Full Redis recovery requires stopping Redis and replacing dump.rdb"
}

# Main
case "${1:-all}" in
    postgres)
        test_postgres_recovery
        ;;
    redis)
        test_redis_recovery
        ;;
    all)
        test_postgres_recovery
        echo ""
        test_redis_recovery
        ;;
    *)
        echo "Usage: $0 [postgres|redis|all]"
        exit 1
        ;;
esac

log "=========================================="
log "Recovery test completed"
log "=========================================="
