# 系統現況追蹤報告書

> **報告日期**: 2026-03-25
> **版本**: v3.0
> **當前階段**: Phase D（系統整合 + 風控升級）
> **代碼庫**: 2026-03-22 起始, master 分支

---

## 1. 技術棧

| 層級 | 技術 |
|------|------|
| 後端 | Python 3.12, mypy strict, FastAPI + Uvicorn |
| 資料庫 | PostgreSQL 16 / SQLite, SQLAlchemy + Alembic |
| 前端 | React 18 + Vite + Tailwind (Web), React Native + Expo 52 (Mobile) |
| 共享 | @quant/shared TypeScript 套件 |
| CI | 9 jobs: lint, test, typecheck, build, e2e |

## 2. 模組清單

### 後端 (93 .py, ~14,700 LOC)

| 模組 | 檔案 | LOC | 功能 |
|------|------|-----|------|
| `src/alpha/` | 11 | 2,158 | Alpha 研究：因子中性化/正交化/分位數回測/Pipeline/regime/attribution |
| `src/allocation/` | 4 | 713 | 戰術配置：宏觀因子/跨資產信號/戰術引擎 |
| `src/portfolio/` | 4 | 757 | 組合最佳化(6 法)/風險模型(LW)/幣別對沖 |
| `src/backtest/` | 6 | 2,162 | 回測引擎/分析/報表/驗證/walk-forward |
| `src/strategy/` | 8 | 1,401 | 策略引擎/因子庫(11)/最佳化器/研究工具/MultiAssetStrategy |
| `src/api/` | 19 | 2,746 | REST API(11 路由) + WebSocket + Alpha + Allocation 端點 |
| `src/data/` | 6 | 895 | Yahoo/FinMind/FRED 數據源 + 快取 |
| `src/domain/` | 3 | 637 | Instrument/Portfolio/Position/Order/Trade 領域模型 |
| `src/risk/` | 4 | 573 | 風控引擎(10 規則) + kill switch + 監控 |
| `src/execution/` | 4 | 384 | SimBroker(含乘數/per-instrument 費率) + OMS |
| `src/instrument/` | 3 | 331 | InstrumentRegistry + 自動推斷 + 預設模板 |
| 其他 | 21 | 1,645 | CLI/通知/排程/config/logging |

### 策略 (9 個)

| 策略 | 位置 | 邏輯 |
|------|------|------|
| Momentum | `strategies/momentum.py` | 12-1 動量 |
| Mean Reversion | `strategies/mean_reversion.py` | Z-score 均值回歸 |
| RSI Oversold | `strategies/rsi_oversold.py` | RSI < 30 超賣 |
| MA Crossover | `strategies/ma_crossover.py` | 均線交叉 |
| Multi-Factor | `strategies/multi_factor.py` | 動量+價值+品質 |
| Pairs Trading | `strategies/pairs_trading.py` | 統計套利 |
| Sector Rotation | `strategies/sector_rotation.py` | 板塊輪動 |
| Alpha | `src/alpha/strategy.py` | 可配置因子管線 |
| Multi-Asset | `src/strategy/multi_asset.py` | 兩層配置(戰術→Alpha→最佳化) |

### 前端

| 套件 | 頁面 | 說明 |
|------|------|------|
| `apps/web/` | 10 | Dashboard/Portfolio/Strategies/Orders/Backtest/Alpha/**Allocation**/Risk/Settings/Admin |
| `apps/mobile/` | 7 tabs | Dashboard/Backtest/Alpha/Strategies/Orders/Risk/Settings |
| `apps/shared/` | — | 型別/API 客戶端/WebSocket/format utils |

### 測試 (40 .py, ~7,950 LOC, 555 tests)

Backend: 40 test files (pytest)
Web: 18 (Vitest) + 3 E2E (Playwright)
Mobile: 14 (Jest)
Shared: 4 (Vitest)

## 3. 功能完成度

| 領域 | 狀態 | 備註 |
|------|------|------|
| 回測引擎 | ✅ | 多資產/多幣別/FX 時序/40+ 指標 |
| 數據源 | ✅ | Yahoo + FinMind + FRED |
| Alpha 研究 | ✅ | 11 因子/中性化/正交化/分位數/Pipeline |
| 戰術配置 | ✅ | 宏觀四因子 + 跨資產信號 + regime |
| 組合最佳化 | ✅ | EW/IV/RP/MVO/BL/HRP + Ledoit-Wolf |
| 幣別對沖 | ✅ | 分級對沖策略 + HedgeRecommendation |
| 兩層整合 | ✅ | MultiAssetStrategy 串接 allocation→alpha→optimizer |
| 風控 | ✅ | 10 規則 + kill switch + 跨資產規則 |
| Instrument Registry | ✅ | 自動推斷 symbol → asset_class/market/currency |
| 多幣別 Portfolio | ✅ | nav_in_base(fx)/currency_exposure/per-bar FX |
| 前端 | ✅ | 10 頁 Web + 7 tabs Mobile + Allocation 頁 |
| 券商對接 | ❌ | 僅 SimBroker |
| 即時行情 | ❌ | market 頻道未接入 |
| Paper Trading | ❌ | 配置項存在但無完整流程 |

## 4. 設計缺陷追蹤

| 編號 | 狀態 | 問題 |
|------|------|------|
| D-01~D-07 | ✅ | Phase A 管線整合 (乘數/費率/FX/Registry/Yahoo) |
| D-08 | 延後 | Alpha Pipeline GIL 限制 |
| D-10~D-13 | ✅ | 模型統一/expiry bug/nav_in_base/mypy errors |
| D-14~D-16 | ✅ | FX per-bar/總權重驗證/FRED ffill 上限 |
| D-17 | ✅ | MultiAssetStrategy 打通兩層流程 |
| D-18 | ✅ | 跨資產風控規則 (asset_class/currency/leverage) |
| D-19 | Phase E | 期貨展期模擬 |

## 5. 開發路線圖

- **Phase A~C** ✅：基礎設施 + 跨資產 Alpha + 組合最佳化
- **Phase D** ✅：系統整合 + 風控升級 + MultiAssetStrategy + Allocation 前端
- **Phase E** 待開始：券商對接 (Shioaji + IB) + Paper Trading + 即時行情
