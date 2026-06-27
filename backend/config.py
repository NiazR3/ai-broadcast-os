"""
QuantAI Configuration — all settings from environment variables.
No hardcoded secrets. Falls back to safe defaults for local dev.
"""

import os
from pathlib import Path
from typing import Optional

# ── Load .env from project root (if present) ──
try:
    from dotenv import load_dotenv
    _dotenv_path = Path(__file__).parent / ".env"
    if _dotenv_path.exists():
        load_dotenv(_dotenv_path)
except ImportError:
    pass

# ── Paths ──
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / ".." / "data_cache"

# ── Supabase ──
SUPABASE_URL: Optional[str] = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY: Optional[str] = os.environ.get("SUPABASE_SERVICE_KEY")
SUPABASE_ANON_KEY: Optional[str] = os.environ.get("SUPABASE_ANON_KEY")

# ── Finnhub ──
FINNHUB_API_KEY: str = os.environ.get("FINNHUB_API_KEY", "")

# ── Stripe ──
STRIPE_SECRET_KEY: Optional[str] = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET: Optional[str] = os.environ.get("STRIPE_WEBHOOK_SECRET")
STRIPE_PRICE_PRO_MONTHLY: Optional[str] = os.environ.get("STRIPE_PRICE_PRO_MONTHLY")

# ── Deploy ──
ENV: str = os.environ.get("ENV", "development")
ALLOWED_ORIGINS: list[str] = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:8000",
).split(",")

# ── Rate Limits ──
FREE_RATE_LIMIT: int = int(os.environ.get("FREE_RATE_LIMIT", "30"))
PRO_RATE_LIMIT: int = int(os.environ.get("PRO_RATE_LIMIT", "300"))

# ── Timing ──
BATCH_INTERVAL_SEC: int = int(os.environ.get("BATCH_INTERVAL_SEC", "10"))
SMA_REFRESH_INTERVAL: int = int(os.environ.get("SMA_REFRESH_INTERVAL", "1800"))
ACCURACY_EVAL_INTERVAL: int = int(os.environ.get("ACCURACY_EVAL_INTERVAL", "900"))
DB_CLEANUP_AGE_HOURS: int = int(os.environ.get("DB_CLEANUP_AGE_HOURS", "48"))
FINNHUB_CACHE_TTL: int = int(os.environ.get("FINNHUB_CACHE_TTL", "10"))

# ── Batching ──
BATCH_SIZE: int = int(os.environ.get("BATCH_SIZE", "15"))
YFINANCE_TIMEOUT: int = int(os.environ.get("YFINANCE_TIMEOUT", "20"))

# ── ML Training ──
TRAINING_INTERVAL: str = os.environ.get("TRAINING_INTERVAL", "15m")      # "15m", "1h", or "1d"
TRAINING_LABEL_OFFSET: int = int(os.environ.get("TRAINING_LABEL_OFFSET", "24"))  # default bars ahead
LABEL_OFFSET_STOCK: int = int(os.environ.get("LABEL_OFFSET_STOCK", "24"))        # stock (24 bars = 6h)
LABEL_OFFSET_CRYPTO: int = int(os.environ.get("LABEL_OFFSET_CRYPTO", "24"))      # crypto (24h market)
LABEL_OFFSET_FOREX: int = int(os.environ.get("LABEL_OFFSET_FOREX", "48"))        # forex (slower, 48 bars = 12h)
TRAINING_DATA_PERIOD: str = os.environ.get("TRAINING_DATA_PERIOD", "60d")        # yfinance period
TRAINING_MIN_SAMPLES: int = int(os.environ.get("TRAINING_MIN_SAMPLES", "2000"))
AUTO_RETRAIN_HOURS: int = int(os.environ.get("AUTO_RETRAIN_HOURS", "168"))       # 7 days
CALIBRATE_PROBABILITIES: bool = os.environ.get("CALIBRATE_PROBABILITIES", "true").lower() == "true"
N_ESTIMATORS: int = int(os.environ.get("N_ESTIMATORS", "300"))
# Set N_ESTIMATORS=0 to trigger per-class hyperparameter search
# (GridSearchCV with TimeSeriesSplit — slower but finds optimal params)
PREDICTION_EVAL_DELAY_MINUTES: int = int(os.environ.get(
    "PREDICTION_EVAL_DELAY_MINUTES",
    str(TRAINING_LABEL_OFFSET * 15),  # 24 bars x 15 min = 6 hours default
))
