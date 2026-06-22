"""評估 harness(可重用):新研究的統一量尺。
目標函數 = 年化 log-growth g = 252·mean(ln(1+r))(Kelly;≈幾何CAGR、內建波動懲罰)。
評估視角 = 滾動 36/60 月分佈(中位/最差5百分位/勝基準占比),非單一全期點估計。
推論 = block bootstrap 的 Δg 信賴區間(尊重自相關)。
邊界:開發集 DEV=2016-01..2025-06-20;鎖盒 LOCKBOX=2025-06-21..2026-05(最後跑一次,不入選擇)。
本檔 __main__ = 在 DEV 上把純動能 vs 三因子先跑出 baseline。
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
TRADING = 252
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "Backtest"))
sys.path.insert(0, str(ROOT))
DATA = ROOT.parent / "Data"
DEV_LO, DEV_HI = "2016-01-01", "2025-06-20"
LOCK_LO, LOCK_HI = "2025-06-21", "2026-05-31"


# ───────────────────────── 指標 ─────────────────────────
def g_ann(nav):
    """年化 log-growth(主目標)。"""
    r = nav.pct_change().dropna()
    if len(r) < 20:
        return np.nan
    return np.log1p(r).mean() * TRADING


def metric_vector(nav):
    r = nav.pct_change().dropna()
    if len(r) < 20:
        return {k: np.nan for k in ["g", "cagr", "sharpe", "sortino", "mdd", "calmar", "vol"]}
    g = np.log1p(r).mean() * TRADING
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (TRADING / len(r)) - 1
    vol = r.std() * np.sqrt(TRADING)
    sharpe = r.mean() / r.std() * np.sqrt(TRADING)
    dn = r[r < 0].std() * np.sqrt(TRADING)
    sortino = r.mean() * TRADING / dn if dn > 0 else np.nan
    mdd = -(nav / nav.cummax() - 1).min()
    calmar = cagr / mdd if mdd > 0 else np.nan
    kelly_g = 0.5 * sharpe ** 2  # 槓桿到 Kelly 最優時的年化 log-growth(=½SR²)
    return dict(g=g, cagr=cagr, sharpe=sharpe, sortino=sortino, mdd=mdd, calmar=calmar, vol=vol, kelly_g=kelly_g)


def rolling_dist(nav, W_months, benches=None):
    """滾動 W 月窗的 g 分佈 + 勝各基準占比。"""
    idx = nav.index
    starts = pd.date_range(idx.min(), idx.max(), freq="MS")
    gs = []
    beat = {k: [] for k in (benches or {})}
    for s in starts:
        e = s + pd.DateOffset(months=W_months)
        if e > idx.max():
            break
        sub = nav[(nav.index >= s) & (nav.index <= e)]
        g = g_ann(sub)
        if np.isnan(g):
            continue
        gs.append(g)
        for k, bnav in (benches or {}).items():
            bsub = bnav[(bnav.index >= s) & (bnav.index <= e)]
            gb = g_ann(bsub)
            beat[k].append(g - gb)
    gs = np.array(gs)
    if len(gs) == 0:
        return None
    out = dict(n=len(gs), median=np.median(gs), p25=np.percentile(gs, 25),
               p5=np.percentile(gs, 5), worst=gs.min())
    for k in (benches or {}):
        d = np.array(beat[k])
        out[f"beat%_{k}"] = (d > 0).mean()
        out[f"dgmed_{k}"] = np.median(d)
        out[f"dgp5_{k}"] = np.percentile(d, 5)
    return out


def block_bootstrap_dg(navA, navB, block=21, n=5000, seed=42):
    """配對 block bootstrap:Δg=g(A)-g(B) 的 95% CI 與雙尾 p。"""
    rng = np.random.RandomState(seed)
    a = np.log1p(navA.pct_change().dropna())
    b = np.log1p(navB.pct_change().dropna())
    j = a.index.intersection(b.index)
    a = a.loc[j].values; b = b.loc[j].values
    N = len(a); nb = max(1, N // block)
    obs = (a.mean() - b.mean()) * TRADING
    boot = np.empty(n)
    for i in range(n):
        st = rng.randint(0, N - block, nb)
        idx = np.concatenate([np.arange(s, s + block) for s in st])
        boot[i] = (a[idx].mean() - b[idx].mean()) * TRADING
    return dict(obs=obs, lo=np.percentile(boot, 2.5), hi=np.percentile(boot, 97.5),
                p=2 * min((boot <= 0).mean(), (boot >= 0).mean()))


# ───────────────────────── 建 navs(定版配置) ─────────────────────────
def build_navs(lo, hi):
    from verify_strategy import (ParquetDataSource, build_universe, eligible_at, get_rebalance_dates,
                                 simulate_nav, top_n_equal_weight_nav, buy_hold_etf)
    import strategies.revenue_momentum as rm
    from liq1e8_factor_archive import load_chip_col, rev_extra
    data = ParquetDataSource(DATA)
    u, panel, vol, _, fl = build_universe(data, "2014-06-01", hi)
    sim = panel.index[(panel.index >= pd.Timestamp(lo)) & (panel.index <= pd.Timestamp(hi))]
    rb = get_rebalance_dates(sim); ip = {d: i for i, d in enumerate(panel.index)}
    price_nh = panel / panel.rolling(252).max()
    advval = (panel * vol).rolling(20).mean()
    base = {d: list(eligible_at(d, panel, vol, fl, min_history_days=0, min_avg_volume=0)) for d in rb}
    pool = {d: [s for s in base[d] if advval.iloc[ip[d]].get(s, 0) >= 1e8] for d in rb}
    trustcon = (load_chip_col("institutional", "trust_net", panel.index) > 0).rolling(20, min_periods=10).mean().shift(1)
    rm._preload_revenue(str(DATA))
    accel = {}
    for d in rb:
        a = {}
        for s in base[d]:
            arr = rm._revenue_np_cache.get(s)
            if arr is None:
                continue
            e = rev_extra(arr, pd.Timestamp(d), 15)
            if e is not None and np.isfinite(e.get("rev_accel", np.nan)):
                a[s] = e["rev_accel"]
        accel[d] = pd.Series(a, dtype=float)

    def wf(keys):
        def f(date, cw, nav):
            ts = pd.Timestamp(date); i = ip[ts]; syms = pool.get(ts, [])
            if not syms:
                return cw or {}
            held = [s for s, w in (cw or {}).items() if w > 0.001]; uni = pd.Index(syms)
            cols = {"p": price_nh.iloc[i].reindex(uni), "a": accel[ts].reindex(uni)}
            if "t" in keys:
                cols["t"] = trustcon.iloc[i].reindex(uni)
            df = pd.DataFrame(cols).dropna(how="any")
            if len(df) < 30:
                return cw or {}
            comp = df.rank(pct=True).mean(axis=1); rk = comp.rank(ascending=False)
            sel = sorted([s for s in held if s in rk.index and rk[s] <= 45], key=lambda s: rk[s])[:30]
            for s in comp.sort_values(ascending=False).index:
                if len(sel) >= 30:
                    break
                if s not in sel:
                    sel.append(s)
            return {x: 0.95 / len(sel) for x in sel} if sel else {}
        return f
    nav_mom, st_mom = simulate_nav(panel, rb, wf("pa"), 20.0, 50.0, sim_idx=sim)
    nav_main, st_main = simulate_nav(panel, rb, wf("pat"), 20.0, 50.0, sim_idx=sim)
    nav_ew = top_n_equal_weight_nav(panel, vol, fl, rb, sim, n_holdings=99999, buy_bps=20.0, sell_bps=50.0)
    nav_0050 = buy_hold_etf(data, "0050.TW", sim)
    return dict(sim=sim, mom=nav_mom, main=nav_main, ew=nav_ew, etf=nav_0050,
                turn_mom=st_mom["annual_turnover"], turn_main=st_main["annual_turnover"])


def main():
    print("建 navs(DEV 2016-01..2025-06-20)...", flush=True)
    d = build_navs(DEV_LO, DEV_HI)
    mom, main, ew, etf = d["mom"], d["main"], d["ew"], d["etf"]
    print(f"DEV 區間實到: {d['sim'][0].date()} ~ {d['sim'][-1].date()}\n")

    print("=" * 84)
    print("(A) 全期(DEV)指標向量 — 主目標 g=年化log-growth;其餘全列")
    print("=" * 84)
    print(f"  {'策略':<12}{'g':>8}{'CAGR':>8}{'Sharpe':>8}{'Sortino':>8}{'MDD':>7}{'Calmar':>8}{'½SR²':>7}")
    for lab, nav in [("純動能", mom), ("三因子", main), ("等權池", ew), ("0050", etf)]:
        m = metric_vector(nav)
        print(f"  {lab:<12}{m['g']*100:>+7.1f}%{m['cagr']*100:>+7.1f}%{m['sharpe']:>8.2f}{m['sortino']:>8.2f}"
              f"{m['mdd']*100:>6.0f}%{m['calmar']:>8.2f}{m['kelly_g']*100:>+6.0f}%")
    print(f"  換手: 純動能 {d['turn_mom']:.1f}x / 三因子 {d['turn_main']:.1f}x")

    print("\n" + "=" * 84)
    print("(B) 滾動分佈(g):中位 / 5百分位最差窗 / 勝基準占比")
    print("=" * 84)
    for W in [36, 60]:
        print(f"  ── 滾動 {W} 月 ──")
        print(f"  {'策略':<10}{'n':>4}{'中位g':>8}{'p5最差':>8}{'最差窗':>8}{'勝0050':>8}{'勝等權':>8}{'勝對方':>8}")
        bm = {"0050": etf, "ew": ew}
        rm_ = rolling_dist(mom, W, {**bm, "other": main})
        ra_ = rolling_dist(main, W, {**bm, "other": mom})
        for lab, rr in [("純動能", rm_), ("三因子", ra_)]:
            print(f"  {lab:<10}{rr['n']:>4}{rr['median']*100:>+7.1f}%{rr['p5']*100:>+7.1f}%{rr['worst']*100:>+7.1f}%"
                  f"{rr['beat%_0050']*100:>7.0f}%{rr['beat%_ew']*100:>7.0f}%{rr['beat%_other']*100:>7.0f}%")

    print("\n" + "=" * 84)
    print("(C) 分期 g(regime 視角:籌碼稀疏期 / 動能順風 / 近年震盪)")
    print("=" * 84)
    print(f"  {'期間':<14}{'純動能g':>9}{'三因子g':>9}{'籌碼Δg':>9}{'0050 g':>9}")
    for lab, lo, hi in [("2016-2018", "2016-01-01", "2018-12-31"),
                        ("2019-2021", "2019-01-01", "2021-12-31"),
                        ("2022-2025H1", "2022-01-01", "2025-06-20")]:
        sl = lambda n: n[(n.index >= pd.Timestamp(lo)) & (n.index <= pd.Timestamp(hi))]
        gm, ga, ge = g_ann(sl(mom)), g_ann(sl(main)), g_ann(sl(etf))
        print(f"  {lab:<14}{gm*100:>+8.1f}%{ga*100:>+8.1f}%{(ga-gm)*100:>+8.1f}%{ge*100:>+8.1f}%")

    print("\n" + "=" * 84)
    print("(D) block bootstrap:Δg 的 95% CI 與 p(尊重自相關)")
    print("=" * 84)
    for lab, A, B in [("三因子 − 純動能", main, mom), ("純動能 − 0050", mom, etf), ("三因子 − 0050", main, etf)]:
        bb = block_bootstrap_dg(A, B)
        sig = "顯著" if bb["p"] < 0.05 else "不顯著"
        print(f"  {lab:<16} Δg={bb['obs']*100:>+5.1f}%  CI[{bb['lo']*100:+.1f}%, {bb['hi']*100:+.1f}%]  p≈{bb['p']:.2f}  {sig}")
    print("\n[判讀] g 是新主目標:看純動能與三因子在 g 上誰勝、滾動最差窗誰穩、分期誰贏哪個 regime、Δg 是否統計顯著。")


if __name__ == "__main__":
    main()
