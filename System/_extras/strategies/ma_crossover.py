"""
均線交叉策略 — 快線上穿慢線時買入。
"""

from __future__ import annotations

from src.strategy.base import Context, Strategy
from src.strategy.factors import moving_average_crossover
from src.strategy.optimizer import signal_weight, OptConstraints


class MaCrossoverStrategy(Strategy):
    """
    均線交叉策略：
    - 快均線 > 慢均線時做多（ma_cross > 0）
    - 信號強度 = ma_cross 值（正值越大越看多）
    - 快線預設 10 日，慢線預設 50 日
    """

    def __init__(self, fast: int = 10, slow: int = 50):
        self.fast = fast
        self.slow = slow

    def name(self) -> str:
        return "ma_crossover"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        signals: dict[str, float] = {}

        for symbol in ctx.universe():
            bars = ctx.bars(symbol, lookback=self.slow + 60)
            if len(bars) < 60:
                continue

            factor = moving_average_crossover(bars, fast=self.fast, slow=self.slow)
            if factor.empty:
                continue

            ma_cross = factor["ma_cross"]
            if ma_cross > 0:
                signals[symbol] = ma_cross

        return signal_weight(
            signals,
            OptConstraints(max_weight=0.10, max_total_weight=0.95, long_only=True),
        )
