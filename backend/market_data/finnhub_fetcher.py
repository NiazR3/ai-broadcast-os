"""Finnhub real-time quote fetcher with in-memory TTL cache."""

import time
import logging
import requests
from backend import config

logger = logging.getLogger("prod_dash")

_finnhub_cache: dict[str, dict] = {}
_finnhub_cache_ts: dict[str, float] = {}


def fetch_finnhub_quote(ticker: str) -> dict | None:
    """
    Fetch real-time quote from Finnhub API.
    Caches results for FINNHUB_CACHE_TTL seconds.
    """
    now = time.time()
    ttl = config.FINNHUB_CACHE_TTL

    cached = _finnhub_cache.get(ticker)
    cached_ts = _finnhub_cache_ts.get(ticker, 0)
    if cached and (now - cached_ts) < ttl:
        return cached

    fn_ticker = ticker
    if ticker.endswith("=X"):
        fn_ticker = ticker.replace("=X", "")
    elif ticker.endswith("-USD"):
        fn_ticker = "BINANCE:" + ticker.replace("-USD", "USDT")

    api_key = config.FINNHUB_API_KEY
    if not api_key:
        return None

    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={fn_ticker}&token={api_key}"
        resp = requests.get(url, timeout=5)
        data = resp.json()

        if "c" in data and data["c"] is not None and data["c"] > 0:
            result = {
                "current_price": float(data["c"]),
                "change_pct": round(float(data.get("dp", 0)), 2),
                "high": float(data.get("h", 0)),
                "low": float(data.get("l", 0)),
                "open": float(data.get("o", 0)),
                "prev_close": float(data.get("pc", 0)),
            }
            _finnhub_cache[ticker] = result
            _finnhub_cache_ts[ticker] = now
            return result
    except Exception as exc:
        logger.debug("Finnhub quote failed for %s: %s", ticker, exc)

    return None
