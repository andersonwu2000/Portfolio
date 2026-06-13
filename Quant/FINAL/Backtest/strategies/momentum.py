"""
12-1 Price Momentum Strategy.

Classic Carhart / Jegadeesh-Titman momentum:
- Rank stocks by return from t-252 days to t-21 days (skip recent 1 month)
- Pick top N by momentum, signal-weighted
- Monthly rebalance

This is a self-contained copy with the momentum factor inlined.
"""

from __future__ import annotations

import pandas as pd

from .base import Context, Strategy
from .optimizer import OptConstraints, signal_weight


def momentum_12_1_factor(prices: pd.DataFrame, lookback: int = 252, skip: int = 21) -> float | None:
    """Return the 12-1 momentum value, or None if insufficient history."""
    close = prices["close"]
    if len(close) < lookback:
        return None
    return float(close.iloc[-skip] / close.iloc[-lookback] - 1)


class MomentumStrategy(Strategy):
    """
    Classic 12-1 price momentum.
    - Buy top N by trailing 12-month return (skip most recent month)
    - Signal weighting; per-symbol cap 10%, total cap 95%
    - Rebalance externally driven (weekly or monthly)
    """

    def __init__(self, lookback: int = 252, skip: int = 21, max_holdings: int = 10):
        self.lookback = lookback
        self.skip = skip
        self.max_holdings = max_holdings

    def name(self) -> str:
        return "momentum_12_1"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        signals: dict[str, float] = {}

        for symbol in ctx.universe():
            bars = ctx.bars(symbol, lookback=self.lookback + self.skip)
            if len(bars) < self.lookback:
                continue
            v = momentum_12_1_factor(bars, lookback=self.lookback, skip=self.skip)
            if v is not None and v > 0:
                signals[symbol] = v

        if len(signals) > self.max_holdings:
            sorted_signals = sorted(signals.items(), key=lambda x: x[1], reverse=True)
            signals = dict(sorted_signals[: self.max_holdings])

        return signal_weight(
            signals,
            OptConstraints(max_weight=0.10, max_total_weight=0.95),
        )
