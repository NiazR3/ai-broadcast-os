"""
Sentiment analysis for QuantAI — three-tier pipeline:

1. Finnhub news API (requires FINNHUB_API_KEY in config)
2. VADER rule-based on cached headlines (zero-cost fallback)
3. Improved mock (regime-aware heuristic)

The sentiment_scorer() function returns a value in [-1.0, +1.0].
"""

from __future__ import annotations

import logging
import math
import threading
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("prod_dash")

# ── Cached news store ──
_news_cache: dict[str, list[dict]] = {}
_news_cache_ts: dict[str, float] = {}
_news_cache_lock = threading.Lock()
_NEWS_CACHE_TTL = 3600  # 1 hour

# ── VADER (lazy import — may not be installed) ──
_VADER = None


def _get_vader():
    global _VADER
    if _VADER is None:
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            _VADER = SentimentIntensityAnalyzer()
        except ImportError:
            _VADER = False  # sentinel
    return _VADER if _VADER is not False else None


def _fetch_finnhub_news(ticker: str) -> list[dict]:
    """Fetch recent news from Finnhub. Returns list of {headline, summary}."""
    from backend import config
    if not config.FINNHUB_API_KEY:
        return []

    try:
        import finnhub
        client = finnhub.Client(api_key=config.FINNHUB_API_KEY)
        now = int(datetime.now(timezone.utc).timestamp())
        week_ago = now - 7 * 86400
        news = client.company_news(ticker, _from=week_ago, to=now)
        return [
            {"headline": item.get("headline", ""), "summary": item.get("summary", "")}
            for item in (news or [])
            if item.get("headline")
        ][:10]  # max 10 articles
    except Exception as exc:
        logger.debug("Finnhub news fetch failed for %s: %s", ticker, exc)
        return []


def _score_with_vader(headlines: list[str]) -> Optional[float]:
    """Score a list of headlines with VADER. Returns None if VADER unavailable."""
    vader = _get_vader()
    if vader is None:
        return None

    scores = []
    for headline in headlines:
        try:
            vs = vader.polarity_scores(headline)
            # compound score in [-1, +1]
            scores.append(vs["compound"])
        except Exception:
            continue

    if not scores:
        return None
    # Average compound score, clamped to [-1, +1]
    return max(-1.0, min(1.0, sum(scores) / len(scores)))


def _regime_mock_sentiment(ticker: str, features: dict) -> float:
    """
    Improved mock sentiment — replaces the original seeded-random approach.
    Uses asset-class bias + recent return direction + volatility regime.
    """
    from backend.market_data import TICKER_CLASS

    asset_class = TICKER_CLASS.get(ticker, "stock")

    # Base biases per class
    biases = {"stock": 0.0, "crypto": 0.05, "forex": -0.02}
    base = biases.get(asset_class, 0.0)

    # Recent return contribution (1d return → sentiment)
    ret_1 = features.get("return_1", 0.0) * 100  # convert to %
    momentum = max(-0.3, min(0.3, ret_1 * 2.0))

    # Volatility regime: high vol → negative bias
    vol_ratio = features.get("volatility_ratio", 1.0)
    vol_bias = -0.1 if vol_ratio > 1.5 else (0.05 if vol_ratio < 0.5 else 0.0)

    # MACD trend confirmation
    macd_hist = features.get("macd_hist", 0.0)
    trend_bias = 0.1 if macd_hist > 0 else (-0.1 if macd_hist < 0 else 0.0)

    combined = base + momentum + vol_bias + trend_bias
    return max(-1.0, min(1.0, round(combined, 4)))


def _sentiment_source(
    ticker: str, features: dict, force_fresh: bool = False
) -> tuple[float, str]:
    """
    Compute sentiment + source label for a ticker.
    Returns (score in [-1.0, +1.0], source_string).

    Source is one of: "finnhub+vader", "cache+vader", "synthetic"
    """
    # ── Tier 1: Finnhub news + VADER ──
    finnhub_news = _fetch_finnhub_news(ticker)
    if finnhub_news:
        headlines = [n["headline"] for n in finnhub_news if n.get("headline")]
        vader_score = _score_with_vader(headlines)
        if vader_score is not None:
            with _news_cache_lock:
                _news_cache[ticker] = finnhub_news
                _news_cache_ts[ticker] = datetime.now(timezone.utc).timestamp()
            if abs(vader_score) > 0.05:
                logger.debug(
                    "Sentiment[%s]: Finnhub+VADER %.3f (%d headlines)",
                    ticker, vader_score, len(headlines),
                )
            return round(vader_score, 4), "finnhub+vader"

    # ── Tier 2: Cached news + VADER ──
    with _news_cache_lock:
        cached = _news_cache.get(ticker, [])
        cached_ts = _news_cache_ts.get(ticker, 0)
        if cached and (datetime.now(timezone.utc).timestamp() - cached_ts) < _NEWS_CACHE_TTL:
            headlines = [n["headline"] for n in cached if n.get("headline")]
            vader_score = _score_with_vader(headlines)
            if vader_score is not None:
                return round(vader_score, 4), "cache+vader"

    # ── Tier 3: Regime-aware synthetic ──
    return _regime_mock_sentiment(ticker, features), "synthetic"


def sentiment_scorer(
    ticker: str, features: dict, force_fresh: bool = False
) -> float:
    """Compute sentiment for a ticker. Returns value in [-1.0, +1.0]."""
    score, _ = _sentiment_source(ticker, features, force_fresh)
    return score


def sentiment_scorer_with_source(
    ticker: str, features: dict
) -> dict:
    """Returns {'score': float, 'source': str}."""
    score, source = _sentiment_source(ticker, features)
    return {"score": round(score, 4), "source": source}
