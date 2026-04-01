# 台股量化交易系統：從因子到策略驗證

## 研究目的

展示量化策略開發的流程：發現因子 → 建構策略 → 統計驗證。以 revenue_acceleration 因子為例。

## 三階段流程

| 階段 | 做什麼 | 關鍵產出 |
|------|--------|---------|
| **因子** | 從月營收數據計算 revenue_acceleration（近3月/近12月營收比率） | ICIR 0.44~0.58，10 年穩定 |
| **策略** | 因子 → 篩選排序 → 權重配置（等權/訊號/風險平價） | 可執行的投組權重 |
| **驗證** | 回測引擎模擬交易 + Validator 16 項統計檢定 | 通過 → 可部署 |

## 系統

- 擬真成本模型（手續費 0.1425% + 證交稅 0.3% + 根號衝擊滑價）
- 防過擬合：Deflated Sharpe Ratio、PBO (CSCV)、Bootstrap、Walk-Forward
- 硬/軟門檻分離：11 項必須通過 + 5 項參考警示

**硬門檻（11 項）：**
- 年化報酬 ≥ 8%、Sharpe ≥ 0.7、成本比率 < 50%
- 前推一致性 ≥ 60%（Walk-Forward Analysis）
- Deflated Sharpe Ratio ≥ 0.70（多重檢定校正，Bailey 2014）
- Bootstrap P(Sharpe > 0) ≥ 80%（1,000 次重抽樣）
- PBO ≤ 50%（過擬合機率，Bailey et al. 2017）
- 市場相關性 ≤ 0.80（獨立 Alpha 要求）

**軟門檻（5 項）：**
- 最大回撤 ≤ 40%、樣本外 Sharpe ≥ 0.3、CVaR(95%) ≥ -5% 等

## 附件

- `System/` — 回測引擎與驗證系統（可獨立運行，含使用範例）
- `System/GLOSSARY.md` — 術語與公式解說


## 參考文獻

1. Bailey, D. H., & López de Prado, M. (2014). "The Deflated Sharpe Ratio." *The Journal of Portfolio Management*, 40(5).
2. Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2017). "The Probability of Backtest Overfitting." *Journal of Computational Finance*, 20(4).
3. DeMiguel, V., Garlappi, L., & Uppal, R. (2009). "Optimal Versus Naive Diversification." *The Review of Financial Studies*, 22(5).