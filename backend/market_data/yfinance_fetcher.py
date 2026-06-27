"""yfinance batch data fetcher — multi-ticker with safeguards."""

import logging
import pandas as pd
import yfinance as yf
from backend.ml.features import compute_ml_features

logger = logging.getLogger("prod_dash")


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
    return df


def _safe_close(series) -> float:
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:, 0]
    try:
        val = float(series.iloc[-1])
        return val
    except (IndexError, ValueError, TypeError):
        return 0.0


def fetch_batch(tickers: list[str]) -> dict[str, dict]:
    """
    Fetch a single batch via yf.download with group_by="ticker".
    Returns {ticker: {current_price, sma_20, sma_50, roc, ...}, ...}
    Returns empty dict on total failure; partial results on partial failure.
    """
    if not tickers:
        return {}

    batch_str = " ".join(tickers)
    result: dict[str, dict] = {}

    try:
        df = yf.download(
            tickers=batch_str,
            period="5d",
            interval="15m",
            group_by="ticker",
            progress=False,
            auto_adjust=True,
            threads=True,
        )
    except Exception as exc:
        logger.warning("yfinance batch failed [%s]: %s", len(tickers), exc)
        return result

    if df is None or df.empty:
        return result

    for ticker in tickers:
        try:
            if isinstance(df.columns, pd.MultiIndex):
                if ticker in df.columns.get_level_values(0):
                    tdf = df.xs(ticker, axis=1, level=0).copy()
                else:
                    tdf = df.copy()
            elif ticker in df.columns:
                tdf = df[[ticker]].copy()
            else:
                tdf = df.copy()

            tdf = _flatten_columns(tdf)
            tdf = tdf.dropna(how="all")

            if tdf.empty or "Close" not in tdf.columns:
                continue

            close = tdf["Close"]
            close_s = close.iloc[:, 0] if isinstance(close, pd.DataFrame) else close
            close_s = close_s.dropna()

            if len(close_s) < 2:
                continue

            current = float(close_s.iloc[-1])
            prev = float(close_s.iloc[-2]) if len(close_s) >= 2 else current
            change = ((current / prev) - 1) * 100 if prev > 0 else 0.0

            sma_20 = float(close_s.rolling(20).mean().iloc[-1]) if len(close_s) >= 20 else current
            sma_50 = float(close_s.rolling(50).mean().iloc[-1]) if len(close_s) >= 50 else current
            roc_5 = (current / close_s.iloc[-min(6, len(close_s))] - 1) * 100 if len(close_s) >= 6 else 0.0

            # ── Compute ML features from full OHLCV history ──
            ml_features = compute_ml_features(tdf)

            result[ticker] = {
                "current_price": current,
                "change_pct": round(change, 2),
                "sma_20": round(sma_20, 4),
                "sma_50": round(sma_50, 4),
                "roc_5": round(roc_5, 4),
                # ML feature vector (from compute_ml_features)
                **ml_features,
            }
        except Exception as exc:
            logger.debug("Parse error %s: %s", ticker, exc)
            continue

    return result


def _fetch_daily_sma(tickers: list[str]) -> dict[str, dict]:
    """Fetch daily data for SMA20/SMA50 on longer timeframe."""
    if not tickers:
        return {}
    batch_str = " ".join(tickers)
    result: dict[str, dict] = {}
    try:
        df = yf.download(batch_str, period="3mo", interval="1d",
                          group_by="ticker", progress=False, auto_adjust=True)
    except Exception:
        return result
    if df is None or df.empty:
        return result

    for ticker in tickers:
        try:
            if isinstance(df.columns, pd.MultiIndex) and ticker in df.columns.get_level_values(0):
                tdf = df.xs(ticker, axis=1, level=0).copy()
            else:
                continue
            tdf = _flatten_columns(tdf)
            close = tdf["Close"].dropna()
            if len(close) < 50:
                continue
            sma20 = float(close.rolling(20).mean().iloc[-1])
            sma50 = float(close.rolling(50).mean().iloc[-1])
            result[ticker] = {"daily_sma_20": round(sma20, 4), "daily_sma_50": round(sma50, 4)}
        except Exception:
            continue
    return result
