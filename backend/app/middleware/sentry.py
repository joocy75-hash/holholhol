"""Sentry error tracking integration.

Phase 11: sentry-sdk integration for production error tracking.

Features:
- Automatic error capture
- Performance monitoring
- User context
- Custom tags for game events
"""

import os
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
import logging


def init_sentry(
    dsn: str | None = None,
    environment: str = "development",
    release: str | None = None,
    traces_sample_rate: float = 0.1,
    profiles_sample_rate: float = 0.1,
) -> bool:
    """Initialize Sentry SDK.

    Args:
        dsn: Sentry DSN (Data Source Name). If None, uses SENTRY_DSN env var.
        environment: Environment name (development, staging, production)
        release: Release version string
        traces_sample_rate: Percentage of transactions to trace (0.0 to 1.0)
        profiles_sample_rate: Percentage of transactions to profile (0.0 to 1.0)

    Returns:
        True if Sentry was initialized, False otherwise
    """
    # Get DSN from parameter or environment
    sentry_dsn = dsn or os.getenv("SENTRY_DSN")

    if not sentry_dsn:
        # Sentry not configured - skip initialization
        return False

    # Configure logging integration
    logging_integration = LoggingIntegration(
        level=logging.INFO,  # Capture INFO and above as breadcrumbs
        event_level=logging.ERROR,  # Send ERROR and above as events
    )

    sentry_sdk.init(
        dsn=sentry_dsn,
        environment=environment,
        release=release or os.getenv("APP_VERSION", "1.0.0"),
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            RedisIntegration(),
            logging_integration,
        ],
        # Performance monitoring
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        # Privacy settings
        send_default_pii=False,  # Don't send personally identifiable information
        # Before send hook for filtering
        before_send=_before_send,
        before_send_transaction=_before_send_transaction,
    )

    return True


def _before_send(event: dict, hint: dict) -> dict | None:
    """Filter events before sending to Sentry.

    Args:
        event: Sentry event dict
        hint: Additional context

    Returns:
        Modified event or None to drop
    """
    # Filter out expected errors
    if "exc_info" in hint:
        exc_type, exc_value, _ = hint["exc_info"]
        exc_name = exc_type.__name__

        # Don't report expected business errors
        expected_errors = [
            "AuthError",
            "RoomError",
            "UserError",
            "ValidationError",
        ]
        if exc_name in expected_errors:
            return None

    return event


def _before_send_transaction(event: dict, hint: dict) -> dict | None:
    """Filter transactions before sending to Sentry.

    Args:
        event: Sentry transaction event
        hint: Additional context

    Returns:
        Modified event or None to drop
    """
    # Filter out health check transactions
    transaction_name = event.get("transaction", "")
    if any(path in transaction_name for path in ["/health", "/metrics"]):
        return None

    return event


def set_user_context(user_id: str, email: str | None = None, nickname: str | None = None) -> None:
    """Set user context for error tracking.

    Args:
        user_id: User ID
        email: User email (optional)
        nickname: User nickname (optional)
    """
    sentry_sdk.set_user({
        "id": user_id,
        "email": email,
        "username": nickname,
    })


def clear_user_context() -> None:
    """Clear user context."""
    sentry_sdk.set_user(None)


def set_game_context(
    table_id: str | None = None,
    hand_id: str | None = None,
    action: str | None = None,
) -> None:
    """Set game-specific context.

    Args:
        table_id: Current table ID
        hand_id: Current hand ID
        action: Current action being performed
    """
    if table_id:
        sentry_sdk.set_tag("table_id", table_id)
    if hand_id:
        sentry_sdk.set_tag("hand_id", hand_id)
    if action:
        sentry_sdk.set_tag("game_action", action)


def capture_financial_error(
    error: Exception,
    user_id: str,
    transaction_type: str,
    amount_krw: int,
    extra: dict[str, Any] | None = None,
) -> str | None:
    """Capture financial transaction error with high priority.

    Args:
        error: The exception that occurred
        user_id: User ID involved
        transaction_type: Type of transaction (deposit, withdrawal, buy_in, etc.)
        amount_krw: Amount in KRW
        extra: Additional context

    Returns:
        Sentry event ID or None
    """
    with sentry_sdk.push_scope() as scope:
        scope.set_level("fatal")  # Financial errors are critical
        scope.set_user({"id": user_id})
        scope.set_tag("transaction_type", transaction_type)
        scope.set_tag("financial_error", "true")
        scope.set_extra("amount_krw", amount_krw)
        if extra:
            for key, value in extra.items():
                scope.set_extra(key, value)

        return sentry_sdk.capture_exception(error)


def capture_game_error(
    error: Exception,
    table_id: str,
    hand_id: str | None = None,
    action: str | None = None,
    extra: dict[str, Any] | None = None,
) -> str | None:
    """Capture game-related error.

    Args:
        error: The exception that occurred
        table_id: Table ID where error occurred
        hand_id: Hand ID if applicable
        action: Action being performed
        extra: Additional context

    Returns:
        Sentry event ID or None
    """
    with sentry_sdk.push_scope() as scope:
        scope.set_level("error")
        scope.set_tag("table_id", table_id)
        scope.set_tag("game_error", "true")
        if hand_id:
            scope.set_tag("hand_id", hand_id)
        if action:
            scope.set_tag("game_action", action)
        if extra:
            for key, value in extra.items():
                scope.set_extra(key, value)

        return sentry_sdk.capture_exception(error)


def add_breadcrumb(
    message: str,
    category: str = "game",
    level: str = "info",
    data: dict[str, Any] | None = None,
) -> None:
    """Add a breadcrumb for debugging.

    Args:
        message: Breadcrumb message
        category: Category (game, auth, wallet, etc.)
        level: Level (debug, info, warning, error)
        data: Additional data
    """
    sentry_sdk.add_breadcrumb(
        message=message,
        category=category,
        level=level,
        data=data,
    )
