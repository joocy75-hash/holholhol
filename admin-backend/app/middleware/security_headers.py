"""Security headers middleware for Admin Backend.

Adds security-related HTTP headers to all responses.
"""

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses.

    Headers added:
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-Frame-Options: Prevents clickjacking
    - X-XSS-Protection: Enables XSS filter (legacy browsers)
    - Referrer-Policy: Controls referrer information
    - Permissions-Policy: Restricts browser features
    - Content-Security-Policy: Controls resource loading (production only)
    - Strict-Transport-Security: Enforces HTTPS (production only)
    """

    def __init__(self, app: Callable, debug: bool = True):
        """Initialize middleware with environment setting.

        Args:
            app: ASGI application
            debug: Debug mode flag (True = development, False = production)
        """
        super().__init__(app)
        self._is_production = not debug

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        response = await call_next(request)

        # === Basic Security Headers (all environments) ===

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # XSS protection for legacy browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict browser features (minimal permissions)
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), "
            "camera=(), "
            "geolocation=(), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "payment=(), "
            "usb=()"
        )

        # === Production-Only Security Headers ===

        if self._is_production:
            # Content Security Policy (CSP)
            csp_directives = [
                "default-src 'self'",
                "script-src 'self'",
                "style-src 'self' 'unsafe-inline'",
                "img-src 'self' data: https:",
                "font-src 'self' data:",
                "connect-src 'self' https:",
                "frame-ancestors 'none'",
                "base-uri 'self'",
                "form-action 'self'",
                "upgrade-insecure-requests",
            ]
            response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

            # HTTP Strict Transport Security (HSTS)
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # === Cache Control for API responses ===

        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        return response
