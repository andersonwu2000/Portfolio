# Analysis — 研究分析與圖表

支撐研究結論的各項分析與圖表。
本目錄說明這裡有哪些分析、各自處理什麼問題。

## 各腳本在做什麼

下列腳本各自回答研究中的一個問題，依主題分組。

### 訊號本身有沒有預測力

| 腳本 | 在做什麼 |
|------|---------|
| `analyze_quantile_spread.py` | 每月把投資池依訊號強弱分成五等分，比較各組後續報酬，並檢視「多最強、空最弱」的中性價差是否正報酬、低 beta、小回撤——這是區分「訊號真實」與「實作不佳」最直接的測試。 |
| `analyze_signal_decay.py` | 計算訊號預測力（IC）隨時間與隨市場狀態的變化，判斷訊號是否在衰減，以及衰減屬於「資金擁擠」還是「特定市場環境才有效」。 |

### 超額報酬是否站得住腳

| 腳本 | 在做什麼 |
|------|---------|
| `analyze_fair_benchmark.py` | 以「等權持有當期所有可投資股票」作為無技能基準，透過 CAPM 迴歸分離出純選股的超額報酬（alpha）與市場暴露（beta）。 |
| `analyze_startdate_sensitivity.py` | 改變回測起點，檢視「輸給 0050」是否取決於起算時間，並以 CAPM 做風險調整後的對照。 |
| `analyze_param_grid.py` | 對持股檔數與營收成長門檻做網格掃描，檢查鄰近參數表現是否平滑相近——藉此排除過擬合。 |
| `analyze_robustness.py` | 對主策略淨值做三項後處理檢定：逐年走勢、Deflated Sharpe Ratio（修正多重檢定偏差），以及對同條件無技能投組的殘差 alpha。 |

### 換手率與交易成本

| 腳本 | 在做什麼 |
|------|---------|
| `analyze_churn_source.py` | 將每次換股的賣出換手拆解成數個來源（被篩網剔除、排名跌出、大盤縮倉、權重微調），找出換手率的真正成因。 |
| `analyze_turnover_opt.py` | 測試兩種降低換手的結構性做法（進出場緩衝、放慢換股頻率），檢視能否補上淨報酬的缺口。 |
| `analyze_quarterly_recheck.py` | 以正確的換手率算法重新比較月／季／半年換股的成本與績效。 |

### 不同訊號與配置的比較

| 腳本 | 在做什麼 |
|------|---------|
| `analyze_newhigh_vs_accel.py` | 「營收創新高」與「營收加速度」兩種訊號的正面對決。 |
| `analyze_newhigh_yearly.py` | 逐年拆解上述兩種訊號的表現，檢視近年是否轉差。 |
| `analyze_ensemble.py` | 在純因子形式下，測試組合多個因子能否勝過單一最佳因子。 |
| `analyze_validate_ensemble.py` | 把上述組合放回完整策略（含篩網、權重、換股規則）中，驗證優勢是否依然成立。 |
| `analyze_holdings_sweep.py` | 掃描持股檔數，呈現集中與分散之間的取捨。 |

### 外部交叉驗證

| 腳本 | 在做什麼 |
|------|---------|
| `analyze_finlab_compare.py` | 在相同時段（2007–2018）以本程式重現第三方平台 FinLab 的結果，互相印證程式的可信度。 |

## 圖表

繪圖腳本在 `visualization/`；產生的圖（淨值、回撤、IC、分位數、基準比較、參數穩健性等）收於 `../Report/figures/`，逐張說明見 `Report/README.md`。

## 結構

```
Analysis/
├── analyze_*.py     各項分析的程式碼
├── visualization/   繪圖腳本（圖輸出到 ../Report/figures/）
└── results/         分析產生的數據結果
```
