"""
In-memory market data cache — thread-safe, zero-I/O access.
All API endpoints and WebSocket broadcasts read from this cache.
The background producer loops write to it.
"""

import time
import threading
from typing import Optional

_cache_lock = threading.Lock()

# ── Per-class lock sharding (June 2026) ──
# Reduces contention: API reads for stocks don't block crypto writes
_CLASS_LOCKS: dict[str, threading.Lock] = {
    cls: threading.Lock() for cls in ["stock", "crypto", "forex"]
}


def _class_lock(ticker: str) -> threading.Lock:
    """Return the appropriate lock for a ticker's asset class."""
    cls = TICKER_CLASS.get(ticker, "stock")
    return _CLASS_LOCKS.get(cls, _cache_lock)
SHARED_MARKET_CACHE: dict[str, dict] = {}

# ── Ticker registry ──

STOCKS = [
    "AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","NFLX","ADBE","CRM",
    "ORCL","IBM","CSCO","AMD","QCOM","TXN","AVGO","MU","INTC","PLTR",
    "JPM","BAC","WFC","GS","MS","V","MA","AXP","BLK","C",
    "SCHW","USB","PNC","TFC","COF","KEY","MET","AIG","PRU","FITB",
    "JNJ","PFE","MRK","ABBV","UNH","TMO","LLY","BMY","CVS","AMGN",
    "VRTX","GILD","REGN","ISRG","SYK","BDX","ZTS","DHR","MDT","ABT",
    "CAT","BA","GE","HON","MMM","UPS","RTX","LMT","GD","NOC",
    "DE","EMR","CSX","UNP","FDX","ETN","ITW","CMI","PH","ROK",
    "WMT","HD","COST","MCD","SBUX","NKE","LOW","TGT","TJX","ROST",
    "LULU","GM","F","BBY","DG","DLTR","KR",
    "KO","PEP","PG","CL","KMB","MO","PM","MDLZ","KHC",
    "SYY","ADM","CPB","GIS","HRL","MNST","TSN","CAG",
    "SPY","QQQ","VOO","IWM","DIA","XLF","XLK","XLV","XLE","XLI",
    "ARKK","TLT","IEF","GLD","SLV","XBI","IBB","KRE","SMH","IVV",
    "VTI","BND","EEM","HYG","LQD",
    "ASML.AS","SAP.DE","MC.PA","TTE.PA","0700.HK","7203.T",
]

CRYPTO = [
    "BTC-USD","ETH-USD","SOL-USD","DOGE-USD","ADA-USD","DOT-USD",
    "LINK-USD","AVAX-USD","AAVE-USD","UNI7083-USD",
]

FOREX = [
    "EURUSD=X","GBPUSD=X","USDJPY=X","USDCAD=X","AUDUSD=X","USDCHF=X",
    "NZDUSD=X","EURJPY=X","GBPJPY=X","EURAUD=X",
]

ALL_TICKERS = STOCKS + CRYPTO + FOREX

TICKER_CLASS: dict[str, str] = {t: "stock" for t in STOCKS}
TICKER_CLASS.update({t: "crypto" for t in CRYPTO})
TICKER_CLASS.update({t: "forex" for t in FOREX})

TICKER_LABEL: dict[str, str] = {
    "SPY": "S&P 500", "QQQ": "Nasdaq 100", "VOO": "Vanguard 500",
    "IWM": "Russell 2000", "DIA": "Dow 30", "XLF": "Financials",
    "XLK": "Technology", "XLV": "Healthcare", "XLE": "Energy",
    "XLI": "Industrials", "ARKK": "ARK Innovation", "TLT": "20+ Yr Treasury",
    "IEF": "7-10 Yr Treasury", "GLD": "Gold", "SLV": "Silver",
    "XBI": "Biotech", "IBB": "Nasdaq Biotech", "KRE": "Regional Banks",
    "SMH": "Semiconductors", "IVV": "iShares Core S&P",
    "VTI": "Total Market", "BND": "Total Bond",
    "EEM": "Emerging Mkts ETF", "HYG": "High Yield Bond",
    "LQD": "Inv Grade Bond",
    "0700.HK": "Tencent", "7203.T": "Toyota",
    "MC.PA": "LVMH", "TTE.PA": "TotalEnergies",
    "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum",
    "SOL-USD": "Solana", "DOGE-USD": "Dogecoin",
    "ADA-USD": "Cardano", "DOT-USD": "Polkadot",
    "LINK-USD": "Chainlink", "AVAX-USD": "Avalanche",
    "AAVE-USD": "Aave", "UNI7083-USD": "Uniswap",
    "EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD",
    "USDJPY=X": "USD/JPY", "USDCAD=X": "USD/CAD",
    "AUDUSD=X": "AUD/USD", "USDCHF=X": "USD/CHF",
    "NZDUSD=X": "NZD/USD", "EURJPY=X": "EUR/JPY",
    "GBPJPY=X": "GBP/JPY", "EURAUD=X": "EUR/AUD",
}

# Fill missing labels
for t in ALL_TICKERS:
    TICKER_LABEL.setdefault(t, t)


# ── Cache operations (thread-safe, per-class sharded) ──

def cache_set(ticker: str, data: dict):
    with _class_lock(ticker):
        SHARED_MARKET_CACHE[ticker] = data

def cache_get(ticker: str) -> Optional[dict]:
    with _class_lock(ticker):
        return SHARED_MARKET_CACHE.get(ticker)

def cache_get_field(ticker: str, field: str, default=None):
    entry = cache_get(ticker)
    if entry is None:
        return default
    return entry.get(field, default)

def cache_snapshot() -> dict[str, dict]:
    with _cache_lock:
        return {k: dict(v) for k, v in SHARED_MARKET_CACHE.items()}

def cache_update(ticker: str, **kwargs):
    with _class_lock(ticker):
        entry = SHARED_MARKET_CACHE.get(ticker)
        if entry is None:
            SHARED_MARKET_CACHE[ticker] = {}
            entry = SHARED_MARKET_CACHE[ticker]
        entry.update(kwargs)
        entry["last_updated_ts"] = time.time()

def cache_init(ticker: str, asset_class: str):
    with _class_lock(ticker):
        if ticker not in SHARED_MARKET_CACHE:
            SHARED_MARKET_CACHE[ticker] = {
                "ticker": ticker,
                "label": TICKER_LABEL.get(ticker, ticker),
                "asset_class": asset_class,
                "current_price": 0.0,
                "change_pct": 0.0,
                "daily_sma_20": None,
                "daily_sma_50": None,
                "prob_up": 0.50,
                "signal": "HOLD",
                "sentiment": 0.0,
                "sentiment_source": "synthetic",
                "ml_active": False,
                "model_class": "heuristic",
                "confidence": 0.0,
                "accuracy_24h": 0.0,
                "accuracy_count": 0,
                "last_updated": "",
                "data_age_s": 0,
                "error": None,
            }

# ── Batch helpers ──

def make_batches(items: list, size: int) -> list[list]:
    return [items[i:i+size] for i in range(0, len(items), size)]

BATCHES = make_batches(ALL_TICKERS, 15)


# ── Seed all entries ──

for tkr in ALL_TICKERS:
    cache_init(tkr, TICKER_CLASS[tkr])
