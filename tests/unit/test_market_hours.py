"""Tests for market hours — 交易時段管理。"""

from __future__ import annotations

from datetime import datetime


from src.execution.market_hours import (
    TW_TZ,
    OrderQueue,
    TradingSession,
    get_current_session,
    is_odd_lot_session,
    is_tradable,
    next_open,
)


# ── get_current_session ───────────────────────────────────


class TestGetCurrentSession:
    def test_regular_session(self) -> None:
        dt = datetime(2026, 3, 25, 10, 0, tzinfo=TW_TZ)  # Wednesday 10:00
        assert get_current_session(dt) == TradingSession.REGULAR

    def test_pre_market(self) -> None:
        dt = datetime(2026, 3, 25, 8, 45, tzinfo=TW_TZ)
        assert get_current_session(dt) == TradingSession.PRE_MARKET

    def test_closing_auction(self) -> None:
        dt = datetime(2026, 3, 25, 14, 0, tzinfo=TW_TZ)
        assert get_current_session(dt) == TradingSession.CLOSING_AUCTION

    def test_after_hours(self) -> None:
        dt = datetime(2026, 3, 25, 15, 0, tzinfo=TW_TZ)
        assert get_current_session(dt) == TradingSession.AFTER_HOURS

    def test_weekend(self) -> None:
        dt = datetime(2026, 3, 28, 10, 0, tzinfo=TW_TZ)  # Saturday
        assert get_current_session(dt) == TradingSession.WEEKEND

    def test_early_morning(self) -> None:
        dt = datetime(2026, 3, 25, 7, 0, tzinfo=TW_TZ)
        assert get_current_session(dt) == TradingSession.AFTER_HOURS

    def test_boundary_9am(self) -> None:
        dt = datetime(2026, 3, 25, 9, 0, 0, tzinfo=TW_TZ)
        assert get_current_session(dt) == TradingSession.REGULAR

    def test_boundary_1325(self) -> None:
        dt = datetime(2026, 3, 25, 13, 25, 0, tzinfo=TW_TZ)
        # 13:25 is NOT in [09:00, 13:25), so it's after_hours (between regular and closing)
        assert get_current_session(dt) == TradingSession.AFTER_HOURS

    def test_naive_datetime_treated_as_tw(self) -> None:
        dt = datetime(2026, 3, 25, 10, 0)  # naive
        session = get_current_session(dt)
        assert session == TradingSession.REGULAR


# ── is_tradable ───────────────────────────────────────────


class TestIsTradable:
    def test_regular_hours(self) -> None:
        dt = datetime(2026, 3, 25, 10, 0, tzinfo=TW_TZ)
        assert is_tradable(dt) is True

    def test_pre_market_allowed(self) -> None:
        dt = datetime(2026, 3, 25, 8, 45, tzinfo=TW_TZ)
        assert is_tradable(dt, allow_pre_market=True) is True

    def test_pre_market_disallowed(self) -> None:
        dt = datetime(2026, 3, 25, 8, 45, tzinfo=TW_TZ)
        assert is_tradable(dt, allow_pre_market=False) is False

    def test_weekend_not_tradable(self) -> None:
        dt = datetime(2026, 3, 28, 10, 0, tzinfo=TW_TZ)
        assert is_tradable(dt) is False

    def test_after_hours_not_tradable(self) -> None:
        dt = datetime(2026, 3, 25, 15, 0, tzinfo=TW_TZ)
        assert is_tradable(dt) is False

    def test_closing_auction_tradable(self) -> None:
        dt = datetime(2026, 3, 25, 14, 0, tzinfo=TW_TZ)
        assert is_tradable(dt) is True


# ── is_odd_lot_session ────────────────────────────────────


class TestIsOddLotSession:
    def test_during_odd_lot(self) -> None:
        dt = datetime(2026, 3, 25, 12, 0, tzinfo=TW_TZ)
        assert is_odd_lot_session(dt) is True

    def test_before_odd_lot(self) -> None:
        dt = datetime(2026, 3, 25, 9, 5, tzinfo=TW_TZ)
        assert is_odd_lot_session(dt) is False

    def test_weekend(self) -> None:
        dt = datetime(2026, 3, 28, 12, 0, tzinfo=TW_TZ)
        assert is_odd_lot_session(dt) is False


# ── next_open ─────────────────────────────────────────────


class TestNextOpen:
    def test_before_open_today(self) -> None:
        dt = datetime(2026, 3, 25, 8, 0, tzinfo=TW_TZ)  # Wednesday 8am
        result = next_open(dt)
        assert result.hour == 9
        assert result.day == 25

    def test_after_open_goes_to_next_day(self) -> None:
        dt = datetime(2026, 3, 25, 10, 0, tzinfo=TW_TZ)
        result = next_open(dt)
        assert result.day == 26
        assert result.hour == 9

    def test_friday_evening_skips_weekend(self) -> None:
        dt = datetime(2026, 3, 27, 15, 0, tzinfo=TW_TZ)  # Friday 3pm
        result = next_open(dt)
        assert result.weekday() == 0  # Monday
        assert result.hour == 9

    def test_saturday_skips_to_monday(self) -> None:
        dt = datetime(2026, 3, 28, 10, 0, tzinfo=TW_TZ)  # Saturday
        result = next_open(dt)
        assert result.weekday() == 0  # Monday


# ── OrderQueue ────────────────────────────────────────────


class TestOrderQueue:
    def test_enqueue_and_drain(self) -> None:
        q = OrderQueue()
        q.enqueue({"symbol": "2330"})
        q.enqueue({"symbol": "2317"})
        assert q.size == 2

        orders = q.drain()
        assert len(orders) == 2
        assert q.size == 0

    def test_drain_empty(self) -> None:
        q = OrderQueue()
        orders = q.drain()
        assert orders == []

    def test_pending_orders_is_copy(self) -> None:
        q = OrderQueue()
        q.enqueue({"symbol": "2330"})
        pending = q.pending_orders
        pending.clear()
        assert q.size == 1  # Original not affected
