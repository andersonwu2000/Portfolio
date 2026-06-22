"""因子歸檔（1億流動池）：所有因子的 IC / IC(去2023) / ICIR / t / 命中率 / 五分位報酬 / 覆蓋 + 正交矩陣。
IC = 截面 Spearman(因子值 d, rebalance→下個rebalance 報酬)；月頻、2018-25。
五分位：Q1(最低)→Q5(最高) 的平均未來報酬，看預測力在頭(rank)還是尾(gate)。
所有因子定向為『越高越好』。存 results/_factor_archive_1e8/{ic_summary,ortho_matrix}.csv。
"""
from __future__ import annotations
import sys, glob, os
from pathlib import Path
import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "Backtest"))
FINAL = ROOT.parent / "Data"
VALTHR = 1e8
LAG = 90


def val_panel(col, idx, positive_only=False):
    d = {}
    for f in glob.glob(str(FINAL / "*_valuation.parquet")):
        sym = os.path.basename(f)[:-len("_valuation.parquet")]
        try:
            t = pd.read_parquet(f)
        except Exception:
            continue
        if col in t:
            t["date"] = pd.to_datetime(t["date"]); s = t.set_index("date")[col].astype(float).sort_index()
            if positive_only:
                s = s.where(s > 0)
            d[sym] = s
    return pd.DataFrame(d).sort_index().reindex(idx, method="ffill")


def fin_panels(idx):
    rev, opi, ni, eq, gp = {}, {}, {}, {}, {}
    for f in glob.glob(str(FINAL / "*_financials.parquet")):
        sym = os.path.basename(f)[:-len("_financials.parquet")]
        try:
            t = pd.read_parquet(f)
        except Exception:
            continue
        t["date"] = pd.to_datetime(t["date"]) + pd.Timedelta(days=LAG)
        t = t.set_index("date").sort_index(); c = t.columns
        if "Revenue" in c:         rev[sym] = t["Revenue"].astype(float).rolling(4).sum()
        if "OperatingIncome" in c: opi[sym] = t["OperatingIncome"].astype(float).rolling(4).sum()
        if "NetIncome" in c:       ni[sym] = t["NetIncome"].astype(float).rolling(4).sum()
        if "GrossProfit" in c:     gp[sym] = t["GrossProfit"].astype(float).rolling(4).sum()
        if "EquityAttributableToOwnersOfParent" in c:
            eq[sym] = t["EquityAttributableToOwnersOfParent"].astype(float)
    def DF(d): return pd.DataFrame(d).sort_index().reindex(idx, method="ffill")
    REV, OPI, NI, GP, EQ = DF(rev), DF(opi), DF(ni), DF(gp), DF(eq)
    op_margin = OPI / REV.where(REV != 0)
    out = {
        "op_margin": op_margin,
        "roe": NI / EQ.where(EQ > 0),
        "gross_margin": GP / REV.where(REV != 0),
        "net_margin": NI / REV.where(REV != 0),
        "earn_growth": (OPI - OPI.shift(252)) / REV.shift(252).abs().where(REV.shift(252) != 0),
        "margin_trend": op_margin - op_margin.shift(252),
    }
    return out


def load_chip_col(suffix, col, idx):
    d = {}
    for f in glob.glob(str(FINAL / f"*_{suffix}.parquet")):
        sym = os.path.basename(f)[:-len(f"_{suffix}.parquet")]
        try:
            t = pd.read_parquet(f)
        except Exception:
            continue
        if col in t.columns:
            t["date"] = pd.to_datetime(t["date"]); d[sym] = t.set_index("date")[col].astype(float).sort_index()
    return pd.DataFrame(d).sort_index().reindex(idx)


def rev_extra(arr, as_of, lag=15):
    dates, rev, yoy = arr
    cutoff = (as_of - pd.Timedelta(days=lag)).to_datetime64()
    idx = int(np.searchsorted(dates, cutoff, side="right"))
    if idx < 15:
        return None
    r = rev[:idx].astype(float)
    r3, r12 = r[-3:].mean(), r[-12:].mean()
    if r12 <= 0:
        return None
    o = {}
    o["rev_accel"] = r3 / r12
    o["rev_newhigh"] = (r[-1] / r[-12:-1].max()) if r[-12:-1].max() > 0 else np.nan
    s3, s3y = r[-3:].sum(), r[-15:-12].sum()
    o["rev_yoy3m"] = (s3 / s3y - 1) if s3y > 0 else np.nan
    mp = r[-6:-3].mean(); o["rev_mom3m"] = (r3 / mp - 1) if mp > 0 else np.nan
    yv = yoy[:idx]; fin = yv[np.isfinite(yv)]; o["rev_yoy1m"] = float(fin[-1]) if fin.size else np.nan
    # 連續創新高 streak
    p = len(r) - 1; st = 0
    for j in range(12):
        pos = p - j
        if pos - 11 < 0:
            break
        pm = r[pos - 11:pos].max()
        if pm > 0 and r[pos] > pm:
            st += 1
        else:
            break
    o["rev_nhstreak"] = float(st)
    return o


def main():
    from verify_strategy import (ParquetDataSource, build_universe, eligible_at, get_rebalance_dates)
    import strategies.revenue_momentum as rm
    data = ParquetDataSource(FINAL)
    u, panel, vol, _, fl = build_universe(data, "2018-01-01", "2025-12-31")
    sim = panel.index[(panel.index >= pd.Timestamp("2018-01-01")) & (panel.index <= pd.Timestamp("2025-12-31"))]
    rb = get_rebalance_dates(sim); ip = {d: i for i, d in enumerate(panel.index)}
    zerofrac = (panel.pct_change(fill_method=None).abs() < 1e-9).rolling(60).mean()
    advval = (panel * vol).rolling(20).mean()
    pool = {d: [s for s in eligible_at(d, panel, vol, fl)
                if not (zerofrac.iloc[ip[d]].get(s, 0) > 0.20) and advval.iloc[ip[d]].get(s, 0) >= VALTHR] for d in rb}

    print("building factor panels ...", flush=True)
    price_nh = panel / panel.rolling(252).max()
    vol60 = panel.pct_change(fill_method=None).rolling(60).std()
    st_rev = -(panel / panel.shift(21) - 1)
    fin = fin_panels(panel.index)
    ep = 1.0 / val_panel("PER", panel.index, True); bm = 1.0 / val_panel("PBR", panel.index, True)
    dy = val_panel("dividend_yield", panel.index)
    fo = load_chip_col("institutional", "foreign_net", panel.index)
    tr = load_chip_col("institutional", "trust_net", panel.index)
    de = load_chip_col("institutional", "dealer_net", panel.index)
    sb = load_chip_col("margin", "short_balance", panel.index)
    mb = load_chip_col("margin", "margin_balance", panel.index)
    v20 = vol.rolling(20, min_periods=10).sum()
    chip_foreign = (fo.rolling(20, min_periods=10).sum() / v20.where(v20 > 0)).shift(1)   # 籌碼盤後→lag1
    chip_trust = (tr.rolling(20, min_periods=10).sum() / v20.where(v20 > 0)).shift(1)
    chip_trustcon = ((tr > 0).rolling(20, min_periods=10).mean()).shift(1)
    chip_dealer = (de.rolling(20, min_periods=10).sum() / v20.where(v20 > 0)).shift(1)
    chip_negSM = (-(sb / mb.where(mb > 0))).shift(1)

    PANEL_FAC = {
        "price_nh": price_nh, "lowvol": -vol60, "st_rev": st_rev,
        "op_margin": fin["op_margin"], "roe": fin["roe"], "gross_margin": fin["gross_margin"],
        "net_margin": fin["net_margin"], "earn_growth": fin["earn_growth"], "margin_trend": fin["margin_trend"],
        "ep": ep, "bm": bm, "divyield": dy,
        "chip_foreign": chip_foreign, "chip_trust": chip_trust, "chip_trustcon": chip_trustcon,
        "chip_dealer": chip_dealer, "chip_negSM": chip_negSM,
    }
    REV_FAC = ["rev_accel", "rev_yoy1m", "rev_yoy3m", "rev_mom3m", "rev_newhigh", "rev_nhstreak"]
    rm._preload_revenue(str(FINAL))
    rev_sig = {k: {} for k in REV_FAC}
    for d in rb:
        cols = {k: {} for k in REV_FAC}
        for s in pool[d]:
            arr = rm._revenue_np_cache.get(s)
            if arr is None:
                continue
            e = rev_extra(arr, pd.Timestamp(d), 15)
            if e is None:
                continue
            for k in REV_FAC:
                v = e.get(k, np.nan)
                if np.isfinite(v):
                    cols[k][s] = v
        for k in REV_FAC:
            rev_sig[k][d] = pd.Series(cols[k], dtype=float)

    FACS = list(PANEL_FAC) + REV_FAC
    def fac_series(name, d, i, syms):
        if name in PANEL_FAC:
            return PANEL_FAC[name].iloc[i].reindex(syms)
        return rev_sig[name][d].reindex(syms)

    # ── 逐 rebalance 計 IC / 五分位 / 正交 ──
    ic = {k: [] for k in FACS}; icyr = {k: [] for k in FACS}
    q1 = {k: [] for k in FACS}; q5 = {k: [] for k in FACS}; cov = {k: [] for k in FACS}
    ortho_accum = None; ortho_n = 0
    rbl = list(rb)
    for t in range(len(rbl) - 1):
        d, d1 = rbl[t], rbl[t + 1]; i = ip[d]
        syms = pool[d]
        fwd = (panel.loc[d1, syms] / panel.loc[d, syms] - 1).replace([np.inf, -np.inf], np.nan)
        fwd = fwd.dropna()
        if len(fwd) < 40:
            continue
        valid = fwd.index
        fac_df = pd.DataFrame({k: fac_series(k, d, i, valid) for k in FACS})
        fr = fwd.rank()
        rk = fac_df.rank()
        for k in FACS:
            m = fac_df[k].notna()
            n = int(m.sum())
            if n >= 40 and fac_df.loc[m, k].std() > 0:
                ic[k].append(rk.loc[m, k].corr(fr.loc[m]))
                icyr[k].append((d.year, rk.loc[m, k].corr(fr.loc[m])))
                cov[k].append(n)
                # 五分位
                try:
                    qq = pd.qcut(fac_df.loc[m, k], 5, labels=False, duplicates="drop")
                    g = fwd.loc[m].groupby(qq).mean()
                    if 0 in g.index and g.index.max() in g.index:
                        q1[k].append(g.loc[g.index.min()]); q5[k].append(g.loc[g.index.max()])
                except Exception:
                    pass
        # 正交（rank corr）
        oc = rk.corr()
        ortho_accum = oc if ortho_accum is None else ortho_accum.add(oc, fill_value=0)
        ortho_n += 1

    rows = []
    for k in FACS:
        s = pd.Series(ic[k]).dropna()
        if len(s) == 0:
            continue
        icir = s.mean() / s.std() if s.std() > 0 else np.nan
        tstat = np.sqrt(len(s)) * s.mean() / s.std() if s.std() > 0 else np.nan
        hit = (s > 0).mean() * 100
        s_ex = pd.Series([v for (y, v) in icyr[k] if y != 2023 and np.isfinite(v)])
        ic_ex = s_ex.mean() if len(s_ex) else np.nan
        qa = np.mean(q1[k]) * 100 if q1[k] else np.nan
        qb = np.mean(q5[k]) * 100 if q5[k] else np.nan
        rows.append(dict(factor=k, IC=s.mean(), IC_ex2023=ic_ex, ICIR=icir, t=tstat,
                         hit=hit, Q1ret=qa, Q5ret=qb, Q5_Q1=qb - qa, cov=int(np.median(cov[k]))))
    summ = pd.DataFrame(rows).sort_values("t", key=lambda x: x.abs(), ascending=False)
    out = ROOT / "results" / "_factor_archive_1e8"; out.mkdir(parents=True, exist_ok=True)
    summ.to_csv(out / "ic_summary.csv", index=False, encoding="utf-8-sig")
    ortho = (ortho_accum / ortho_n)
    ortho.to_csv(out / "ortho_matrix.csv", encoding="utf-8-sig")

    print("=" * 104)
    print(f"因子歸檔 IC（1億池, 月頻 2018-25, 池中位 {int(np.median([len(pool[d]) for d in rb]))}）— 依 |t| 排序")
    print("=" * 104)
    print(f"  {'因子':<14}{'IC':>8}{'IC去23':>8}{'ICIR':>7}{'t':>7}{'命中%':>7}{'Q1報酬':>8}{'Q5報酬':>8}{'Q5-Q1':>8}{'覆蓋':>6}")
    for _, r in summ.iterrows():
        print(f"  {r['factor']:<14}{r['IC']:>+8.4f}{r['IC_ex2023']:>+8.4f}{r['ICIR']:>+7.3f}{r['t']:>+7.2f}"
              f"{r['hit']:>6.0f}%{r['Q1ret']:>+7.1f}%{r['Q5ret']:>+7.1f}%{r['Q5_Q1']:>+7.1f}%{r['cov']:>6}")
    print(f"\n存檔：{out/'ic_summary.csv'} 與 ortho_matrix.csv")
    print("[判讀] |t|>2 真訊號；Q5-Q1 正且 Q1 很差→可當 gate(排Q1)；IC 微弱正且彼此正交→組合料。")


if __name__ == "__main__":
    main()
