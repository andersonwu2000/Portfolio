"""Holdings-count sweep for the best signal (new_high), full framework, net.

How does concentration trade off against diversification? Sweep max_holdings for
ranking=new_high through the FULL hedged strategy (5 screens + signal-wt + NTZ +
regime), net 2018-2025. accel/15 (committed reference) shown for context.

Usage:  python analyze_holdings_sweep.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "Backtest"))


def main():
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
    rb = get_rebalance_dates(sim_idx)
    pool_cache = {d: eligible_at(d, panel, volume_panel, first_listed) for d in rb}

    def make_fn(strategy):
        def weight_fn(date, current_weights, nav, _s=strategy):
            ts = pd.Timestamp(date)
            feed.set_dynamic_universe(pool_cache.get(ts, []))
            pf = VerifyPortfolio(nav)
            for sym, w in current_weights.items():
                pf.positions[sym] = VerifyPosition(value=w * nav)
            return _s.on_bar(VerifyContext(feed, pf, ts))
        return weight_fn

    def run(ranking, maxh):
        s = RevenueMomentumHedgedStrategy(revenue_dir=str(ROOT.parent / "Data"), ranking=ranking, max_holdings=maxh)
        navn, st = simulate_nav(panel, rb, make_fn(s), buy_cost_bps=17.0, sell_cost_bps=47.0, sim_idx=sim_idx)
        m = compute_metrics(navn)
        return m, st["annual_turnover"]

    print("=" * 74)
    print("HOLDINGS SWEEP — ranking=new_high, full framework (NET, 2018-2025)")
    print("=" * 74)
    print(f"{'config':<22}{'CAGR':>8}{'Sharpe':>8}{'MDD':>9}{'turn/yr':>9}")
    rows = []
    m, t = run("accel", 15)
    print(f"{'accel 15 (reference)':<22}{m['cagr']*100:>7.1f}%{m['sharpe']:>8.2f}{m['max_drawdown']*100:>8.1f}%{t:>9.1f}")
    rows.append({"ranking": "accel", "n_holdings": 15, "cagr": m["cagr"],
                 "sharpe": m["sharpe"], "mdd": m["max_drawdown"], "turnover": t})
    print("-" * 74)
    for n in [12, 15, 20, 30, 50]:
        m, t = run("new_high", n)
        print(f"{'new_high ' + str(n):<22}{m['cagr']*100:>7.1f}%{m['sharpe']:>8.2f}{m['max_drawdown']*100:>8.1f}%{t:>9.1f}")
        rows.append({"ranking": "new_high", "n_holdings": n, "cagr": m["cagr"],
                     "sharpe": m["sharpe"], "mdd": m["max_drawdown"], "turnover": t})

    out = ROOT / "results" / "_holdings_sweep"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out / "sweep.csv", index=False)
    print(f"\nOutput: {(out / 'sweep.csv').resolve()}")


if __name__ == "__main__":
    main()
