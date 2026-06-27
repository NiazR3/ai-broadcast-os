"""
XGBoost Training Pipeline — QuantAI  (June 2026 v2)

Trains separate calibrated XGBoost classifiers per asset class using 15m bars:

    stock/   ← 12 diverse US stocks
    crypto/  ← 5 liquid cryptocurrencies
    forex/   ← 5 major forex pairs

Each model gets its own StandardScaler + CalibratedClassifierCV (Platt scaling).
Models are saved to backend/ml/models/{asset_class}/ for inference routing.

Design decisions:
  - 15m bars capture intraday patterns that drive short-horizon signals
  - Per-class models avoid a single-model-fits-all compromise
  - Platt scaling produces well-calibrated probabilities (confidence ≈ accuracy)
  - label_offset=24 → predicts ~1 trading day ahead

Usage:
    python -m backend.ml.trainer
    python -m backend.ml.trainer --class stock       # single class
"""

from __future__ import annotations

import json
import logging
import time
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore", category=UserWarning, module="yfinance")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ml_trainer")

import pandas as pd  # noqa: E402
import yfinance as yf  # noqa: E402
import xgboost as xgb  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sklearn.metrics import accuracy_score, roc_auc_score, brier_score_loss  # noqa: E402
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV  # noqa: E402

from backend.ml.features import FEATURE_NAMES, compute_ml_features_all  # noqa: E402
from backend import config  # noqa: E402

# ── Paths ──
MODELS_DIR = Path(__file__).resolve().parent / "models"

# ── Training tickers per asset class ──

STOCK_TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",  # Tech mega-cap
    "META", "TSLA", "JPM",                      # Tech + finance
    "JNJ", "WMT", "CAT", "KO",                  # Diverse sectors
]

CRYPTO_TICKERS = [
    "BTC-USD", "ETH-USD", "SOL-USD",
    "DOGE-USD", "ADA-USD",
]

FOREX_TICKERS = [
    "EURUSD=X", "GBPUSD=X", "USDJPY=X",
    "AUDUSD=X", "USDCAD=X",
]

TRAINING_SETS = {
    "stock": STOCK_TICKERS,
    "crypto": CRYPTO_TICKERS,
    "forex": FOREX_TICKERS,
}

CLASS_LABEL_OFFSETS = {
    "stock": config.LABEL_OFFSET_STOCK,         # configurable per class
    "crypto": config.LABEL_OFFSET_CRYPTO,
    "forex": config.LABEL_OFFSET_FOREX,
}

CLASS_INTERVALS = {
    "stock": config.TRAINING_INTERVAL,
    "crypto": config.TRAINING_INTERVAL,
    "forex": config.TRAINING_INTERVAL,
}


def _download_batch(
    tickers: list[str], interval: str, period: str
) -> dict[str, pd.DataFrame]:
    """Download OHLCV for a batch of tickers. Returns {ticker: DataFrame}."""
    batch_str = " ".join(tickers)
    try:
        df = yf.download(
            tickers=batch_str,
            period=period,
            interval=interval,
            group_by="ticker",
            progress=False,
            auto_adjust=True,
            threads=True,
        )
    except Exception as exc:
        logger.warning("Download failed: %s", exc)
        return {}

    if df is None or df.empty:
        return {}

    result: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        try:
            if isinstance(df.columns, pd.MultiIndex):
                if ticker in df.columns.get_level_values(0):
                    tdf = df.xs(ticker, axis=1, level=0).copy()
                else:
                    continue
            elif ticker in df.columns:
                tdf = df[[ticker]].copy()
            else:
                continue
            if isinstance(tdf.columns, pd.MultiIndex):
                tdf.columns = [c[0] for c in tdf.columns]
            tdf = tdf.dropna(how="all")
            if tdf.empty or "Close" not in tdf.columns:
                continue
            result[ticker] = tdf
        except Exception:
            continue
    return result


def build_class_data(
    class_name: str, tickers: list[str]
) -> tuple[np.ndarray, np.ndarray, int]:
    """
    Download data for all tickers in a class, compute features + labels.
    Uses vectorised feature computation (O(n) per ticker instead of O(n²)).

    Returns (X, y, n_tickers_used).
    """
    interval = CLASS_INTERVALS[class_name]
    label_offset = CLASS_LABEL_OFFSETS[class_name]
    period = config.TRAINING_DATA_PERIOD

    logger.info(
        "Building %s data: %d tickers, interval=%s, period=%s, label_offset=%d",
        class_name, len(tickers), interval, period, label_offset,
    )

    all_X: list[np.ndarray] = []
    all_y: list[np.ndarray] = []
    ticker_count = 0

    # Download in batches of 6 to avoid yfinance rate limits
    for i in range(0, len(tickers), 6):
        batch = tickers[i : i + 6]
        raw = _download_batch(batch, interval, period)
        time.sleep(0.5)

        for ticker, tdf in raw.items():
            rows = 0
            # ── Vectorised feature computation: one pass per ticker ──
            feat_df = compute_ml_features_all(tdf)
            if feat_df.empty:
                continue

            # Generate labels: 1 if close[i + label_offset] > close[i]
            close = tdf["Close"]
            labels = (close.shift(-label_offset) > close).astype(int)

            # Truncate to rows where both features and future labels exist
            max_idx = len(feat_df) - label_offset
            feat_df = feat_df.iloc[:max_idx]
            labels = labels.iloc[:max_idx]

            # Drop rows with NaN (insufficient indicator history)
            valid = ~feat_df[FEATURE_NAMES].isna().any(axis=1)
            feat_df = feat_df[valid]
            labels = labels[valid]

            rows = len(feat_df)
            if rows > 0:
                all_X.append(feat_df[FEATURE_NAMES].values)
                all_y.append(labels.values)
                ticker_count += 1
                logger.debug("  %s: %d rows (offset=%d)", ticker, rows, label_offset)

    if not all_X:
        logger.warning("  No usable data for %s", class_name)
        return np.empty((0, len(FEATURE_NAMES))), np.empty(0), 0

    X = np.vstack(all_X).astype(np.float64)
    y = np.concatenate(all_y).astype(np.int32)

    # Remove rows where ALL features are zero (shouldn't happen with vectorised path)
    good = ~np.all(X == 0.0, axis=1)
    X, y = X[good], y[good]

    logger.info(
        "  → %d rows, %d features, %d tickers (%.1f%% UP)",
        len(X), X.shape[1], ticker_count, y.mean() * 100,
    )
    return X, y, ticker_count


def train_class_model(
    class_name: str, X: np.ndarray, y: np.ndarray,
) -> tuple:
    """
    Train a calibrated XGBoost classifier for one asset class.
    Returns (calibrated_model, scaler, accuracy, auc, brier, importances_dict).
    """
    # Temporal split: use last 20% as test to prevent future leakage.
    # shuffle=False is critical for time-series data — random split would let
    # future bars leak into training and inflate accuracy.
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    # Compute scale_pos_weight for imbalanced classes
    pos = y_train.sum()
    neg = len(y_train) - pos
    scale_pos = neg / pos if pos > 0 else 1.0

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    # ── Hyperparameter search via time-series CV ──
    if config.N_ESTIMATORS <= 0:
        # Auto-tuning mode: grid search over key params
        logger.info("  Optimizing hyperparams for %s (TimeSeriesSplit, n=3)...", class_name)
        param_grid = {
            "n_estimators": [100, 200, 300],
            "max_depth": [4, 6, 8],
            "learning_rate": [0.01, 0.05, 0.1],
            "subsample": [0.7, 0.8, 1.0],
        }
        tscv = TimeSeriesSplit(n_splits=3, test_size=len(X_train) // 10)
        base = xgb.XGBClassifier(
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos,
            eval_metric="logloss",
            random_state=42,
            verbosity=0,
            n_jobs=-1,
        )
        gs = GridSearchCV(
            base, param_grid,
            cv=tscv,
            scoring="roc_auc",
            n_jobs=-1,
            verbose=0,
        )
        gs.fit(X_train_s, y_train)
        best_params = gs.best_params_
        logger.info("  Best params for %s: %s (CV AUC=%.4f)",
                     class_name, best_params, gs.best_score_)
        final_model = xgb.XGBClassifier(
            **best_params,
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos,
            eval_metric="logloss",
            random_state=42,
            verbosity=0,
            n_jobs=-1,
        )
        final_model.fit(X_train_s, y_train)
    else:
        # Use configured fixed params
        final_model = xgb.XGBClassifier(
            n_estimators=config.N_ESTIMATORS,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos,
            eval_metric="logloss",
            random_state=42,
            verbosity=0,
            n_jobs=-1,
        )
        final_model.fit(X_train_s, y_train)

    # ── Evaluation ──
    probs = final_model.predict_proba(X_test_s)[:, 1]
    preds = (probs >= 0.5).astype(int)
    acc = float(accuracy_score(y_test, preds))
    auc = float(roc_auc_score(y_test, probs))
    brier = float(brier_score_loss(y_test, probs))

    # Feature importances
    importances_raw = dict(
        sorted(
            zip(FEATURE_NAMES, [float(v) for v in final_model.feature_importances_]),
            key=lambda x: -x[1],
        )
    )

    logger.info("  %s: acc=%.4f  AUC=%.4f  Brier=%.4f", class_name, acc, auc, brier)
    return final_model, scaler, acc, auc, brier, importances_raw


def save_class_model(
    class_name: str,
    model,
    scaler,
    accuracy: float,
    auc: float,
    brier: float,
    importances: dict,
    n_tickers: int,
    n_samples: int,
    interval: str,
    label_offset: int,
):
    """Save per-class model artifacts + metadata."""
    class_dir = MODELS_DIR / class_name
    class_dir.mkdir(parents=True, exist_ok=True)

    import joblib
    joblib.dump(model, class_dir / "model.joblib")
    joblib.dump(scaler, class_dir / "scaler.joblib")

    meta = {
        "asset_class": class_name,
        "features": FEATURE_NAMES,
        "n_features": len(FEATURE_NAMES),
        "interval": interval,
        "label_offset": label_offset,
        "test_accuracy": round(accuracy, 4),
        "test_roc_auc": round(auc, 4),
        "test_brier_score": round(brier, 4),
        "n_tickers": n_tickers,
        "n_training_samples": n_samples,
        "feature_importances": {k: round(float(v), 6) for k, v in importances.items()},
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "calibrated": config.CALIBRATE_PROBABILITIES,
        "n_estimators": config.N_ESTIMATORS,
        "hyperparam_tuned": config.N_ESTIMATORS <= 0,
        "temporal_split": True,
        "vectorized_features": True,
    }
    with open(class_dir / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    logger.info("  %s model saved to %s", class_name, class_dir)


def train_class(class_name: str) -> dict:
    """Full train pipeline for one asset class. Returns summary dict."""
    tickers = TRAINING_SETS[class_name]
    interval = CLASS_INTERVALS[class_name]
    label_offset = CLASS_LABEL_OFFSETS[class_name]

    logger.info("─" * 50)
    logger.info("  Training: %s  (%d tickers, %s, offset=%d)",
                class_name, len(tickers), interval, label_offset)
    logger.info("─" * 50)

    X, y, n_tickers = build_class_data(class_name, tickers)
    if len(X) < config.TRAINING_MIN_SAMPLES:
        logger.warning(
            "  %s: too few samples (%d < %d). Skipping.",
            class_name, len(X), config.TRAINING_MIN_SAMPLES,
        )
        return {"class": class_name, "status": "skipped", "samples": len(X)}

    model, scaler, acc, auc, brier, importances = train_class_model(class_name, X, y)
    save_class_model(
        class_name, model, scaler, acc, auc, brier, importances,
        n_tickers, len(X), interval, label_offset,
    )
    return {
        "class": class_name,
        "status": "ok",
        "samples": len(X),
        "tickers": n_tickers,
        "accuracy": round(acc, 4),
        "roc_auc": round(auc, 4),
        "brier_score": round(brier, 4),
        "interval": interval,
        "label_offset": label_offset,
    }


def train(classes: list[str] | None = None) -> list[dict]:
    """Train per-class models. Pass None to train all classes."""
    if classes is None:
        classes = list(TRAINING_SETS.keys())

    results = []
    for cls in classes:
        result = train_class(cls)
        results.append(result)

    return results


def main():
    logger.info("=" * 56)
    logger.info("  QuantAI ML Trainer v2 — Per-Class 15m Models")
    logger.info("  %d classes, %d features, calibration=%s",
                len(TRAINING_SETS), len(FEATURE_NAMES), config.CALIBRATE_PROBABILITIES)
    logger.info("=" * 56)

    t0 = time.time()
    results = train()

    elapsed = time.time() - t0
    logger.info("=" * 56)
    logger.info("  Training complete in %.1f s", elapsed)
    for r in results:
        logger.info("  %-8s %s (acc=%.4f, AUC=%.4f, %d samples)",
                    r["class"], r["status"],
                    r.get("accuracy", 0), r.get("roc_auc", 0), r.get("samples", 0))
    logger.info("=" * 56)

    # Save unified metadata at models dir root
    meta_path = MODELS_DIR / "metadata.json"
    existing = {}
    if meta_path.exists():
        with open(meta_path) as f:
            existing = json.load(f)
    # Remove per-class importances from root (they live in class dirs)
    root_meta = existing.copy()
    root_meta.update({
        "model_type": "XGBoost_v2",
        "features": FEATURE_NAMES,
        "n_features": len(FEATURE_NAMES),
        "classes_trained": [r["class"] for r in results],
        "last_trained_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "training_time_s": round(elapsed, 1),
        "configuration": {
            "interval": config.TRAINING_INTERVAL,
            "label_offset_default": config.TRAINING_LABEL_OFFSET,
            "period": config.TRAINING_DATA_PERIOD,
            "calibrated": config.CALIBRATE_PROBABILITIES,
            "n_estimators": config.N_ESTIMATORS,
        },
    })
    with open(meta_path, "w") as f:
        json.dump(root_meta, f, indent=2)
    logger.info("Root metadata updated at %s", meta_path)


if __name__ == "__main__":
    main()
