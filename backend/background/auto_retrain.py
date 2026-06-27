"""
Background auto-retraining loop — periodically retrains per-class models.

Schedule: configurable via AUTO_RETRAIN_HOURS (default: 168h = 7 days).
  - After training, fresh-initializes the inference engine to pick up new models.
  - Logs training metrics to track model drift over time.
  - Runs in a background asyncio task, non-blocking to API.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from backend import config
from backend.ml.trainer import train
from backend.ml.inference import get_engine

logger = logging.getLogger("prod_dash")

# ── Training history (in-memory, for dashboard exposition) ──
_training_history: list[dict] = []


def get_training_history(limit: int = 20) -> list[dict]:
    """Return recent training runs."""
    return _training_history[-limit:]


async def auto_retrain_loop():
    """Periodic retraining loop. Runs once at boot (after delay), then on schedule."""
    if config.AUTO_RETRAIN_HOURS <= 0:
        logger.info("Auto-retrain disabled (AUTO_RETRAIN_HOURS=%d)", config.AUTO_RETRAIN_HOURS)
        return

    # First training: delay 5 min to let the server stabilise
    await asyncio.sleep(300)
    logger.info("Auto-retrain loop started (interval=%dh)", config.AUTO_RETRAIN_HOURS)

    while True:
        try:
            await _run_training_cycle()
        except Exception as exc:
            logger.error("Auto-retrain cycle failed: %s", exc, exc_info=True)

        await asyncio.sleep(config.AUTO_RETRAIN_HOURS * 3600)


async def _run_training_cycle():
    """Execute one training cycle in a thread executor."""
    logger.info("=" * 60)
    logger.info("  Auto-retrain cycle starting at %s",
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
    logger.info("=" * 60)

    t0 = time.time()

    # Run training in thread executor (blocking I/O + CPU)
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, _do_train)

    elapsed = time.time() - t0

    # Reload inference engine
    loop.run_in_executor(None, _reload_engine)

    # Record history
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(elapsed, 1),
        "results": results,
    }
    _training_history.append(record)

    logger.info("─" * 60)
    logger.info("  Auto-retrain complete in %.1f s", elapsed)
    for r in results:
        logger.info("  %-8s: acc=%.4f AUC=%.4f Brier=%.4f (%d samples)",
                    r.get("class", "?"), r.get("accuracy", 0),
                    r.get("roc_auc", 0), r.get("brier_score", 0),
                    r.get("samples", 0))
    logger.info("─" * 60)


def _do_train() -> list[dict]:
    """Blocking call to train all class models. Runs in thread pool."""
    return train()


def _reload_engine():
    """Re-initialize the inference engine to pick up new model files."""
    import backend.ml.inference as inf_mod

    try:
        # Pre-load new engine so we don't leave the API without a model
        new_engine = inf_mod.XGBoostEngine()
        loaded = new_engine.load()
        if loaded:
            # Atomic swap — inference calls will pick up the new engine
            inf_mod._engine = new_engine
            logger.info("Inference engine reloaded after retrain.")
        else:
            logger.warning("New engine loaded no models — keeping existing engine.")
    except Exception as exc:
        logger.warning("Engine reload failed: %s — old models still active.", exc)
