"""Background loop — updates cache with Finnhub real-time quotes (~30 calls/s limit)."""

import asyncio
import logging
from backend import config
from backend.market_data import ALL_TICKERS, cache_update
from backend.market_data.finnhub_fetcher import fetch_finnhub_quote

logger = logging.getLogger("prod_dash")


async def finnhub_quote_loop():
    """Update SHARED_MARKET_CACHE with Finnhub real-time quotes every ~15s."""
    await asyncio.sleep(15)
    logger.info("Finnhub quote loop started")
    BATCH = 20
    INTERVAL = 15

    while True:
        cycle_start = asyncio.get_event_loop().time()
        all_tickers = list(ALL_TICKERS)
        for i in range(0, len(all_tickers), BATCH):
            batch = all_tickers[i:i+BATCH]
            for ticker in batch:
                try:
                    quote = await asyncio.get_event_loop().run_in_executor(
                        None, fetch_finnhub_quote, ticker
                    )
                    if quote:
                        cache_update(ticker,
                            current_price=quote["current_price"],
                            change_pct=quote["change_pct"],
                            finnhub_price=quote["current_price"],
                        )
                except Exception:
                    pass
                await asyncio.sleep(0.05)

        elapsed = asyncio.get_event_loop().time() - cycle_start
        await asyncio.sleep(max(1, INTERVAL - elapsed))
