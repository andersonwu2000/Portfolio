"""
Revenue Momentum strategy — Taiwan equities monthly revenue acceleration.

Adapted from the production strategy:
- Replaced src.data.registry lookup with a configurable `revenue_dir` parameter
- Removed event-driven rebalancer code path (use monthly rebalance only)

Architecture (separation of concerns):
  Universe (feasibility, in verify_strategy.eligible_at):
      alive + >=90-day history + base liquidity.
  Universal screens (factor-agnostic hygiene, applied here):
      - Liquidity:     20-day avg volume >= min_volume_lots (default 300 lots).
      - Minimum price: close >= min_price (default NT$10; penny / microstructure-noise floor).
  Signal (revenue momentum, factor-specific):
      - Acceleration condition: rev_3m_avg > rev_12m_avg (use_accel_gate).
      - Persistence: require a new 12-month high sustained for >= min_newhigh_streak
        months (denoise one-off spikes; 1 = off).
      - Rank by `ranking` (accel | new_high | ensemble); take top `max_holdings`.
      - new_high winsorized at `newhigh_cap` (bound base-effect artifacts, e.g. revenue
        off a near-zero base producing an implausible ratio).
  Portfolio: weights by `weight_method`; equal-weight is preferred for the new_high book
      (its rank-IC validates ordering, not cardinal magnitude, so signal-proportional
      weights just add single-name risk from low-base spikes). Per-name cap, 5% cash buffer.
  Market-risk: handled by the revenue_momentum_hedged wrapper (scale down in bear/sideways).

Design note: earlier versions also screened on price trend (close > 60d MA), price
momentum (60d return > 0) and a YoY>=10% growth gate. A screen-by-screen ablation
showed the price screens add ~0 Sharpe (a price-momentum confound on a revenue thesis)
and the YoY gate hurt; all three are off by default. See Analysis/ for the ablation.

Revenue lag:  +15 days (committed). Data labels revenue by publication month (revenue of
              month M -> date (M+1)-01, public by the 10th), so ~15 days is the look-ahead
              floor. A longer lag improves the in-sample backtest but is a discretionary,
              isolated spike (~lag 40 x streak-2) that fails OOS / multiple-testing scrutiny,
              so the report uses 15 (the principled floor).
Rebalance:    monthly, on first on_bar of each calendar month.
"""

from __future__ import annotations

import time as _time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .base import Context, Strategy
from .optimizer import OptConstraints, equal_weight, risk_parity, signal_weight


# ── Revenue cache (module-level so multiple instances share it) ─────────
_revenue_cache: dict[str, pd.DataFrame] | None = None
# Parallel numpy cache for the hot path: sym -> (dates[datetime64ns], revenue[f64], yoy[f64]).
# `_get_revenue_at` uses searchsorted on these instead of pandas boolean indexing (~10-50x faster).
_revenue_np_cache: dict[str, tuple] = {}
_revenue_cache_time: float = 0.0
_REVENUE_CACHE_TTL = 3600 * 6  # 6 hours


def _preload_revenue(revenue_dir: str = "data") -> dict[str, pd.DataFrame]:
    """Preload all *_revenue.parquet files from `revenue_dir` into memory.

    Files expected: {revenue_dir}/{symbol}_revenue.parquet
    Each file must have columns: date, revenue (yoy_growth optional — recomputed if missing).
    """
    global _revenue_cache, _revenue_cache_time, _revenue_np_cache
    if _revenue_cache is not None and (_time.time() - _revenue_cache_time) < _REVENUE_CACHE_TTL:
        return _revenue_cache

    cache: dict[str, pd.DataFrame] = {}
    np_cache: dict[str, tuple] = {}
    revenue_path = Path(revenue_dir)
    if not revenue_path.exists():
        _revenue_cache = cache
        _revenue_np_cache = np_cache
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
            np_cache[sym] = (df["date"].values,
                             df["revenue"].to_numpy(dtype=float),
                             df["yoy_growth"].to_numpy(dtype=float))
        except Exception:
            continue

    _revenue_cache = cache
    _revenue_np_cache = np_cache
    _revenue_cache_time = _time.time()
    return cache


def _newhigh_streak(revenues: np.ndarray, max_check: int = 12) -> int:
    """Consecutive most-recent months whose revenue set a strict 12-month high.

    A single-month new high is often a one-off (bulk order / channel stuffing);
    requiring the high to persist for several months denoises the signal. Counts
    backwards from the latest month: month at position p is a new high iff
    rev[p] > max(rev[p-11 : p]); stops at the first month that is not.
    """
    r = np.asarray(revenues, dtype=float)
    p = len(r) - 1
    streak = 0
    for j in range(max_check):
        pos = p - j
        if pos - 11 < 0:
            break
        prior_max = float(np.max(r[pos - 11:pos]))
        if prior_max > 0 and r[pos] > prior_max:
            streak += 1
        else:
            break
    return streak


def _get_revenue_at(
    cache: dict[str, pd.DataFrame],
    symbol: str,
    as_of: pd.Timestamp,
    lag_days: int = 15,
) -> tuple[float, float, float, float, int] | None:
    """Return (rev_3m_avg, rev_12m_avg, latest_yoy, new_high, nh_streak) as of
    `as_of` - lag_days (default 15; see below), or None.

    new_high = rev[-1] / max(rev[-12:-1]) — latest revenue vs prior 11-month peak
    (the canonical revenue new-high factor; >1 means a new high).
    nh_streak = consecutive months ending now that set a strict 12-month high
    (persistence gate input; see `_newhigh_streak`).

    `lag_days`: the data labels revenue of month M as date (M+1)-01 (public by the
    10th), so ~15 days is the look-ahead floor (default; committed). A longer lag
    improves the in-sample backtest but is an isolated, discretionary spike (~lag 40
    x streak-2) that does not clear OOS / multiple-testing scrutiny — not used.
    """
    arr = _revenue_np_cache.get(symbol)
    if arr is None:
        # fallback for callers with a custom df cache not preloaded via _preload_revenue
        df = cache.get(symbol)
        if df is None or "revenue" not in df.columns or "yoy_growth" not in df.columns:
            return None
        arr = (df["date"].values, df["revenue"].to_numpy(dtype=float),
               df["yoy_growth"].to_numpy(dtype=float))
        _revenue_np_cache[symbol] = arr
    dates, rev, yoy = arr

    as_of_naive = as_of.tz_localize(None) if as_of.tzinfo is not None else as_of
    cutoff = (as_of_naive - pd.Timedelta(days=lag_days)).to_datetime64()
    idx = int(np.searchsorted(dates, cutoff, side="right"))   # rows [0:idx] have date <= cutoff
    if idx < 12:
        return None

    revenues = rev[:idx]
    rev_3m = float(revenues[-3:].mean())
    rev_12m = float(revenues[-12:].mean())
    past_max = float(revenues[-12:-1].max())
    new_high = (float(revenues[-1]) / past_max) if past_max > 0 else 0.0

    yv = yoy[:idx]
    fin = yv[np.isfinite(yv)]
    latest_yoy = float(fin[-1]) if fin.size else 0.0

    nh_streak = _newhigh_streak(revenues)

    return (rev_3m, rev_12m, latest_yoy, new_high, nh_streak)


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
        min_yoy_growth: float | None = None,  # signal gate (off by default): require latest YoY >= this
        min_volume_lots: int = 300,           # universal screen: liquidity floor
        min_price: float = 10.0,              # universal screen: min close price (penny / microstructure floor)
        use_ma_screen: bool = False,     # legacy price-trend screen (close > 60d MA); ablation: ~0 alpha, confound
        use_return_screen: bool = False, # legacy price-momentum screen (60d return > 0); ablation: hurts
        use_accel_gate: bool = True,     # signal: rev_3m > rev_12m (revenue acceleration condition)
        min_newhigh_streak: int = 1,     # signal: require a new high sustained >= this many months (1 = off)
        revenue_lag_days: int = 15,      # publication look-ahead floor (committed); longer is a discretionary in-sample choice
        newhigh_cap: float | None = 20.0,  # signal hygiene: winsorize new_high at a high cap (bound base-effect artifacts)
        price_mom_factor: str | None = None,  # 2nd momentum leg: None | "nhigh" (price near 52-week high)
        intersect_pct: float | None = None,   # dual-momentum: hold names in top-pct of BOTH revenue & price (None = off)
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
        self.min_price = min_price
        self.use_ma_screen = use_ma_screen
        self.use_return_screen = use_return_screen
        self.use_accel_gate = use_accel_gate
        self.min_newhigh_streak = min_newhigh_streak
        self.revenue_lag_days = revenue_lag_days
        self.newhigh_cap = newhigh_cap
        self.price_mom_factor = price_mom_factor
        self.intersect_pct = intersect_pct
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

                # universal screen: minimum price (penny-stock / microstructure-noise floor)
                if self.min_price > 0 and float(close.iloc[-1]) < self.min_price:
                    continue

                # data sufficiency for the 60-day price screens
                if len(close) < 60:
                    continue
                # screen ②: price > 60-day MA (trend confirmation)
                if self.use_ma_screen and float(close.iloc[-1]) <= float(close.iloc[-60:].mean()):
                    continue
                # screen ③: 60-day return > 0 (price momentum)
                if self.use_return_screen and float(close.iloc[-1]) / float(close.iloc[-60]) - 1 <= 0:
                    continue

                # revenue factors (publication+confirmation lag handled inside)
                rev_data = _get_revenue_at(self._rev_cache, symbol, as_of, self.revenue_lag_days)
                if rev_data is None:
                    continue

                rev_3m, rev_12m, latest_yoy, new_high, nh_streak = rev_data
                if rev_12m <= 0:
                    continue
                # screen ④: revenue acceleration (rev_3m > rev_12m)
                if self.use_accel_gate and rev_3m <= rev_12m:
                    continue
                # signal: require a new high sustained for >= min_newhigh_streak months
                # (denoise one-off spikes; 1 = off). See _newhigh_streak.
                if self.min_newhigh_streak > 1 and nh_streak < self.min_newhigh_streak:
                    continue
                # optional signal gate: latest YoY growth >= threshold (off by default)
                if self.min_yoy_growth is not None and latest_yoy < self.min_yoy_growth:
                    continue

                # Carry both ranking factors; the active one is chosen below.
                acceleration = rev_3m / rev_12m
                # price near-52-week-high (dual-momentum 2nd leg): close / trailing max (no look-ahead)
                near_high = float(close.iloc[-1]) / float(close.max()) if float(close.max()) > 0 else 0.0
                candidates.append((symbol, acceleration, new_high, near_high))

            except Exception as e:
                continue

        if not candidates:
            self._last_month = current_month
            self._cached_weights = {}
            return {}

        # Ranking score: accel (default, reference) / new_high / ensemble (rank-avg).
        syms = [c[0] for c in candidates]
        acc = np.array([c[1] for c in candidates], dtype=float)
        nh = np.array([c[2] for c in candidates], dtype=float)
        ph = np.array([c[3] for c in candidates], dtype=float)   # price near-52w-high (dual-momentum leg)
        if self.newhigh_cap is not None:
            nh = np.minimum(nh, self.newhigh_cap)   # winsorize: low-base spikes get a real-momentum weight, not a 1000x one
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

        # Dual momentum (intersection): hold names in the top-`intersect_pct` of BOTH the
        # revenue ranking AND price near-52w-high, capped at max_holdings by revenue rank.
        # (FinLab 雙渦輪-style: revenue breakout INTERSECT price breakout. Off by default.)
        if self.intersect_pct is not None and self.price_mom_factor == "nhigh":
            n = len(ranked_syms)
            mom_pct = {s: i / max(n - 1, 1) for i, s in enumerate(ranked_syms)}
            price_ranked = [syms[i] for i in np.argsort(ph)[::-1]]   # high near-high first
            np_ = len(price_ranked)
            price_pct = {s: i / max(np_ - 1, 1) for i, s in enumerate(price_ranked)}
            p = self.intersect_pct
            selected_syms = [s for s in ranked_syms
                             if mom_pct[s] <= p and price_pct.get(s, 1.1) <= p][: self.max_holdings]
        # Selection hysteresis (buffering): when exit_rank is set, keep currently
        # held names that still rank within [0, exit_rank) before filling the rest
        # from the top. Suppresses turnover from names oscillating around the
        # rank-`max_holdings` boundary without touching the entry bar.
        elif self.exit_rank is not None and self.exit_rank > self.max_holdings:
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
