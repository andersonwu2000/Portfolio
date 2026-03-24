"""Tests for ShioajiFeed — 使用 mock SDK 的完整單元測試。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.data.sources.shioaji_feed import ShioajiFeed


# ── Mock Helpers ──────────────────────────────────────────


def _make_mock_contract(code: str = "2330") -> MagicMock:
    """Create a mock Shioaji contract."""
    contract = MagicMock()
    contract.code = code
    return contract


def _make_mock_kbars(
    n: int = 5,
    base_ts: int = 1700000000000000000,
    interval_ns: int = 60_000_000_000,
) -> MagicMock:
    """Create mock kbars response with n bars."""
    kbars = MagicMock()
    kbars.ts = [base_ts + i * interval_ns for i in range(n)]
    kbars.Open = [100.0 + i for i in range(n)]
    kbars.High = [101.0 + i for i in range(n)]
    kbars.Low = [99.0 + i for i in range(n)]
    kbars.Close = [100.5 + i for i in range(n)]
    kbars.Volume = [1000 * (i + 1) for i in range(n)]
    return kbars


def _make_mock_snapshot(code: str = "2330", close: float = 600.0) -> MagicMock:
    """Create a mock snapshot object."""
    snap = MagicMock()
    snap.code = code
    snap.close = close
    snap.volume = 100
    snap.change_price = 5.0
    snap.change_rate = 0.84
    snap.buy_price = 599.0
    snap.sell_price = 601.0
    snap.total_volume = 50000
    return snap


def _make_mock_ticks(n: int = 3) -> MagicMock:
    """Create mock ticks response."""
    ticks = MagicMock()
    base_ts = 1700000000000000000
    ticks.ts = [base_ts + i * 1_000_000_000 for i in range(n)]
    ticks.close = [600.0 + i * 0.5 for i in range(n)]
    ticks.volume = [10, 20, 30][:n]
    ticks.bid_price = [599.0 + i * 0.5 for i in range(n)]
    ticks.ask_price = [601.0 + i * 0.5 for i in range(n)]
    return ticks


def _make_mock_api() -> MagicMock:
    """Build a mock Shioaji API with standard contracts."""
    api = MagicMock()

    contract_2330 = _make_mock_contract("2330")
    contract_2317 = _make_mock_contract("2317")

    def stocks_get(symbol: str, default: object = None) -> object:
        mapping = {"2330": contract_2330, "2317": contract_2317}
        return mapping.get(symbol, default)

    api.Contracts.Stocks.get = MagicMock(side_effect=stocks_get)
    api.Contracts.Futures.get = MagicMock(return_value=None)

    return api


# ── Tests: Initialization ────────────────────────────────


class TestShioajiFeedInit:
    def test_init_without_api(self) -> None:
        feed = ShioajiFeed()
        assert feed._api is None
        assert feed._universe == []

    def test_init_with_api(self) -> None:
        api = _make_mock_api()
        feed = ShioajiFeed(api=api)
        assert feed._api is api

    def test_init_with_universe(self) -> None:
        feed = ShioajiFeed(universe=["2330", "2317"])
        assert feed._universe == ["2330", "2317"]


# ── Tests: No API connected ──────────────────────────────


class TestShioajiFeedNoApi:
    def test_get_bars_raises_connection_error(self) -> None:
        feed = ShioajiFeed()
        with pytest.raises(ConnectionError, match="not connected"):
            feed.get_bars("2330")

    def test_get_latest_price_raises_connection_error(self) -> None:
        feed = ShioajiFeed()
        with pytest.raises(ConnectionError, match="not connected"):
            feed.get_latest_price("2330")

    def test_get_universe_with_preset(self) -> None:
        """If universe was provided at init, no API needed."""
        feed = ShioajiFeed(universe=["2330", "2317"])
        assert feed.get_universe() == ["2330", "2317"]

    def test_get_universe_without_preset_raises(self) -> None:
        feed = ShioajiFeed()
        with pytest.raises(ConnectionError, match="not connected"):
            feed.get_universe()


# ── Tests: get_bars ───────────────────────────────────────


class TestGetBars:
    def test_basic_kbars(self) -> None:
        api = _make_mock_api()
        kbars = _make_mock_kbars(n=5)
        api.kbars.return_value = kbars
        feed = ShioajiFeed(api=api)

        df = feed.get_bars("2330", start="2023-01-01", end="2023-12-31", freq="1min")

        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert len(df) == 5
        assert df.index.tz is None  # tz-naive

    def test_kbars_with_datetime_params(self) -> None:
        api = _make_mock_api()
        api.kbars.return_value = _make_mock_kbars(n=3)
        feed = ShioajiFeed(api=api)

        start = datetime(2023, 6, 1)
        end = datetime(2023, 12, 31)
        df = feed.get_bars("2330", start=start, end=end, freq="1min")

        assert len(df) == 3
        api.kbars.assert_called_once()

    def test_empty_kbars(self) -> None:
        api = _make_mock_api()
        empty_kbars = MagicMock()
        empty_kbars.ts = []
        api.kbars.return_value = empty_kbars
        feed = ShioajiFeed(api=api)

        df = feed.get_bars("2330", freq="1min")
        assert df.empty
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]

    def test_none_kbars(self) -> None:
        api = _make_mock_api()
        api.kbars.return_value = None
        feed = ShioajiFeed(api=api)

        df = feed.get_bars("2330", freq="1min")
        assert df.empty

    def test_daily_resampling(self) -> None:
        """Daily freq should resample 1-min bars into daily bars."""
        api = _make_mock_api()
        # Create kbars with timestamps spanning 2 days
        kbars = MagicMock()
        day1 = pd.Timestamp("2023-06-01 09:00").value
        day2 = pd.Timestamp("2023-06-02 09:00").value
        kbars.ts = [day1, day1 + 60_000_000_000, day2, day2 + 60_000_000_000]
        kbars.Open = [100.0, 101.0, 102.0, 103.0]
        kbars.High = [105.0, 104.0, 108.0, 107.0]
        kbars.Low = [99.0, 100.0, 101.0, 102.0]
        kbars.Close = [101.0, 102.0, 107.0, 106.0]
        kbars.Volume = [1000, 2000, 3000, 4000]
        api.kbars.return_value = kbars
        feed = ShioajiFeed(api=api)

        df = feed.get_bars("2330", freq="1d")

        assert len(df) == 2  # 2 trading days
        # First day: open=first(100), high=max(105), low=min(99), close=last(102)
        assert df.iloc[0]["open"] == 100.0
        assert df.iloc[0]["high"] == 105.0
        assert df.iloc[0]["low"] == 99.0
        assert df.iloc[0]["close"] == 102.0
        assert df.iloc[0]["volume"] == 3000  # sum(1000, 2000)

    def test_unknown_symbol_raises(self) -> None:
        api = _make_mock_api()
        feed = ShioajiFeed(api=api)

        with pytest.raises(ValueError, match="Cannot find contract"):
            feed.get_bars("9999")

    def test_tz_naive_index(self) -> None:
        """Verify timezone info is stripped from DatetimeIndex."""
        api = _make_mock_api()
        kbars = _make_mock_kbars(n=2)
        # Use timezone-aware timestamps (Asia/Taipei)
        aware_ts = pd.to_datetime(kbars.ts).tz_localize("Asia/Taipei")
        kbars.ts = [t.value for t in aware_ts]
        api.kbars.return_value = kbars
        feed = ShioajiFeed(api=api)

        df = feed.get_bars("2330", freq="1min")
        assert df.index.tz is None


# ── Tests: get_latest_price ───────────────────────────────


class TestGetLatestPrice:
    def test_basic_snapshot(self) -> None:
        api = _make_mock_api()
        snap = _make_mock_snapshot(close=595.0)
        api.snapshots.return_value = [snap]
        feed = ShioajiFeed(api=api)

        price = feed.get_latest_price("2330")
        assert price == Decimal("595.0")

    def test_empty_snapshot(self) -> None:
        api = _make_mock_api()
        api.snapshots.return_value = []
        feed = ShioajiFeed(api=api)

        price = feed.get_latest_price("2330")
        assert price == Decimal("0")

    def test_none_snapshot(self) -> None:
        api = _make_mock_api()
        api.snapshots.return_value = None
        feed = ShioajiFeed(api=api)

        price = feed.get_latest_price("2330")
        assert price == Decimal("0")


# ── Tests: get_universe ───────────────────────────────────


class TestGetUniverse:
    def test_preset_universe(self) -> None:
        feed = ShioajiFeed(universe=["2330", "2317", "2454"])
        assert feed.get_universe() == ["2330", "2317", "2454"]

    def test_from_api_contracts(self) -> None:
        api = _make_mock_api()
        # Mock iterating over exchanges
        c1 = _make_mock_contract("2330")
        c2 = _make_mock_contract("2317")
        c3 = _make_mock_contract("2454")
        exchange1 = [c1, c2]
        exchange2 = [c3]
        api.Contracts.Stocks.__iter__ = MagicMock(
            return_value=iter([exchange1, exchange2])
        )
        feed = ShioajiFeed(api=api)

        universe = feed.get_universe()
        assert universe == ["2330", "2317", "2454"]

    def test_from_api_with_error(self) -> None:
        api = _make_mock_api()
        api.Contracts.Stocks.__iter__ = MagicMock(
            side_effect=RuntimeError("API error")
        )
        feed = ShioajiFeed(api=api)

        universe = feed.get_universe()
        assert universe == []  # Graceful degradation


# ── Tests: get_snapshot ───────────────────────────────────


class TestGetSnapshot:
    def test_single_symbol(self) -> None:
        api = _make_mock_api()
        snap = _make_mock_snapshot("2330", close=600.0)
        api.snapshots.return_value = [snap]
        feed = ShioajiFeed(api=api)

        df = feed.get_snapshot(["2330"])
        assert len(df) == 1
        assert df.iloc[0]["symbol"] == "2330"
        assert df.iloc[0]["close"] == 600.0

    def test_multiple_symbols(self) -> None:
        api = _make_mock_api()
        snap1 = _make_mock_snapshot("2330", close=600.0)
        snap2 = _make_mock_snapshot("2317", close=120.0)
        api.snapshots.return_value = [snap1, snap2]
        feed = ShioajiFeed(api=api)

        df = feed.get_snapshot(["2330", "2317"])
        assert len(df) == 2
        assert set(df["symbol"]) == {"2330", "2317"}

    def test_empty_symbols_list(self) -> None:
        api = _make_mock_api()
        feed = ShioajiFeed(api=api)

        df = feed.get_snapshot([])
        assert df.empty

    def test_unknown_symbol_skipped(self) -> None:
        api = _make_mock_api()
        snap = _make_mock_snapshot("2330", close=600.0)
        api.snapshots.return_value = [snap]
        feed = ShioajiFeed(api=api)

        # "9999" is unknown and should be skipped
        df = feed.get_snapshot(["2330", "9999"])
        assert len(df) == 1

    def test_batching_over_limit(self) -> None:
        """Should split into batches of _SNAPSHOT_BATCH_SIZE."""
        api = _make_mock_api()

        # Create 600 symbols (exceeds 500 batch limit)
        symbols = [str(i) for i in range(600)]
        contracts = {}
        for sym in symbols:
            contracts[sym] = _make_mock_contract(sym)

        def stocks_get(symbol: str, default: object = None) -> object:
            return contracts.get(symbol, default)

        api.Contracts.Stocks.get = MagicMock(side_effect=stocks_get)

        # Return one snap per contract in each batch call
        def mock_snapshots(batch: list[object]) -> list[MagicMock]:
            return [_make_mock_snapshot(c.code, close=100.0) for c in batch]

        api.snapshots.side_effect = mock_snapshots
        feed = ShioajiFeed(api=api)

        df = feed.get_snapshot(symbols)
        assert len(df) == 600
        # Should have been called twice: 500 + 100
        assert api.snapshots.call_count == 2

    def test_snapshot_returns_none(self) -> None:
        api = _make_mock_api()
        api.snapshots.return_value = None
        feed = ShioajiFeed(api=api)

        df = feed.get_snapshot(["2330"])
        assert df.empty


# ── Tests: get_ticks ──────────────────────────────────────


class TestGetTicks:
    def test_basic_ticks(self) -> None:
        api = _make_mock_api()
        api.ticks.return_value = _make_mock_ticks(n=3)
        feed = ShioajiFeed(api=api)

        df = feed.get_ticks("2330", "2023-06-01")
        assert len(df) == 3
        assert list(df.columns) == ["price", "volume", "bid_price", "ask_price"]
        assert df.index.tz is None

    def test_empty_ticks(self) -> None:
        api = _make_mock_api()
        empty_ticks = MagicMock()
        empty_ticks.ts = []
        api.ticks.return_value = empty_ticks
        feed = ShioajiFeed(api=api)

        df = feed.get_ticks("2330", "2023-06-01")
        assert df.empty

    def test_none_ticks(self) -> None:
        api = _make_mock_api()
        api.ticks.return_value = None
        feed = ShioajiFeed(api=api)

        df = feed.get_ticks("2330", "2023-06-01")
        assert df.empty

    def test_ticks_with_datetime(self) -> None:
        api = _make_mock_api()
        api.ticks.return_value = _make_mock_ticks(n=2)
        feed = ShioajiFeed(api=api)

        df = feed.get_ticks("2330", datetime(2023, 6, 1))
        assert len(df) == 2


# ── Tests: Factory registration ───────────────────────────


class TestFactoryRegistration:
    def test_create_shioaji_feed(self) -> None:
        from src.data.sources import create_feed

        api = _make_mock_api()
        feed = create_feed("shioaji", ["2330"], api=api)
        assert isinstance(feed, ShioajiFeed)
        assert feed._universe == ["2330"]

    def test_create_shioaji_feed_no_api(self) -> None:
        from src.data.sources import create_feed

        feed = create_feed("shioaji", ["2330"])
        assert isinstance(feed, ShioajiFeed)
        assert feed._api is None
