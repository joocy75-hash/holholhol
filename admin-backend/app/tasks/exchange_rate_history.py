"""Exchange rate history recording task.

Background task that periodically records USDT/KRW exchange rates
to the exchange_rate_history table for historical analysis.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.crypto import ExchangeRateHistory
from app.services.crypto.ton_exchange_rate import TonExchangeRateService

logger = logging.getLogger(__name__)
settings = get_settings()


class ExchangeRateHistoryTask:
    """Background task for recording exchange rate history.

    Periodically fetches the current USDT/KRW exchange rate and saves
    it to the database for historical tracking and analysis.
    """

    def __init__(
        self,
        db_session_factory: Callable[[], AsyncSession],
        redis_client=None,
        interval: int = 60,  # Record every minute
    ):
        """Initialize exchange rate history task.

        Args:
            db_session_factory: Factory function to create DB sessions
            redis_client: Redis client for exchange rate service
            interval: Seconds between recordings (default: 60)
        """
        self.db_session_factory = db_session_factory
        self.redis_client = redis_client
        self.interval = interval
        self._running = False
        self._rate_service: Optional[TonExchangeRateService] = None
        self._consecutive_errors = 0
        self._max_consecutive_errors = 10

    async def _get_rate_service(self) -> TonExchangeRateService:
        """Get or create exchange rate service."""
        if self._rate_service is None:
            self._rate_service = TonExchangeRateService(self.redis_client)
        return self._rate_service

    async def start(self):
        """Start the exchange rate recording loop.

        Runs continuously until stop() is called.
        Backs off on consecutive errors to prevent log spam.
        """
        self._running = True
        logger.info(
            f"Starting exchange rate history task (interval: {self.interval}s)"
        )

        while self._running:
            try:
                await self._record_rate()
                self._consecutive_errors = 0  # Reset on success
            except Exception as e:
                self._consecutive_errors += 1

                # Log less frequently on repeated errors
                if self._consecutive_errors <= 3 or self._consecutive_errors % 10 == 0:
                    logger.error(
                        f"Error recording exchange rate "
                        f"(attempt {self._consecutive_errors}): {e}"
                    )

                # Back off if too many errors
                if self._consecutive_errors >= self._max_consecutive_errors:
                    logger.warning(
                        f"Too many consecutive errors ({self._consecutive_errors}), "
                        f"backing off for 5 minutes"
                    )
                    await asyncio.sleep(300)  # 5 minutes
                    self._consecutive_errors = 0
                    continue

            await asyncio.sleep(self.interval)

        # Cleanup
        if self._rate_service:
            await self._rate_service.close()

        logger.info("Exchange rate history task stopped")

    def stop(self):
        """Stop the recording loop."""
        self._running = False

    async def _record_rate(self):
        """Fetch and record current exchange rate."""
        rate_service = await self._get_rate_service()

        # Get current rate
        rate = await rate_service.get_usdt_krw_rate()

        # Determine source (CoinGecko or Binance fallback)
        # Since the service tries CoinGecko first, we assume coingecko
        # unless there was a specific indicator
        source = "coingecko"  # Default source

        # Save to database
        await self._save_to_history(rate, source)

    async def _save_to_history(self, rate: Decimal, source: str):
        """Save rate to ExchangeRateHistory table.

        Args:
            rate: Exchange rate (KRW per USDT)
            source: Rate source (coingecko, binance, etc.)
        """
        async with self.db_session_factory() as db:
            history = ExchangeRateHistory(
                rate=rate,
                source=source,
                recorded_at=datetime.now(timezone.utc),
            )
            db.add(history)
            await db.commit()

            logger.debug(f"Recorded exchange rate: {rate} KRW/USDT from {source}")


async def record_exchange_rate_once(
    db: AsyncSession,
    redis_client=None,
) -> ExchangeRateHistory:
    """One-shot function to record current exchange rate.

    Can be called from API endpoints or manual triggers.

    Args:
        db: Database session
        redis_client: Optional Redis client

    Returns:
        ExchangeRateHistory: The created record
    """
    rate_service = TonExchangeRateService(redis_client)

    try:
        rate = await rate_service.get_usdt_krw_rate()
        source = "coingecko"

        history = ExchangeRateHistory(
            rate=rate,
            source=source,
            recorded_at=datetime.now(timezone.utc),
        )
        db.add(history)
        await db.commit()

        logger.info(f"Manually recorded exchange rate: {rate} KRW/USDT")
        return history

    finally:
        await rate_service.close()
