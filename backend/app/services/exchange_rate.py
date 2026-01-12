"""Exchange Rate Service for cryptocurrency to KRW conversion.

Phase 5.5: Real-time exchange rate API integration.
- CoinGecko as primary API
- Binance as fallback
- Redis caching with 1-minute TTL

지원 코인 (빠른 송금 위주):
- USDT (TRC-20): 테더
- XRP: 리플
- TRX: 트론
- SOL: 솔라나
"""

import asyncio
import logging
from datetime import datetime
from decimal import Decimal

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.models.wallet import CryptoType
from app.utils.redis_client import get_redis

logger = logging.getLogger(__name__)


class ExchangeRateError(Exception):
    """Exchange rate fetch error."""

    pass


class ExchangeRateService:
    """Real-time cryptocurrency exchange rate service.

    Features:
    - Real-time rate fetching from CoinGecko/Binance
    - Redis caching with 60-second TTL
    - Fallback to cached rate on API failure
    - Support for USDT, XRP, TRX, SOL (빠른 송금 코인)
    """

    CACHE_TTL = 60  # 1 minute cache
    CACHE_KEY_PREFIX = "exchange_rate:"

    # CoinGecko ID mapping (빠른 송금 코인)
    COINGECKO_IDS = {
        CryptoType.USDT: "tether",
        CryptoType.XRP: "ripple",
        CryptoType.TRX: "tron",
        CryptoType.SOL: "solana",
    }

    # Binance symbol mapping (fallback)
    BINANCE_SYMBOLS = {
        CryptoType.USDT: "USDTKRW",
        CryptoType.XRP: "XRPKRW",
        CryptoType.TRX: "TRXKRW",
        CryptoType.SOL: "SOLKRW",
    }

    def __init__(self) -> None:
        """Initialize exchange rate service."""
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_connections=20),
        )

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()

    async def get_rate_to_krw(self, crypto_type: CryptoType) -> int:
        """Get exchange rate: 1 crypto = X KRW.

        Args:
            crypto_type: Cryptocurrency type (BTC, ETH, USDT, USDC)

        Returns:
            Exchange rate in KRW (integer)

        Raises:
            ExchangeRateError: If rate cannot be fetched
        """
        cache_key = f"{self.CACHE_KEY_PREFIX}{crypto_type.value}"

        # Try cache first
        redis = get_redis()
        cached_rate = await redis.get(cache_key)
        if cached_rate:
            logger.debug(f"Cache hit for {crypto_type.value} rate: {cached_rate}")
            return int(cached_rate)

        # Fetch from API
        try:
            rate = await self._fetch_rate_coingecko(crypto_type)
        except Exception as e:
            logger.warning(
                f"CoinGecko failed for {crypto_type.value}: {e}, trying Binance"
            )
            try:
                rate = await self._fetch_rate_binance(crypto_type)
            except Exception as e2:
                logger.error(f"Both APIs failed for {crypto_type.value}: {e2}")
                # Try to return stale cache
                stale_key = f"{cache_key}:stale"
                stale_rate = await redis.get(stale_key)
                if stale_rate:
                    logger.warning(
                        f"Using stale rate for {crypto_type.value}: {stale_rate}"
                    )
                    return int(stale_rate)
                raise ExchangeRateError(f"Could not fetch rate for {crypto_type.value}")

        # Cache the rate
        await redis.setex(cache_key, self.CACHE_TTL, str(rate))
        # Also keep a stale copy for 24 hours as fallback
        await redis.setex(f"{cache_key}:stale", 86400, str(rate))

        logger.info(f"Fetched {crypto_type.value} rate: {rate:,} KRW")
        return rate

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((httpx.HTTPError, KeyError)),
    )
    async def _fetch_rate_coingecko(self, crypto_type: CryptoType) -> int:
        """Fetch rate from CoinGecko API."""
        coin_id = self.COINGECKO_IDS[crypto_type]
        url = (
            f"https://api.coingecko.com/api/v3/simple/price"
            f"?ids={coin_id}&vs_currencies=krw"
        )

        response = await self._client.get(url)
        response.raise_for_status()
        data = response.json()

        return int(data[coin_id]["krw"])

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((httpx.HTTPError, KeyError)),
    )
    async def _fetch_rate_binance(self, crypto_type: CryptoType) -> int:
        """Fetch rate from Binance API (fallback)."""
        symbol = self.BINANCE_SYMBOLS[crypto_type]
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"

        response = await self._client.get(url)
        response.raise_for_status()
        data = response.json()

        return int(float(data["price"]))

    async def convert_crypto_to_krw(
        self,
        crypto_type: CryptoType,
        crypto_amount: str | Decimal,
    ) -> tuple[int, int]:
        """Convert cryptocurrency amount to KRW.

        Args:
            crypto_type: Cryptocurrency type
            crypto_amount: Amount in crypto (string/Decimal for precision)

        Returns:
            Tuple of (krw_amount, exchange_rate)
        """
        if isinstance(crypto_amount, str):
            crypto_amount = Decimal(crypto_amount)

        rate = await self.get_rate_to_krw(crypto_type)
        krw_amount = int(crypto_amount * rate)

        return krw_amount, rate

    async def convert_krw_to_crypto(
        self,
        crypto_type: CryptoType,
        krw_amount: int,
    ) -> tuple[Decimal, int]:
        """Convert KRW amount to cryptocurrency.

        Args:
            crypto_type: Cryptocurrency type
            krw_amount: Amount in KRW

        Returns:
            Tuple of (crypto_amount as Decimal, exchange_rate)
        """
        rate = await self.get_rate_to_krw(crypto_type)
        crypto_amount = Decimal(krw_amount) / Decimal(rate)

        return crypto_amount, rate

    async def get_all_rates(self) -> dict[CryptoType, int]:
        """Get all crypto rates concurrently.

        Returns:
            Dict mapping CryptoType to KRW rate
        """
        tasks = [self.get_rate_to_krw(crypto_type) for crypto_type in CryptoType]
        rates = await asyncio.gather(*tasks, return_exceptions=True)

        result = {}
        for crypto_type, rate in zip(CryptoType, rates):
            if isinstance(rate, Exception):
                logger.error(f"Failed to get {crypto_type.value} rate: {rate}")
            else:
                result[crypto_type] = rate

        return result


# Singleton instance
_exchange_rate_service: ExchangeRateService | None = None


def get_exchange_rate_service() -> ExchangeRateService:
    """Get exchange rate service singleton."""
    global _exchange_rate_service
    if _exchange_rate_service is None:
        _exchange_rate_service = ExchangeRateService()
    return _exchange_rate_service


async def close_exchange_rate_service() -> None:
    """Close exchange rate service."""
    global _exchange_rate_service
    if _exchange_rate_service:
        await _exchange_rate_service.close()
        _exchange_rate_service = None
