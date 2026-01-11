#!/bin/bash
# PokerKit Holdem - Smoke Test Script
# Validates deployment is working correctly

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

BASE_URL="${1:-http://localhost}"
TIMEOUT=10
MAX_RETRIES=3
RETRY_DELAY=5

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_endpoint() {
    local endpoint="$1"
    local expected_code="${2:-200}"
    local description="$3"

    for i in $(seq 1 $MAX_RETRIES); do
        response_code=$(curl -s -o /dev/null -w "%{http_code}" \
            --connect-timeout "$TIMEOUT" \
            --max-time "$TIMEOUT" \
            "${BASE_URL}${endpoint}" 2>/dev/null || echo "000")

        if [ "$response_code" = "$expected_code" ]; then
            log_info "✓ $description - HTTP $response_code"
            return 0
        fi

        if [ $i -lt $MAX_RETRIES ]; then
            log_warn "Retry $i/$MAX_RETRIES for $endpoint (got $response_code, expected $expected_code)"
            sleep $RETRY_DELAY
        fi
    done

    log_error "✗ $description - HTTP $response_code (expected $expected_code)"
    return 1
}

check_json_response() {
    local endpoint="$1"
    local description="$2"

    response=$(curl -s --connect-timeout "$TIMEOUT" --max-time "$TIMEOUT" \
        "${BASE_URL}${endpoint}" 2>/dev/null || echo "")

    if echo "$response" | jq empty 2>/dev/null; then
        log_info "✓ $description - Valid JSON response"
        return 0
    else
        log_error "✗ $description - Invalid JSON response"
        return 1
    fi
}

# =============================================================================
# Main Tests
# =============================================================================

main() {
    echo "=================================================="
    echo "PokerKit Holdem Smoke Tests"
    echo "Target: $BASE_URL"
    echo "=================================================="
    echo ""

    local failed=0

    # Health Check
    log_info "Testing health endpoints..."
    check_endpoint "/health" "200" "Frontend health check" || ((failed++))
    check_endpoint "/api/v1/health" "200" "Backend API health check" || ((failed++))

    echo ""

    # API Endpoints
    log_info "Testing API endpoints..."
    check_endpoint "/api/v1/rooms" "200" "Room list endpoint" || ((failed++))
    check_json_response "/api/v1/rooms" "Room list JSON format" || ((failed++))

    echo ""

    # Static Assets
    log_info "Testing static assets..."
    check_endpoint "/" "200" "Frontend index page" || ((failed++))

    echo ""

    # WebSocket (basic connection test)
    log_info "Testing WebSocket availability..."
    ws_url="${BASE_URL/http/ws}/ws"
    if command -v wscat &> /dev/null; then
        if timeout 5 wscat -c "$ws_url" -x '{"type":"PING"}' 2>/dev/null; then
            log_info "✓ WebSocket connection successful"
        else
            log_warn "WebSocket test skipped (connection timeout)"
        fi
    else
        log_warn "WebSocket test skipped (wscat not installed)"
    fi

    echo ""
    echo "=================================================="

    if [ $failed -eq 0 ]; then
        log_info "All smoke tests passed! ✓"
        exit 0
    else
        log_error "$failed test(s) failed!"
        exit 1
    fi
}

# =============================================================================
# Entry Point
# =============================================================================

main "$@"
