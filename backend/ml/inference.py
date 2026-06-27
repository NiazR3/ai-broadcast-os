"""
Real-time XGBoost inference engine for QuantAI (June 2026 v2).

Per-class model routing:
  - Loads separate calibrated XGBoost models for stock / crypto / forex
  - Routes each ticker to its class model based on TICKER_CLASS
  - Falls back to heuristic if per-class model unavailable

Sentiment:
  - Tier 1: Finnhub news + VADER NLP (requires FINNHUB_API_KEY)
  - Tier 2: Improved regime-aware heuristic

Feature importance:
  - Per-class importances exposed via model_health() dict
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Optional

import numpy as np

from backend.market_data import TICKER_CLASS
from backend.ml.features import FEATURE_NAMES, compute_ml_features
from backend.ml.sentiment import sentiment_scorer, sentiment_scorer_with_source

logger = logging.getLogger("prod_dash")

# ── Signal thresholds ──
SIGNAL_THRESHOLDS = [
    (0.80, "STRONG BUY"),
    (0.60, "BUY"),
    (0.40, "HOLD"),
    (0.20, "SELL"),
    (0.00, "STRONG SELL"),
]

MODELS_DIR = Path(__file__).resolve().parent / "models"
ASSET_CLASSES = ["stock", "crypto", "forex"]


class XGBoostEngine:
    """
    Per-class XGBoost prediction engine.

    Usage (singleton):
        engine = XGBoostEngine()
        engine.load()           # loads all per-class models
        result = engine.predict(features_dict, ticker)
        info   = engine.model_health()  # per-class status + importances
    """

    def __init__(self):
        # Per-class models
        self._models: dict[str, object] = {}       # class_name → model
        self._scalers: dict[str, object] = {}       # class_name → scaler
        self._metas: dict[str, dict] = {}           # class_name → metadata
        self._fallback_reasons: dict[str, str] = {} # class_name → reason

        self._features = FEATURE_NAMES

    # ── Loading ──

    def load(self) -> bool:
        """Load per-class models + scalers from disk. Returns True if any loaded."""
        any_loaded = False
        for cls in ASSET_CLASSES:
            loaded = self._load_class(cls)
            if loaded:
                any_loaded = True

        if not any_loaded:
            logger.info("No ML models found — falling back to heuristic for all classes.")

        return any_loaded

    def _load_class(self, class_name: str) -> bool:
        """Load one asset-class model. Returns True if successful."""
        import joblib

        cls_dir = MODELS_DIR / class_name
        model_path = cls_dir / "model.joblib"
        scaler_path = cls_dir / "scaler.joblib"
        meta_path = cls_dir / "metadata.json"

        if not model_path.exists() or not scaler_path.exists():
            self._fallback_reasons[class_name] = "model files not found"
            return False

        try:
            self._models[class_name] = joblib.load(model_path)
            self._scalers[class_name] = joblib.load(scaler_path)

            if meta_path.exists():
                with open(meta_path) as f:
                    meta = json.load(f)
                self._metas[class_name] = meta
                logger.info(
                    "  %s model loaded: acc=%.3f, AUC=%.3f, Brier=%.3f, calibrated=%s",
                    class_name,
                    meta.get("test_accuracy", 0),
                    meta.get("test_roc_auc", 0),
                    meta.get("test_brier_score", 0),
                    meta.get("calibrated", False),
                )
            else:
                self._metas[class_name] = {}
                logger.info("  %s model loaded (no metadata).", class_name)

            return True

        except Exception as exc:
            self._fallback_reasons[class_name] = str(exc)
            logger.warning("Failed to load %s model: %s — falling back.", class_name, exc)
            self._models.pop(class_name, None)
            self._scalers.pop(class_name, None)
            self._metas.pop(class_name, None)
            return False

    @property
    def active(self) -> bool:
        """True when at least one class model is loaded."""
        return len(self._models) > 0

    def class_active(self, class_name: str) -> bool:
        """True when the specific class model is loaded."""
        return class_name in self._models

    def fallback_reason(self, class_name: str = "stock") -> Optional[str]:
        return self._fallback_reasons.get(class_name)

    # ── Inference ──

    def predict(self, features: dict[str, float], ticker: str = "") -> dict:
        """
        Run inference on a feature dict.

        Route: ticker → TICKER_CLASS → per-class model → predict

        Returns:
            {
                "prob_up": float (0..1),
                "signal": str,
                "sentiment": float (-1..1),
                "confidence": float (0..1),
                "ml_active": bool,
                "model_class": str,        # which class model was used
            }
        """
        asset_class = TICKER_CLASS.get(ticker, "stock")

        if self.class_active(asset_class):
            return self._ml_predict(features, ticker, asset_class)
        # Try any available model as fallback
        for cls in ASSET_CLASSES:
            if self.class_active(cls):
                return self._ml_predict(features, ticker, cls)
        # No models at all — heuristic
        return self._fallback_predict(features, ticker)

    # ── ML path ──

    def _ml_predict(
        self, features: dict[str, float], ticker: str, class_name: str
    ) -> dict:
        """Predict using the per-class XGBoost model."""
        vec = np.array([[features.get(f, 0.0) for f in self._features]], dtype=np.float64)

        model = self._models[class_name]
        scaler = self._scalers[class_name]

        try:
            vec_s = scaler.transform(vec)
            prob_up = float(model.predict_proba(vec_s)[0, 1])
        except Exception as exc:
            logger.debug("ML inference error for %s (%s): %s — falling back.", ticker, class_name, exc)
            return self._fallback_predict(features, ticker)

        prob_up = max(0.01, min(0.99, prob_up))

        # Confidence: how far from 0.5
        confidence = round(2.0 * abs(prob_up - 0.5), 4)

        # Real sentiment (Finnhub+VADER, or synthetic estimate)
        sent_data = sentiment_scorer_with_source(ticker, features)

        signal = self._signal_from_prob(prob_up)

        return {
            "prob_up": round(prob_up, 4),
            "signal": signal,
            "sentiment": sent_data["score"],
            "sentiment_source": sent_data["source"],
            "confidence": confidence,
            "ml_active": True,
            "model_class": class_name,
        }

    # ── Fallback (improved heuristic) ──

    def _fallback_predict(self, features: dict[str, float], ticker: str) -> dict:
        """Improved sigmoid heuristic when ML model is unavailable."""
        rsi = features.get("rsi_14", 50)
        rsi_norm = (50 - rsi) / 50 * 0.35 + 0.5

        roc = features.get("return_5", 0) * 100
        roc_sig = 1 / (1 + math.exp(-roc * 0.25))

        sma_20 = features.get("close_vs_sma20", 0)
        sma_50 = features.get("close_vs_sma50", 0)
        cross_bias = 0.15 if sma_20 > sma_50 else -0.05

        # Enhanced: add VWAP distance + efficiency ratio signals
        vwap_dist = features.get("vwap_dist", 0)
        vwap_bias = max(-0.1, min(0.1, -vwap_dist * 0.01))  # reversion signal

        eff = features.get("efficiency_ratio", 0)
        eff_bias = 0.1 if eff > 0.5 else -0.05  # trending vs choppy

        logit = (
            (rsi_norm - 0.5) * 1.2
            + (roc_sig - 0.5) * 1.0
            + cross_bias
            + vwap_bias
            + eff_bias
        )
        prob_up = 1 / (1 + math.exp(-logit))
        prob_up = max(0.01, min(0.99, prob_up))

        confidence = round(2.0 * abs(prob_up - 0.5), 4)
        sent_data = sentiment_scorer_with_source(ticker, features)
        signal = self._signal_from_prob(prob_up)

        return {
            "prob_up": round(prob_up, 4),
            "signal": signal,
            "sentiment": sent_data["score"],
            "sentiment_source": sent_data["source"],
            "confidence": confidence,
            "ml_active": False,
            "model_class": "heuristic",
        }

    # ── Shared helpers ──

    @staticmethod
    def _signal_from_prob(prob: float) -> str:
        for threshold, label in SIGNAL_THRESHOLDS:
            if prob >= threshold:
                return label
        return "HOLD"

    # ── Model health / introspection ──

    def model_health(self) -> dict:
        """Return per-class model status + feature importances."""
        health = {}
        for cls in ASSET_CLASSES:
            meta = self._metas.get(cls, {})
            health[cls] = {
                "active": cls in self._models,
                "model_type": "XGBoost_Calibrated" if cls in self._models else None,
                "fallback_reason": self._fallback_reasons.get(cls),
                "test_accuracy": meta.get("test_accuracy"),
                "test_roc_auc": meta.get("test_roc_auc"),
                "test_brier_score": meta.get("test_brier_score"),
                "n_training_samples": meta.get("n_training_samples"),
                "calibrated": meta.get("calibrated"),
                "trained_at": meta.get("trained_at"),
                "feature_importances": meta.get("feature_importances"),
                "label_offset": meta.get("label_offset"),
                "interval": meta.get("interval"),
            }
        health["features"] = self._features
        health["n_features"] = len(self._features)
        return health


    # ── Feature drift detection ──

    def detect_feature_drift(self, class_name: str) -> list[str]:
        """
        Compare current feature importances against the previous metadata.
        Returns a list of drift warnings (empty = no significant drift).

        A feature is considered to have drifted if its rank changed by >= 10
        positions between the previous and current training run.
        """
        meta = self._metas.get(class_name, {})
        if not meta or "feature_importances" not in meta:
            return []

        previous = meta["feature_importances"]

        # Only works if the engine was reloaded after retraining
        if class_name not in self._models:
            return []

        model = self._models[class_name]
        current_importances = dict(
            sorted(
                zip(self._features, model.feature_importances_),
                key=lambda x: -x[1],
            )
        )

        prev_rank = {f: i for i, f in enumerate(previous.keys())}
        curr_rank = {f: i for i, f in enumerate(current_importances.keys())}

        warnings: list[str] = []
        for feat, curr_pos in curr_rank.items():
            prev_pos = prev_rank.get(feat, len(previous))
            if abs(curr_pos - prev_pos) >= 10:
                warnings.append(
                    f"{feat}: rank {prev_pos} -> {curr_pos} (delta={curr_pos - prev_pos:+d})"
                )

        if warnings:
            logger.warning(
                "Feature drift detected for %s: %s",
                class_name, "; ".join(warnings[:5]),
            )
        return warnings


# ── Module-level singleton ──
_engine: Optional[XGBoostEngine] = None


def get_engine() -> XGBoostEngine:
    """Return (and lazily initialize) the global prediction engine."""
    global _engine
    if _engine is None:
        _engine = XGBoostEngine()
        _engine.load()
    return _engine
