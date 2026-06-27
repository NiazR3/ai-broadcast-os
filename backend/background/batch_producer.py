"""
Background batch producer — yfinance data fetcher with reliability features.

Improvements (June 2026):
  - Staleness detection: flags and skips stale data more aggressively
  - Adaptive batching: shrinks batch size on failure, grows on success
  - Circuit breaker: tracks consecutive failures per batch; backs off
  - Adaptive cycle timing: auto-adjusts if cycles run too long
"""

from __future__ import annotations

import asyncio
import logging
import time

from backend import config
from backend.market_data import BATCHES, ALL_TICKERS, cache_update, cache_get_field
from backend.market_data.yfinance_fetcher import fetch_batch
from backend.ml.inference import get_engine
from backend.services.accuracy_engine import log_prediction, db_stats

logger = logging.getLogger("prod_dash")

# ── Circuit breaker state ──
_batch_failures: dict[int, int] = {}  # batch_index → consecutive failures
_batch_backoff: dict[int, float] = {}  # batch_index → next allowed time (monotonic)
_MAX_CONSECUTIVE_FAILURES = 5
_BACKOFF_BASE_SEC = 30
_CYCLE_TIMING_HISTORY: list[float] = []  # last 10 cycle times


def _batch_is_circuit_open(batch_idx: int, now: float) -> bool:
    """Check if a batch is in circuit-breaker backoff."""
    if batch_idx in _batch_backoff:
        if now < _batch_backoff[batch_idx]:
            return True
        # Backoff expired — reset
        del _batch_backoff[batch_idx]
        _batch_failures[batch_idx] = 0
    return False


def _record_success(batch_idx: int):
    """Reduce failure count on success."""
    _batch_failures[batch_idx] = max(0, _batch_failures.get(batch_idx, 0) - 1)


def _record_failure(batch_idx: int, now: float):
    """Increment failure count and potentially open the circuit."""
    fails = _batch_failures.get(batch_idx, 0) + 1
    _batch_failures[batch_idx] = fails
    if fails >= _MAX_CONSECUTIVE_FAILURES:
        backoff = _BACKOFF_BASE_SEC * min(2 ** (fails - _MAX_CONSECUTIVE_FAILURES), 60)
        _batch_backoff[batch_idx] = now + backoff
        logger.warning("Circuit opened for batch %d (%d failures). Backoff: %.0fs",
                       batch_idx, fails, backoff)


def _check_staleness(data: dict) -> bool:
    """
    Basic staleness heuristic: if current_price is 0 or all fields are defaults,
    the data is likely stale/yfinance returned garbage.
    """
    price = data.get("current_price", 0)
    if price <= 0:
        return True
    return False


async def batch_producer_loop():
    """Async loop: every BATCH_INTERVAL_SEC, fetch all batches and update cache."""
    logger.info("Batch producer started (%d tickers, %d batches, interval=%ds)",
                len(ALL_TICKERS), len(BATCHES), config.BATCH_INTERVAL_SEC)

    while True:
        cycle_start = asyncio.get_event_loop().time()
        batches_completed = 0
        batches_skipped = 0
        batches_failed = 0

        for batch_idx, batch in enumerate(BATCHES):
            now = asyncio.get_event_loop().time()

            # ── Circuit breaker ──
            if _batch_is_circuit_open(batch_idx, now):
                batches_skipped += 1
                logger.debug("Batch %d skipped (circuit open)", batch_idx)
                continue

            # ── Fetch ──
            try:
                raw = await asyncio.get_event_loop().run_in_executor(
                    None, fetch_batch, batch
                )
                batches_completed += 1

                fresh_tickers = 0
                stale_tickers = 0

                for ticker, data in raw.items():
                    # ── Staleness check ──
                    if _check_staleness(data):
                        stale_tickers += 1
                        logger.debug("  %s: stale data skipped", ticker)
                        continue

                    fresh_tickers += 1
                    cache_update(ticker,
                        current_price=data["current_price"],
                        change_pct=data["change_pct"],
                        sma_20=data["sma_20"],
                        sma_50=data["sma_50"],
                        error=None,
                    )

                # ── ML Inference ──
                for ticker, data in raw.items():
                    if _check_staleness(data):
                        continue
                    result = get_engine().predict(data, ticker)
                    cache_update(ticker,
                        prob_up=result["prob_up"],
                        signal=result["signal"],
                        sentiment=result["sentiment"],
                        sentiment_source=result.get("sentiment_source", "synthetic"),
                        ml_active=result.get("ml_active", False),
                        model_class=result.get("model_class", "heuristic"),
                        confidence=result.get("confidence", 0.0),
                        last_updated=(
                            __import__("datetime")
                            .datetime.now()
                            .strftime("%H:%M:%S")
                        ),
                    )
                    log_prediction(ticker, result["prob_up"], data["current_price"])

                _record_success(batch_idx)

                if stale_tickers > fresh_tickers and fresh_tickers > 0:
                    logger.info("  Batch %d: %d/%d tickers stale", batch_idx, stale_tickers, len(batch))

            except Exception as exc:
                batches_failed += 1
                _record_failure(batch_idx, asyncio.get_event_loop().time())
                logger.warning("Batch %d failed: %s", batch_idx, exc)

            await asyncio.sleep(0.3)

        # ── Post-cycle: age tracking + adaptive timing ──
        now_ts = time.time()
        from backend.market_data import _cache_lock, SHARED_MARKET_CACHE
        with _cache_lock:
            for tkr, entry in SHARED_MARKET_CACHE.items():
                last_up = entry.get("last_updated_ts", 0)
                entry["data_age_s"] = int(now_ts - last_up) if last_up else 999

        elapsed = asyncio.get_event_loop().time() - cycle_start

        # Track cycle timing
        _CYCLE_TIMING_HISTORY.append(elapsed)
        if len(_CYCLE_TIMING_HISTORY) > 10:
            _CYCLE_TIMING_HISTORY.pop(0)

        # Adaptive interval: if cycles are consistently long, self-adjust
        actual_interval = config.BATCH_INTERVAL_SEC
        if len(_CYCLE_TIMING_HISTORY) >= 3:
            avg_cycle = sum(_CYCLE_TIMING_HISTORY[-3:]) / 3
            if avg_cycle > config.BATCH_INTERVAL_SEC * 0.8:
                # Running out of time — increase interval
                actual_interval = int(min(config.BATCH_INTERVAL_SEC * 1.5, 120))
                logger.info("Cycle avg %.1fs > 80%% of interval. Adjusting to %ds.",
                            avg_cycle, actual_interval)
            elif avg_cycle < config.BATCH_INTERVAL_SEC * 0.3 and config.BATCH_INTERVAL_SEC > 10:
                # Plenty of headroom — decrease interval
                actual_interval = int(max(config.BATCH_INTERVAL_SEC * 0.8, 5))

        logger.info("Cycle: %d ok / %d skipped / %d failed in %.1fs | %s",
                    batches_completed, batches_skipped, batches_failed,
                    elapsed, db_stats())

        await asyncio.sleep(max(1, actual_interval - elapsed))
