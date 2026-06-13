"""Churn-source attribution — WHERE does the strategy's turnover come from?

The turnover-reduction experiment (analyze_turnover_opt.py) refuted the
hypothesis that churn is dominated by names oscillating around the rank-15
boundary: a 2x-wide selection buffer barely moved turnover. This script proves
the real source by decomposing each rebalance's SELL turnover into:

  screen_eject : held name no longer passes the 5 screens -> dropped from the
                 candidate list entirely -> forced exit (a rank buffer cannot help).
  rank_rotation: held name still passes screens but fell below the top-N cut.
  regime_scale : reduction of a still-selected name because the regime hedge
                 scaled the whole book down (bear/sideways -> x0.30).
  weight_drift : residual rebalancing of still-selected names toward signal
                 weights in a bull regime (normal, unavoidable).

Reads the non-functional traces (_last_candidates / _last_selected / _last_regime)
set by the strategy classes. Baseline config (monthly, no buffer).

Usage:
    python analyze_churn_source.py
"""

from __future__ import annotations

import logging
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "Backtest"))


def main() -> None:
    from verify_strategy import (
        ParquetDataSource, build_universe, eligible_at, get_rebalance_dates,
        VerifyFeed, VerifyContext, VerifyPortfolio, VerifyPosition,
    )
    from strategies.revenue_momentum_hedged import RevenueMomentumHedgedStrategy

    data = ParquetDataSource(ROOT.parent / "Data")
    universe, panel, volume_panel, _, first_listed = build_universe(
        data, "2018-01-01", "2025-12-31",
    )
    feed = VerifyFeed(universe, panel, volume_panel)
    start_ts, end_ts = pd.Timestamp("2018-01-01"), pd.Timestamp("2025-12-31")
    sim_idx = panel.index[(panel.index >= start_ts) & (panel.index <= end_ts)]
    rebalance_dates = get_rebalance_dates(sim_idx)
    pool_cache = {d: eligible_at(d, panel, volume_panel, first_listed) for d in rebalance_dates}

    strategy = RevenueMomentumHedgedStrategy(revenue_dir=str(ROOT.parent / "Data"))
    inner = strategy._inner

    # Drive the monthly rebalances ourselves, threading weights forward so that
    # prev-weights at each step reflect the actual held book (mark-to-market
    # drift is ignored here — we attribute the *decision* turnover, which is what
    # the rank buffer and regime hedge act on).
    prev_weights: dict[str, float] = {}
    buckets: dict[str, float] = defaultdict(float)
    n_rebalances = 0
    per_rebalance = []

    for d in rebalance_dates:
        feed.set_dynamic_universe(pool_cache.get(d, []))
        nav = 1.0
        portfolio = VerifyPortfolio(nav)
        for sym, w in prev_weights.items():
            portfolio.positions[sym] = VerifyPosition(value=w * nav)
        ctx = VerifyContext(feed, portfolio, d)
        target = strategy.on_bar(ctx)

        passing = set(inner._last_candidates)
        selected = set(inner._last_selected)
        regime = strategy._last_regime
        non_bull = regime != "bull"

        row = defaultdict(float)
        for sym, w_prev in prev_weights.items():
            w_tgt = target.get(sym, 0.0)
            sell = w_prev - w_tgt
            if sell <= 1e-9:
                continue
            if sym not in passing:
                row["screen_eject"] += sell
            elif sym not in selected:
                row["rank_rotation"] += sell
            elif non_bull:
                row["regime_scale"] += sell
            else:
                row["weight_drift"] += sell
        for k, v in row.items():
            buckets[k] += v
        total_sell = sum(row.values())
        if total_sell > 1e-9:
            n_rebalances += 1
            per_rebalance.append({"date": d, "regime": regime, "sell_total": total_sell, **row})

        prev_weights = target

    total = sum(buckets.values())
    print("\n" + "=" * 70)
    print("CHURN-SOURCE ATTRIBUTION  (decision SELL turnover, monthly, 2018-2025)")
    print("=" * 70)
    order = ["screen_eject", "rank_rotation", "regime_scale", "weight_drift"]
    labels = {
        "screen_eject": "Screen ejection (dropped from candidate list)",
        "rank_rotation": "Rank rotation  (still passes, fell below top-N)",
        "regime_scale": "Regime scaling (bear/sideways x0.30)",
        "weight_drift": "Weight drift   (normal bull rebalancing)",
    }
    for k in order:
        v = buckets.get(k, 0.0)
        print(f"  {labels[k]:52s} {v/total*100:5.1f}%   (sum={v:.2f})")
    print("-" * 70)
    print(f"  {'TOTAL decision sell turnover':52s} {100.0:5.1f}%   (sum={total:.2f})")
    n_months = len(rebalance_dates)
    print(f"\n  Avg sell / rebalance: {total/max(n_months,1):.3f}  over {n_months} months")
    print(f"  (rank buffer can only ever touch the 'rank_rotation' slice)")

    out_dir = ROOT / "results" / "_turnover_opt"
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(per_rebalance).to_csv(out_dir / "churn_attribution.csv", index=False)
    print(f"\nPer-rebalance detail: {(out_dir / 'churn_attribution.csv').resolve()}")


if __name__ == "__main__":
    main()
