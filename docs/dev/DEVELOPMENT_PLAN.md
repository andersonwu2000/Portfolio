# 開發計畫書

> **版本**: v4.0
> **日期**: 2026-03-25
> **目標**: 涵蓋多個可自動交易市場的投資組合研究與優化系統
> **可交易市場**: 台股、美股、ETF（含債券/商品 ETF 代理）、台灣期貨、美國期貨
> **不納入**: 直接債券交易（OTC）、實體商品、零售外匯
> **架構設計**: `docs/dev/MULTI_ASSET_ARCHITECTURE.md`

---

## 階段概覽

```
Phase A ✅       Phase B ✅       Phase C ✅       Phase D ✅       Phase E (當前)
基礎設施          跨資產 Alpha     組合最佳化        系統整合+風控     實盤交易
─────────       ────────────    ─────────       ─────────       ─────────
Instrument      宏觀因子模型      6 種最佳化器     MultiAssetStrategy  券商對接
多幣別 Portfolio  跨資產信號       風險模型(LW)     跨資產風控規則      Paper Trading
DataFeed 擴展   戰術配置引擎      幣別對沖         FX per-bar 修復    即時行情
FRED 數據源     API + 前端型別                    Allocation 前端    多資產前端
管線整合                                         因子/型別同步
```

---

## Phase A~D：已完成摘要

### Phase A：多資產基礎設施 ✅
InstrumentRegistry (自動推斷) + 多幣別 Portfolio (`nav_in_base`, `currency_exposure`) + DataFeed 擴展 (FX time series) + FRED 數據源 + 管線整合 (weights_to_orders 乘數, SimBroker per-instrument 費率) + 模型統一

### Phase B：跨資產 Alpha ✅
`src/allocation/`: MacroFactorModel (成長/通膨/利率/信用) + CrossAssetSignals (動量/波動率/均值回歸) + TacticalEngine (戰略 + 宏觀 + 跨資產 + regime → 資產類別權重) + `POST /api/v1/allocation`

### Phase C：組合最佳化 ✅
`src/portfolio/`: PortfolioOptimizer (EW/IV/RP/MVO/BL/HRP) + RiskModel (Ledoit-Wolf 收縮共變異數 + 風險貢獻) + CurrencyHedger (分級對沖)

### Phase D：系統整合 + 風控 ✅
- MultiAssetStrategy (`src/strategy/multi_asset.py`): 兩層配置策略，已註冊至 registry
- 跨資產風控: `max_asset_class_weight`, `max_currency_exposure`, `max_gross_leverage`
- Bug fixes: FX per-bar 更新 / 總權重驗證 / FRED ffill(66)
- 前端: AllocationPage + 11 因子同步 + 跨資產風控規則 + i18n (en/zh)

---

## Phase E：實盤交易（當前目標）

### E1: 券商對接

| 市場 | 券商 | SDK | 狀態 |
|------|------|-----|------|
| 台股 | 永豐金 | Shioaji | 待實作 |
| 美股 | Interactive Brokers | ib_insync | 待實作 |

**實作方式**: `src/execution/` 新增 `shioaji_broker.py` / `ib_broker.py`，實作 `Broker` ABC。

> 券商評估見 `docs/dev/BROKER_API_EVALUATION.md`

### E2: 即時行情

填補 WebSocket `market` 頻道，連接 Shioaji / IB 的即時行情 push。

### E3: Paper Trading

完整紙上交易循環：策略 → 權重 → 下單 → 模擬成交 → 持倉更新。使用 SimBroker 後端但透過 API 操作。

### E4: 期貨展期模擬

`src/execution/roll.py`: 自動偵測近月到期 → roll 到下月合約 → 展期成本納入績效。

### E5: 績效歸因

擴展 `src/alpha/attribution.py`: 資產配置歸因 + 選股歸因 + 匯率歸因。

### Phase E 完成標誌

能在台股 + 美股上執行一次完整的 Paper Trading 循環：
1. 策略產出權重 → 2. 券商 API 下單 → 3. 即時行情更新 → 4. 持倉同步 → 5. 績效報告

---

## 里程碑時間線

| 日期 | 里程碑 |
|------|--------|
| 2026-03-22~23 | 股票交易系統 (回測+7策略+風控+API+Web+Mobile) |
| 2026-03-24 | Alpha 研究層 (11 模組+API+前端) |
| 2026-03-24 | Phase A (基礎設施+管線整合+模型統一) |
| 2026-03-24 | Phase B (宏觀因子+跨資產信號+戰術配置+API) |
| 2026-03-24 | Phase C (6 種最佳化+風險模型+幣別對沖) |
| 2026-03-24 | 測試覆蓋補齊 (+29 tests: 期貨成本/golden value/E2E/FX) |
| 2026-03-25 | Phase D (MultiAssetStrategy+跨資產風控+FX 修復+Allocation 前端) |

---

## 設計缺陷追蹤

| 編號 | 狀態 | 問題 |
|------|------|------|
| D-01~D-07 | ✅ | Phase A 管線整合 |
| D-08 | 延後 | Alpha Pipeline GIL 限制 |
| D-10~D-18 | ✅ | 模型統一/bug fixes/FX/權重/風控/整合 |
| D-19 | Phase E | 期貨展期模擬 |
