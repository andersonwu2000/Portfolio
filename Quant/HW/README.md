# Quantitative Research — Assignment 1

## 研究目的

作業涵蓋**機率論基礎、Copula 理論與實證分析**。以台股雙雄（TSMC 2330 + 鴻海 2317）為資料集，驗證金融時序的 stylized facts（厚尾、偏態、尾部依賴），並落實 mean-covariance class 的幾何直覺（PCA、confidence ellipsoid、線性投影）。

## 四大主題

| Part | 主題 | 關鍵工具 |
|------|------|---------|
| I  | 機率論與推導 | Lognormal mode、Quantile elicitability（pinball loss）、Markov property |
| II | Copula 理論與模擬 | PIT、Sklar's theorem、Gaussian copula、Student's $t$-copula |
| III | 均值–共變異數分析 | 仿射不變性、殘差性質、Total covariance、Normal coincidence、線性投影 |
| IV | 實證分析 | TSMC + 鴻海 2019–2024 日報酬：厚尾、偏態、Q-Q、尾部依賴 |

## 核心發現

| 指標 | 數值 | 意涵 |
|------|-----:|------|
| Excess kurtosis（TSMC / 鴻海） | $+3.38$ / $+5.56$ | 強厚尾，Jarque–Bera 強拒絕常態 |
| Pearson $\rho$ | $+0.448$ | 線性共變（傳統指標） |
| Kendall $\tau$ | $+0.317$ | 序列共變（rank-based） |
| 聯合下尾點數（$u_i < 0.10$） | 68 pts | vs 獨立假設預期 15 pts ⇒ 下尾依賴 |
| Linear projection $\beta$ | $+0.455$ | $\text{TSMC} = 0.0008 + 0.455 \cdot \text{鴻海} + \varepsilon$ |
| $R^2$ | $0.20$ | 鴻海僅解釋 TSMC 20% 變異，80% 在 idiosyncratic |

Q8 （Section 6.3 非線性合成範例）另外指出：partial correlation 與 raw correlation 可能**符號相反**（Simpson 式效應），且若共享非線性項（如 $\cos\varepsilon_2$）以相反符號進入兩變量，殘差**無法**達成 $\perp\!\!\!\perp_{mc}$。

## 附件

- `assignment1.ipynb` — 答題 notebook（推導 + Python 模擬 + 實證分析，9 題）
- `assignment1_en.md` / `assignment1_zh.md` — 題目（中英對照）
- `Figure_1.png` ~ `Figure_9.png` — notebook 引用圖表

## 題目 ↔ 圖對照

| 圖 | 對應題目 | 內容 |
|----|---------|------|
| `Figure_1.png` | Q1b | Lognormal PDF + mode/median/mean 標記 |
| `Figure_2.png` | Q5a | Gaussian copula 5 種 $\rho$ |
| `Figure_3.png` | Q5b | Student's $t$-copula（變 $\nu$ / $\rho$） |
| `Figure_4.png` | Q9a | 經驗分佈 vs Gaussian 疊加 |
| `Figure_5.png` | Q9c | Q-Q plot vs 常態 |
| `Figure_6.png` | Q9d | Raw scatter + 經驗 copula + 尾部依賴 |
| `Figure_7.png` | Q6b | 95% Confidence ellipsoid + PC1/PC2 |
| `Figure_8.png` | Q8   | Partial uncorrelation（Section 6.3） |
| `Figure_9.png` | Q9e  | TSMC 對鴻海線性投影 + 殘差 |
