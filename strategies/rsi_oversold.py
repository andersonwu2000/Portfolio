"""
RSI 超賣策略 — 買入 RSI 低於閾值的股票，賣出 RSI 高於閾值的股票。
"""

from __future__ import annotations

from src.strategy.base import Context, Strategy
from src.strategy.factors import rsi
from src.strategy.optimizer import signal_weight, OptConstraints


class RsiOversoldStrategy(Strategy):
    """
    RSI 超賣策略：
    - 買入 RSI < 30 的股票（超賣區間）
    - RSI > 70 時不持有（超買區間）
    - 信號強度 = 100 - RSI（RSI 越低，信號越強）
    """

    def __init__(self, oversold: float = 30.0, overbought: float = 70.0, period: int = 14):
        self.oversold = oversold
        self.overbought = overbought
        self.period = period

    def name(self) -> str:
        return "rsi_oversold"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        signals: dict[str, float] = {}

        for symbol in ctx.universe():
            bars = ctx.bars(symbol, lookback=20 + self.period)
            if len(bars) < 20:
                continue

            factor = rsi(bars, period=self.period)
            if factor.empty:
                continue

            rsi_value = factor["rsi"]
            if rsi_value < self.oversold:
                # 信號 = 100 - RSI，RSI 越低信號越強
                signals[symbol] = 100.0 - rsi_value

        return signal_weight(
            signals,
            OptConstraints(max_weight=0.10, max_total_weight=0.90, long_only=True),
        )
