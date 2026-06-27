"""Dashboard REST API endpoints — all served from in-memory cache (zero I/O)."""

from fastapi import APIRouter, Depends, Request
from backend.market_data import cache_snapshot, cache_get, ALL_TICKERS, TICKER_CLASS
from backend.market_data.cache import STOCKS, CRYPTO, FOREX
from backend.services.accuracy_engine import (
    db_stats, compute_class_metrics, compute_rolling_brier,
    compute_rolling_logloss, compute_24h_accuracy,
)
from backend.services.accuracy_engine import compute_rolling_roc_auc
from backend.ml.inference import get_engine
from backend.background.auto_retrain import get_training_history
from backend.api.middleware import get_current_user, rate_limiter

router = APIRouter()


@router.get("/api/dashboard/summary")
async def dashboard_summary(
    request: Request,
    user: dict | None = Depends(get_current_user),
):
    """Ultra-fast: dumps entire SHARED_MARKET_CACHE as JSON."""
    await rate_limiter.check(request, user)
    return cache_snapshot()


@router.get("/api/dashboard/predict/{ticker:path}")
async def dashboard_predict(
    ticker: str,
    request: Request,
    user: dict | None = Depends(get_current_user),
):
    """Ultra-fast: serves the focused asset's analytics from memory."""
    await rate_limiter.check(request, user)
    ticker = ticker.upper().strip()
    entry = cache_get(ticker)
    if entry is None:
        return {"error": f"ticker '{ticker}' not tracked", "ticker": ticker}
    return entry


@router.get("/api/dashboard/tickers")
async def dashboard_tickers():
    """Return just the list of tracked tickers (for UI dropdowns)."""
    return {
        "count": len(ALL_TICKERS),
        "tickers": ALL_TICKERS,
        "classes": {"stock": len(STOCKS), "crypto": len(CRYPTO), "forex": len(FOREX)},
    }


@router.get("/api/dashboard/stats")
async def dashboard_stats():
    """Diagnostics: cache health, DB stats, cycle timing."""
    import time
    from backend.market_data import SHARED_MARKET_CACHE

    now_ts = time.time()
    fresh = 0
    stale = 0
    from backend.market_data import _cache_lock
    with _cache_lock:
        for entry in SHARED_MARKET_CACHE.values():
            age = entry.get("data_age_s", 999)
            if age < 60:
                fresh += 1
            else:
                stale += 1

    engine = get_engine()
    return {
        "cache_entries": len(SHARED_MARKET_CACHE),
        "fresh_tickers (<60s)": fresh,
        "stale_tickers (>=60s)": stale,
        "db": db_stats(),
        "ml_model": engine.active,
        "ml_status": {
            cls: {
                "active": engine.class_active(cls),
                "fallback_reason": engine.fallback_reason(cls),
            }
            for cls in ["stock", "crypto", "forex"]
        },
    }


@router.get("/api/dashboard/model-health")
async def dashboard_model_health():
    """Per-class model health: accuracy, AUC, Brier, feature importances, training history."""
    engine = get_engine()

    # Live accuracy metrics per class
    live_metrics = compute_class_metrics(window_hours=168)

    model_health = engine.model_health()
    training_history = get_training_history(limit=10)

    return {
        "per_class_models": model_health,
        "live_metrics_7d": live_metrics,
        "training_history": training_history,
        "inference_active": engine.active,
    }


@router.get("/api/dashboard/accuracy/{ticker:path}")
async def dashboard_ticker_accuracy(ticker: str):
    """Per-ticker accuracy metrics over rolling windows."""
    ticker = ticker.upper().strip()
    acc, count = compute_24h_accuracy(ticker)
    return {
        "ticker": ticker,
        "accuracy_24h": round(acc, 4) if count > 0 else None,
        "accuracy_count_24h": count,
        "brier_score_24h": compute_rolling_brier(ticker, 24),
        "brier_score_7d": compute_rolling_brier(ticker, 168),
        "logloss_24h": compute_rolling_logloss(ticker, 24),
        "logloss_7d": compute_rolling_logloss(ticker, 168),
        "roc_auc_7d": compute_rolling_roc_auc(ticker, 168),
    }
