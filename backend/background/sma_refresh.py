"""Background loop — refresh daily SMA20/SMA50 every SMA_REFRESH_INTERVAL."""

import asyncio
import logging
from backend import config
from backend.market_data import ALL_TICKERS, cache_update, make_batches
from backend.market_data.yfinance_fetcher import _fetch_daily_sma

logger = logging.getLogger("prod_dash")


async def sma_daily_loop():
    """Refresh daily SMAs every SMA_REFRESH_INTERVAL."""
    await asyncio.sleep(30)
    logger.info("Daily SMA loop started")
    batches = make_batches(ALL_TICKERS, 20)
    while True:
        for batch in batches:
            try:
                data = await asyncio.get_event_loop().run_in_executor(
                    None, _fetch_daily_sma, batch
                )
                for tkr, vals in data.items():
                    cache_update(tkr, **vals)
            except Exception:
                pass
            await asyncio.sleep(0.5)
        await asyncio.sleep(config.SMA_REFRESH_INTERVAL)
