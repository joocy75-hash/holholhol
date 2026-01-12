"""Prometheus metrics middleware and custom metrics.

Phase 8: Monitoring & Alerts

Features:
- HTTP request metrics (latency, count, errors)
- WebSocket connection metrics
- Game-specific metrics (active tables, hands per minute)
- Database and Redis metrics
"""

from prometheus_client import Counter, Gauge, Histogram, Info
from prometheus_fastapi_instrumentator import Instrumentator, metrics
from prometheus_fastapi_instrumentator.metrics import Info as MetricInfo
from fastapi import FastAPI


# =============================================================================
# Custom Metrics
# =============================================================================

# Application info
APP_INFO = Info("pokerkit_app", "Application information")

# WebSocket metrics
WS_CONNECTIONS_TOTAL = Gauge(
    "pokerkit_ws_connections_total",
    "Total active WebSocket connections",
)

WS_CONNECTIONS_BY_TABLE = Gauge(
    "pokerkit_ws_connections_by_table",
    "WebSocket connections per table",
    ["table_id"],
)

WS_MESSAGES_SENT = Counter(
    "pokerkit_ws_messages_sent_total",
    "Total WebSocket messages sent",
    ["message_type"],
)

WS_MESSAGES_RECEIVED = Counter(
    "pokerkit_ws_messages_received_total",
    "Total WebSocket messages received",
    ["message_type"],
)

# Game metrics
ACTIVE_TABLES = Gauge(
    "pokerkit_active_tables",
    "Number of active game tables",
)

ACTIVE_PLAYERS = Gauge(
    "pokerkit_active_players",
    "Number of players currently in games",
)

HANDS_COMPLETED = Counter(
    "pokerkit_hands_completed_total",
    "Total number of hands completed",
    ["table_type"],  # cash, tournament
)

HAND_DURATION = Histogram(
    "pokerkit_hand_duration_seconds",
    "Duration of completed hands",
    buckets=[10, 30, 60, 120, 300, 600],
)

# Financial metrics
RAKE_COLLECTED = Counter(
    "pokerkit_rake_collected_krw_total",
    "Total rake collected in KRW",
)

DEPOSITS_TOTAL = Counter(
    "pokerkit_deposits_total",
    "Total deposits",
    ["crypto_type"],
)

WITHDRAWALS_TOTAL = Counter(
    "pokerkit_withdrawals_total",
    "Total withdrawals",
    ["crypto_type"],
)

# Cache metrics
CACHE_HITS = Counter(
    "pokerkit_cache_hits_total",
    "Cache hit count",
    ["cache_type"],  # table, hand, user
)

CACHE_MISSES = Counter(
    "pokerkit_cache_misses_total",
    "Cache miss count",
    ["cache_type"],
)

# Database metrics
DB_POOL_SIZE = Gauge(
    "pokerkit_db_pool_size",
    "Database connection pool size",
)

DB_POOL_CHECKED_OUT = Gauge(
    "pokerkit_db_pool_checked_out",
    "Database connections currently in use",
)

# Redis metrics
REDIS_CONNECTIONS = Gauge(
    "pokerkit_redis_connections",
    "Active Redis connections",
)


# =============================================================================
# Instrumentator Setup
# =============================================================================

def setup_prometheus(app: FastAPI, app_version: str = "1.0.0") -> Instrumentator:
    """Setup Prometheus metrics instrumentation.

    Args:
        app: FastAPI application instance
        app_version: Application version string

    Returns:
        Configured Instrumentator instance
    """
    # Set application info
    APP_INFO.info({
        "version": app_version,
        "app_name": "pokerkit-holdem",
    })

    # Create instrumentator with default metrics
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/health", "/health/live", "/health/ready", "/metrics"],
        inprogress_name="pokerkit_http_requests_inprogress",
        inprogress_labels=True,
    )

    # Add default metrics
    instrumentator.add(
        metrics.default(
            metric_namespace="pokerkit",
            metric_subsystem="http",
            should_include_handler=True,
            should_include_method=True,
            should_include_status=True,
            latency_highr_buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5),
        )
    )

    # Add request size metric
    instrumentator.add(
        metrics.request_size(
            metric_namespace="pokerkit",
            metric_subsystem="http",
            should_include_handler=True,
            should_include_method=True,
        )
    )

    # Add response size metric
    instrumentator.add(
        metrics.response_size(
            metric_namespace="pokerkit",
            metric_subsystem="http",
            should_include_handler=True,
            should_include_method=True,
        )
    )

    # Instrument the app
    instrumentator.instrument(app)

    # Expose metrics endpoint
    instrumentator.expose(app, endpoint="/metrics", include_in_schema=True, tags=["Monitoring"])

    return instrumentator


# =============================================================================
# Metric Helper Functions
# =============================================================================

def record_ws_connection(connected: bool, table_id: str | None = None) -> None:
    """Record WebSocket connection change.

    Args:
        connected: True if connected, False if disconnected
        table_id: Optional table ID for per-table metrics
    """
    if connected:
        WS_CONNECTIONS_TOTAL.inc()
        if table_id:
            WS_CONNECTIONS_BY_TABLE.labels(table_id=table_id).inc()
    else:
        WS_CONNECTIONS_TOTAL.dec()
        if table_id:
            WS_CONNECTIONS_BY_TABLE.labels(table_id=table_id).dec()


def record_ws_message(direction: str, message_type: str) -> None:
    """Record WebSocket message.

    Args:
        direction: "sent" or "received"
        message_type: Type of message (e.g., "TABLE_STATE_UPDATE", "PLAYER_ACTION")
    """
    if direction == "sent":
        WS_MESSAGES_SENT.labels(message_type=message_type).inc()
    else:
        WS_MESSAGES_RECEIVED.labels(message_type=message_type).inc()


def record_hand_completed(table_type: str, duration_seconds: float) -> None:
    """Record completed hand.

    Args:
        table_type: Type of table (cash, tournament)
        duration_seconds: Duration of the hand
    """
    HANDS_COMPLETED.labels(table_type=table_type).inc()
    HAND_DURATION.observe(duration_seconds)


def record_rake(amount_krw: int) -> None:
    """Record rake collection.

    Args:
        amount_krw: Rake amount in KRW
    """
    RAKE_COLLECTED.inc(amount_krw)


def record_deposit(crypto_type: str) -> None:
    """Record deposit.

    Args:
        crypto_type: Type of cryptocurrency (btc, eth, usdt, usdc)
    """
    DEPOSITS_TOTAL.labels(crypto_type=crypto_type).inc()


def record_withdrawal(crypto_type: str) -> None:
    """Record withdrawal.

    Args:
        crypto_type: Type of cryptocurrency
    """
    WITHDRAWALS_TOTAL.labels(crypto_type=crypto_type).inc()


def record_cache_access(cache_type: str, hit: bool) -> None:
    """Record cache access.

    Args:
        cache_type: Type of cache (table, hand, user)
        hit: True if cache hit, False if miss
    """
    if hit:
        CACHE_HITS.labels(cache_type=cache_type).inc()
    else:
        CACHE_MISSES.labels(cache_type=cache_type).inc()


def update_active_counts(tables: int, players: int) -> None:
    """Update active table and player counts.

    Args:
        tables: Number of active tables
        players: Number of active players
    """
    ACTIVE_TABLES.set(tables)
    ACTIVE_PLAYERS.set(players)


def update_db_pool_stats(pool_size: int, checked_out: int) -> None:
    """Update database pool statistics.

    Args:
        pool_size: Total pool size
        checked_out: Connections currently in use
    """
    DB_POOL_SIZE.set(pool_size)
    DB_POOL_CHECKED_OUT.set(checked_out)


def update_redis_connections(count: int) -> None:
    """Update Redis connection count.

    Args:
        count: Number of active Redis connections
    """
    REDIS_CONNECTIONS.set(count)
