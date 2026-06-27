"""Data models / types for the QuantAI backend."""

from enum import Enum
from typing import Optional


class AssetClass(str, Enum):
    stock = "stock"
    crypto = "crypto"
    forex = "forex"


class Signal(str, Enum):
    STRONG_BUY = "STRONG BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG SELL"


SIGNAL_THRESHOLDS = [
    (0.80, "STRONG BUY"),
    (0.60, "BUY"),
    (0.40, "HOLD"),
    (0.20, "SELL"),
    (0.00, "STRONG SELL"),
]
