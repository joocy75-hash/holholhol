"""Rate limiting middleware.

Provides Redis-based rate limiting for API endpoints.
"""

import logging
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-based rate limiting middleware.

    Rate limits are defined per endpoint path with format:
    (max_requests, window_seconds)
    """

    # Endpoint-specific rate limits
    RATE_LIMITS: dict[str, tuple[int, int]] = {
        "/api/v1/auth/login": (5, 60),       # 5 requests per 60 seconds
        "/api/v1/auth/register": (3, 60),    # 3 requests per 60 seconds
        "/api/v1/auth/refresh": (10, 60),    # 10 requests per 60 seconds
        "/api/v1/rooms": (30, 60),           # 30 requests per 60 seconds
        # Wallet endpoints - stricter limits for financial security
        "/api/v1/wallet/withdraw": (5, 3600),  # 5 requests per hour
        "/api/v1/wallet/deposit-address": (10, 60),  # 10 requests per minute
        "/api/v1/wallet/balance": (30, 60),   # 30 requests per minute
        "/api/v1/wallet/transactions": (20, 60),  # 20 requests per minute
        "/api/v1/wallet/rates": (60, 60),     # 60 requests per minute (cached)
    }

    # Default rate limit for unspecified endpoints
    DEFAULT_LIMIT: tuple[int, int] = (100, 60)  # 100 requests per 60 seconds

    def __init__(self, app: Callable, redis_client=None):
        """Initialize rate limiter.

        Args:
            app: ASGI application
            redis_client: Redis client instance (optional, disables rate limiting if None)
        """
        super().__init__(app)
        self._redis = redis_client

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check rate limit before processing request."""
        # Skip WebSocket upgrade requests - BaseHTTPMiddleware doesn't handle them properly
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        # Skip rate limiting if Redis not available
        if self._redis is None:
            return await call_next(request)

        # Skip rate limiting for WebSocket, health checks, and docs
        path = request.url.path
        if path.startswith(("/ws", "/health", "/docs", "/redoc", "/openapi.json")):
            return await call_next(request)

        # Get client identifier (IP address)
        client_ip = self._get_client_ip(request)

        # Get rate limit for this path
        limit, window = self._get_limit_for_path(path)

        # Build rate limit key
        key = f"ratelimit:{client_ip}:{path}"

        try:
            # Increment counter
            current = await self._redis.incr(key)

            # Set expiry on first request
            if current == 1:
                await self._redis.expire(key, window)

            # Check if over limit
            if current > limit:
                logger.warning(
                    f"Rate limit exceeded: {client_ip} on {path} "
                    f"({current}/{limit} in {window}s)"
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests. Please try again later.",
                            "details": {
                                "limit": limit,
                                "window": window,
                                "retry_after": window,
                            },
                        }
                    },
                    headers={"Retry-After": str(window)},
                )

            # Add rate limit headers to response
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(max(0, limit - current))
            response.headers["X-RateLimit-Reset"] = str(window)
            return response

        except Exception as e:
            # If Redis fails, allow request but log error
            logger.error(f"Rate limit check failed: {e}")
            return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request.

        Handles X-Forwarded-For header for reverse proxy setups.
        """
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take first IP in chain (original client)
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _get_limit_for_path(self, path: str) -> tuple[int, int]:
        """Get rate limit for the given path."""
        # Check exact match first
        if path in self.RATE_LIMITS:
            return self.RATE_LIMITS[path]

        # Check prefix match for parameterized routes
        for pattern, limit in self.RATE_LIMITS.items():
            if path.startswith(pattern):
                return limit

        return self.DEFAULT_LIMIT
