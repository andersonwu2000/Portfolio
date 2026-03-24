"""Tests for src.data.scanner -- ShioajiScanner with mock API."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.data.scanner import ShioajiScanner


# ── helpers ────────────────────────────────────────────────


def _make_item(code: str, name: str = "", close: float = 100.0,
               volume: int = 1000, total_volume: int = 5000,
               change_price: float = 1.0, change_rate: float = 1.0) -> SimpleNamespace:
    return SimpleNamespace(
        code=code, name=name, close=close,
        volume=volume, total_volume=total_volume,
        change_price=change_price, change_rate=change_rate,
    )


def _mock_api(
    scanner_items: list | None = None,
    punish_codes: list[str] | None = None,
    notice_codes: list[str] | None = None,
) -> MagicMock:
    api = MagicMock()
    api.scanners.return_value = scanner_items or []
    api.punish.return_value = SimpleNamespace(code=punish_codes or [])
    api.notice.return_value = SimpleNamespace(code=notice_codes or [])
    return api


@pytest.fixture(autouse=True)
def _fake_shioaji():
    """Inject a fake shioaji module so local imports inside scanner methods succeed."""
    fake_sj = SimpleNamespace(
        constant=SimpleNamespace(
            ScannerType=SimpleNamespace(
                VolumeRank="VolumeRank",
                ChangePercentRank="ChangePercentRank",
                AmountRank="AmountRank",
            ),
        ),
    )
    sys.modules["shioaji"] = fake_sj  # type: ignore[assignment]
    yield
    sys.modules.pop("shioaji", None)


# ── no API connected ──────────────────────────────────────


class TestNoApi:
    def test_top_volume_raises_without_api(self):
        scanner = ShioajiScanner(api=None)
        with pytest.raises(RuntimeError, match="not connected"):
            scanner.top_volume()

    def test_get_disposition_raises_without_api(self):
        scanner = ShioajiScanner(api=None)
        with pytest.raises(RuntimeError, match="not connected"):
            scanner.get_disposition_stocks()

    def test_get_active_universe_raises_without_api(self):
        scanner = ShioajiScanner(api=None)
        with pytest.raises(RuntimeError, match="not connected"):
            scanner.get_active_universe()


# ── scanner methods ───────────────────────────────────────


class TestScannerMethods:
    def test_top_volume_returns_dicts(self):
        items = [_make_item("2330", "TSMC", 600.0, 5000, 20000, 5.0, 0.8)]
        api = _mock_api(scanner_items=items)
        scanner = ShioajiScanner(api=api)

        result = scanner.top_volume(count=10)

        assert len(result) == 1
        assert result[0]["code"] == "2330"
        assert result[0]["name"] == "TSMC"
        assert result[0]["close"] == 600.0
        assert result[0]["volume"] == 5000
        assert result[0]["total_volume"] == 20000
        assert result[0]["change_price"] == 5.0
        assert result[0]["change_rate"] == 0.8

    def test_top_volume_passes_scanner_type(self):
        api = _mock_api(scanner_items=[_make_item("2330")])
        scanner = ShioajiScanner(api=api)
        scanner.top_volume(count=20)

        call_kwargs = api.scanners.call_args[1]
        assert call_kwargs["scanner_type"] == "VolumeRank"
        assert call_kwargs["ascending"] is False
        assert call_kwargs["count"] == 20

    def test_top_gainers(self):
        items = [_make_item("3008"), _make_item("2317")]
        api = _mock_api(scanner_items=items)
        scanner = ShioajiScanner(api=api)

        result = scanner.top_gainers(count=5)

        assert len(result) == 2
        call_kwargs = api.scanners.call_args[1]
        assert call_kwargs["scanner_type"] == "ChangePercentRank"
        assert call_kwargs["ascending"] is False

    def test_top_losers(self):
        items = [_make_item("1234")]
        api = _mock_api(scanner_items=items)
        scanner = ShioajiScanner(api=api)

        result = scanner.top_losers(count=5)

        assert len(result) == 1
        call_kwargs = api.scanners.call_args[1]
        assert call_kwargs["ascending"] is True

    def test_top_amount(self):
        items = [_make_item("2454")]
        api = _mock_api(scanner_items=items)
        scanner = ShioajiScanner(api=api)

        result = scanner.top_amount(count=3)

        assert len(result) == 1
        assert result[0]["code"] == "2454"
        call_kwargs = api.scanners.call_args[1]
        assert call_kwargs["scanner_type"] == "AmountRank"

    def test_empty_scanner_result(self):
        api = _mock_api(scanner_items=[])
        scanner = ShioajiScanner(api=api)

        result = scanner.top_volume()

        assert result == []


# ── disposition / attention ───────────────────────────────


class TestRegulatoryLists:
    def test_get_disposition_stocks(self):
        api = _mock_api(punish_codes=["9999", "8888"])
        scanner = ShioajiScanner(api=api)

        result = scanner.get_disposition_stocks()
        assert result == {"9999", "8888"}

    def test_get_attention_stocks(self):
        api = _mock_api(notice_codes=["7777"])
        scanner = ShioajiScanner(api=api)

        result = scanner.get_attention_stocks()
        assert result == {"7777"}

    def test_empty_disposition(self):
        api = _mock_api(punish_codes=[])
        scanner = ShioajiScanner(api=api)

        result = scanner.get_disposition_stocks()
        assert result == set()


# ── active universe ───────────────────────────────────────


class TestActiveUniverse:
    def test_filters_disposition_and_attention(self):
        items = [_make_item(c) for c in ["2330", "2317", "9999", "7777", "3008"]]
        api = _mock_api(
            scanner_items=items,
            punish_codes=["9999"],
            notice_codes=["7777"],
        )
        scanner = ShioajiScanner(api=api)

        result = scanner.get_active_universe(count=10, exclude_disposition=True)

        assert result == ["2330", "2317", "3008"]

    def test_no_exclusion(self):
        items = [_make_item(c) for c in ["2330", "9999"]]
        api = _mock_api(scanner_items=items, punish_codes=["9999"])
        scanner = ShioajiScanner(api=api)

        result = scanner.get_active_universe(count=10, exclude_disposition=False)

        assert result == ["2330", "9999"]

    def test_all_filtered_returns_empty(self):
        items = [_make_item("9999")]
        api = _mock_api(
            scanner_items=items,
            punish_codes=["9999"],
            notice_codes=[],
        )
        scanner = ShioajiScanner(api=api)

        result = scanner.get_active_universe(count=10)

        assert result == []

    def test_preserves_order(self):
        codes = ["A", "B", "C", "D", "E"]
        items = [_make_item(c) for c in codes]
        api = _mock_api(scanner_items=items, punish_codes=["C"])
        scanner = ShioajiScanner(api=api)

        result = scanner.get_active_universe(count=10)

        assert result == ["A", "B", "D", "E"]
