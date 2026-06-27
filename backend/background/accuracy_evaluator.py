"""Background loop — evaluates predictions, recomputes 24h accuracy, purges old rows."""

import asyncio
import logging
from backend import config
from backend.market_data import ALL_TICKERS, cache_update, cache_get_field
from backend.services.accuracy_engine import evaluate_predictions, compute_24h_accuracy, purge_old_predictions, db_stats

logger = logging.getLogger("prod_dash")


async def accuracy_evaluator_loop():
    """Every ACCURACY_EVAL_INTERVAL: evaluate, recompute, purge."""
    await asyncio.sleep(60)
    logger.info("Accuracy evaluator started (interval=%ds)", config.ACCURACY_EVAL_INTERVAL)

    while True:
        try:
            evaled = evaluate_predictions()

            for ticker in ALL_TICKERS:
                acc, count = compute_24h_accuracy(ticker)
                prev_cnt = cache_get_field(ticker, "accuracy_count", 0)
                if count > prev_cnt or count > 0:
                    cache_update(ticker,
                        accuracy_24h=round(acc, 4),
                        accuracy_count=count,
                    )

            purge_old_predictions()

            if evaled > 0 or True:
                stats = db_stats()
                logger.info("Accuracy: %d evaluated | %s | 24h scores updated", evaled, stats)

        except Exception as exc:
            logger.warning("Accuracy eval cycle failed: %s", exc)

        await asyncio.sleep(config.ACCURACY_EVAL_INTERVAL)
