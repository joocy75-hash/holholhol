#!/bin/bash
#
# Infrastructure Configuration Verification Script
#
# Verifies that PostgreSQL, Redis, and Nginx are configured correctly
# for 500 concurrent users.
#
# Usage:
#   ./verify_config.sh [postgres|redis|nginx|all]
#
# Environment Variables:
#   PGHOST, PGPORT, PGUSER - PostgreSQL connection
#   REDIS_HOST, REDIS_PORT - Redis connection
#

set -e

# Configuration targets for 500 users
TARGET_PG_MAX_CONNECTIONS=350
TARGET_REDIS_MAXCLIENTS=1500
TARGET_REDIS_TCP_KEEPALIVE=60
TARGET_REDIS_TIMEOUT=300

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_pass() {
    echo -e "${GREEN}✅ PASS${NC} | $1"
}

log_fail() {
    echo -e "${RED}❌ FAIL${NC} | $1"
}

log_warn() {
    echo -e "${YELLOW}⚠️  WARN${NC} | $1"
}

log_info() {
    echo -e "ℹ️  INFO | $1"
}

# Track results
PASSED=0
FAILED=0
WARNINGS=0

# Verify PostgreSQL configuration
verify_postgres() {
    echo ""
    echo "=========================================="
    echo "PostgreSQL Configuration Verification"
    echo "=========================================="
    
    PGHOST="${PGHOST:-localhost}"
    PGPORT="${PGPORT:-5432}"
    PGUSER="${PGUSER:-postgres}"
    
    # Check connection
    if ! psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -c "SELECT 1" postgres > /dev/null 2>&1; then
        log_fail "Cannot connect to PostgreSQL at ${PGHOST}:${PGPORT}"
        ((FAILED++))
        return
    fi
    
    log_pass "Connected to PostgreSQL at ${PGHOST}:${PGPORT}"
    
    # Check max_connections
    MAX_CONN=$(psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -t -c "SHOW max_connections;" postgres | tr -d ' ')
    if [ "${MAX_CONN}" -ge "${TARGET_PG_MAX_CONNECTIONS}" ]; then
        log_pass "max_connections = ${MAX_CONN} (target: >= ${TARGET_PG_MAX_CONNECTIONS})"
        ((PASSED++))
    else
        log_fail "max_connections = ${MAX_CONN} (target: >= ${TARGET_PG_MAX_CONNECTIONS})"
        ((FAILED++))
    fi
    
    # Check shared_buffers
    SHARED_BUFFERS=$(psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -t -c "SHOW shared_buffers;" postgres | tr -d ' ')
    log_info "shared_buffers = ${SHARED_BUFFERS}"
    
    # Check effective_cache_size
    CACHE_SIZE=$(psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -t -c "SHOW effective_cache_size;" postgres | tr -d ' ')
    log_info "effective_cache_size = ${CACHE_SIZE}"
    
    # Check current connections
    CURRENT_CONN=$(psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -t -c "SELECT count(*) FROM pg_stat_activity;" postgres | tr -d ' ')
    log_info "Current connections: ${CURRENT_CONN}"
    
    # Check for slow query logging
    LOG_MIN_DURATION=$(psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -t -c "SHOW log_min_duration_statement;" postgres | tr -d ' ')
    if [ "${LOG_MIN_DURATION}" != "-1" ]; then
        log_pass "Slow query logging enabled (threshold: ${LOG_MIN_DURATION})"
        ((PASSED++))
    else
        log_warn "Slow query logging disabled"
        ((WARNINGS++))
    fi
}

# Verify Redis configuration
verify_redis() {
    echo ""
    echo "=========================================="
    echo "Redis Configuration Verification"
    echo "=========================================="
    
    REDIS_HOST="${REDIS_HOST:-localhost}"
    REDIS_PORT="${REDIS_PORT:-6379}"
    
    # Check connection
    if ! redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" ping > /dev/null 2>&1; then
        log_fail "Cannot connect to Redis at ${REDIS_HOST}:${REDIS_PORT}"
        ((FAILED++))
        return
    fi
    
    log_pass "Connected to Redis at ${REDIS_HOST}:${REDIS_PORT}"
    
    # Check maxclients
    MAXCLIENTS=$(redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" CONFIG GET maxclients | tail -1)
    if [ "${MAXCLIENTS}" -ge "${TARGET_REDIS_MAXCLIENTS}" ]; then
        log_pass "maxclients = ${MAXCLIENTS} (target: >= ${TARGET_REDIS_MAXCLIENTS})"
        ((PASSED++))
    else
        log_fail "maxclients = ${MAXCLIENTS} (target: >= ${TARGET_REDIS_MAXCLIENTS})"
        ((FAILED++))
    fi
    
    # Check tcp-keepalive
    TCP_KEEPALIVE=$(redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" CONFIG GET tcp-keepalive | tail -1)
    if [ "${TCP_KEEPALIVE}" -le "${TARGET_REDIS_TCP_KEEPALIVE}" ] && [ "${TCP_KEEPALIVE}" -gt 0 ]; then
        log_pass "tcp-keepalive = ${TCP_KEEPALIVE} (target: <= ${TARGET_REDIS_TCP_KEEPALIVE})"
        ((PASSED++))
    else
        log_fail "tcp-keepalive = ${TCP_KEEPALIVE} (target: <= ${TARGET_REDIS_TCP_KEEPALIVE})"
        ((FAILED++))
    fi
    
    # Check timeout
    TIMEOUT=$(redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" CONFIG GET timeout | tail -1)
    if [ "${TIMEOUT}" -gt 0 ]; then
        log_pass "timeout = ${TIMEOUT} (target: > 0)"
        ((PASSED++))
    else
        log_warn "timeout = ${TIMEOUT} (idle connections never timeout)"
        ((WARNINGS++))
    fi
    
    # Check maxmemory
    MAXMEMORY=$(redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" CONFIG GET maxmemory | tail -1)
    MAXMEMORY_HUMAN=$(redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" INFO memory | grep maxmemory_human | cut -d: -f2 | tr -d '\r')
    log_info "maxmemory = ${MAXMEMORY_HUMAN:-${MAXMEMORY}}"
    
    # Check memory policy
    POLICY=$(redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" CONFIG GET maxmemory-policy | tail -1)
    if [ "${POLICY}" = "allkeys-lru" ] || [ "${POLICY}" = "volatile-lru" ]; then
        log_pass "maxmemory-policy = ${POLICY}"
        ((PASSED++))
    else
        log_warn "maxmemory-policy = ${POLICY} (recommended: allkeys-lru)"
        ((WARNINGS++))
    fi
    
    # Check current connections
    CONNECTED=$(redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" INFO clients | grep connected_clients | cut -d: -f2 | tr -d '\r')
    log_info "Current connections: ${CONNECTED}"
    
    # Check memory usage
    USED_MEMORY=$(redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" INFO memory | grep used_memory_human | cut -d: -f2 | tr -d '\r')
    log_info "Memory usage: ${USED_MEMORY}"
}

# Verify Nginx configuration
verify_nginx() {
    echo ""
    echo "=========================================="
    echo "Nginx Configuration Verification"
    echo "=========================================="
    
    # Check if nginx is installed
    if ! command -v nginx &> /dev/null; then
        log_warn "Nginx not installed or not in PATH"
        ((WARNINGS++))
        return
    fi
    
    # Check if nginx is running
    if pgrep -x "nginx" > /dev/null; then
        log_pass "Nginx is running"
        ((PASSED++))
    else
        log_fail "Nginx is not running"
        ((FAILED++))
    fi
    
    # Check configuration syntax
    if nginx -t 2>&1 | grep -q "syntax is ok"; then
        log_pass "Nginx configuration syntax is valid"
        ((PASSED++))
    else
        log_fail "Nginx configuration has syntax errors"
        ((FAILED++))
    fi
    
    # Check for sticky session configuration
    NGINX_CONF="/etc/nginx/nginx.conf"
    if [ -f "${NGINX_CONF}" ]; then
        if grep -q "ip_hash" "${NGINX_CONF}" 2>/dev/null; then
            log_pass "Sticky sessions (ip_hash) configured"
            ((PASSED++))
        else
            log_warn "Sticky sessions (ip_hash) not found in config"
            ((WARNINGS++))
        fi
        
        # Check for WebSocket upgrade headers
        if grep -q "proxy_set_header Upgrade" "${NGINX_CONF}" 2>/dev/null; then
            log_pass "WebSocket upgrade headers configured"
            ((PASSED++))
        else
            log_warn "WebSocket upgrade headers not found"
            ((WARNINGS++))
        fi
    else
        log_info "Nginx config not at ${NGINX_CONF}, skipping detailed checks"
    fi
}

# Print summary
print_summary() {
    echo ""
    echo "=========================================="
    echo "VERIFICATION SUMMARY"
    echo "=========================================="
    echo -e "${GREEN}Passed:${NC}   ${PASSED}"
    echo -e "${RED}Failed:${NC}   ${FAILED}"
    echo -e "${YELLOW}Warnings:${NC} ${WARNINGS}"
    echo "=========================================="
    
    if [ ${FAILED} -gt 0 ]; then
        echo -e "${RED}⚠️  Some checks failed. Please fix before deployment.${NC}"
        exit 1
    elif [ ${WARNINGS} -gt 0 ]; then
        echo -e "${YELLOW}⚠️  Some warnings. Review recommended.${NC}"
        exit 0
    else
        echo -e "${GREEN}✅ All checks passed!${NC}"
        exit 0
    fi
}

# Main
case "${1:-all}" in
    postgres)
        verify_postgres
        ;;
    redis)
        verify_redis
        ;;
    nginx)
        verify_nginx
        ;;
    all)
        verify_postgres
        verify_redis
        verify_nginx
        ;;
    *)
        echo "Usage: $0 [postgres|redis|nginx|all]"
        exit 1
        ;;
esac

print_summary
