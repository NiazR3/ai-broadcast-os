"""SQLite-backed prediction accuracy tracker — 24h rolling metrics.

Tracks:
  - Binary accuracy (UP/DOWN correctness)
  - Brier score  ((prob - actual)²)
  - Log-loss    (cross-entropy: lower is better)
  - Rolling ROC-AUC (when sufficient evaluated predictions accumulate)
"""

from __future__ import annotations

import logging
import math
import sqlite3
import threading
from typing import Optional

import numpy as np

from backend.market_data import TICKER_CLASS
from backend import config

logger = logging.getLogger("prod_dash")

_db_lock = threading.Lock()
ACCURACY_DB = config.DATA_DIR / "prediction_accuracy.db"


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(ACCURACY_DB), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _init_db():
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker          TEXT NOT NULL,
            logged_at       TEXT NOT NULL DEFAULT (datetime('now')),
            baseline_price  REAL NOT NULL,
            predicted_dir   TEXT NOT NULL,
            prob_up         REAL DEFAULT 0.0,
            actual_price    REAL,
            actual_dir      TEXT,
            actual_up       INTEGER,         -- 1 if price went up, 0 if down
            is_evaluated    INTEGER DEFAULT 0,
            evaluated_at    TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pred_ticker
        ON predictions(ticker, logged_at)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pred_eval
        ON predictions(is_evaluated, logged_at)
    """)
    conn.commit()
    conn.close()


def log_prediction(ticker: str, prob_up: float, price: float):
    direction = "UP" if prob_up >= 0.5 else "DOWN"
    try:
        conn = _get_db()
        with _db_lock:
            conn.execute(
                "INSERT INTO predictions "
                "(ticker, logged_at, baseline_price, predicted_dir, prob_up) "
                "VALUES (?, datetime('now'), ?, ?, ?)",
                (ticker, price, direction, round(prob_up, 4)),
            )
            conn.commit()
        conn.close()
    except Exception as exc:
        logger.warning("DB log failed %s: %s", ticker, exc)


def evaluate_predictions() -> int:
    """Evaluate all un-evaluated predictions older than 15 minutes."""
    from backend.market_data import cache_get_field

    conn = _get_db()
    evaluated = 0
    try:
        with _db_lock:
            rows = conn.execute(
                "SELECT id, ticker, baseline_price, predicted_dir, prob_up "
                "FROM predictions "
                "WHERE is_evaluated = 0 "
                "  AND logged_at < datetime('now', ?)",
                (f'-{config.PREDICTION_EVAL_DELAY_MINUTES} minutes',),
            ).fetchall()

            for row in rows:
                pred_id, ticker, base_price, pred_dir, prob_up = row
                current_price = cache_get_field(ticker, "current_price")
                if current_price is None or current_price <= 0:
                    continue
                actual_up = 1 if current_price >= base_price else 0
                actual_dir = "UP" if actual_up else "DOWN"
                conn.execute(
                    "UPDATE predictions SET "
                    "  actual_price = ?, actual_dir = ?, actual_up = ?, "
                    "  is_evaluated = 1, evaluated_at = datetime('now') "
                    "WHERE id = ?",
                    (round(current_price, 4), actual_dir, actual_up, pred_id),
                )
                evaluated += 1
            conn.commit()
    except Exception as exc:
        logger.warning("DB evaluate error: %s", exc)
    finally:
        conn.close()
    return evaluated


# ═══════════════════════════════════════════════════════════════════
# Accuracy metrics
# ═══════════════════════════════════════════════════════════════════


def compute_24h_accuracy(ticker: str) -> tuple[float, int]:
    """Binary accuracy (UP/DOWN correctness) over last 24 hours."""
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT "
            "  SUM(CASE WHEN predicted_dir = actual_dir THEN 1 ELSE 0 END) AS correct, "
            "  COUNT(*) AS total "
            "FROM predictions "
            "WHERE ticker = ? AND is_evaluated = 1 "
            "  AND logged_at > datetime('now', '-24 hours')",
            (ticker,),
        ).fetchone()
        conn.close()
        if row and row["total"] and row["total"] > 0:
            return (row["correct"] / row["total"], row["total"])
        return (0.0, 0)
    except Exception:
        conn.close()
        return (0.0, 0)


def compute_rolling_brier(ticker: str, window_hours: int = 24) -> Optional[float]:
    """
    Brier score for a ticker over the rolling window.
    Brier = mean((prob_up - actual_up)²)
    Range: 0 (perfect) to 1 (worst).  <0.25 is skilful.
    """
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT prob_up, actual_up "
            "FROM predictions "
            "WHERE ticker = ? AND is_evaluated = 1 AND actual_up IS NOT NULL "
            "  AND logged_at > datetime('now', ?)",
            (ticker, f'-{window_hours} hours'),
        ).fetchall()
        conn.close()
        if not rows:
            return None
        errors = [(row["prob_up"] - row["actual_up"]) ** 2 for row in rows]
        return round(sum(errors) / len(errors), 4)
    except Exception:
        conn.close()
        return None


def compute_rolling_logloss(ticker: str, window_hours: int = 24) -> Optional[float]:
    """
    Log-loss (cross-entropy) for a ticker.
    LL = -mean(actual·log(prob) + (1-actual)·log(1-prob))
    Range: 0 (perfect) to ∞.  Lower is better.
    """
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT prob_up, actual_up "
            "FROM predictions "
            "WHERE ticker = ? AND is_evaluated = 1 AND actual_up IS NOT NULL "
            "  AND logged_at > datetime('now', ?)",
            (ticker, f'-{window_hours} hours'),
        ).fetchall()
        conn.close()
        if not rows:
            return None
        losses = []
        eps = 1e-15  # avoid log(0)
        for row in rows:
            p = max(eps, min(1 - eps, row["prob_up"]))
            y = row["actual_up"]
            losses.append(-(y * math.log(p) + (1 - y) * math.log(1 - p)))
        return round(sum(losses) / len(losses), 4)
    except Exception:
        conn.close()
        return None


def compute_rolling_roc_auc(ticker: str, window_hours: int = 168) -> Optional[float]:
    """
    ROC-AUC over the rolling window (default 7 days).
    Requires at least one positive and one negative sample.
    """
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT prob_up, actual_up "
            "FROM predictions "
            "WHERE ticker = ? AND is_evaluated = 1 AND actual_up IS NOT NULL "
            "  AND logged_at > datetime('now', ?)",
            (ticker, f'-{window_hours} hours'),
        ).fetchall()
        conn.close()
        if len(rows) < 10:
            return None
        y_true = np.array([r["actual_up"] for r in rows], dtype=np.int32)
        y_prob = np.array([r["prob_up"] for r in rows], dtype=np.float64)
        if y_true.sum() == 0 or (1 - y_true).sum() == 0:
            return None  # need both classes
        from sklearn.metrics import roc_auc_score
        return round(float(roc_auc_score(y_true, y_prob)), 4)
    except Exception:
        conn.close()
        return None


def compute_class_metrics(window_hours: int = 168) -> dict:
    """
    Aggregate metrics across all tickers, grouped by asset class.
    Returns {class_name: {accuracy, brier, logloss, roc_auc, n_tickers, n_preds}}.
    """
    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT ticker, prob_up, actual_up "
            "FROM predictions "
            "WHERE is_evaluated = 1 AND actual_up IS NOT NULL "
            "  AND logged_at > datetime('now', ?)",
            (f'-{window_hours} hours',),
        ).fetchall()
        conn.close()

        if not rows:
            return {}

        from collections import defaultdict
        by_class: dict[str, dict] = defaultdict(lambda: {"probs": [], "actuals": [], "correct": 0, "total": 0})

        for row in rows:
            ticker = row["ticker"]
            cls = TICKER_CLASS.get(ticker, "stock")
            p = row["prob_up"]
            a = row["actual_up"]
            by_class[cls]["probs"].append(p)
            by_class[cls]["actuals"].append(a)
            by_class[cls]["total"] += 1
            if (p >= 0.5 and a == 1) or (p < 0.5 and a == 0):
                by_class[cls]["correct"] += 1

        result = {}
        eps = 1e-15
        for cls, data in by_class.items():
            n = data["total"]
            if n < 5:
                continue
            acc = data["correct"] / n
            probs = np.clip(np.array(data["probs"]), eps, 1 - eps)
            actuals = np.array(data["actuals"])
            brier = float(np.mean((probs - actuals) ** 2))
            logloss = float(-np.mean(actuals * np.log(probs) + (1 - actuals) * np.log(1 - probs)))

            # ROC-AUC per class
            auc = None
            unique_cls = set(data["actuals"])
            if len(unique_cls) == 2 and n >= 10:
                try:
                    from sklearn.metrics import roc_auc_score
                    auc = round(float(roc_auc_score(actuals, probs)), 4)
                except Exception:
                    pass

            result[cls] = {
                "accuracy": round(acc, 4),
                "brier_score": round(brier, 4),
                "logloss": round(logloss, 4),
                "roc_auc": auc,
                "n_predictions": n,
            }

        return result
    except Exception:
        conn.close()
        return {}


# ═══════════════════════════════════════════════════════════════════
# Housekeeping
# ═══════════════════════════════════════════════════════════════════


def purge_old_predictions():
    conn = _get_db()
    try:
        with _db_lock:
            conn.execute(
                "DELETE FROM predictions "
                "WHERE logged_at < datetime('now', ?)",
                (f'-{config.DB_CLEANUP_AGE_HOURS} hours',),
            )
            conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def db_stats() -> dict:
    conn = _get_db()
    try:
        total = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        uneval = conn.execute(
            "SELECT COUNT(*) FROM predictions WHERE is_evaluated = 0"
        ).fetchone()[0]
        evaluated = conn.execute(
            "SELECT COUNT(*) FROM predictions WHERE is_evaluated = 1"
        ).fetchone()[0]
        conn.close()
        return {
            "total_rows": total,
            "unevaluated": uneval,
            "evaluated": evaluated,
        }
    except Exception:
        conn.close()
        return {"total_rows": 0, "unevaluated": 0, "evaluated": 0}


# Initialize DB on import
_init_db()
