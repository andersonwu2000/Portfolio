"""Re-check rebalance frequency with CORRECT turnover accounting.

simulate_nav reports annual_turnover = avg_per_rebalance * 12, which hardcodes
a monthly (12/yr) cadence. For quarterly/semi-annual rebalancing that OVERSTATES
turnover by 3x / 6x. NAV/CAGR/Sharpe are correct (cost is applied per actual
rebalance); only the reported turnover metric is wrong.

Here we compute frequency-agnostic annual turnover = (total_buy + total_sell)
/ n_years, alongside the buggy *12 number, for monthly / quarterly / semi-annual.
Same engine (verify_strategy.simulate_nav), RevenueMomentumHedgedStrategy, NET,
2018-2025.

Usage:  python analyze_quarterly_recheck.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "Backtest"))


def main() -> None:
    from verify_strategy import (
        ParquetDataSource, build_universe, eligible_at, get_rebalance_dates,
        simulate_nav, VerifyFeed, VerifyContext, VerifyPortfolio, VerifyPosition,
        compute_metrics,
    )
    from strategies.revenue_momentum_hedged import RevenueMomentumHedgedStrategy

    data = ParquetDataSource(ROOT.parent / "Data")
    universe, panel, volume_panel, _, first_listed = build_universe(data, "2018-01-01", "2025-12-31")
    feed = VerifyFeed(universe, panel, volume_panel)
    sim_idx = panel.index[(panel.index >= pd.Timestamp("2018-01-01")) & (panel.index <= pd.Timestamp("2025-12-31"))]
    monthly = get_rebalance_dates(sim_idx)
    pool_cache = {d: eligible_at(d, panel, volume_panel, first_listed) for d in monthly}
    n_years = (sim_idx[-1] - sim_idx[0]).days / 365.25

    def make_fn(strategy):
        def weight_fn(date, current_weights, nav, _s=strategy):
            ts = pd.Timestamp(date)
            feed.set_dynamic_universe(pool_cache.get(ts, []))
            pf = VerifyPortfolio(nav)
            for sym, w in current_weights.items():
                pf.positions[sym] = VerifyPosition(value=w * nav)
            return _s.on_bar(VerifyContext(feed, pf, ts))
        return weight_fn

    configs = [("monthly", monthly), ("quarterly", monthly[::3]), ("semi-annual", monthly[::6])]
    print("\n" + "=" * 90)
    print("REBALANCE FREQUENCY RE-CHECK (NET, hedged, 2018-2025) — CORRECT vs buggy turnover")
    print("=" * 90)
    print(f"{'cadence':>12}{'CAGR':>8}{'Sharpe':>8}{'MDD':>8}{'turn/yr(correct)':>18}{'turn(buggy*12)':>16}{'n_rb':>6}")
    for name, dates in configs:
        strat = RevenueMomentumHedgedStrategy(revenue_dir=str(ROOT.parent / "Data"))
        nav, stats = simulate_nav(panel, dates, make_fn(strat),
                                  buy_cost_bps=17.0, sell_cost_bps=47.0, sim_idx=sim_idx)
        m = compute_metrics(nav)
        correct_turn = (stats["buy_turnover_total"] + stats["sell_turnover_total"]) / n_years
        print(f"{name:>12}{m['cagr']*100:>7.2f}%{m['sharpe']:>8.2f}{m['max_drawdown']*100:>7.1f}%"
              f"{correct_turn:>18.2f}{stats['annual_turnover']:>16.2f}{stats['n_rebalances']:>6}")

    print("\nNote: 'turn/yr(correct)' = total two-way turnover / years (frequency-agnostic).")
    print("      'turn(buggy*12)' = simulate_nav's reported annual_turnover (avg_per_rb * 12).")


if __name__ == "__main__":
    main()
