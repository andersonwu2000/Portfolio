"""報告繪圖輔助：把圖表代碼移出 notebook(報告本體只保留關鍵策略碼與回測邏輯)。
所有函式接收 notebook 已算好的 navs / 物件,只負責繪圖與必要的重計算(結構網格),不重複策略邏輯。
"""
import numpy as np
import pandas as pd
import itertools
import matplotlib.pyplot as plt
from liq1e8_eval_harness import g_ann

plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def _src(fig, name):
    """於圖右下角以小灰字標註繪圖函式(report_lib.py 內);讀者欲看 code 或重現此圖,
    即由上方 code cell 的 R.<函式> 與此標註定位。數值表格另由 Analysis/ 腳本重現。"""
    fig.text(0.997, 0.002, "繪圖:report_lib." + name, ha="right", va="bottom", fontsize=6, color="#9AA4AD")


def build_benchmarks(panel, vol, first_listed, rb_full, sim_full, hi,
                     eligible_at, simulate_nav, buy_hold_etf, data):
    """三個基準 navs:0050 / Top-50 大型股等權 / 等權可投資範圍。回傳 DEV 版(≤hi)與全期版(含保留樣本)。
    與 verify_strategy.top_n_equal_weight_nav **數學等價**(同 eligible_at + 同 60 日 ADV、同等權),
    但把 eligible_at(每換股日掃全市場)**只算一次**給兩個等權基準共用、且 DEV 版由全期版切片而來——
    原本 4 次 top_n(~90s)縮為 1 次 eligibility + 2 條回測。含 data-fingerprint 快取(Report/_cache),
    重跑直接載入。基準屬對照樣板(非策略本體),故其計算移至此繪圖庫、不佔報告的策略 cell。"""
    import hashlib
    import pickle
    import inspect
    from pathlib import Path
    hi = pd.Timestamp(hi)
    ip = {d: i for i, d in enumerate(panel.index)}
    out, cf = None, None
    try:
        src = inspect.getsource(build_benchmarks)                 # 邏輯指紋:本函式一改,快取即失效(避免取到過期值)
        sig = "bench|%s|%d|%s|%.8e|%s" % (panel.shape, len(rb_full), hi.date(),
                                          float(np.nansum(panel.to_numpy())), hashlib.md5(src.encode()).hexdigest()[:8])
        cdir = Path(__file__).resolve().parent / "_cache"; cdir.mkdir(exist_ok=True)
        cf = cdir / ("bench_%s.pkl" % hashlib.md5(sig.encode()).hexdigest()[:16])
        if cf.exists():
            out = pickle.load(open(cf, "rb"))
    except Exception:
        cf = None
    if out is None:
        elig = {d: eligible_at(d, panel, vol, first_listed) for d in rb_full}   # 一次(預設門檻),兩等權基準共用
        adv60 = (panel * vol).rolling(60, min_periods=1).mean().shift(1)        # = top_n 的 panel.iloc[pos-60:pos] 均值(skipna)
        def wf(n):
            def f(date, _cw, _nav):
                e = elig.get(date, [])
                if not e:
                    return {}
                a = adv60.iloc[ip[date]].reindex(e).dropna()
                top = a.sort_values(ascending=False).head(n)
                if len(top) == 0:
                    return {}
                w = 0.95 / len(top)
                return {s: w for s in top.index}
            return f
        ew_f = simulate_nav(panel, rb_full, wf(99999), 20.0, 50.0, sim_idx=sim_full)[0]
        t50_f = simulate_nav(panel, rb_full, wf(50), 20.0, 50.0, sim_idx=sim_full)[0]
        etf_f = buy_hold_etf(data, "0050.TW", sim_full)
        cut = lambda s: s[s.index <= hi]
        out = dict(ew=cut(ew_f), top50=cut(t50_f), etf=cut(etf_f),
                   ew_full=ew_f, top50_full=t50_f, etf_full=etf_f)
        if cf is not None:
            try:
                pickle.dump(out, open(cf, "wb"))
            except Exception:
                pass
    return out


def fig_main(nav_mom, nav_0050, nav_ew, nav_top50):
    """主策略 vs 多基準:淨值(對數軸) + 回撤走勢——皆為**開發期**(到 HI)。
    保留樣本(鎖盒)的揭示留到 §6.4 的 fig_lockbox(報告紀律:鎖盒封存到最後才拆,不在此提前劇透)。"""
    fig, ax = plt.subplots(figsize=(11, 4.8))
    ax.plot(nav_mom.index, nav_mom, lw=2.4, color="#E74C3C", label="雙動能(主策略) g=%.0f%%" % (g_ann(nav_mom) * 100))
    ax.plot(nav_0050.index, nav_0050, lw=1.6, ls="--", color="#3498DB", label="0050 市值大盤 g=%.0f%%" % (g_ann(nav_0050) * 100))
    ax.plot(nav_top50.index, nav_top50, lw=1.4, ls=":", color="#E67E22", label="Top-50 大型股等權 g=%.0f%%" % (g_ann(nav_top50) * 100))
    ax.plot(nav_ew.index, nav_ew, lw=1.3, ls="-.", color="#95A5A6", label="等權可投資範圍 g=%.0f%%" % (g_ann(nav_ew) * 100))
    ax.set_yscale("log"); ax.set_title("主策略 vs 多基準（淨值，對數軸，扣成本 20/50；開發期）")
    ax.set_ylabel("淨值(對數)"); ax.legend(loc="upper left"); ax.grid(alpha=.3); _src(fig, "fig_main"); plt.show()

    # 回撤(折線)獨立整列 — 主策略以填色面積為主角、基準以細虛線為背景(清楚對比,仿舊報告)
    fig, a1 = plt.subplots(figsize=(11, 3.6))
    ddm = (nav_mom / nav_mom.cummax() - 1) * 100
    a1.fill_between(ddm.index, ddm, 0, color="#E74C3C", alpha=.22)
    a1.plot(ddm.index, ddm, lw=1.9, color="#E74C3C", label="雙動能（主策略）", zorder=5)
    for nv, c, ls, lab in [(nav_0050, "#2980B9", "--", "0050 市值大盤"),
                           (nav_top50, "#E67E22", ":", "Top-50 大型股等權"),
                           (nav_ew, "#7F8C8D", "-.", "等權可投資範圍")]:
        dd = (nv / nv.cummax() - 1) * 100
        a1.plot(dd.index, dd, lw=1.0, ls=ls, color=c, alpha=.8, label=lab)
    a1.set_title("回撤走勢 (%)：主策略（填色）vs 基準（虛線）"); a1.set_ylabel("回撤 (%)")
    a1.legend(fontsize=8, ncol=2, loc="lower left"); a1.grid(alpha=.3); _src(fig, "fig_main"); plt.show()


def fig_lockbox(nav_mom_full, nav_0050_full, lock_start):
    """§6.4 保留樣本(鎖盒)揭示:lock_start(2025-06-21)起的樣本外,淨值各自重設為 1.0,雙動能 vs 0050。
    此窗為極端多頭、只讀方向(不讀絕對量級);重點=策略於從未污染的向前樣本未失效、仍領先。"""
    def seg(nv):
        s = nv[nv.index >= lock_start]
        return s / s.iloc[0] if len(s) else s
    M, Z = seg(nav_mom_full), seg(nav_0050_full)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.axvspan(M.index.min(), M.index.max(), color="#7F8C8D", alpha=.08)
    ax.plot(M.index, M, lw=2.4, color="#E74C3C", label="雙動能(主策略)")
    ax.plot(Z.index, Z, lw=1.7, ls="--", color="#3498DB", label="0050")
    ax.axhline(1, color="k", lw=.6)
    ax.set_title("保留樣本（2025-07~2026-05）：從未參與選擇的樣本外，淨值重設為 1.0")
    ax.set_ylabel("淨值（鎖盒起點 = 1.0）"); ax.legend(loc="upper left"); ax.grid(alpha=.3); _src(fig, "fig_lockbox"); plt.show()


def fig_rolling(nav_mom, nav_0050):
    """滾動 36 月 g 走勢 + 滾動 g 分佈箱型(含最差視窗)。"""
    def roll_g(nav, W=36):
        out = {}
        for s in pd.date_range(nav.index.min(), nav.index.max(), freq="MS"):
            e = s + pd.DateOffset(months=W)
            if e > nav.index.max():
                break
            out[e] = g_ann(nav[(nav.index >= s) & (nav.index <= e)])
        return pd.Series(out)

    # 滾動 36 月 g 走勢(折線)獨立整列
    fig, a1 = plt.subplots(figsize=(11, 4))
    a1.plot(roll_g(nav_mom).index, roll_g(nav_mom) * 100, lw=2, color="#E74C3C", label="雙動能")
    a1.plot(roll_g(nav_0050).index, roll_g(nav_0050) * 100, lw=1.5, ls="--", color="#3498DB", label="0050")
    a1.axhline(0, color="k", lw=.6); a1.set_title("滾動 36 月年化 g（視窗結束日）")
    a1.set_ylabel("年化 g (%)"); a1.legend(); a1.grid(alpha=.3); _src(fig, "fig_rolling"); plt.show()
    # 滾動 g 分佈(箱型)獨立
    fig, a2 = plt.subplots(figsize=(7, 4))
    bdata = [roll_g(nav_mom, 36).values * 100, roll_g(nav_0050, 36).values * 100,
             roll_g(nav_mom, 60).values * 100, roll_g(nav_0050, 60).values * 100]
    bp = a2.boxplot(bdata, tick_labels=["雙\n36月", "0050\n36月", "雙\n60月", "0050\n60月"], patch_artist=True, showfliers=False)
    for i, box in enumerate(bp["boxes"]):
        box.set_facecolor("#E74C3C" if i % 2 == 0 else "#3498DB"); box.set_alpha(.45)
    a2.axhline(0, color="k", lw=.6); a2.set_title("滾動 g 的分佈（箱型；含最差視窗）")
    a2.set_ylabel("年化 g (%)"); a2.grid(alpha=.3, axis="y"); _src(fig, "fig_rolling"); plt.show()


def fig_yearly(nav_mom, nav_0050):
    """主策略逐年:報酬(對照0050) / Sharpe / 最大回撤——三格【直向堆疊、各佔整列】(仿舊報告,清楚易讀)。
    末年(2025)為上半年(至 6/20),標為 2025H1。"""
    yrs, ret_s, ret_b, sh, mdd, partial = [], [], [], [], [], []
    ymax = nav_mom.index.year.max()
    for y in range(nav_mom.index.year.min(), ymax + 1):
        sub = nav_mom[nav_mom.index.year == y]; sub0 = nav_0050[nav_0050.index.year == y]
        if len(sub) < 20:
            continue
        r = sub.pct_change().dropna()
        yrs.append(y)
        ret_s.append((sub.iloc[-1] / sub.iloc[0] - 1) * 100)
        ret_b.append((sub0.iloc[-1] / sub0.iloc[0] - 1) * 100 if len(sub0) > 20 else np.nan)
        sh.append(r.mean() / r.std() * np.sqrt(252))
        mdd.append(-(sub / sub.cummax() - 1).min() * 100)
        partial.append(sub.index.max().month < 12)
    x = np.arange(len(yrs)); lab = [("%dH1" % y if p else str(y)) for y, p in zip(yrs, partial)]
    w = 0.4
    fig, (a1, a2, a3) = plt.subplots(3, 1, figsize=(10.5, 8.6), sharex=True)
    # ① 逐年報酬:雙動能(綠/紅) vs 0050(藍)
    a1.bar(x - w / 2, ret_s, w, color=["#27AE60" if v >= 0 else "#C0392B" for v in ret_s], label="雙動能")
    a1.bar(x + w / 2, ret_b, w, color="#3498DB", alpha=.65, label="0050")
    for xi, v in zip(x, ret_s):
        a1.annotate("%+.0f" % v, (xi - w / 2, v), ha="center", va="bottom" if v >= 0 else "top", fontsize=8)
    a1.set_title("① 逐年報酬 (%)：雙動能 vs 0050"); a1.set_ylabel("報酬 (%)"); a1.legend(fontsize=9, loc="upper right")
    # ② 逐年 Sharpe
    a2.bar(x, sh, color=["#27AE60" if v >= 0 else "#C0392B" for v in sh])
    for xi, v in zip(x, sh):
        a2.annotate("%+.2f" % v, (xi, v), ha="center", va="bottom" if v >= 0 else "top", fontsize=8)
    a2.set_title("② 逐年 Sharpe"); a2.set_ylabel("Sharpe")
    # ③ 逐年最大回撤
    a3.bar(x, mdd, color="#9B59B6")
    for xi, v in zip(x, mdd):
        a3.annotate("%.0f" % v, (xi, v), ha="center", va="bottom", fontsize=8)
    a3.set_title("③ 逐年最大回撤 (%)"); a3.set_ylabel("回撤 (%)")
    for a in (a1, a2, a3):
        a.axhline(0, color="k", lw=.6); a.grid(alpha=.3, axis="y")
    a3.set_xticks(x); a3.set_xticklabels(lab, fontsize=9)
    _src(fig, "fig_yearly"); plt.tight_layout(); plt.show()


def fig_signal_evidence(panel, rb, pool, ip, score_of, name="訊號"):
    """單一因子的橫斷面證據:分位數 spread(長條) + 滾動 12 月 IC(折線,獨立整列)。
    score_of(date) → 該換股日池內各股的因子分數(Series);對『持有至次換股日』報酬計分位/IC。"""
    from scipy.stats import spearmanr
    rbi = list(rb); ics, dts, qmat = [], [], []
    for k in range(len(rbi) - 1):
        d, dn = rbi[k], rbi[k + 1]
        score = score_of(d).dropna()
        if len(score) < 25:
            continue
        fwd = panel.loc[dn, score.index] / panel.loc[d, score.index] - 1
        m = fwd.notna()
        score, fwd = score[m], fwd[m]
        if len(score) < 25:
            continue
        ic = spearmanr(score, fwd).correlation
        if np.isfinite(ic):
            ics.append(ic); dts.append(dn)
        try:
            mn = fwd.groupby(pd.qcut(score, 5, labels=False, duplicates="drop")).mean()
            if len(mn) == 5:
                qmat.append(mn.values)
        except Exception:
            pass
    # 分位數(長條)獨立
    qm = np.array(qmat).mean(0) * 100
    fig, a = plt.subplots(figsize=(7, 4))
    a.bar(["Q1\n最弱", "Q2", "Q3", "Q4", "Q5\n最強"], qm, color=["#95A5A6"] * 4 + ["#E74C3C"])
    for i, v in enumerate(qm):
        a.annotate("%+.2f%%" % v, (i, v), ha="center", va="bottom", fontsize=9)
    a.set_title("%s分位數：後一月平均報酬（由弱到強）" % name)
    a.set_ylabel("月均報酬 (%)"); a.axhline(0, color="k", lw=.6); a.grid(alpha=.3, axis="y"); _src(fig, "fig_signal_evidence"); plt.show()
    # 滾動 12 月 IC(折線)獨立整列
    ser = pd.Series(ics, index=pd.DatetimeIndex(dts)).sort_index()
    roll = ser.rolling(12).mean()
    fig, a = plt.subplots(figsize=(11, 3.6))
    a.plot(roll.index, roll, lw=2, color="#E74C3C", label="滾動 12 月 IC")
    a.fill_between(roll.index, roll, 0, where=(roll.values > 0), color="#E74C3C", alpha=.12)
    a.axhline(ser.mean(), color="#27AE60", ls="--", lw=1, label="全期均值 IC=%.3f" % ser.mean())
    a.axhline(0, color="k", lw=.6); a.set_title("%s的滾動 12 月 IC（長期穩定為正）" % name)
    a.set_ylabel("IC"); a.legend(loc="upper left"); a.grid(alpha=.3); _src(fig, "fig_signal_evidence"); plt.show()


HOLD = [20, 25, 30, 35, 40]; EXIT = [35, 45, 55]; POOLT = [5e7, 1e8, 2e8]   # 對稱中立網格:以選用值(持股30/遲滯45/池1億)為中心等幅展開,不把選用值擺邊界(避免 PBO 美化);45 組


def compute_grid(panel, rb, sim, make_wf, pool_at, simulate_nav):
    """結構參數網格(池門檻 × 持股 × 遲滯)的 36 條淨值。算一次,供熱力圖與走動式驗證共用。
    含『行為指紋』安全快取:先以選用設定(1億/30/遲滯45)跑一條 nav,用其數值雜湊當快取鍵——
    make_wf 邏輯或底層資料一旦改變,這條 nav 即變、鍵即變、自動重算,**不會取到過期結果**。
    快取存於 Report/_cache/(可隨時安全刪除);重跑時 36 次回測縮為 1 次。"""
    import hashlib
    import pickle
    from pathlib import Path
    probe = simulate_nav(panel, rb, make_wf("pa", use_pool=pool_at(1e8), n=30, exit_rank=45),
                         20.0, 50.0, sim_idx=sim)[0]                      # 行為指紋(亦= grid 的選用格)
    grid, cf = None, None
    try:
        sig = "%s|%s|%s|%d|%.8e" % (POOLT, HOLD, EXIT, len(probe), float(np.nansum(probe.to_numpy())))
        cdir = Path(__file__).resolve().parent / "_cache"; cdir.mkdir(exist_ok=True)
        cf = cdir / ("grid_%s.pkl" % hashlib.md5(sig.encode()).hexdigest()[:16])
        if cf.exists():
            grid = pickle.load(open(cf, "rb"))
    except Exception:
        cf = None
    if grid is None:
        grid = {(1e8, 30, 45): probe}
        for thr, nh, ex in itertools.product(POOLT, HOLD, EXIT):
            if (thr, nh, ex) == (1e8, 30, 45):
                continue
            grid[(thr, nh, ex)] = simulate_nav(panel, rb, make_wf("pa", use_pool=pool_at(thr), n=nh, exit_rank=ex),
                                               20.0, 50.0, sim_idx=sim)[0]
        if cf is not None:
            try:
                pickle.dump(grid, open(cf, "wb"))
            except Exception:
                pass
    return grid


def fig_grid(grid):
    """持股×遲滯敏感度熱力圖(池=1億):選用值周圍應是平台、非孤立尖峰。"""
    gv = {k: g_ann(v) for k, v in grid.items()}
    Gmap = np.array([[gv[(1e8, nh, ex)] * 100 for ex in EXIT] for nh in HOLD])
    fig, a1 = plt.subplots(figsize=(7, 4.4))
    im = a1.imshow(Gmap, cmap="RdYlGn", aspect="auto")
    a1.set_xticks(range(len(EXIT))); a1.set_xticklabels(["遲滯%d" % e for e in EXIT])
    a1.set_yticks(range(len(HOLD))); a1.set_yticklabels(["持股%d" % nh for nh in HOLD])
    for i in range(len(HOLD)):
        for j in range(len(EXIT)):
            a1.text(j, i, "%.0f" % Gmap[i, j], ha="center", va="center", fontsize=10)
    a1.set_title("敏感度熱力圖：年化 g (%)（池=1億）"); fig.colorbar(im, ax=a1, fraction=.046)
    _src(fig, "fig_grid"); plt.tight_layout(); plt.show()


def fig_walkforward(grid, rb, nav_0050, is_years=3):
    """走動式驗證:每年僅用『過去』資料從 36 組結構參數中挑 g 最佳者,向前套用一年,串成樣本外淨值。
    與固定設定(1億/30檔/遲滯45)、0050 對照——若走動式選參≈固定設定,表參數選擇穩健、非事後挑揀。"""
    rbi = pd.DatetimeIndex(sorted(rb))
    Rdf = pd.DataFrame({k: v.reindex(rbi).pct_change() for k, v in grid.items()})
    fixed = (1e8, 30, 45)
    y0 = rbi.min().year
    picks = []          # (date, return) of walk-forward 選參
    for y in sorted(set(rbi.year)):
        if y - y0 < is_years:
            continue                                   # 起始 in-sample 暖身,尚無樣本外
        is_g = np.log1p(Rdf[Rdf.index.year < y]).mean() * 12   # 錨定:僅用過去逐配置年化 g
        cstar = is_g.idxmax()
        for d in Rdf.index[Rdf.index.year == y]:       # 該年向前套用 c*
            picks.append((d, Rdf.loc[d, cstar]))
    wf = pd.Series(dict(picks)).dropna().sort_index()
    idx = wf.index
    wf_nav = (1 + wf).cumprod()
    fix_nav = (1 + Rdf[fixed].reindex(idx)).cumprod()
    etf = nav_0050.reindex(rbi).pct_change().reindex(idx)
    etf_nav = (1 + etf).cumprod()
    def gpct(s): return np.log1p(s.dropna()).mean() * 12 * 100
    fig, ax = plt.subplots(figsize=(11, 4.4))
    ax.plot(wf_nav.index, wf_nav, lw=2.4, color="#E74C3C", label="走動式選參(樣本外) g=%.0f%%" % gpct(wf))
    ax.plot(fix_nav.index, fix_nav, lw=1.8, ls="--", color="#27AE60", label="固定設定(1億/30/45) g=%.0f%%" % gpct(Rdf[fixed].reindex(idx)))
    ax.plot(etf_nav.index, etf_nav, lw=1.5, ls="-.", color="#3498DB", label="0050 g=%.0f%%" % gpct(etf))
    ax.set_yscale("log"); ax.set_title("走動式驗證：每年僅用過去資料選參，向前套用（樣本外淨值，對數軸）")
    ax.set_ylabel("淨值(對數)"); ax.legend(); ax.grid(alpha=.3); _src(fig, "fig_walkforward"); plt.show()


def fig_liquidity_gradient(panel, rb, sim, make_wf, pool_at, simulate_nav):
    """純動能 g 隨流動性門檻的梯度——說明為何釘 1億，並呈現 size 梯度（容量限制）。"""
    THR = [5e7, 1e8, 2e8, 5e8, 1e9]
    labels = ["5千萬", "1億", "2億", "5億", "10億"]
    gs, sizes = [], []
    for thr in THR:
        pl = pool_at(thr)
        nv = simulate_nav(panel, rb, make_wf("pa", use_pool=pl), 20.0, 50.0, sim_idx=sim)[0]
        gs.append(g_ann(nv) * 100)
        sizes.append(int(np.median([len(pl[d]) for d in rb])))
    x = list(range(len(THR)))
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    ax.plot(x, gs, "-o", color="#E74C3C", lw=2)
    for i, (g, n) in enumerate(zip(gs, sizes)):
        ax.annotate("%.0f%%\n(%d檔)" % (g, n), (i, g), ha="center", va="bottom", fontsize=9)
    ax.axvline(1, color="#27AE60", ls="--", lw=1.2)
    ax.text(1.05, min(gs), "選用(1億)", color="#27AE60", fontsize=9)
    ax.set_xticks(x); ax.set_xticklabels(labels); ax.set_xlabel("流動性門檻（近 20 日均成交值／日）")
    ax.set_title("純動能年化 g 隨流動性門檻遞減（標註中位池檔數）")
    ax.set_ylabel("年化 g (%)"); ax.grid(alpha=.3, axis="y"); _src(fig, "fig_liquidity_gradient"); plt.show()


def fig_factor_tradeoff():
    """候選訊號的『預測力(左) vs 加進策略後 g 的變化(右)』雙欄對照,依預測力排序。
    一眼看到「越會預測報酬、加進去 g 掉越多」的反向。數據取自 Analysis/FACTOR_INVENTORY.md §3
    (條件 t 值、Δg over 純動能)。刻意用白話描述、不放因子代號(讀者在本報告才初識因子)。"""
    # (白話描述, 預測力 t 值, Δg over 純動能 %) — 依預測力遞減
    F = [("配息最高的", 4.6, -4.5), ("本益比最低（最便宜）的", 3.8, -5.7),
         ("法人連續買超的", 3.6, -2.2), ("營收最穩定的", 3.5, -2.4),
         ("股價波動最小的", 3.5, -5.3), ("獲利最穩定的", 3.4, +2.0),
         ("淨值最便宜的", 1.9, -5.5), ("營收成長最快的", 0.0, -1.8)]
    labels = [f[0] for f in F]; tval = [f[1] for f in F]; dg = [f[2] for f in F]
    y = np.arange(len(F))[::-1]                                   # 最強預測力排最上
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True, gridspec_kw={"wspace": 0.30})
    axL.barh(y, tval, color="#34495E", height=.6)
    axL.set_yticks(y); axL.set_yticklabels(labels, fontsize=9)
    axL.set_title("① 這個訊號預測報酬有多準（越長越準）", fontsize=10, loc="left")
    axL.set_xlabel("預測力（t 值；>2 即顯著）"); axL.grid(alpha=.3, axis="x")
    for yi, v in zip(y, tval):
        axL.annotate("%.1f" % v, (v, yi), ha="left", va="center", fontsize=8, xytext=(2, 0), textcoords="offset points")
    axR.barh(y, dg, color=["#27AE60" if v > 0 else "#C0392B" for v in dg], height=.6)
    axR.axvline(0, color="k", lw=.7)
    axR.set_title("② 加進策略後，資本成長 g 怎麼變（%）", fontsize=10, loc="left")
    axR.set_xlabel("Δg（紅 = 拖慢成長）"); axR.grid(alpha=.3, axis="x")
    for yi, v in zip(y, dg):
        axR.annotate("%+.1f" % v, (v, yi), ha="left" if v >= 0 else "right", va="center", fontsize=8,
                     xytext=(3 if v >= 0 else -3, 0), textcoords="offset points")
    fig.suptitle("越會預測報酬的訊號（①越長），加進策略後反而越拖慢成長（②越紅）", fontsize=12)
    fig.tight_layout(); plt.show()
