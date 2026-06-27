"""
Feature engineering for ML-based price prediction.

All functions operate on a ticker's OHLCV DataFrame (columns: Open, High, Low,
Close, Volume), as returned by yfinance with auto_adjust=True.

The training pipeline and the real-time inference path both call
compute_ml_features() — this guarantees feature consistency between training
and live prediction.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import kurtosis as scipy_kurtosis

# ── Canonical feature list (order matters — must match model input) ──

FEATURE_NAMES = [
    # ── Original 16 features (preserved) ──
    "return_1",
    "return_3",
    "return_5",
    "return_10",
    "return_20",
    "rsi_14",
    "macd",
    "macd_signal",
    "macd_hist",
    "bb_pct",
    "bb_width",
    "sma_cross",
    "atr_pct",
    "volume_change",
    "close_vs_sma20",
    "close_vs_sma50",
    # ── New features (added June 2026) ──
    "obv_norm",          # On-Balance Volume, z-scored (volume-pressure divergence)
    "vwap_dist",         # % distance from VWAP (mean reversion signal)
    "mfi_14",            # Money Flow Index (volume-weighted RSI)
    "volatility_ratio",  # ATR(14) / median(ATR, 50) — regime detector
    "efficiency_ratio",  # Directionality over 10 bars (trend strength)
    "kurtosis_20",       # Return-distribution tail-risk metric
    "max_dist_20",       # Position within 20-bar range [0,1]
]

# TARGET = 1 if close[i + LABEL_OFFSET] > close[i]
# Daily data:      5 = one trading week ahead
# 15m data:       24 = one trading day ahead (~6.5 h × 4 bars/h)
# 1h data:         8 = one trading day ahead
LABEL_OFFSET = 5  # overridden by training config at runtime


# ═══════════════════════════════════════════════════════════════════
# Individual indicator helpers
# ═══════════════════════════════════════════════════════════════════


def rsi(series: pd.Series, period: int = 14) -> float:
    """Wilder RSI."""
    if len(series) < period + 1:
        return 50.0
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_g = gain.ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
    avg_l = loss.ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
    if avg_l == 0.0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + avg_g / avg_l)


def macd(series: pd.Series) -> tuple[float, float, float]:
    """MACD line, signal line, histogram."""
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    line = ema12 - ema26
    sig = line.ewm(span=9, adjust=False).mean()
    hist = line - sig
    return float(line.iloc[-1]), float(sig.iloc[-1]), float(hist.iloc[-1])


def bollinger(series: pd.Series, period: int = 20) -> tuple[float, float]:
    """%B and bandwidth (width / price)."""
    if len(series) < period:
        return 0.5, 0.0
    sma = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = sma + 2.0 * std
    lower = sma - 2.0 * std
    price = series.iloc[-1]
    denom = upper.iloc[-1] - lower.iloc[-1]
    bb_pct = (price - lower.iloc[-1]) / max(denom, 1e-10)
    bb_width = denom / max(price, 1e-10)
    return float(bb_pct), float(bb_width)


def atr(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> float:
    """Average True Range."""
    if len(close) < period + 1:
        return 0.0
    tr = pd.DataFrame(
        {
            "hl": high - low,
            "hc": (high - close.shift()).abs(),
            "lc": (low - close.shift()).abs(),
        }
    ).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])


# ═══════════════════════════════════════════════════════════════════
# New indicator helpers (June 2026)
# ═══════════════════════════════════════════════════════════════════


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume series."""
    delta = close.diff()
    direction = delta.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv_series = (direction * volume).cumsum()
    return obv_series


def _vwap(ohlcv: pd.DataFrame) -> float:
    """VWAP from the full OHLCV window (cumulative)."""
    if "Volume" not in ohlcv.columns or "Close" not in ohlcv.columns:
        return 0.0
    vol = ohlcv["Volume"].dropna()
    close = ohlcv["Close"].dropna()
    if len(vol) < 1 or len(close) < 1:
        return 0.0
    # Align lengths
    min_len = min(len(vol), len(close))
    vol, close = vol.iloc[-min_len:], close.iloc[-min_len:]
    total_vol = vol.sum()
    if total_vol <= 0:
        return 0.0
    return float((close * vol).sum() / total_vol)


def _money_flow_index(
    high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int = 14
) -> float:
    """Money Flow Index — volume-weighted RSI analogue."""
    if len(close) < period + 1:
        return 50.0
    typical_price = (high + low + close) / 3.0
    money_flow = typical_price * volume
    delta = typical_price.diff()
    positive_flow = money_flow.where(delta > 0, 0.0).rolling(period).sum()
    negative_flow = money_flow.where(delta < 0, 0.0).rolling(period).sum()
    # Shift to align with the last completed period
    positive_flow = positive_flow.shift(0)
    negative_flow = negative_flow.shift(0)
    mfr = positive_flow / negative_flow.replace(0, 1e-10)
    mfi = 100.0 - 100.0 / (1.0 + mfr)
    return float(mfi.iloc[-1])


def _efficiency_ratio(close: pd.Series, period: int = 10) -> float:
    """Directionality ratio: |close - close[period]| / sum(|returns|).

    1.0 = perfectly directional trend. 0.0 = random walk / consolidation.
    Used in Kaufman's Adaptive Moving Average (KAMA).
    """
    if len(close) < period + 1:
        return 0.0
    direction = abs(float(close.iloc[-1] - close.iloc[-period - 1]))
    total_movement = float(
        close.diff().abs().iloc[-period:].sum()
    )
    if total_movement < 1e-10:
        return 0.0
    return direction / total_movement


def _max_dist_20(close: pd.Series, high: pd.Series, low: pd.Series) -> float:
    """Position within 20-bar range: (close - low_20) / (high_20 - low_20)."""
    if len(close) < 20:
        return 0.5
    h20 = float(high.iloc[-20:].max())
    l20 = float(low.iloc[-20:].min())
    denom = h20 - l20
    if denom < 1e-10:
        return 0.5
    return float((close.iloc[-1] - l20) / denom)


# ═══════════════════════════════════════════════════════════════════
# Full feature computation
# ═══════════════════════════════════════════════════════════════════


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns (yfinance output) to single level."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
    return df


def _ensure_scalar(val):
    """Ensure a value is a scalar, not a Series."""
    if isinstance(val, pd.Series):
        return float(val.iloc[0])
    return float(val)


def compute_ml_features(ohlcv: pd.DataFrame) -> dict[str, float]:
    """
    Compute all ML features from a ticker's OHLCV DataFrame (single-row, last bar).

    Returns a dict keyed by FEATURE_NAMES.  Missing features (insufficient
    history) are filled with 0.0 so the inference engine always receives a
    complete vector.
    """
    # Min viable length
    if ohlcv is None or ohlcv.empty:
        return {f: 0.0 for f in FEATURE_NAMES}

    # Flatten yfinance MultiIndex columns
    ohlcv = _flatten_columns(ohlcv.copy())

    close = ohlcv["Close"].dropna()
    if len(close) < 3:
        return {f: 0.0 for f in FEATURE_NAMES}

    last_c = _ensure_scalar(close.iloc[-1])
    out: dict[str, float] = {}

    # ── Returns (log) ──
    for period in [1, 3, 5, 10, 20]:
        idx = -(period + 1)
        if len(close) > period and last_c > 0 and close.iloc[idx] > 0:
            out[f"return_{period}"] = math.log(last_c / close.iloc[idx])
        else:
            out[f"return_{period}"] = 0.0

    # ── RSI ──
    out["rsi_14"] = rsi(close, 14)

    # ── MACD ──
    if len(close) >= 26:
        l, s, h = macd(close)
        out["macd"] = l
        out["macd_signal"] = s
        out["macd_hist"] = h
    else:
        out["macd"] = out["macd_signal"] = out["macd_hist"] = 0.0

    # ── Bollinger ──
    pct, bw = bollinger(close, 20)
    out["bb_pct"] = pct
    out["bb_width"] = bw

    # ── SMA cross & price relative ──
    if len(close) >= 50:
        s20 = float(close.rolling(20).mean().iloc[-1])
        s50 = float(close.rolling(50).mean().iloc[-1])
        out["sma_cross"] = (s20 / s50 - 1.0) * 100.0 if s50 > 0 else 0.0
        out["close_vs_sma20"] = (last_c / s20 - 1.0) * 100.0 if s20 > 0 else 0.0
        out["close_vs_sma50"] = (last_c / s50 - 1.0) * 100.0 if s50 > 0 else 0.0
    elif len(close) >= 20:
        s20 = float(close.rolling(20).mean().iloc[-1])
        out["sma_cross"] = 0.0
        out["close_vs_sma20"] = (last_c / s20 - 1.0) * 100.0 if s20 > 0 else 0.0
        out["close_vs_sma50"] = 0.0
    else:
        out["sma_cross"] = out["close_vs_sma20"] = out["close_vs_sma50"] = 0.0

    # ── ATR ──
    if all(c in ohlcv.columns for c in ["High", "Low"]):
        hi = ohlcv["High"].dropna()
        lo = ohlcv["Low"].dropna()
        atr_v = atr(hi, lo, close, 14)
        out["atr_pct"] = (atr_v / last_c * 100.0) if last_c > 0 else 0.0
    else:
        out["atr_pct"] = 0.0

    # ── Volume change ──
    if "Volume" in ohlcv.columns:
        vol = ohlcv["Volume"].dropna()
        if len(vol) >= 5:
            avg5 = float(vol.iloc[-5:].mean())
            out["volume_change"] = (vol.iloc[-1] / max(avg5, 1e-10)) - 1.0
        else:
            out["volume_change"] = 0.0
    else:
        out["volume_change"] = 0.0

    # ═══════════════════════════════════════════════════════════════
    # New features (June 2026)
    # ═══════════════════════════════════════════════════════════════

    hi = ohlcv["High"].dropna() if "High" in ohlcv.columns else None
    lo = ohlcv["Low"].dropna() if "Low" in ohlcv.columns else None
    vol = ohlcv["Volume"].dropna() if "Volume" in ohlcv.columns else None

    # ── OBV (normalized z-score over last 20 bars) ──
    if vol is not None and len(close) >= 21 and len(vol) >= 21:
        obv_series = _obv(close, vol)
        obv_recent = obv_series.iloc[-20:]
        obv_mean = float(obv_recent.mean())
        obv_std = float(obv_recent.std())
        if obv_std > 1e-10:
            out["obv_norm"] = float((obv_series.iloc[-1] - obv_mean) / obv_std)
        else:
            out["obv_norm"] = 0.0
    else:
        out["obv_norm"] = 0.0

    # ── VWAP distance (% away from VWAP) ──
    vwap_val = _vwap(ohlcv)
    out["vwap_dist"] = ((last_c / max(vwap_val, 1e-10)) - 1.0) * 100.0 if vwap_val > 0 else 0.0

    # ── MFI (Money Flow Index, 14-period) ──
    if all(c in ohlcv.columns for c in ["High", "Low", "Close", "Volume"]):
        out["mfi_14"] = _money_flow_index(
            hi, lo, close, vol, 14
        )
    else:
        out["mfi_14"] = 50.0

    # ── Volatility regime: ATR(14) / median(ATR, 50) ──
    if hi is not None and lo is not None and len(close) >= 64:
        atr_14 = atr(hi, lo, close, 14)
        tr = pd.DataFrame(
            {
                "hl": hi - lo,
                "hc": (hi - close.shift()).abs(),
                "lc": (lo - close.shift()).abs(),
            }
        ).max(axis=1)
        atr_50_median = float(tr.rolling(50).median().iloc[-1])
        if atr_50_median > 1e-10:
            out["volatility_ratio"] = atr_14 / atr_50_median
        else:
            out["volatility_ratio"] = 1.0
    else:
        out["volatility_ratio"] = 1.0

    # ── Efficiency ratio (10-bar trend strength) ──
    out["efficiency_ratio"] = _efficiency_ratio(close, 10)

    # ── Kurtosis of 20-bar returns ──
    if len(close) >= 21:
        returns_20 = close.diff().iloc[-20:].dropna().values
        if len(returns_20) >= 5:
            out["kurtosis_20"] = float(scipy_kurtosis(returns_20, fisher=True))
        else:
            out["kurtosis_20"] = 0.0
    else:
        out["kurtosis_20"] = 0.0

    # ── Position in 20-bar range [0, 1] ──
    if hi is not None and lo is not None and len(close) >= 20:
        out["max_dist_20"] = _max_dist_20(close, hi, lo)
    else:
        out["max_dist_20"] = 0.5

    return out


def compute_ml_features_all(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """
    Vectorized: compute ALL ML features for EVERY bar position in one pass.

    Returns a DataFrame with the same index as *ohlcv* and columns = FEATURE_NAMES.
    Early bars with insufficient history produce NaN (caller should dropna()).

    Use this during TRAINING for O(n) instead of O(n²) feature computation.
    For live inference (single bar), use compute_ml_features() instead.
    """
    import numpy as np

    if ohlcv is None or ohlcv.empty:
        return pd.DataFrame(columns=FEATURE_NAMES)

    ohlcv = _flatten_columns(ohlcv.copy())

    close = ohlcv["Close"].dropna()
    if len(close) < 3:
        return pd.DataFrame(columns=FEATURE_NAMES, index=ohlcv.index)

    has_hl = all(c in ohlcv.columns for c in ["High", "Low"])
    has_vol = "Volume" in ohlcv.columns

    high = ohlcv["High"] if has_hl else close
    low = ohlcv["Low"] if has_hl else close
    volume = ohlcv["Volume"] if has_vol else None

    df = pd.DataFrame(index=ohlcv.index, dtype=float)

    # ── Returns (log) ──
    for period in [1, 3, 5, 10, 20]:
        shifted = close.shift(period)
        df[f"return_{period}"] = np.where(
            (close > 0) & (shifted > 0),
            np.log(close / shifted),
            0.0,
        )

    # ── RSI 14 (Wilder) ──
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_g = gain.ewm(alpha=1 / 14, adjust=False).mean()
    avg_l = loss.ewm(alpha=1 / 14, adjust=False).mean()
    rs = avg_g / avg_l.replace(0, 1e-10)
    df["rsi_14"] = 100.0 - 100.0 / (1.0 + rs)

    # ── MACD ──
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    macd_sig = macd_line.ewm(span=9, adjust=False).mean()
    df["macd"] = macd_line
    df["macd_signal"] = macd_sig
    df["macd_hist"] = macd_line - macd_sig

    # ── Bollinger %B and Width ──
    sma20_c = close.rolling(20).mean()
    std20_c = close.rolling(20).std()
    upper = sma20_c + 2.0 * std20_c
    lower = sma20_c - 2.0 * std20_c
    denom_bb = upper - lower
    df["bb_pct"] = (close - lower) / denom_bb.replace(0, 1e-10)
    df["bb_width"] = denom_bb / close.replace(0, 1e-10)

    # ── SMA cross / price relative ──
    sma50_c = close.rolling(50).mean()
    df["sma_cross"] = ((sma20_c / sma50_c) - 1.0) * 100.0
    df["close_vs_sma20"] = ((close / sma20_c) - 1.0) * 100.0
    df["close_vs_sma50"] = ((close / sma50_c) - 1.0) * 100.0

    # ── ATR ──
    if has_hl:
        tr = pd.DataFrame({
            "hl": high - low,
            "hc": (high - close.shift()).abs(),
            "lc": (low - close.shift()).abs(),
        }).max(axis=1)
        atr_14 = tr.rolling(14).mean()
    else:
        atr_14 = pd.Series(0.0, index=close.index)
    df["atr_pct"] = (atr_14 / close * 100.0).where(
        (atr_14 > 0) & (close > 0), 0.0
    )

    # ── Volume change (vs 5-bar avg) ──
    if has_vol:
        vol_avg5 = volume.rolling(5).mean()
        df["volume_change"] = (volume / vol_avg5.replace(0, 1e-10)) - 1.0
    else:
        df["volume_change"] = 0.0

    # ── OBV (normalised z-score over trailing 20 bars) ──
    if has_vol:
        delta_dir = np.sign(close.diff()).fillna(0)
        obv = (delta_dir * volume).fillna(0).cumsum()
        obv_mean = obv.rolling(20).mean()
        obv_std = obv.rolling(20).std()
        df["obv_norm"] = (obv - obv_mean) / obv_std.replace(0, 1e-10)
    else:
        df["obv_norm"] = 0.0

    # ── VWAP distance (% away from cumulative VWAP) ──
    if has_vol and volume.sum() > 0:
        cum_vol = volume.cumsum()
        vwap = (close * volume).cumsum() / cum_vol.replace(0, 1e-10)
        df["vwap_dist"] = ((close / vwap) - 1.0) * 100.0
    else:
        df["vwap_dist"] = 0.0

    # ── MFI 14 ──
    if has_vol:
        typical_price = (high + low + close) / 3.0
        money_flow = typical_price * volume
        tp_delta = typical_price.diff()
        pos_mf = money_flow.where(tp_delta > 0, 0.0).rolling(14).sum()
        neg_mf = money_flow.where(tp_delta < 0, 0.0).rolling(14).sum()
        mfr = pos_mf / neg_mf.replace(0, 1e-10)
        df["mfi_14"] = 100.0 - 100.0 / (1.0 + mfr)
    else:
        df["mfi_14"] = 50.0

    # ── Volatility ratio: ATR(14) / median(ATR, 50) ──
    if has_hl:
        atr_50_med = tr.rolling(50).median()
        df["volatility_ratio"] = atr_14 / atr_50_med.replace(0, 1e-10)
    else:
        df["volatility_ratio"] = 1.0

    # ── Efficiency ratio (10-bar) ──
    direction_er = (close - close.shift(10)).abs()
    total_mvmt = close.diff().abs().rolling(10).sum()
    df["efficiency_ratio"] = direction_er / total_mvmt.replace(0, 1e-10)

    # ── Kurtosis of 20-bar returns ──
    returns = close.diff()
    df["kurtosis_20"] = returns.rolling(20).apply(
        lambda x: float(
            scipy_kurtosis(x.dropna().values, fisher=True)
        ) if len(x.dropna()) >= 5 else 0.0,
        raw=False,
    )

    # ── Position in 20-bar range [0, 1] ──
    if has_hl:
        h20 = high.rolling(20).max()
        l20 = low.rolling(20).min()
        denom_r = h20 - l20
        df["max_dist_20"] = (close - l20) / denom_r.replace(0, 1e-10)
    else:
        df["max_dist_20"] = 0.5

    return df


def create_label(ohlcv: pd.DataFrame, offset: int = LABEL_OFFSET) -> int | None:
    """
    Return 1 if close[i+offset] > close[i] (up), 0 if down, None if
    insufficient data.  Used during training only.
    """
    close = ohlcv["Close"].dropna()
    if len(close) <= offset:
        return None
    current = float(close.iloc[-offset - 1])
    future = float(close.iloc[-1])
    if current <= 0:
        return None
    return 1 if future > current else 0
