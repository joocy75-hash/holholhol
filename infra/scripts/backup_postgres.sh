#!/bin/bash
#
# PostgreSQL Backup Script
#
# Creates compressed backups of the poker database and manages retention.
#
# Usage:
#   ./backup_postgres.sh
#
# Environment Variables:
#   PGHOST     - PostgreSQL host (default: localhost)
#   PGPORT     - PostgreSQL port (default: 5432)
#   PGUSER     - PostgreSQL user (default: postgres)
#   PGPASSWORD - PostgreSQL password
#   PGDATABASE - Database name (default: poker_db)
#   BACKUP_DIR - Backup directory (default: /var/backups/postgres)
#   RETENTION_DAYS - Days to keep backups (default: 7)
#
# Cron Example (daily at 2 AM):
#   0 2 * * * /opt/scripts/backup_postgres.sh >> /var/log/backup.log 2>&1
#

set -e

# Configuration
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-poker_db}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

# Timestamp for backup file
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${PGDATABASE}_${TIMESTAMP}.dump"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Error handling
error_exit() {
    log "ERROR: $1"
    exit 1
}

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}" || error_exit "Failed to create backup directory"

log "Starting PostgreSQL backup..."
log "Database: ${PGDATABASE}@${PGHOST}:${PGPORT}"
log "Backup file: ${BACKUP_FILE}"

# Perform backup with compression
pg_dump \
    -h "${PGHOST}" \
    -p "${PGPORT}" \
    -U "${PGUSER}" \
    -Fc \
    -Z 6 \
    "${PGDATABASE}" > "${BACKUP_FILE}" || error_exit "pg_dump failed"

# Get backup size
BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
log "Backup completed: ${BACKUP_SIZE}"

# Verify backup integrity
pg_restore --list "${BACKUP_FILE}" > /dev/null 2>&1 || error_exit "Backup verification failed"
log "Backup verification passed"

# Clean up old backups
log "Cleaning up backups older than ${RETENTION_DAYS} days..."
DELETED_COUNT=$(find "${BACKUP_DIR}" -name "*.dump" -mtime +${RETENTION_DAYS} -delete -print | wc -l)
log "Deleted ${DELETED_COUNT} old backup(s)"

# List current backups
log "Current backups:"
ls -lh "${BACKUP_DIR}"/*.dump 2>/dev/null || log "No backups found"

# Optional: Upload to S3 (uncomment to enable)
# if [ -n "${S3_BUCKET}" ]; then
#     log "Uploading to S3: s3://${S3_BUCKET}/backups/"
#     aws s3 cp "${BACKUP_FILE}" "s3://${S3_BUCKET}/backups/" || log "WARNING: S3 upload failed"
# fi

log "Backup process completed successfully"
