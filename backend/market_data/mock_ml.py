"""
Prediction engine — XGBoost with fallback to heuristic.

Module-level convenience functions that delegate to the global
XGBoostEngine singleton.  Drop-in replacement for the original MockEngine.
"""

from backend.ml.inference import get_engine, SIGNAL_THRESHOLDS

# ── Public API (same names as original MockEngine) ──


def compute_prob_up(features: dict) -> float:
    """Return P(↑) from the active prediction engine."""
    ticker = features.get("_ticker", "")
    result = get_engine().predict(features, ticker)
    return result["prob_up"]


def signal_from_prob(prob: float) -> str:
    """Map a probability to a signal label."""
    for threshold, label in SIGNAL_THRESHOLDS:
        if prob >= threshold:
            return label
    return "HOLD"


def compute_sentiment(ticker: str, features: dict) -> float:
    """Return sentiment from the active prediction engine."""
    result = get_engine().predict(features, ticker)
    return result["sentiment"]


def compute_rsi(closes, period: int = 14) -> float:
    """RSI kept for external callers; uses built-in Pandas logic."""
    if len(closes) < period + 1:
        return 50.0
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_g = gain.ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
    avg_l = loss.ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100 - 100 / (1 + rs)


def get_model_active() -> bool:
    """True when any XGBoost class model is loaded and running."""
    return get_engine().active


def get_model_info() -> str:
    """Human-readable status of the inference engine."""
    eng = get_engine()
    if eng.active:
        classes = [k for k in ["stock", "crypto", "forex"] if k in eng._models]
        return f"XGBoost (classes: {', '.join(classes)})"
    reasons = [eng._fallback_reasons.get(c, "?") for c in ["stock", "crypto", "forex"]]
    return f"Heuristic (fallback: {reasons[0]})"
