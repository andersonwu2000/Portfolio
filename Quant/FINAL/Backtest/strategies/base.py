"""
Strategy base class + Context — the only interface a strategy needs to implement.

Pared down to the minimum interface a strategy needs:
- Removed DataCatalog/FundamentalsProvider methods (revenue strategies load data
  directly from a configurable directory, see revenue_momentum.py)
- _feed / _portfolio typed as Any so the host project can plug its own classes
  (must satisfy duck-typed interfaces noted below)

Required duck-typed interfaces (provide these in the host project):

    DataFeed:
        get_bars(symbol: str) -> pandas.DataFrame    # columns: open/high/low/close/volume, DatetimeIndex
        get_universe() -> list[str]
        get_latest_price(symbol: str) -> Decimal | float

    Portfolio:
        nav: float
        positions: dict[str, Any]
        get_position_weight(symbol: str) -> float
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class Context:
    """
    Strategy data entry point.

    Backtest:  truncate visible data to current_time (no look-ahead).
    Live:      provides real-time data.
    """

    def __init__(
        self,
        feed: Any,
        portfolio: Any,
        current_time: datetime | None = None,
    ):
        self._feed = feed
        self._portfolio = portfolio
        self._current_time = current_time
        self._logger = logging.getLogger("strategy")

    def bars(self, symbol: str, lookback: int = 252) -> pd.DataFrame:
        """Historical OHLCV; auto-truncated to current_time (causal)."""
        df = self._feed.get_bars(symbol)
        if df.empty:
            return df

        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        if hasattr(df.index, "tz") and df.index.tz is not None:
            df.index = df.index.tz_convert("UTC").tz_localize(None)

        if self._current_time is not None:
            df = df[df.index <= pd.Timestamp(self._current_time)]

        if len(df) > lookback:
            df = df.iloc[-lookback:]

        return df

    def universe(self) -> list[str]:
        return self._feed.get_universe()

    def portfolio(self) -> Any:
        return self._portfolio

    def now(self) -> datetime:
        if self._current_time is not None:
            return self._current_time
        return datetime.now(timezone.utc)

    def latest_price(self, symbol: str) -> Decimal:
        return self._feed.get_latest_price(symbol)

    def log(self, msg: str, **kwargs: Any) -> None:
        self._logger.info(msg, **kwargs)


class Strategy(ABC):
    """
    Strategy base class — the only thing a strategy needs to inherit.

    Usage:
        class MyStrategy(Strategy):
            def name(self) -> str:
                return "my_strategy"

            def on_bar(self, ctx: Context) -> dict[str, float]:
                return {"2330.TW": 0.05, "2317.TW": 0.03}

    A strategy only declares "what I want to hold and how much".
    The host system handles diff vs current positions, risk checks, order generation.
    """

    @abstractmethod
    def name(self) -> str:
        """Unique strategy identifier."""

    @abstractmethod
    def on_bar(self, ctx: Context) -> dict[str, float]:
        """
        Return target weights on a new bar.

        Returns:
            {"symbol": weight, ...}
            weight = fraction of NAV; positive = long, negative = short.
            Symbols not in dict implicitly map to weight 0 (close).
        """

    def on_start(self, ctx: Context) -> None:
        """Optional: called when strategy starts."""

    def on_stop(self) -> None:
        """Optional: called when strategy stops."""

    def on_fill(self, symbol: str, side: str, qty: float, price: float) -> None:
        """Optional: fill notification."""

    def __repr__(self) -> str:
        return f"Strategy({self.name()})"
