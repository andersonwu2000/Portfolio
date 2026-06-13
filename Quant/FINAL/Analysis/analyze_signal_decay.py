"""Signal decay test — is revenue_acceleration's alpha CROWDING out, or REGIME-dependent?

Both look like "the signal is weakening" but have different fingerprints:
  - Crowding / secular decay : monthly IC trends DOWN monotonically over time
                               (more capital chases the factor -> alpha arbitraged away).
  - Regime dependence        : monthly IC oscillates with MARKET STATE, not with time
                               (works in up-trends, fails in range-bound / rotations).

Distinguishing them decides the verdict: crowding -> abandon the factor;
regime -> cyclical, may recover but un-timeable.

Method: monthly cross-sectional Spearman IC of accel = rev3m/rev12m (40-day lag)
vs forward 20d & 60d returns, over 2015-2025 (thick universe). Then:
  1. linear trend of IC vs time (slope + t-stat)   -> crowding test
  2. yearly mean IC
  3. IC split by market state (60d market return > 0 vs <= 0) -> regime test
  4. overall ICIR

Usage:  python analyze_signal_decay.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "Backtest"))

START, END = "2015-01-01", "2025-12-31"
FWD = [20, 60]


def main() -> None:
    from verify_strategy import ParquetDataSource, build_universe, get_rebalance_dates
    from strategies.revenue_momentum import _preload_revenue, _get_revenue_at

    data = ParquetDataSource(ROOT.parent / "Data")
    universe, panel, volume_panel, _, first_listed = build_universe(data, START, END)
    rev_cache = _preload_revenue(str(ROOT.parent / "Data"))

    start_ts, end_ts = pd.Timestamp(START), pd.Timestamp(END)
    sim_idx = panel.index[(panel.index >= start_ts) & (panel.index <= end_ts)]
    month_dates = get_rebalance_dates(sim_idx)
    idx_pos = {d: i for i, d in enumerate(panel.index)}

    # market proxy = cross-sectional mean daily return (equal-weight market)
    mkt = panel.pct_change().mean(axis=1)
    mkt_60d = panel.mean(axis=1).pct_change(60)  # 60d trend of EW market level

    rows = []
    for d in month_dates:
        if d not in idx_pos:
            continue
        i = idx_pos[d]
        accel, fwd = {h: [] for h in FWD}, {h: [] for h in FWD}
        a_vec, f_vec = {h: [] for h in FWD}, {h: [] for h in FWD}
        accels, fwds = [], {h: [] for h in FWD}
        for sym in universe:
            rv = _get_revenue_at(rev_cache, sym, d)
            if rv is None:
                continue
            r3, r12, _, _ = rv
            if r12 <= 0:
                continue
            a = r3 / r12
            p0 = panel[sym].iloc[i] if i < len(panel) else np.nan
            if not np.isfinite(p0) or p0 <= 0:
                continue
            ok = False
            frets = {}
            for h in FWD:
                j = i + h
                if j < len(panel):
                    p1 = panel[sym].iloc[j]
                    if np.isfinite(p1) and p1 > 0:
                        frets[h] = p1 / p0 - 1
                        ok = True
            if not ok:
                continue
            accels.append(a)
            for h in FWD:
                fwds[h].append(frets.get(h, np.nan))
        if len(accels) < 30:
            continue
        a_arr = np.array(accels)
        row = {"date": d, "n": len(accels), "mkt60": float(mkt_60d.iloc[i]) if i < len(mkt_60d) else np.nan}
        for h in FWD:
            f_arr = np.array(fwds[h])
            m = np.isfinite(f_arr)
            if m.sum() >= 30:
                ic, _ = stats.spearmanr(a_arr[m], f_arr[m])
                row[f"ic{h}"] = ic
        rows.append(row)

    df = pd.DataFrame(rows).set_index("date")
    out = ROOT / "results" / "_signal_decay"
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "monthly_ic.csv")

    print("\n" + "=" * 78)
    print("SIGNAL DECAY TEST — revenue_acceleration IC, 2015-2025 (monthly)")
    print("=" * 78)
    t = np.arange(len(df))
    for h in FWD:
        col = f"ic{h}"
        s = df[col].dropna()
        tt = np.arange(len(s))
        slope, intercept, r, p, se = stats.linregress(tt, s.values)
        icir = s.mean() / s.std() * np.sqrt(12)  # annualised-ish (monthly)
        print(f"\n-- IC({h}d) --  n_months={len(s)}")
        print(f"  mean IC      = {s.mean():+.4f}   std = {s.std():.4f}   ICIR(ann) = {icir:+.2f}")
        print(f"  TIME TREND   : slope/month = {slope:+.5f}  t = {slope/se:+.2f}  p = {p:.3f}"
              f"   <- crowding if significantly negative")
        # per year
        yr = s.groupby(s.index.year).mean()
        print("  yearly mean IC: " + "  ".join(f"{y}:{v:+.3f}" for y, v in yr.items()))
        # regime split
        reg = df.loc[s.index]
        up = s[reg["mkt60"] > 0]
        dn = s[reg["mkt60"] <= 0]
        print(f"  REGIME split : market-up months IC = {up.mean():+.4f} (n={len(up)})   "
              f"market-down IC = {dn.mean():+.4f} (n={len(dn)})"
              f"   <- regime if up>>down")

    print(f"\nOutput: {(out / 'monthly_ic.csv').resolve()}")


if __name__ == "__main__":
    main()
