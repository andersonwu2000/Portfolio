"""
永豐金 Shioaji 數據源 — 台股 K 棒、tick、快照。

Shioaji 提供 2020-03-02 起的 1 分鐘 K 棒和逐筆 tick。
Shioaji SDK 為條件導入：未安裝時仍可載入模組（用於測試），
但實際呼叫 API 會拋出 ImportError。
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

import pandas as pd

from src.data.feed import DataFeed

logger = logging.getLogger(__name__)

# Shioaji snapshots API limit
_SNAPSHOT_BATCH_SIZE = 500


def _import_shioaji() -> Any:
    """Conditionally import shioaji; raise ImportError with clear message."""
    try:
        import shioaji

        return shioaji
    except ImportError:
        raise ImportError(
            "shioaji is not installed. Install it with: pip install shioaji"
        )


class ShioajiFeed(DataFeed):
    """
    Shioaji 台股資料源。

    支援歷史 K 棒 (1 分鐘)、逐筆 tick、即時快照。
    需要已連線的 Shioaji API instance 或自動建立連線。
    """

    def __init__(
        self,
        api: Any | None = None,
        universe: list[str] | None = None,
    ):
        self._api = api
        self._universe = universe or []

    @property
    def api(self) -> Any:
        """Return connected API instance; raise if not set."""
        if self._api is None:
            raise ConnectionError(
                "Shioaji API not connected. Pass a connected api instance to ShioajiFeed."
            )
        return self._api

    def _resolve_contract(self, symbol: str) -> Any:
        """Resolve symbol to Shioaji contract object."""
        contract = self.api.Contracts.Stocks.get(symbol, None)
        if contract is None:
            # Try futures
            contract = self.api.Contracts.Futures.get(symbol, None)
        if contract is None:
            raise ValueError(f"Cannot find contract for symbol: {symbol}")
        return contract

    def get_bars(
        self,
        symbol: str,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        freq: str = "1d",
    ) -> pd.DataFrame:
        """
        取得 K 線數據。

        Uses Shioaji api.kbars() for 1-min bars.
        Kbars response has: ts (timestamps), Open, High, Low, Close, Volume.

        Returns:
            DataFrame[open, high, low, close, volume] with tz-naive DatetimeIndex.
        """
        empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        contract = self._resolve_contract(symbol)

        # Format dates
        start_str = _format_date(start) if start else "2020-03-02"
        end_str = _format_date(end) if end else _format_date(datetime.now())

        kbars = self.api.kbars(contract, start=start_str, end=end_str)

        if kbars is None or not hasattr(kbars, "ts") or len(kbars.ts) == 0:
            return empty

        # Build DataFrame from kbars attributes
        df = pd.DataFrame({
            "open": kbars.Open,
            "high": kbars.High,
            "low": kbars.Low,
            "close": kbars.Close,
            "volume": kbars.Volume,
        })

        # Convert timestamps (nanosecond int) to DatetimeIndex
        df.index = pd.to_datetime(kbars.ts)

        # Ensure tz-naive (strip timezone if present)
        idx = df.index
        if isinstance(idx, pd.DatetimeIndex) and idx.tz is not None:
            df.index = idx.tz_convert("UTC").tz_localize(None)

        df = df.sort_index()

        # If daily freq requested, resample 1-min bars to daily
        if freq == "1d" and not df.empty:
            df = df.resample("1D").agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }).dropna(subset=["close"])

        return df

    def get_latest_price(self, symbol: str) -> Decimal:
        """取得最新價格 (via snapshot)。"""
        contract = self._resolve_contract(symbol)
        snapshots = self.api.snapshots([contract])

        if not snapshots or len(snapshots) == 0:
            return Decimal("0")

        snap = snapshots[0]
        return Decimal(str(snap.close))

    def get_universe(self) -> list[str]:
        """取得可交易標的清單。

        If universe was provided at init, return that.
        Otherwise iterate api.Contracts.Stocks to list all stock codes.
        """
        if self._universe:
            return list(self._universe)

        # Ensure API is connected (raises ConnectionError if not)
        _ = self.api

        codes: list[str] = []
        try:
            for exchange in self.api.Contracts.Stocks:
                for contract in exchange:
                    codes.append(contract.code)
        except ConnectionError:
            raise
        except Exception:
            logger.warning("Failed to iterate Shioaji stock contracts", exc_info=True)

        return codes

    def get_snapshot(self, symbols: list[str]) -> pd.DataFrame:
        """
        批量快照 — 取得多檔標的的即時報價。

        Shioaji snapshots API 限制每次最多 500 檔。
        自動分批呼叫。

        Returns:
            DataFrame with columns: [symbol, close, volume, change_price,
            change_rate, buy_price, sell_price, total_volume]
        """
        contracts = []
        for sym in symbols:
            try:
                contracts.append(self._resolve_contract(sym))
            except ValueError:
                logger.warning("Skipping unknown symbol: %s", sym)

        if not contracts:
            return pd.DataFrame()

        all_snaps: list[dict[str, Any]] = []

        # Batch into groups of _SNAPSHOT_BATCH_SIZE
        for i in range(0, len(contracts), _SNAPSHOT_BATCH_SIZE):
            batch = contracts[i : i + _SNAPSHOT_BATCH_SIZE]
            snapshots = self.api.snapshots(batch)
            if snapshots:
                for snap in snapshots:
                    all_snaps.append({
                        "symbol": snap.code,
                        "close": float(snap.close),
                        "volume": getattr(snap, "volume", 0),
                        "change_price": getattr(snap, "change_price", 0.0),
                        "change_rate": getattr(snap, "change_rate", 0.0),
                        "buy_price": getattr(snap, "buy_price", 0.0),
                        "sell_price": getattr(snap, "sell_price", 0.0),
                        "total_volume": getattr(snap, "total_volume", 0),
                    })

        if not all_snaps:
            return pd.DataFrame()

        return pd.DataFrame(all_snaps)

    def get_ticks(self, symbol: str, date: datetime | str) -> pd.DataFrame:
        """
        取得逐筆 tick 數據。

        Args:
            symbol: Stock symbol (e.g. "2330")
            date: Trading date

        Returns:
            DataFrame[price, volume, bid_price, ask_price] with tz-naive DatetimeIndex.
        """
        empty = pd.DataFrame(columns=["price", "volume", "bid_price", "ask_price"])

        contract = self._resolve_contract(symbol)
        date_str = _format_date(date)
        ticks = self.api.ticks(contract, date=date_str)

        if ticks is None or not hasattr(ticks, "ts") or len(ticks.ts) == 0:
            return empty

        df = pd.DataFrame({
            "price": ticks.close,
            "volume": ticks.volume,
            "bid_price": ticks.bid_price,
            "ask_price": ticks.ask_price,
        })

        df.index = pd.to_datetime(ticks.ts)

        # Ensure tz-naive
        idx = df.index
        if isinstance(idx, pd.DatetimeIndex) and idx.tz is not None:
            df.index = idx.tz_convert("UTC").tz_localize(None)

        df = df.sort_index()
        return df


def _format_date(dt: datetime | str) -> str:
    """Format a date to 'YYYY-MM-DD' string."""
    if isinstance(dt, str):
        return dt[:10]  # Handle ISO format strings
    return dt.strftime("%Y-%m-%d")
