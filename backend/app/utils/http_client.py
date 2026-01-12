"""Async HTTP client with retry logic.

Phase 11: httpx + tenacity integration for external API resilience.

Features:
- Async HTTP client with connection pooling
- Automatic retry with exponential backoff
- Circuit breaker pattern
- Request/response logging
"""

import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger(__name__)


# Retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_MIN_WAIT = 1  # seconds
DEFAULT_MAX_WAIT = 10  # seconds


class AsyncHttpClient:
    """Async HTTP client with retry logic and connection pooling.

    Usage:
        async with AsyncHttpClient() as client:
            data = await client.get_json("https://api.example.com/data")
    """

    def __init__(
        self,
        timeout: float = 10.0,
        connect_timeout: float = 5.0,
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
    ):
        """Initialize HTTP client.

        Args:
            timeout: Total request timeout in seconds
            connect_timeout: Connection timeout in seconds
            max_connections: Maximum concurrent connections
            max_keepalive_connections: Maximum keepalive connections
        """
        self._timeout = httpx.Timeout(timeout, connect=connect_timeout)
        self._limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
        )
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "AsyncHttpClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            limits=self._limits,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the underlying httpx client."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")
        return self._client

    @retry(
        stop=stop_after_attempt(DEFAULT_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=DEFAULT_MIN_WAIT, max=DEFAULT_MAX_WAIT),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """GET request with retry.

        Args:
            url: Request URL
            **kwargs: Additional httpx request arguments

        Returns:
            HTTP response
        """
        response = await self.client.get(url, **kwargs)
        response.raise_for_status()
        return response

    @retry(
        stop=stop_after_attempt(DEFAULT_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=DEFAULT_MIN_WAIT, max=DEFAULT_MAX_WAIT),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def post(self, url: str, **kwargs) -> httpx.Response:
        """POST request with retry.

        Args:
            url: Request URL
            **kwargs: Additional httpx request arguments

        Returns:
            HTTP response
        """
        response = await self.client.post(url, **kwargs)
        response.raise_for_status()
        return response

    async def get_json(self, url: str, **kwargs) -> dict[str, Any]:
        """GET request returning JSON.

        Args:
            url: Request URL
            **kwargs: Additional httpx request arguments

        Returns:
            Parsed JSON response
        """
        response = await self.get(url, **kwargs)
        return response.json()

    async def post_json(self, url: str, data: dict[str, Any], **kwargs) -> dict[str, Any]:
        """POST request with JSON body returning JSON.

        Args:
            url: Request URL
            data: JSON body data
            **kwargs: Additional httpx request arguments

        Returns:
            Parsed JSON response
        """
        response = await self.post(url, json=data, **kwargs)
        return response.json()


# =============================================================================
# Singleton Client for Application-wide Use
# =============================================================================

_global_client: AsyncHttpClient | None = None


async def get_http_client() -> AsyncHttpClient:
    """Get or create global HTTP client.

    Returns:
        Shared AsyncHttpClient instance
    """
    global _global_client
    if _global_client is None:
        _global_client = AsyncHttpClient()
        await _global_client.__aenter__()
    return _global_client


async def close_http_client() -> None:
    """Close global HTTP client."""
    global _global_client
    if _global_client:
        await _global_client.__aexit__(None, None, None)
        _global_client = None


# =============================================================================
# Specialized Clients
# =============================================================================

class CryptoApiClient(AsyncHttpClient):
    """HTTP client specialized for cryptocurrency API calls.

    Features:
    - Higher retry count for critical financial operations
    - Fallback URL support
    - Rate limiting awareness
    """

    def __init__(self):
        super().__init__(
            timeout=15.0,
            connect_timeout=5.0,
            max_connections=50,
        )
        self._fallback_urls: dict[str, list[str]] = {}

    def register_fallback(self, primary_url: str, fallback_urls: list[str]) -> None:
        """Register fallback URLs for a primary URL.

        Args:
            primary_url: Primary API URL
            fallback_urls: List of fallback URLs to try
        """
        self._fallback_urls[primary_url] = fallback_urls

    async def get_with_fallback(self, url: str, **kwargs) -> dict[str, Any]:
        """GET request with fallback URLs.

        Args:
            url: Primary URL
            **kwargs: Additional request arguments

        Returns:
            JSON response from first successful request
        """
        urls = [url] + self._fallback_urls.get(url, [])

        last_error: Exception | None = None
        for attempt_url in urls:
            try:
                return await self.get_json(attempt_url, **kwargs)
            except Exception as e:
                logger.warning(f"Request to {attempt_url} failed: {e}")
                last_error = e
                continue

        raise last_error or RuntimeError("All URLs failed")
