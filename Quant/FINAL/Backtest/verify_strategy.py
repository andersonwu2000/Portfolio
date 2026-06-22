"""
Standalone strategy verifier for the course project.

Loads parquet data from `data/`, runs:
  1. RevenueMomentumHedgedStrategy (the production strategy under review)
  2. MomentumStrategy (12-1 price momentum) — canonical academic baseline
  3. Random N=15 portfolios (200-1000 samples) — "no-skill" benchmark
  4. 0050 / 0056 ETF buy-and-hold

All strategies/baselines face the same point-in-time investable pool at
each rebalance date (no survivorship bias, no data-availability bias).

Dependencies:    pandas + numpy
Data layout:     ./data/{sym}.TW_1d.parquet     (price OHLCV)
                 ./data/{sym}.TW_revenue.parquet (monthly revenue)
                 ./data/0050.TW_1d.parquet        (ETF reference)
                 ./data/0056.TW_1d.parquet
Strategy code:   ./strategies/

Usage:
    python verify_strategy.py
    python verify_strategy.py --start 2018-01-01 --end 2025-12-31 --random-samples 200

Outputs (to ./results/_verify/):
    summary.json            — all metrics (gross + net for strategies)
    strategy_nav_*.csv      — daily NAV of revenue strategy
    momentum_12_1_nav_*.csv — daily NAV of price momentum
    benchmarks/0050.csv     — 0050 buy-and-hold NAV
    benchmarks/0056.csv     — 0056 buy-and-hold NAV
    benchmarks/random_portfolios_*.csv
                            — daily p5/p25/p50/p75/p95 of random portfolios
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd


def _default_workers() -> int:
    """min(16, cores-2) — leave headroom. Override with QUANT_WORKERS (e.g. =4 when
    running several internally-parallel scripts at once, to avoid oversubscribing cores)."""
    env = os.environ.get("QUANT_WORKERS")
    if env and env.isdigit():
        return max(1, int(env))
    return max(1, min(16, (os.cpu_count() or 4) - 2))


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


# ════════════════════════════════════════════════════════════════════════
# Data layer — read parquets directly (no DataCatalog dependency)
# ════════════════════════════════════════════════════════════════════════

class ParquetDataSource:
    """Minimal data source: directory of parquet files."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")

    def list_price_symbols(self) -> set[str]:
        return {p.stem.replace("_1d", "") for p in self.data_dir.glob("*_1d.parquet")}

    def list_revenue_symbols(self) -> set[str]:
        return {p.stem.replace("_revenue", "") for p in self.data_dir.glob("*_revenue.parquet")}

    def get_price(self, symbol: str) -> pd.DataFrame:
        path = self.data_dir / f"{symbol}_1d.parquet"
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_parquet(path)
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        df.index = pd.to_datetime(df.index.date)
        df = df[~df.index.duplicated(keep="first")]
        return df

    def get_revenue(self, symbol: str) -> pd.DataFrame:
        path = self.data_dir / f"{symbol}_revenue.parquet"
        if not path.exists():
            return pd.DataFrame()
        return pd.read_parquet(path)


# ════════════════════════════════════════════════════════════════════════
# Universe — point-in-time, no survivorship filter
# ════════════════════════════════════════════════════════════════════════

def build_universe(data: ParquetDataSource, start: str, end: str
                   ) -> tuple[list[str], pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame], dict[str, pd.Timestamp]]:
    price_syms = data.list_price_symbols()
    rev_syms = data.list_revenue_symbols()
    candidates = sorted(price_syms & rev_syms)

    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)

    close_data: dict[str, pd.Series] = {}
    volume_data: dict[str, pd.Series] = {}
    revenue_data: dict[str, pd.DataFrame] = {}
    first_listed: dict[str, pd.Timestamp] = {}

    # Load FULL history per symbol (so strategies have 252+ days for momentum,
    # and first_listed_date can be computed correctly). The simulation loop in
    # main() will slice to [start, end] separately.
    for sym in candidates:
        df = data.get_price(sym)
        if df.empty or "close" not in df.columns:
            continue
        s_full = df["close"].astype(float).where(lambda x: x > 0.01).dropna()
        if s_full.empty:
            continue
        first_listed[sym] = s_full.index.min()
        # Trim to [end_ts] only (no future data); keep all pre-start history
        s = s_full[s_full.index <= end_ts]
        if s.empty:
            continue
        close_data[sym] = s
        if "volume" in df.columns:
            v = df["volume"].astype(float)
            v = v[v.index <= end_ts]
            volume_data[sym] = v

        rdf = data.get_revenue(sym)
        if not rdf.empty and "date" in rdf.columns:
            rdf["date"] = pd.to_datetime(rdf["date"])
            rdf = rdf.sort_values("date")
            rdf["revenue"] = pd.to_numeric(rdf["revenue"], errors="coerce")
            if "yoy_growth" not in rdf.columns or rdf["yoy_growth"].isna().all():
                prev = rdf["revenue"].shift(12)
                prev = prev.where(prev > 0, np.nan)
                rdf["yoy_growth"] = ((rdf["revenue"] / prev) - 1) * 100
            revenue_data[sym] = rdf

    universe = sorted(set(close_data) & set(revenue_data))
    close_panel = pd.DataFrame({s: close_data[s] for s in universe}).sort_index()
    volume_panel = pd.DataFrame(volume_data).reindex(close_panel.index).fillna(0)
    close_panel = close_panel.ffill(limit=10)

    n_alive = (close_panel.notna()).sum(axis=1)

    return universe, close_panel, volume_panel, {s: revenue_data[s] for s in universe}, first_listed


def eligible_at(date: pd.Timestamp, close_panel: pd.DataFrame, volume_panel: pd.DataFrame,
                first_listed: dict[str, pd.Timestamp],
                min_history_days: int = 90, min_avg_volume: float = 50_000) -> list[str]:
    """Symbols investable at `date`: alive + has 90+ calendar-day history + liquid."""
    if date not in close_panel.index:
        return []
    row = close_panel.loc[date]
    eligible = []
    pos = close_panel.index.get_loc(date)
    cutoff_days = pd.Timedelta(days=min_history_days)
    for sym in close_panel.columns:
        p = row.get(sym, np.nan)
        if not (np.isfinite(p) and p > 0.01):
            continue
        first = first_listed.get(sym)
        if first is None or (date - first) < cutoff_days:
            continue
        if sym in volume_panel.columns and pos >= 20:
            if volume_panel[sym].iloc[max(0, pos - 20):pos].mean() < min_avg_volume:
                continue
        eligible.append(sym)
    return eligible


# ════════════════════════════════════════════════════════════════════════
# Strategy adapters — feed verifier's universe into real Strategy classes
# ════════════════════════════════════════════════════════════════════════

class VerifyFeed:
    def __init__(self, all_symbols: list[str], close_panel: pd.DataFrame, volume_panel: pd.DataFrame):
        self._close = close_panel
        self._volume = volume_panel
        self._cache: dict[str, pd.DataFrame] = {}
        self._dynamic_universe: list[str] = list(all_symbols)

    def set_dynamic_universe(self, symbols: list[str]) -> None:
        self._dynamic_universe = symbols

    def get_bars(self, symbol: str) -> pd.DataFrame:
        if symbol in self._cache:
            return self._cache[symbol]
        if symbol not in self._close.columns:
            df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        else:
            close = self._close[symbol]
            volume = self._volume[symbol] if symbol in self._volume.columns else pd.Series(0, index=close.index)
            df = pd.DataFrame({
                "open": close, "high": close, "low": close,
                "close": close, "volume": volume,
            }).dropna(subset=["close"])
        self._cache[symbol] = df
        return df

    def get_universe(self) -> list[str]:
        return self._dynamic_universe

    def get_latest_price(self, symbol: str):
        if symbol not in self._close.columns:
            return 0.0
        s = self._close[symbol].dropna()
        return float(s.iloc[-1]) if len(s) else 0.0


class VerifyPosition:
    def __init__(self, value: float):
        self.value = value


class VerifyPortfolio:
    def __init__(self, nav: float):
        self.nav = nav
        self.positions: dict[str, VerifyPosition] = {}
        self.cash = nav

    def get_position_weight(self, symbol: str) -> float:
        pos = self.positions.get(symbol)
        if pos is None or self.nav <= 0:
            return 0.0
        return float(pos.value / self.nav)


class VerifyContext:
    def __init__(self, feed: VerifyFeed, portfolio: VerifyPortfolio, current_time: pd.Timestamp):
        self._feed = feed
        self._portfolio = portfolio
        self._current_time = current_time

    def bars(self, symbol: str, lookback: int = 252) -> pd.DataFrame:
        df = self._feed.get_bars(symbol)
        if df.empty:
            return df
        # searchsorted + iloc instead of boolean indexing (rows [0:pos] have index <= current_time)
        pos = int(df.index.searchsorted(self._current_time, side="right"))
        return df.iloc[max(0, pos - lookback):pos]

    def universe(self):
        return self._feed.get_universe()

    def portfolio(self):
        return self._portfolio

    def now(self):
        return self._current_time.to_pydatetime()

    def latest_price(self, symbol: str):
        return self._feed.get_latest_price(symbol)

    def log(self, msg, **kw):
        pass


# ════════════════════════════════════════════════════════════════════════
# NAV simulation
# ════════════════════════════════════════════════════════════════════════

def simulate_nav(
    panel: pd.DataFrame,
    rebalance_dates: list[pd.Timestamp],
    weight_fn,
    buy_cost_bps: float = 17.0,        # commission 14.25 + slippage ~3 bps
    sell_cost_bps: float = 47.0,       # commission 14.25 + tax 30 + slippage ~3 bps
    initial_nav: float = 1.0,
    sim_idx: pd.DatetimeIndex | None = None,
) -> tuple[pd.Series, dict]:
    """Daily NAV simulation. Position carried at last valid price after delisting
    (no haircut); position dropped at next rebalance if no longer in pool.

    Cost model: ASYMMETRIC TW (Taiwan stock market)
        Buy:  ~17 bps  (commission 14.25 bps + slippage ~3 bps)
        Sell: ~47 bps  (commission 14.25 + 30 bps tax + slippage ~3 bps)
        Round-trip ≈ 64 bps — matches TW realistic execution

    Why asymmetric: TW commission is symmetric (0.1425% both sides) but tax is
    only on sells (0.3%). High-turnover strategies pay more (more sells) than
    low-turnover ones. Symmetric 30 bps × 2 = 60 bps round-trip understates
    sell cost and overstates buy cost.

    panel: full-history price panel (used for daily mark-to-market)
    sim_idx: subset of panel.index to iterate (defaults to panel.index)
    """
    daily_idx = panel.index if sim_idx is None else sim_idx
    nav_series = pd.Series(index=daily_idx, dtype=float)
    nav = initial_nav
    last_weights: dict[str, float] = {}
    last_prices: dict[str, float] = {}
    rebalance_set = set(rebalance_dates)
    total_buy_turnover = 0.0
    total_sell_turnover = 0.0
    n_rebalances = 0

    for date in daily_idx:
        if last_weights:
            row = panel.loc[date]
            day_return = 0.0
            for sym, w in last_weights.items():
                p_now = row.get(sym, np.nan)
                p_prev = last_prices.get(sym, np.nan)
                if not np.isnan(p_now) and not np.isnan(p_prev) and p_prev > 0:
                    ret = p_now / p_prev - 1
                    # Data-glitch guard: TW daily price limit is +/-10%, so a
                    # single-day |return| > 50% is a bad / zero / unadjusted print
                    # (~0.15% of obs, concentrated in thin names a top-50 book holds;
                    # some are inf from a zero prev price). Hold flat through it
                    # instead of letting NAV explode / go negative. Large-cap
                    # top-15 names never trigger this, so the reference is unchanged.
                    if -0.5 < ret < 0.5:
                        day_return += w * ret
            nav *= (1 + day_return)
            for sym in list(last_weights):
                p = row.get(sym, np.nan)
                if not np.isnan(p):
                    last_prices[sym] = float(p)

        if date in rebalance_set:
            new_weights = weight_fn(date, dict(last_weights), nav)
            row = panel.loc[date]
            # Asymmetric cost: split turnover into buys and sells
            buy_turnover = 0.0
            sell_turnover = 0.0
            for sym in set(new_weights) | set(last_weights):
                diff = new_weights.get(sym, 0) - last_weights.get(sym, 0)
                if diff > 0:
                    buy_turnover += diff
                elif diff < 0:
                    sell_turnover += -diff
            total_buy_turnover += buy_turnover
            total_sell_turnover += sell_turnover
            n_rebalances += 1
            cost = (buy_turnover * buy_cost_bps + sell_turnover * sell_cost_bps) / 10000.0
            nav *= (1 - cost)
            last_weights = dict(new_weights)
            last_prices = {s: float(row.get(s, np.nan)) for s in new_weights
                          if np.isfinite(row.get(s, np.nan)) and row.get(s, np.nan) > 0}

        nav_series[date] = nav

    avg_total_turnover = (total_buy_turnover + total_sell_turnover) / max(n_rebalances, 1)
    # Frequency-agnostic: total two-way turnover / years. (Previously avg_per_rebalance*12,
    # which hardcoded a monthly cadence and overstated quarterly/semi-annual turnover 3x/6x.
    # For a monthly run total/n_years == avg_per_rebalance*12, so the reference is unchanged.)
    n_years = max((daily_idx[-1] - daily_idx[0]).days / 365.25, 1e-9)
    return nav_series.ffill(), {
        "avg_turnover_per_rebalance": avg_total_turnover,
        "annual_turnover": (total_buy_turnover + total_sell_turnover) / n_years,
        "buy_turnover_total": total_buy_turnover,
        "sell_turnover_total": total_sell_turnover,
        "n_rebalances": n_rebalances,
    }


def get_rebalance_dates(daily_idx: pd.DatetimeIndex) -> list[pd.Timestamp]:
    s = pd.Series(daily_idx, index=daily_idx)
    return s.groupby(s.dt.to_period("M")).first().tolist()


# ════════════════════════════════════════════════════════════════════════
# Baselines
# ════════════════════════════════════════════════════════════════════════

def top_n_equal_weight_nav(panel: pd.DataFrame, volume_panel: pd.DataFrame,
                           first_listed: dict[str, pd.Timestamp],
                           rebalance_dates: list[pd.Timestamp],
                           sim_idx: pd.DatetimeIndex,
                           n_holdings: int = 50,
                           buy_bps: float = 17.0, sell_bps: float = 47.0) -> pd.Series:
    """Top N stocks by 60-day ADV (close × volume), equal-weight, monthly rebalance.

    "Diversified passive large-cap" baseline — what an unsophisticated retail
    investor would get from buying the most-traded TW stocks equally. Captures
    "I don't pick, I just hold the big ones" without 0050's TSMC concentration.
    """
    def weight_fn(date, _cw, _nav):
        pos = panel.index.get_loc(date)
        eligible = eligible_at(date, panel, volume_panel, first_listed)
        if not eligible:
            return {}
        lookback_close = panel.iloc[max(0, pos - 60):pos][eligible]
        lookback_vol = volume_panel.iloc[max(0, pos - 60):pos][eligible]
        adv = (lookback_close * lookback_vol).mean().dropna()
        top = adv.sort_values(ascending=False).head(n_holdings)
        if len(top) == 0:
            return {}
        w = 0.95 / len(top)
        return {s: w for s in top.index}

    nav, _ = simulate_nav(panel, rebalance_dates, weight_fn,
                          buy_cost_bps=buy_bps, sell_cost_bps=sell_bps, sim_idx=sim_idx)
    return nav


def buy_hold_etf(data: ParquetDataSource, symbol: str, daily_idx: pd.DatetimeIndex) -> pd.Series:
    df = data.get_price(symbol)
    if df.empty:
        return pd.Series(dtype=float)
    s = df["close"].astype(float)
    s = s.reindex(daily_idx, method="ffill").dropna()
    return s / s.iloc[0] if len(s) else s


# ── parallel random-portfolio worker (module-level so ProcessPoolExecutor can pickle it) ──
_RP: dict = {}


def _rp_init(panel, rebalance_dates, sim_idx, pool_cache, n_holdings, buy_bps, sell_bps, seed):
    _RP.update(panel=panel, rb=rebalance_dates, sim_idx=sim_idx, pool=pool_cache,
               n=n_holdings, buy=buy_bps, sell=sell_bps, seed=seed)


def _rp_one(i):
    rng = np.random.default_rng(_RP["seed"] + i)   # seed+i -> identical picks to the serial loop
    n, pool_cache = _RP["n"], _RP["pool"]

    def weight_fn(date, _cw, _nav):
        pool = pool_cache.get(date, [])
        if len(pool) < n:
            return {}
        picks = rng.choice(pool, size=n, replace=False)
        return {s: 0.95 / n for s in picks}

    nav, _ = simulate_nav(_RP["panel"], _RP["rb"], weight_fn,
                          buy_cost_bps=_RP["buy"], sell_cost_bps=_RP["sell"], sim_idx=_RP["sim_idx"])
    return nav.values


def random_portfolios_nav(panel: pd.DataFrame, volume_panel: pd.DataFrame,
                          first_listed: dict[str, pd.Timestamp],
                          rebalance_dates: list[pd.Timestamp],
                          sim_idx: pd.DatetimeIndex,
                          n_samples: int = 1000, n_holdings: int = 15,
                          buy_bps: float = 17.0, sell_bps: float = 47.0,
                          seed: int = 42, n_workers: int | None = None) -> pd.DataFrame:
    """1000 independent random-portfolio sims — parallelised across cores (identical
    results: sample i always uses default_rng(seed+i)). ex.map preserves order."""
    pool_cache = {d: eligible_at(d, panel, volume_panel, first_listed) for d in rebalance_dates}
    nav_matrix = np.full((n_samples, len(sim_idx)), np.nan)
    n_workers = min(n_workers or _default_workers(), n_samples)
    if n_workers <= 1:
        _rp_init(panel, rebalance_dates, sim_idx, pool_cache, n_holdings, buy_bps, sell_bps, seed)
        for i in range(n_samples):
            nav_matrix[i] = _rp_one(i)
    else:
        with ProcessPoolExecutor(max_workers=n_workers, initializer=_rp_init,
                                 initargs=(panel, rebalance_dates, sim_idx, pool_cache,
                                           n_holdings, buy_bps, sell_bps, seed)) as ex:
            for i, vals in enumerate(ex.map(_rp_one, range(n_samples), chunksize=8)):
                nav_matrix[i] = vals

    pcts = np.nanpercentile(nav_matrix, [5, 25, 50, 75, 95], axis=0)
    return pd.DataFrame(
        {"p5": pcts[0], "p25": pcts[1], "p50": pcts[2], "p75": pcts[3], "p95": pcts[4]},
        index=sim_idx,
    )


# ── parallel strategy-config grid (DSR trials, param grid, …) ────────────────
# Each item is (label, strategy_kwargs); runs the full hedged strategy per config and
# returns its daily NAV. Identical to serial (deterministic). Worker builds the feed +
# preloads revenue once per process (in the initializer), reused across its configs.
_PS: dict = {}


def _ps_init(panel, volume_panel, rb, sim_idx, pool, data_dir, buy_bps, sell_bps):
    from strategies.revenue_momentum import _preload_revenue
    _preload_revenue(data_dir)
    _PS.update(panel=panel, rb=rb, sim_idx=sim_idx, pool=pool, data=data_dir,
               buy=buy_bps, sell=sell_bps, feed=VerifyFeed(list(panel.columns), panel, volume_panel))


def _ps_one(item):
    from strategies.revenue_momentum_hedged import RevenueMomentumHedgedStrategy
    label, kwargs = item
    feed, pool = _PS["feed"], _PS["pool"]
    strat = RevenueMomentumHedgedStrategy(revenue_dir=_PS["data"], **kwargs)

    def wf(date, cw, nav):
        ts = pd.Timestamp(date)
        feed.set_dynamic_universe(pool.get(ts, []))
        pf = VerifyPortfolio(nav)
        for s, w in cw.items():
            pf.positions[s] = VerifyPosition(value=w * nav)
        return strat.on_bar(VerifyContext(feed, pf, ts))

    nav, stats = simulate_nav(_PS["panel"], _PS["rb"], wf, buy_cost_bps=_PS["buy"],
                              sell_cost_bps=_PS["sell"], sim_idx=_PS["sim_idx"])
    return label, (nav.values, float(stats["annual_turnover"]))


def parallel_strategy_navs(panel, volume_panel, pool, rb, sim_idx, data_dir, items,
                           buy_bps=17.0, sell_bps=47.0, n_workers=None):
    """items: list of (label, strategy_kwargs). Returns {label: (nav np.array, annual_turnover)}, parallel."""
    n_workers = min(n_workers or _default_workers(), max(1, len(items)))
    out = {}
    if n_workers <= 1:
        _ps_init(panel, volume_panel, rb, sim_idx, pool, data_dir, buy_bps, sell_bps)
        for it in items:
            label, vals = _ps_one(it)
            out[label] = vals
    else:
        with ProcessPoolExecutor(max_workers=n_workers, initializer=_ps_init,
                                 initargs=(panel, volume_panel, rb, sim_idx, pool, data_dir, buy_bps, sell_bps)) as ex:
            for label, vals in ex.map(_ps_one, items):
                out[label] = vals
    return out


# ════════════════════════════════════════════════════════════════════════
# Metrics
# ════════════════════════════════════════════════════════════════════════

def compute_metrics(nav: pd.Series) -> dict:
    nav = nav.dropna()
    if len(nav) < 30:
        return {}
    n_years = (nav.index[-1] - nav.index[0]).days / 365.25
    total = nav.iloc[-1] / nav.iloc[0] - 1
    cagr = (1 + total) ** (1 / max(n_years, 0.01)) - 1 if total > -0.999 else -1.0
    rets = nav.pct_change().dropna()
    vol = float(rets.std() * np.sqrt(252)) if len(rets) > 1 else 0.0
    sharpe = float(cagr / vol) if vol > 0 else 0.0
    downside = rets[rets < 0]
    ds_vol = float(downside.std() * np.sqrt(252)) if len(downside) > 1 else 0.0
    sortino = float(cagr / ds_vol) if ds_vol > 0 else 0.0
    rolling_max = nav.cummax()
    dd = (nav - rolling_max) / rolling_max
    mdd = -float(dd.min()) if len(dd) else 0.0
    calmar = float(cagr / mdd) if mdd > 0 else 0.0
    return {
        "total_return": float(total),
        "cagr": float(cagr),
        "volatility": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "max_drawdown": mdd,
    }


def position_in_random(nav: pd.Series, rp: pd.DataFrame) -> str:
    s_final = nav.dropna().iloc[-1]
    common = nav.index.intersection(rp.index)
    if len(common) == 0:
        return "N/A"
    last = rp.loc[common[-1]]
    if s_final > last["p95"]: return "above p95 (top 5%)"
    if s_final > last["p75"]: return "p75-p95 (top 25%)"
    if s_final > last["p50"]: return "p50-p75 (above median)"
    if s_final > last["p25"]: return "p25-p50 (below median)"
    if s_final > last["p5"]:  return "p5-p25 (bottom 25%)"
    return "below p5 (bottom 5%)"


# ════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════

def _save_nav(series: pd.Series, path: Path) -> None:
    """Write a daily-NAV series to CSV with columns [date, nav]."""
    series.rename("nav").reset_index().rename(columns={"index": "date"}).to_csv(path, index=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--out", default=str(ROOT / "results" / "_verify"))
    parser.add_argument("--random-samples", type=int, default=200)
    parser.add_argument("--buy-bps", type=float, default=17.0,
                        help="Buy-side cost: commission 14.25 + slippage ~3 = 17 bps (TW)")
    parser.add_argument("--sell-bps", type=float, default=47.0,
                        help="Sell-side cost: commission 14.25 + tax 30 + slippage ~3 = 47 bps (TW)")
    parser.add_argument("--also-gross", action="store_true")
    parser.add_argument("--no-regime", action="store_true")
    parser.add_argument("--ranking", default="accel",
                        choices=["accel", "new_high", "ensemble"],
                        help="Ranking factor (default accel = committed reference)")
    parser.add_argument("--max-holdings", type=int, default=15,
                        help="Holdings count; random-portfolio benchmark is matched to this")
    parser.add_argument("--weight-method", default="signal",
                        choices=["signal", "equal", "risk_parity"],
                        help="Portfolio weighting (equal preferred for the new_high book)")
    parser.add_argument("--min-streak", type=int, default=1,
                        help="Require a new high sustained >= this many months (1 = off)")
    parser.add_argument("--revenue-lag", type=int, default=15,
                        help="Revenue lag in days; 15 = committed look-ahead floor")
    parser.add_argument("--price-mom", default=None,
                        help='2nd momentum leg for dual momentum, e.g. "nhigh" (price near 52w high)')
    parser.add_argument("--intersect-pct", type=float, default=None,
                        help="dual-momentum: hold names in top-pct of BOTH revenue & price")
    parser.add_argument("--no-accel-gate", action="store_true",
                        help="disable the revenue-acceleration gate (used for the dual-momentum book)")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "benchmarks").mkdir(exist_ok=True)
    data = ParquetDataSource(Path(args.data_dir))

    universe, panel, volume_panel, _revenue, first_listed = build_universe(data, args.start, args.end)
    feed = VerifyFeed(universe, panel, volume_panel)

    # Simulation window: only iterate [start, end] for daily marks/rebalances.
    # The strategies see ALL pre-start history via ctx.bars() because feed
    # uses the full-history panel.
    start_ts = pd.Timestamp(args.start)
    end_ts = pd.Timestamp(args.end)
    sim_idx = panel.index[(panel.index >= start_ts) & (panel.index <= end_ts)]
    rebalance_dates = get_rebalance_dates(sim_idx)

    # Pre-compute eligible pool (shared across strategies + random)
    pool_cache = {d: eligible_at(d, panel, volume_panel, first_listed) for d in rebalance_dates}
    pool_sizes = [len(pool_cache[d]) for d in rebalance_dates]

    # Import real strategy classes
    from strategies.revenue_momentum import RevenueMomentumStrategy
    from strategies.revenue_momentum_hedged import RevenueMomentumHedgedStrategy
    from strategies.momentum import MomentumStrategy

    def make_strategy_weight_fn(strategy):
        def weight_fn(date, current_weights, nav):
            ts = pd.Timestamp(date)
            feed.set_dynamic_universe(pool_cache.get(ts, []))
            portfolio = VerifyPortfolio(nav)
            for sym, w in current_weights.items():
                portfolio.positions[sym] = VerifyPosition(value=w * nav)
            ctx = VerifyContext(feed, portfolio, ts)
            return strategy.on_bar(ctx)
        return weight_fn

    def run_at_cost(buy_bps: float, sell_bps: float, suffix: str) -> dict:

        strat_kwargs = dict(revenue_dir=args.data_dir, ranking=args.ranking,
                            max_holdings=args.max_holdings,
                            weight_method=args.weight_method, min_newhigh_streak=args.min_streak,
                            revenue_lag_days=args.revenue_lag,
                            price_mom_factor=args.price_mom, intersect_pct=args.intersect_pct,
                            use_accel_gate=(not args.no_accel_gate))
        rev_strategy = (RevenueMomentumStrategy(**strat_kwargs)
                        if args.no_regime
                        else RevenueMomentumHedgedStrategy(**strat_kwargs))
        strategy_nav, strat_stats = simulate_nav(
            panel, rebalance_dates, make_strategy_weight_fn(rev_strategy),
            buy_cost_bps=buy_bps, sell_cost_bps=sell_bps, sim_idx=sim_idx)
        _save_nav(strategy_nav, out_dir / f"strategy_nav_{suffix}.csv")

        mom_strategy = MomentumStrategy(max_holdings=15)
        momentum_nav, mom_stats = simulate_nav(
            panel, rebalance_dates, make_strategy_weight_fn(mom_strategy),
            buy_cost_bps=buy_bps, sell_cost_bps=sell_bps, sim_idx=sim_idx)
        _save_nav(momentum_nav, out_dir / f"momentum_12_1_nav_{suffix}.csv")

        # Diversified passive: top 50 by liquidity, equal-weight monthly
        top50_nav = top_n_equal_weight_nav(
            panel, volume_panel, first_listed, rebalance_dates, sim_idx,
            n_holdings=50, buy_bps=buy_bps, sell_bps=sell_bps,
        )
        _save_nav(top50_nav, out_dir / f"benchmarks/top50_eq_weight_{suffix}.csv")

        rp = random_portfolios_nav(panel, volume_panel, first_listed, rebalance_dates, sim_idx,
                                   n_samples=args.random_samples, n_holdings=args.max_holdings,
                                   buy_bps=buy_bps, sell_bps=sell_bps)
        rp.reset_index().rename(columns={"index": "date"}).to_csv(
            out_dir / f"benchmarks/random_portfolios_{suffix}.csv", index=False)

        return {
            "strategy": {**compute_metrics(strategy_nav), "annual_turnover": strat_stats["annual_turnover"]},
            "momentum_12_1": {**compute_metrics(momentum_nav), "annual_turnover": mom_stats["annual_turnover"]},
            "top50_equal_weight": compute_metrics(top50_nav),
            "random_p5":  compute_metrics(rp["p5"]),
            "random_p25": compute_metrics(rp["p25"]),
            "random_p50": compute_metrics(rp["p50"]),
            "random_p75": compute_metrics(rp["p75"]),
            "random_p95": compute_metrics(rp["p95"]),
            "strategy_position_vs_random": position_in_random(strategy_nav, rp),
            "momentum_position_vs_random": position_in_random(momentum_nav, rp),
        }

    bh_0050 = buy_hold_etf(data, "0050.TW", sim_idx)
    _save_nav(bh_0050, out_dir / "benchmarks/0050.csv")
    bh_0056 = buy_hold_etf(data, "0056.TW", sim_idx)
    _save_nav(bh_0056, out_dir / "benchmarks/0056.csv")

    net = run_at_cost(args.buy_bps, args.sell_bps, "net")
    gross = run_at_cost(0.0, 0.0, "gross") if args.also_gross else None

    summary = {
        "config": {
            "start": args.start, "end": args.end,
            "universe_size": len(universe),
            "trading_days": len(panel),
            "n_random_samples": args.random_samples,
            "buy_bps": args.buy_bps,
            "sell_bps": args.sell_bps,
            "regime_detection": not args.no_regime,
        },
        "etf_baselines": {
            "0050_buy_hold": compute_metrics(bh_0050),
            "0056_buy_hold": compute_metrics(bh_0056),
        },
        "net": net,
    }
    if gross:
        summary["gross"] = gross
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")

    print("\n" + "=" * 60)
    print("VERIFICATION RESULTS")
    print("=" * 60)
    print("\nETF baselines (buy & hold, no cost):")
    for name, key in [("0050 (cap-weight)", "0050_buy_hold"), ("0056 (high-dividend)", "0056_buy_hold")]:
        m = summary["etf_baselines"][key]
        if m:
            print(f"  {name:25s}  total={m['total_return']*100:+8.2f}%  CAGR={m['cagr']*100:+5.2f}%  Sharpe={m['sharpe']:+5.2f}  MDD={m['max_drawdown']*100:5.2f}%")

    cost_label = f"NET (buy={args.buy_bps:.0f}bps / sell={args.sell_bps:.0f}bps)"
    for tag, block in [(cost_label, net), ("GROSS (signal-only)", gross)]:
        if block is None:
            continue
        print(f"\n{tag}:")
        for name, key in [("Revenue Mom (subject)", "strategy"),
                          ("Price Mom 12-1", "momentum_12_1"),
                          ("Top 50 EW (passive)", "top50_equal_weight"),
                          ("Random p5",  "random_p5"),
                          ("Random p25", "random_p25"),
                          ("Random p50", "random_p50"),
                          ("Random p75", "random_p75"),
                          ("Random p95", "random_p95")]:
            m = block[key]
            if m:
                print(f"  {name:25s}  total={m['total_return']*100:+8.2f}%  CAGR={m['cagr']*100:+5.2f}%  Sharpe={m['sharpe']:+5.2f}  MDD={m['max_drawdown']*100:5.2f}%")
        print(f"  Revenue Mom vs random: {block['strategy_position_vs_random']}")
        print(f"  Price Mom   vs random: {block['momentum_position_vs_random']}")


if __name__ == "__main__":
    main()
