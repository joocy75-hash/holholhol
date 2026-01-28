"""FastAPI application entry point.

홀덤1등 API - Texas Hold'em Poker Game Server

Phase 8: Prometheus metrics integration
Phase 11: Sentry error tracking, structlog, orjson
"""

import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import admin, admin_partner, auth, checkin, dev, hands, messages, partner, referral, rooms, users, wallet
from app.tournament.api import (
    router as tournament_router,
    admin_router as tournament_admin_router,
)
from app.config import get_settings
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.maintenance import MaintenanceMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.sentry import init_sentry
from app.services.auth import AuthError
from app.services.room import RoomError
from app.services.user import UserError
from app.utils.db import close_db, engine, init_db, async_session_factory
from app.utils.redis_client import close_redis, init_redis, get_redis
from app.utils.json_utils import ORJSONResponse
from app.utils.secrets_validator import validate_startup_secrets
from app.ws.gateway import router as ws_router, get_manager, shutdown_manager
from app.logging_config import configure_logging, get_logger
from app.services.fraud_event_publisher import init_fraud_publisher
from app.services.player_session_tracker import init_session_tracker
from app.game.manager import game_manager

settings = get_settings()

# Validate secrets at module load time (before app starts)
validate_startup_secrets(
    jwt_secret_key=settings.jwt_secret_key,
    serialization_hmac_key=settings.serialization_hmac_key,
    session_secret_key=getattr(settings, "session_secret_key", None),
    deposit_webhook_secret=getattr(settings, "deposit_webhook_secret", None),
    environment=settings.app_env,
)

# Configure structured logging (Phase 11)
configure_logging(
    log_level=settings.log_level,
    json_logs=settings.app_env == "production",
    app_env=settings.app_env,
)
logger = get_logger(__name__)

# Initialize Sentry (Phase 11)
sentry_enabled = init_sentry(
    dsn=settings.sentry_dsn,
    environment=settings.app_env,
    traces_sample_rate=settings.sentry_traces_sample_rate
    if settings.app_env == "production"
    else 0.0,
    profiles_sample_rate=settings.sentry_profiles_sample_rate
    if settings.app_env == "production"
    else 0.0,
)
if sentry_enabled:
    logger.info("Sentry error tracking initialized")
elif settings.app_env == "production":
    logger.warning("Sentry DSN not configured - error tracking disabled")


# =============================================================================
# Lifespan Events
# =============================================================================


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    logger.info("Starting application...")

    try:
        # Initialize database connection
        logger.info("Initializing database connection...")
        await init_db()
        logger.info("Database connection established")

        # Initialize Redis connection
        logger.info("Initializing Redis connection...")
        redis_instance = await init_redis()
        logger.info("Redis connection established")

        # Initialize Fraud Event Publisher (Phase 2.3)
        logger.info("Initializing FraudEventPublisher...")
        fraud_publisher = init_fraud_publisher(redis_instance)
        logger.info(
            f"FraudEventPublisher initialized (enabled={fraud_publisher.enabled})"
        )

        # Initialize Player Session Tracker (Phase 2.3)
        logger.info("Initializing PlayerSessionTracker...")
        init_session_tracker(fraud_publisher)
        logger.info("PlayerSessionTracker initialized")

        # Initialize WebSocket connection manager
        logger.info("Initializing WebSocket gateway...")
        await get_manager()
        logger.info("WebSocket gateway initialized")

        # Start GameManager cleanup task (Phase 4.5)
        logger.info("Starting GameManager cleanup task...")
        await game_manager.start_cleanup_task()
        logger.info("GameManager cleanup task started")

        # === P0: Tournament Engine Auto-Recovery (Production Critical) ===
        logger.info("Initializing Tournament Engine with auto-recovery...")
        try:
            from app.tournament.engine import TournamentEngine
            from app.tournament.models import TournamentStatus

            tournament_engine = TournamentEngine(redis_instance)
            await tournament_engine.initialize()

            # Auto-recover active tournaments from Redis snapshots
            recovery_count = 0
            async for key in redis_instance.scan_iter(
                match="tournament:snapshot:*:latest"
            ):
                # key format: tournament:snapshot:{tournament_id}:latest
                key_str = key.decode() if isinstance(key, bytes) else key
                parts = key_str.split(":")
                if len(parts) >= 3:
                    tournament_id = parts[2]
                    try:
                        state = await tournament_engine.recover_tournament(
                            tournament_id
                        )
                        if state and state.status in [
                            TournamentStatus.RUNNING,
                            TournamentStatus.STARTING,
                            TournamentStatus.PAUSED,
                            TournamentStatus.FINAL_TABLE,
                        ]:
                            recovery_count += 1
                            logger.info(
                                f"Recovered tournament: {tournament_id}, "
                                f"status={state.status.value}, "
                                f"players={state.active_player_count}"
                            )
                    except Exception as e:
                        logger.warning(
                            f"Failed to recover tournament {tournament_id}: {e}"
                        )

            if recovery_count > 0:
                logger.info(
                    f"Tournament auto-recovery complete: "
                    f"{recovery_count} tournaments restored"
                )
            else:
                logger.info("No active tournaments to recover")

            # Store in app state for global access
            _app.state.tournament_engine = tournament_engine
            logger.info("Tournament Engine initialized successfully")

        except Exception as e:
            logger.error(f"Tournament engine initialization failed: {e}")
            # Non-critical: basic game functionality continues

        # === Live Bot Orchestrator (프로덕션 봇 시스템) ===
        if settings.livebot_enabled:
            logger.info("Initializing Live Bot Orchestrator...")
            try:
                from app.bot.orchestrator import init_bot_orchestrator
                bot_orchestrator = await init_bot_orchestrator()
                _app.state.bot_orchestrator = bot_orchestrator
                logger.info(
                    f"Live Bot Orchestrator initialized "
                    f"(target={bot_orchestrator.target_count})"
                )
            except Exception as e:
                logger.error(f"Bot orchestrator initialization failed: {e}")
                # Non-critical: game functionality continues without bots
        else:
            logger.info("Live Bot system disabled")

        logger.info("Application startup complete")
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down application...")

    try:
        # Shutdown Live Bot Orchestrator
        if hasattr(_app.state, 'bot_orchestrator'):
            logger.info("Shutting down Live Bot Orchestrator...")
            from app.bot.orchestrator import shutdown_bot_orchestrator
            await shutdown_bot_orchestrator()
            logger.info("Live Bot Orchestrator shutdown complete")

        # Shutdown WebSocket manager
        logger.info("Shutting down WebSocket gateway...")
        await shutdown_manager()
        logger.info("WebSocket gateway shutdown complete")

        # Close database connection
        logger.info("Closing database connection...")
        await close_db()
        logger.info("Database connection closed")

        # Close Redis connection
        logger.info("Closing Redis connection...")
        await close_redis()
        logger.info("Redis connection closed")

        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")


# =============================================================================
# FastAPI Application
# =============================================================================


app = FastAPI(
    title="홀덤1등 API",
    version="1.0.0",
    description="Texas Hold'em Poker Game Server API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    default_response_class=ORJSONResponse,  # Phase 11: orjson for faster JSON
)

# Setup Prometheus metrics (Phase 8)
from app.middleware.prometheus import setup_prometheus

prometheus_instrumentator = setup_prometheus(app, app_version="1.0.0")


# =============================================================================
# Middleware
# =============================================================================


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add X-Request-ID header to all requests and responses."""

    async def dispatch(self, request: Request, call_next):
        # Skip WebSocket upgrade requests - BaseHTTPMiddleware doesn't handle them properly
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        # Store request ID in request state for access in handlers
        request.state.request_id = request_id

        # Add request start time for logging
        request.state.start_time = datetime.now(timezone.utc)

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        # Log request completion
        duration = (
            datetime.now(timezone.utc) - request.state.start_time
        ).total_seconds()
        logger.info(
            f"{request.method} {request.url.path} - "
            f"Status: {response.status_code} - "
            f"Duration: {duration:.3f}s - "
            f"Request-ID: {request_id}"
        )

        return response


# Add Request ID middleware
app.add_middleware(RequestIDMiddleware)


# CORS configuration for development
cors_origins = [origin.strip() for origin in settings.cors_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Dev-Key"],
    expose_headers=["X-Request-ID"],
)

# Security headers middleware (with environment for CSP/HSTS)
app.add_middleware(SecurityHeadersMiddleware, app_env=settings.app_env)

# Rate limiting middleware (uses Redis when available)
app.add_middleware(RateLimitMiddleware, redis_client=get_redis())

# Maintenance mode middleware (checks Redis for maintenance status)
app.add_middleware(MaintenanceMiddleware, redis_client=get_redis())


# =============================================================================
# Error Handlers
# =============================================================================


def get_request_id(request: Request) -> str:
    """Get request ID from request state or headers."""
    if hasattr(request.state, "request_id"):
        return request.state.request_id
    return request.headers.get("X-Request-ID", str(uuid.uuid4()))


def create_error_response(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    """Create standardized error response."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
        "traceId": trace_id,
    }


@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError) -> ORJSONResponse:
    """Handle authentication errors."""
    trace_id = get_request_id(request)

    # Determine status code based on error code
    status_code = status.HTTP_401_UNAUTHORIZED
    if "INACTIVE" in exc.code:
        status_code = status.HTTP_403_FORBIDDEN
    elif "EXISTS" in exc.code:
        status_code = status.HTTP_409_CONFLICT
    elif "NOT_FOUND" in exc.code:
        status_code = status.HTTP_404_NOT_FOUND

    logger.warning("auth_error", code=exc.code, message=exc.message, trace_id=trace_id)

    return ORJSONResponse(
        status_code=status_code,
        content=create_error_response(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            trace_id=trace_id,
        ),
    )


@app.exception_handler(RoomError)
async def room_error_handler(request: Request, exc: RoomError) -> ORJSONResponse:
    """Handle room operation errors."""
    trace_id = get_request_id(request)

    # Determine status code based on error code
    status_code = status.HTTP_400_BAD_REQUEST
    if "NOT_FOUND" in exc.code:
        status_code = status.HTTP_404_NOT_FOUND
    elif "NOT_OWNER" in exc.code or "PASSWORD" in exc.code:
        status_code = status.HTTP_403_FORBIDDEN
    elif "FULL" in exc.code or "ALREADY" in exc.code:
        status_code = status.HTTP_409_CONFLICT

    logger.warning("room_error", code=exc.code, message=exc.message, trace_id=trace_id)

    return ORJSONResponse(
        status_code=status_code,
        content=create_error_response(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            trace_id=trace_id,
        ),
    )


@app.exception_handler(UserError)
async def user_error_handler(request: Request, exc: UserError) -> ORJSONResponse:
    """Handle user operation errors."""
    trace_id = get_request_id(request)

    # Determine status code based on error code
    status_code = status.HTTP_400_BAD_REQUEST
    if "NOT_FOUND" in exc.code:
        status_code = status.HTTP_404_NOT_FOUND
    elif "INACTIVE" in exc.code:
        status_code = status.HTTP_403_FORBIDDEN
    elif "EXISTS" in exc.code:
        status_code = status.HTTP_409_CONFLICT

    logger.warning("user_error", code=exc.code, message=exc.message, trace_id=trace_id)

    return ORJSONResponse(
        status_code=status_code,
        content=create_error_response(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            trace_id=trace_id,
        ),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request, exc: HTTPException
) -> ORJSONResponse:
    """Handle HTTP exceptions."""
    trace_id = get_request_id(request)

    # Check if detail is already formatted
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        content = exc.detail
        content["traceId"] = trace_id
    else:
        content = create_error_response(
            code="HTTP_ERROR",
            message=str(exc.detail),
            trace_id=trace_id,
        )

    return ORJSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> ORJSONResponse:
    """Handle unexpected exceptions."""
    trace_id = get_request_id(request)

    logger.error(
        "unexpected_error",
        error_type=type(exc).__name__,
        error_message=str(exc),
        trace_id=trace_id,
        exc_info=True,
    )

    # Don't expose internal error details in production
    message = "Internal server error"
    if settings.app_debug:
        message = f"{type(exc).__name__}: {exc}"

    return ORJSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=create_error_response(
            code="INTERNAL_ERROR",
            message=message,
            trace_id=trace_id,
        ),
    )


# =============================================================================
# Health Check Endpoints
# =============================================================================


@app.get(
    "/health",
    tags=["Health"],
    summary="Health check endpoint",
    response_model=dict,
)
async def health_check() -> dict[str, Any]:
    """Check application health status.

    Returns:
        Health status including database and Redis connectivity.
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "services": {
            "database": "unknown",
            "redis": "unknown",
        },
    }

    overall_healthy = True

    # Check database connection
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        health_status["services"]["database"] = "healthy"
    except Exception as e:
        health_status["services"]["database"] = f"unhealthy: {str(e)}"
        overall_healthy = False
        logger.error(f"Database health check failed: {e}")

    # Check Redis connection
    try:
        current_redis = get_redis()

        if current_redis:
            await current_redis.ping()
            health_status["services"]["redis"] = "healthy"
        else:
            health_status["services"]["redis"] = "not initialized"
            overall_healthy = False
    except Exception as e:
        health_status["services"]["redis"] = f"unhealthy: {str(e)}"
        overall_healthy = False
        logger.error(f"Redis health check failed: {e}")

    if not overall_healthy:
        health_status["status"] = "degraded"

    return health_status


@app.get(
    "/health/live",
    tags=["Health"],
    summary="Liveness probe",
)
async def liveness_probe() -> dict[str, str]:
    """Kubernetes liveness probe endpoint.

    Returns:
        Simple status indicating the application is running.
    """
    return {"status": "alive"}


@app.get(
    "/health/ready",
    tags=["Health"],
    summary="Readiness probe",
)
async def readiness_probe() -> dict[str, str]:
    """Kubernetes readiness probe endpoint.

    Checks if the application is ready to receive traffic.

    Returns:
        Status indicating readiness.
    """
    # Check critical dependencies
    try:
        # Database check
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

        # Redis check
        current_redis = get_redis()

        if current_redis:
            await current_redis.ping()

        return {"status": "ready"}
    except Exception as e:
        logger.error("readiness_probe_failed", error=str(e))
        return ORJSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not ready", "error": str(e)},
        )


# =============================================================================
# API Routers
# =============================================================================


# API version prefix
API_V1_PREFIX = "/api/v1"

# Include routers with API version prefix
app.include_router(auth.router, prefix=API_V1_PREFIX)
app.include_router(hands.router, prefix=API_V1_PREFIX)  # Phase 2.5: 핸드 히스토리 API
app.include_router(rooms.router, prefix=API_V1_PREFIX)
app.include_router(users.router, prefix=API_V1_PREFIX)
app.include_router(wallet.router, prefix=API_V1_PREFIX)
app.include_router(messages.router, prefix=API_V1_PREFIX)
app.include_router(checkin.router, prefix=API_V1_PREFIX)
app.include_router(referral.router, prefix=API_V1_PREFIX)

# Internal Admin API (called from admin-backend)
app.include_router(admin.router, prefix=API_V1_PREFIX)
app.include_router(admin_partner.router, prefix=API_V1_PREFIX)

# Partner Dashboard API
app.include_router(partner.router, prefix=API_V1_PREFIX)

# Tournament API (Phase: Tournament Engine)
app.include_router(tournament_router)
app.include_router(tournament_admin_router)

# Include Dev/Test API router (disabled in production)
if settings.dev_api_enabled:
    app.include_router(dev.router, prefix="/api")

# Include WebSocket router (no prefix - endpoint is /ws)
app.include_router(ws_router)


# =============================================================================
# Root Endpoint
# =============================================================================


@app.get(
    "/",
    tags=["Root"],
    summary="API root endpoint",
)
async def root() -> dict[str, str]:
    """Root endpoint with API information."""
    return {
        "name": "홀덤1등 API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


# =============================================================================
# Development / Production Server
# =============================================================================


if __name__ == "__main__":
    import uvicorn

    # 프로덕션 환경에서는 멀티 워커 사용 (WebSocket Sticky Session 필요)
    # 개발 환경에서는 reload=True로 단일 워커 사용
    if settings.app_debug:
        # Development: single worker with reload
        uvicorn.run(
            "app.main:app",
            host=settings.app_host,
            port=settings.app_port,
            reload=True,
            log_level=settings.log_level.lower(),
        )
    else:
        # Production: multiple workers (requires Redis Pub/Sub for WebSocket)
        # 참고: 멀티 워커 시 WebSocket은 Sticky Session 또는 Redis Pub/Sub 필요
        uvicorn.run(
            "app.main:app",
            host=settings.app_host,
            port=settings.app_port,
            workers=settings.uvicorn_workers,
            log_level=settings.log_level.lower(),
            access_log=True,
            # Production optimizations
            limit_concurrency=1000,
            limit_max_requests=10000,
            timeout_keep_alive=5,
        )
