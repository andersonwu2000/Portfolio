"""新策略測試 — 基本行為驗證。"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

from src.strategy.base import Context


# ---------------------------------------------------------------------------
# 共用工具
# ---------------------------------------------------------------------------

SYMBOLS = ["AAPL", "MSFT", "GOOGL"]


def _make_bars(n: int = 300, base: float = 100.0, seed: int = 42) -> pd.DataFrame:
    """產生合成 OHLCV 數據。"""
    rng = np.random.RandomState(seed)
    returns = rng.normal(0.0005, 0.02, size=n)
    close = base * np.cumprod(1 + returns)
    dates = pd.date_range("2019-01-02", periods=n, freq="B")
    return pd.DataFrame(
        {
            "open": close * (1 + rng.uniform(-0.005, 0.005, n)),
            "high": close * (1 + rng.uniform(0.0, 0.015, n)),
            "low": close * (1 + rng.uniform(-0.015, 0.0, n)),
            "close": close,
            "volume": rng.randint(500_000, 5_000_000, size=n).astype(float),
        },
        index=dates,
    )


def _make_context(
    symbols: list[str] | None = None,
    n: int = 300,
) -> Context:
    """建立帶有合成數據的 Context。"""
    symbols = symbols or SYMBOLS
    bar_data = {s: _make_bars(n=n, seed=hash(s) % 2**31) for s in symbols}

    feed = MagicMock()
    feed.get_universe.return_value = symbols
    feed.get_bars.side_effect = lambda s: bar_data.get(s, pd.DataFrame())
    feed.get_latest_price.return_value = Decimal("100.00")

    portfolio = MagicMock()
    portfolio.nav = Decimal("10000000")

    return Context(feed=feed, portfolio=portfolio, current_time=None)


def _make_empty_context(symbols: list[str] | None = None) -> Context:
    """建立空數據 Context（測試不足數據的情境）。"""
    symbols = symbols or SYMBOLS
    feed = MagicMock()
    feed.get_universe.return_value = symbols
    feed.get_bars.return_value = pd.DataFrame()
    feed.get_latest_price.return_value = Decimal("100.00")

    portfolio = MagicMock()
    portfolio.nav = Decimal("10000000")

    return Context(feed=feed, portfolio=portfolio, current_time=None)


def _make_short_context(symbols: list[str] | None = None, n: int = 5) -> Context:
    """建立只有少量數據的 Context。"""
    return _make_context(symbols=symbols, n=n)


# ---------------------------------------------------------------------------
# RSI Oversold Strategy
# ---------------------------------------------------------------------------

class TestRsiOversoldStrategy:
    def test_returns_dict(self):
        from strategies.rsi_oversold import RsiOversoldStrategy
        strategy = RsiOversoldStrategy()
        assert strategy.name() == "rsi_oversold"
        result = strategy.on_bar(_make_context())
        assert isinstance(result, dict)

    def test_empty_data(self):
        from strategies.rsi_oversold import RsiOversoldStrategy
        strategy = RsiOversoldStrategy()
        result = strategy.on_bar(_make_empty_context())
        assert result == {}

    def test_insufficient_data(self):
        from strategies.rsi_oversold import RsiOversoldStrategy
        strategy = RsiOversoldStrategy()
        result = strategy.on_bar(_make_short_context(n=5))
        assert result == {}

    def test_weights_within_constraints(self):
        from strategies.rsi_oversold import RsiOversoldStrategy
        strategy = RsiOversoldStrategy()
        result = strategy.on_bar(_make_context())
        for w in result.values():
            assert 0 <= w <= 0.10 + 1e-9
        assert sum(result.values()) <= 0.90 + 1e-9


# ---------------------------------------------------------------------------
# MA Crossover Strategy
# ---------------------------------------------------------------------------

class TestMaCrossoverStrategy:
    def test_returns_dict(self):
        from strategies.ma_crossover import MaCrossoverStrategy
        strategy = MaCrossoverStrategy()
        assert strategy.name() == "ma_crossover"
        result = strategy.on_bar(_make_context())
        assert isinstance(result, dict)

    def test_empty_data(self):
        from strategies.ma_crossover import MaCrossoverStrategy
        strategy = MaCrossoverStrategy()
        result = strategy.on_bar(_make_empty_context())
        assert result == {}

    def test_insufficient_data(self):
        from strategies.ma_crossover import MaCrossoverStrategy
        strategy = MaCrossoverStrategy()
        result = strategy.on_bar(_make_short_context(n=10))
        assert result == {}

    def test_weights_within_constraints(self):
        from strategies.ma_crossover import MaCrossoverStrategy
        strategy = MaCrossoverStrategy()
        result = strategy.on_bar(_make_context())
        for w in result.values():
            assert 0 <= w <= 0.10 + 1e-9
        assert sum(result.values()) <= 0.95 + 1e-9


# ---------------------------------------------------------------------------
# Pairs Trading Strategy
# ---------------------------------------------------------------------------

class TestPairsTradingStrategy:
    def test_returns_dict(self):
        from strategies.pairs_trading import PairsTradingStrategy
        strategy = PairsTradingStrategy()
        assert strategy.name() == "pairs_trading"
        result = strategy.on_bar(_make_context())
        assert isinstance(result, dict)

    def test_empty_data(self):
        from strategies.pairs_trading import PairsTradingStrategy
        strategy = PairsTradingStrategy()
        result = strategy.on_bar(_make_empty_context())
        assert result == {}

    def test_insufficient_data(self):
        from strategies.pairs_trading import PairsTradingStrategy
        strategy = PairsTradingStrategy()
        result = strategy.on_bar(_make_short_context(n=5))
        assert result == {}

    def test_needs_at_least_two_symbols(self):
        from strategies.pairs_trading import PairsTradingStrategy
        strategy = PairsTradingStrategy()
        result = strategy.on_bar(_make_context(symbols=["AAPL"]))
        assert result == {}

    def test_weights_within_constraints(self):
        from strategies.pairs_trading import PairsTradingStrategy
        strategy = PairsTradingStrategy()
        result = strategy.on_bar(_make_context())
        for w in result.values():
            assert 0 <= w <= 0.15 + 1e-9
        assert sum(result.values()) <= 0.90 + 1e-9


# ---------------------------------------------------------------------------
# Multi-Factor Strategy
# ---------------------------------------------------------------------------

class TestMultiFactorStrategy:
    def test_returns_dict(self):
        from strategies.multi_factor import MultiFactorStrategy
        strategy = MultiFactorStrategy()
        assert strategy.name() == "multi_factor"
        result = strategy.on_bar(_make_context())
        assert isinstance(result, dict)

    def test_empty_data(self):
        from strategies.multi_factor import MultiFactorStrategy
        strategy = MultiFactorStrategy()
        result = strategy.on_bar(_make_empty_context())
        assert result == {}

    def test_insufficient_data(self):
        from strategies.multi_factor import MultiFactorStrategy
        strategy = MultiFactorStrategy()
        # 252 bars needed, only 50 provided
        result = strategy.on_bar(_make_short_context(n=50))
        assert result == {}

    def test_custom_weights(self):
        from strategies.multi_factor import MultiFactorStrategy
        strategy = MultiFactorStrategy(
            momentum_weight=0.5, value_weight=0.25, quality_weight=0.25
        )
        result = strategy.on_bar(_make_context())
        assert isinstance(result, dict)

    def test_weights_within_constraints(self):
        from strategies.multi_factor import MultiFactorStrategy
        strategy = MultiFactorStrategy()
        result = strategy.on_bar(_make_context())
        for w in result.values():
            assert 0 <= w <= 0.08 + 1e-9
        assert sum(result.values()) <= 0.90 + 1e-9


# ---------------------------------------------------------------------------
# Sector Rotation Strategy
# ---------------------------------------------------------------------------

class TestSectorRotationStrategy:
    def test_returns_dict(self):
        from strategies.sector_rotation import SectorRotationStrategy
        strategy = SectorRotationStrategy()
        assert strategy.name() == "sector_rotation"
        result = strategy.on_bar(_make_context())
        assert isinstance(result, dict)

    def test_empty_data(self):
        from strategies.sector_rotation import SectorRotationStrategy
        strategy = SectorRotationStrategy()
        result = strategy.on_bar(_make_empty_context())
        assert result == {}

    def test_insufficient_data(self):
        from strategies.sector_rotation import SectorRotationStrategy
        strategy = SectorRotationStrategy()
        result = strategy.on_bar(_make_short_context(n=10))
        assert result == {}

    def test_top_n_limit(self):
        from strategies.sector_rotation import SectorRotationStrategy
        strategy = SectorRotationStrategy(top_n=2)
        result = strategy.on_bar(_make_context())
        assert len(result) <= 2

    def test_weights_within_constraints(self):
        from strategies.sector_rotation import SectorRotationStrategy
        strategy = SectorRotationStrategy()
        result = strategy.on_bar(_make_context())
        for w in result.values():
            assert 0 <= w <= 0.25 + 1e-9
        assert sum(result.values()) <= 0.95 + 1e-9
