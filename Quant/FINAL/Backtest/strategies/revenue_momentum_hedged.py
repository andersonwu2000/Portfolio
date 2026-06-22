"""
Revenue Momentum + composite bear-detector — production strategy.

Wraps RevenueMomentumStrategy with a regime-aware position scaler:
  Bear:      market < MA200*0.95 AND MA50 < MA200,  OR  20d vol > 25%
  Sideways:  market < MA200,                         OR  20d vol > 60d vol * 1.5
  Bull:      otherwise -> 100% exposure

Validated in experiment #10 — OOS 2025 H1 improved from -16% to -5.4%.
StrategyValidator: 10/13 passed.

NOTE: 2025 OOS later hit -22.83% in production paper trading — the regime
detector flagged bear during the early-2025 vol spike and missed the rally.
Open issue: bear/sideways both scale to 30%, very binary.
"""

from __future__ import annotations


import numpy as np

from .base import Context, Strategy
from .registry import resolve_strategy


class RevenueMomentumHedgedStrategy(Strategy):
    """Revenue momentum + composite bear detector with position scaling."""

    def __init__(
        self,
        market_proxy: str = "0050.TW",
        bear_scale: float = 0.30,
        sideways_scale: float = 0.30,
        ma_threshold: float = 0.95,
        vol_threshold: float = 0.25,
        vol_spike_ratio: float = 1.5,
        **inner_kwargs: object,
    ):
        self._inner = resolve_strategy(
            "revenue_momentum",
            dict(inner_kwargs) if inner_kwargs else None,
        )
        self.market_proxy = market_proxy
        self.bear_scale = bear_scale
        self.sideways_scale = sideways_scale
        self.ma_threshold = ma_threshold
        self.vol_threshold = vol_threshold
        self.vol_spike_ratio = vol_spike_ratio
        self._last_regime: str = "bull"   # diagnostic trace (read by analyze_churn_source.py)

    def name(self) -> str:
        return "revenue_momentum_hedged"

    def _detect_regime(self, ctx: Context) -> str:
        """Composite detector: MA200 trend OR vol spike."""
        try:
            bars = ctx.bars(self.market_proxy, lookback=252)
            if len(bars) < 200:
                return "bull"
            close = bars["close"]
            returns = close.pct_change().dropna()
        except Exception:
            return "bull"

        current = float(close.iloc[-1])
        ma200 = float(close.iloc[-200:].mean())
        ma50 = float(close.iloc[-50:].mean())
        vol_20d = float(returns.iloc[-20:].std() * np.sqrt(252)) if len(returns) >= 20 else 0
        vol_60d = float(returns.iloc[-60:].std() * np.sqrt(252)) if len(returns) >= 60 else vol_20d

        ma_bear = current < ma200 * self.ma_threshold and ma50 < ma200
        vol_bear = vol_20d > self.vol_threshold

        if ma_bear or vol_bear:
            return "bear"

        ma_sideways = current < ma200
        vol_sideways = vol_20d > vol_60d * self.vol_spike_ratio

        if ma_sideways or vol_sideways:
            return "sideways"

        return "bull"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        weights = self._inner.on_bar(ctx)
        if not weights:
            return weights

        regime = self._detect_regime(ctx)
        self._last_regime = regime

        if regime == "bear":
            return {k: v * self.bear_scale for k, v in weights.items()}
        elif regime == "sideways":
            return {k: v * self.sideways_scale for k, v in weights.items()}
        return weights
