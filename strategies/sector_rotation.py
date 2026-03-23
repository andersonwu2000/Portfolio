"""
板塊輪動策略 — 買入短期動量最強的 Top N 標的，風險平價配置。
"""

from __future__ import annotations

from src.strategy.base import Context, Strategy
from src.strategy.factors import volatility
from src.strategy.optimizer import risk_parity, OptConstraints


class SectorRotationStrategy(Strategy):
    """
    板塊輪動策略：
    - 使用 60 日短期動量排名（無跳過期間）
    - 集中持倉：只買入前 N 名
    - 風險平價配置：按波動率倒數分配權重
    """

    def __init__(self, lookback: int = 60, top_n: int = 5):
        self.lookback = lookback
        self.top_n = top_n

    def name(self) -> str:
        return "sector_rotation"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        momentum_scores: dict[str, float] = {}
        vol_data: dict[str, float] = {}

        for symbol in ctx.universe():
            bars = ctx.bars(symbol, lookback=self.lookback + 30)
            if len(bars) < 80:
                continue

            close = bars["close"]
            # 短期動量：lookback 日報酬率，無跳過期間
            ret = close.iloc[-1] / close.iloc[-self.lookback] - 1
            momentum_scores[symbol] = float(ret)

            # 波動率
            vol = volatility(bars, lookback=self.lookback)
            if not vol.empty and vol["volatility"] > 0:
                vol_data[symbol] = vol["volatility"]

        if not momentum_scores:
            return {}

        # 只取前 N 強（正動量）
        sorted_scores = sorted(momentum_scores.items(), key=lambda x: x[1], reverse=True)
        top_signals = {}
        for symbol, score in sorted_scores[: self.top_n]:
            if score > 0:
                top_signals[symbol] = score

        if not top_signals:
            return {}

        # 確保所有 top 標的都有波動率數據
        valid_vols = {s: vol_data[s] for s in top_signals if s in vol_data}
        if not valid_vols:
            return {}

        return risk_parity(
            top_signals,
            valid_vols,
            OptConstraints(max_weight=0.25, max_total_weight=0.95),
        )
