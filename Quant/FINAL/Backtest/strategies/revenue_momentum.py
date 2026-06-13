"""
Revenue Momentum strategy — Taiwan equities monthly revenue acceleration.

Adapted from the production strategy:
- Replaced src.data.registry lookup with a configurable `revenue_dir` parameter
- Removed event-driven rebalancer code path (use monthly rebalance only)

Core ranking factor: revenue_acceleration = mean(rev[-3:]) / mean(rev[-12:])
- ICIR 0.476 (acceleration)  vs  0.188 (raw YoY) — after 40-day publication lag.

Selection screens (5 layers):
  1. Liquidity:           20-day avg volume >= 300 lots (300,000 shares)
  2. Trend confirmation:  close > 60-day MA
  3. Momentum:            60-day return > 0
  4. Revenue acceleration: rev_3m_avg > rev_12m_avg
  5. Growth threshold:    latest YoY revenue growth >= min_yoy_growth (default 10%)

Revenue lag:  +40 days (TW monthly revenue is published by the 10th of the next month).
Rebalance:    monthly, on first on_bar of each calendar month.
"""

from __future__ import annotations

import logging
import time as _time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .base import Context, Strategy
from .optimizer import OptConstraints, equal_weight, risk_parity, signal_weight

logger = logging.getLogger(__name__)

# ── Revenue cache (module-level so multiple instances share it) ─────────
_revenue_cache: dict[str, pd.DataFrame] | None = None
_revenue_cache_time: float = 0.0
_REVENUE_CACHE_TTL = 3600 * 6  # 6 hours


def _preload_revenue(revenue_dir: str = "data") -> dict[str, pd.DataFrame]:
    """Preload all *_revenue.parquet files from `revenue_dir` into memory.

    Files expected: {revenue_dir}/{symbol}_revenue.parquet
    Each file must have columns: date, revenue (yoy_growth optional — recomputed if missing).
    """
    global _revenue_cache, _revenue_cache_time
    if _revenue_cache is not None and (_time.time() - _revenue_cache_time) < _REVENUE_CACHE_TTL:
        return _revenue_cache

    cache: dict[str, pd.DataFrame] = {}
    revenue_path = Path(revenue_dir)
    if not revenue_path.exists():
        logger.warning("Revenue dir not found: %s", revenue_path.resolve())
        _revenue_cache = cache
        _revenue_cache_time = _time.time()
        return cache

    for p in sorted(revenue_path.glob("*_revenue.parquet")):
        sym = p.stem.replace("_revenue", "")
        try:
            df = pd.read_parquet(p)
            if df.empty or "revenue" not in df.columns:
                continue
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce")

            # Recompute YoY if missing (monthly data -> shift 12 rows)
            if "yoy_growth" not in df.columns or df["yoy_growth"].isna().all():
                prev_year_rev = df["revenue"].shift(12)
                prev_year_rev = prev_year_rev.where(prev_year_rev > 0, np.nan)
                df["yoy_growth"] = ((df["revenue"] / prev_year_rev) - 1) * 100

            cache[sym] = df
        except Exception:
            continue

    logger.info("Preloaded revenue data: %d symbols from %s", len(cache), revenue_path)
    _revenue_cache = cache
    _revenue_cache_time = _time.time()
    return cache


def _get_revenue_at(
    cache: dict[str, pd.DataFrame],
    symbol: str,
    as_of: pd.Timestamp,
) -> tuple[float, float, float, float] | None:
    """Return (rev_3m_avg, rev_12m_avg, latest_yoy, new_high) as of `as_of`-40d, or None.

    new_high = rev[-1] / max(rev[-12:-1]) — latest revenue vs prior 11-month peak
    (the canonical revenue new-high factor; >1 means a new high).

    The 40-day lag prevents look-ahead: TW monthly revenue for month M is
    published by Mth+10, so on date d we should only use data dated <= d - 40.
    """
    df = cache.get(symbol)
    if df is None:
        return None

    as_of_naive = as_of.tz_localize(None) if as_of.tzinfo is not None else as_of
    usable_cutoff = as_of_naive - pd.DateOffset(days=40)
    mask = df["date"] <= usable_cutoff
    available = df[mask]
    if len(available) < 12:
        return None

    revenues = available["revenue"].values
    rev_3m = float(np.mean(np.asarray(revenues[-3:]))) if len(revenues) >= 3 else 0
    rev_12m = float(np.mean(np.asarray(revenues[-12:]))) if len(revenues) >= 12 else 0

    past_max = float(np.max(np.asarray(revenues[-12:-1]))) if len(revenues) >= 12 else 0.0
    new_high = (float(revenues[-1]) / past_max) if past_max > 0 else 0.0

    yoy_vals = available["yoy_growth"].dropna().values
    latest_yoy = float(yoy_vals[-1]) if len(yoy_vals) > 0 else 0

    return (rev_3m, rev_12m, latest_yoy, new_high)


class RevenueMomentumStrategy(Strategy):
    """
    Revenue momentum + price confirmation.

    See module docstring for filter / ranking / rebalance rules.
    """

    def __init__(
        self,
        max_holdings: int = 15,
        ranking: str = "accel",         # "accel" | "new_high" | "ensemble" (rank-avg of both)
        exit_rank: int | None = None,   # hysteresis: hold a name until its rank > exit_rank (None = no buffer)
        min_yoy_growth: float = 10.0,
        min_volume_lots: int = 300,
        max_weight: float = 0.10,
        weight_method: str = "signal",        # "equal" | "signal" | "risk_parity"
        enable_regime_hedge: bool = False,    # use the _hedged wrapper instead
        bear_position_scale: float = 0.30,
        sideways_position_scale: float = 0.60,
        market_proxy: str = "0050.TW",
        revenue_dir: str = "data",    # path to {sym}_revenue.parquet files
    ):
        self.max_holdings = max_holdings
        self.ranking = ranking
        self.exit_rank = exit_rank
        self.min_yoy_growth = min_yoy_growth
        self.min_volume_lots = min_volume_lots
        self.max_weight = max_weight
        self.weight_method = weight_method
        self.enable_regime_hedge = enable_regime_hedge
        self.bear_position_scale = bear_position_scale
        self.sideways_position_scale = sideways_position_scale
        self.market_proxy = market_proxy
        self.revenue_dir = revenue_dir
        self._last_month: str = ""
        self._cached_weights: dict[str, float] = {}
        self._rev_cache: dict[str, pd.DataFrame] | None = None
        # Diagnostic traces (non-functional; read by analyze_churn_source.py)
        self._last_candidates: list[str] = []   # full ranked, post-screen
        self._last_selected: list[str] = []      # intended top-N, pre-NTZ

    def name(self) -> str:
        return "revenue_momentum"

    def _market_regime(self, ctx: Context) -> str:
        """Detect bull / bear / sideways using market proxy MA200/MA50 cross."""
        try:
            market_bars = ctx.bars(self.market_proxy, lookback=252)
            if len(market_bars) < 200:
                return "bull"

            close = market_bars["close"]
            current = float(close.iloc[-1])
            ma200 = float(close.iloc[-200:].mean())
            ma50 = float(close.iloc[-50:].mean())

            if current < ma200 and ma50 < ma200:
                return "bear"
            elif current > ma200 and ma50 > ma200:
                return "bull"
            else:
                return "sideways"
        except Exception:
            return "bull"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        current_date = ctx.now()

        # Monthly rebalance only (revenue lag is handled by _get_revenue_at)
        current_month = pd.Timestamp(current_date).strftime("%Y-%m")
        if current_month == self._last_month:
            return self._cached_weights

        if self._rev_cache is None:
            self._rev_cache = _preload_revenue(self.revenue_dir)

        as_of = pd.Timestamp(current_date)
        candidates: list[tuple[str, float]] = []

        for symbol in ctx.universe():
            try:
                bars = ctx.bars(symbol, lookback=252)
                if len(bars) < 120:
                    continue

                close = bars["close"]
                volume = bars["volume"]

                # 5: liquidity
                avg_vol_20 = float(volume.iloc[-20:].mean()) if len(volume) >= 20 else 0
                if avg_vol_20 < self.min_volume_lots * 1000:
                    continue

                # 3: price > 60-day MA
                if len(close) < 60:
                    continue
                ma60 = float(close.iloc[-60:].mean())
                if float(close.iloc[-1]) <= ma60:
                    continue

                # 4: 60-day return > 0
                if float(close.iloc[-1]) / float(close.iloc[-60]) - 1 <= 0:
                    continue

                # 1 & 2: revenue
                rev_data = _get_revenue_at(self._rev_cache, symbol, as_of)
                if rev_data is None:
                    continue

                rev_3m, rev_12m, latest_yoy, new_high = rev_data
                if rev_12m <= 0 or rev_3m <= rev_12m:
                    continue
                if latest_yoy < self.min_yoy_growth:
                    continue

                # Carry both ranking factors; the active one is chosen below.
                acceleration = rev_3m / rev_12m
                candidates.append((symbol, acceleration, new_high))

            except Exception as e:
                logger.debug("Skip %s: %s", symbol, e)
                continue

        if not candidates:
            self._last_month = current_month
            self._cached_weights = {}
            return {}

        # Ranking score: accel (default, reference) / new_high / ensemble (rank-avg).
        syms = [c[0] for c in candidates]
        acc = np.array([c[1] for c in candidates], dtype=float)
        nh = np.array([c[2] for c in candidates], dtype=float)
        if self.ranking == "new_high":
            score = nh
        elif self.ranking == "ensemble":
            ra = pd.Series(acc).rank(pct=True).to_numpy()
            rn = pd.Series(nh).rank(pct=True).to_numpy()
            score = (ra + rn) / 2.0
        else:  # "accel"
            score = acc
        score_of = {syms[i]: float(score[i]) for i in range(len(syms))}
        ranked_syms = [syms[i] for i in np.argsort(score)[::-1]]  # high -> low

        # Selection hysteresis (buffering): when exit_rank is set, keep currently
        # held names that still rank within [0, exit_rank) before filling the rest
        # from the top. Suppresses turnover from names oscillating around the
        # rank-`max_holdings` boundary without touching the entry bar.
        if self.exit_rank is not None and self.exit_rank > self.max_holdings:
            rank_of = {s: i for i, s in enumerate(ranked_syms)}
            portfolio = ctx.portfolio()
            held: list[str] = []
            if portfolio is not None and getattr(portfolio, "nav", 0) > 0:
                held = [s for s in getattr(portfolio, "positions", {})
                        if float(portfolio.get_position_weight(s)) > 0.001]
            keepers = [s for s in held if rank_of.get(s, 10**9) < self.exit_rank]
            keepers.sort(key=lambda s: rank_of[s])
            selected_syms = list(keepers[: self.max_holdings])
            for s in ranked_syms:
                if len(selected_syms) >= self.max_holdings:
                    break
                if s not in selected_syms:
                    selected_syms.append(s)
        else:
            selected_syms = ranked_syms[: self.max_holdings]
        signals = {s: score_of[s] for s in selected_syms}

        # Diagnostic traces for churn-source attribution (non-functional).
        self._last_candidates = ranked_syms
        self._last_selected = list(signals.keys())

        constraints = OptConstraints(
            max_weight=self.max_weight,
            max_total_weight=0.95,
        )

        if self.weight_method == "signal":
            weights = signal_weight(signals, constraints)
        elif self.weight_method == "risk_parity":
            vols: dict[str, float] = {}
            for sym in signals:
                bars = ctx.bars(sym, lookback=25)
                if bars is not None and len(bars) >= 20:
                    rets = bars["close"].pct_change().dropna()
                    vols[sym] = float(rets.std()) if len(rets) > 1 else 0.20
                else:
                    vols[sym] = 0.20
            weights = risk_parity(signals, vols, constraints)
        else:
            weights = equal_weight(signals, constraints)

        # Optional internal regime hedge (off by default; prefer the _hedged wrapper)
        if self.enable_regime_hedge and weights:
            regime = self._market_regime(ctx)
            if regime == "bear":
                weights = {k: v * self.bear_position_scale for k, v in weights.items()}
            elif regime == "sideways":
                weights = {k: v * self.sideways_position_scale for k, v in weights.items()}

        # Asymmetric no-trade zone (TW sell cost = 3x buy cost)
        NO_TRADE_BUY = 0.015   # buy/add when drift > 1.5%
        NO_TRADE_SELL = 0.030  # sell when drift > 3.0%
        portfolio = ctx.portfolio()
        if portfolio is not None and getattr(portfolio, "nav", 0) > 0:
            current_w: dict[str, float] = {}
            position_syms = list(getattr(portfolio, "positions", {}))
            for sym in set(list(weights.keys()) + position_syms):
                current_w[sym] = float(portfolio.get_position_weight(sym))
            adjusted: dict[str, float] = {}
            for sym in set(list(weights.keys()) + list(current_w.keys())):
                target = weights.get(sym, 0.0)
                current = current_w.get(sym, 0.0)
                diff = target - current
                if diff > NO_TRADE_BUY:        # buy/add: drift > 1.5%
                    adjusted[sym] = target
                elif diff < -NO_TRADE_SELL:    # sell: drift > 3%
                    adjusted[sym] = target
                elif current > 0.001 and target > 0:   # in-zone AND still selected: hold
                    adjusted[sym] = current
                # else: deselected (target==0) or not held -> drop (sell).
                # The `target > 0` guard is essential for diversified books: with
                # top-50 each weight (~1.9%) is below NO_TRADE_SELL (3%), so without
                # it a deselected name never trips the sell branch and positions
                # accumulate unbounded (weights sum >> 1 -> NAV blows up). Top-15
                # weights are all > 3%, so deselected names already sell via the
                # branch above -> this guard leaves the reference unchanged.
            weights = adjusted

        self._last_month = current_month
        self._cached_weights = weights
        return weights
