# 規劃 vs 實際：系統對照分析

**日期**: 2026-03-24（最後更新）
**對照文件**: `Project Requirements (Archived).md`（v3.0 架構設計）vs 目前程式碼

---

## 目錄

1. [總覽](#1-總覽)
2. [設計哲學：高度一致](#2-設計哲學高度一致)
3. [逐模組對照](#3-逐模組對照)
4. [規劃有但未實作的功能](#4-規劃有但未實作的功能)
5. [實作有但規劃沒提的功能](#5-實作有但規劃沒提的功能)
6. [架構偏離與取捨](#6-架構偏離與取捨)
7. [開發路線圖進度](#7-開發路線圖進度)
8. [結論](#8-結論)

---

## 1. 總覽

| 面向 | 規劃完成度 | 說明 |
|------|:---------:|------|
| 設計哲學 | 95% | v3 的簡化原則幾乎完全貫徹 |
| 目錄結構 | 95% | 新增 notifications/, scheduler/, data/fundamentals.py |
| 領域模型 | 90% | 核心一致，新增 settlement, repository |
| 策略框架 | 95% | 幾乎完美實現，加入基本面因子 |
| 風控引擎 | 95% | 規則完整，kill switch 已串接回測 |
| 回測引擎 | 90% | 7 helpers 重構、validation、WFA、dividend |
| API 層 | 80% | 核心端點齊全，新增 portfolio CRUD、WFA、rebalance preview |
| 前端 | 70% | Web + Mobile 完整，桌面版砍掉 |
| 資料庫 | 70% | 4 migrations，portfolio persistence 完成 |
| 資料源 | 85% | Yahoo + FinMind (OHLCV + 基本面 + 產業) |
| 實盤交易 | 5% | 僅有空殼介面 |

---

## 2. 設計哲學：高度一致

v3 規劃的五條設計原則在實作中**全部被遵循**：

| 原則 | 實際體現 |
|------|---------|
| 能用函式解決的不用類別 | ✅ 風控規則用 function factory，不用繼承 |
| 能用單體解決的不用微服務 | ✅ 全部在單一 FastAPI 進程內 |
| 能用 SQL 解決的不用自建存儲 | ✅ SQLAlchemy + 單一 DB |
| 能用標準庫解決的不用框架 | ✅ 未引入 Celery/Redis/Kafka |
| 每層抽象必須有具體收益 | ✅ Strategy ABC + DataFeed ABC + FundamentalsProvider ABC，每個有明確理由 |

量化面的不可簡化原則：

| 原則 | 狀態 | 備註 |
|------|:----:|------|
| 時間因果性 | ✅ | `Context` 截斷 + `HistoricalFeed.set_current_date()` + execution_delay |
| 市場摩擦建模 | ✅ | fixed/sqrt 滑價、手續費、稅、T+N 結算、整股單位 |
| 統計嚴謹性 | ✅ | `validation.py` 因果性/確定性/敏感度檢查 + WFA |
| 風控獨立性 | ✅ | risk 模組不依賴 strategy，kill switch 已串接 |

---

## 3. 逐模組對照

### 3.1 領域模型 (`src/domain/`)

| 規劃 | 實際 | 差異 |
|------|------|------|
| `Instrument` 含 `asset_class`, `currency`, `multiplier` | `Instrument` 僅有 `symbol`, `lot_size`, `tick_size` | 🟡 簡化了，砍掉期貨/選擇權 |
| `Order` 含 `client_order_id`（冪等鍵） | `Order` 無冪等鍵 | 🟡 缺失，實盤時需補 |
| `Portfolio` 含 `as_of: datetime` | `Portfolio` 有 `nav_sod`, `daily_drawdown`, `settled_cash`, `pending_settlements` | 🟢 比規劃更豐富 |
| 無持久化 | `PortfolioRepository` 完整 CRUD | 🟢 額外完成 |
| 全部使用 `Decimal` | ✅ 一致 | ✅ |

### 3.2 策略框架 (`src/strategy/`)

| 規劃 | 實際 | 差異 |
|------|------|------|
| `Strategy` ABC: `name()` + `on_bar(ctx) → dict[str, float]` | ✅ 完全一致 | ✅ |
| `Context`: `bars()`, `universe()`, `portfolio()` | `Context`: 加 `fundamentals()`, `sector()` | 🟢 比規劃更豐富 |
| 因子計算是純函式 | ✅ `factors.py` 含技術因子 + 基本面因子 | ✅ |
| 8 個策略 | ✅ 8 個策略，multi_factor/sector_rotation 已升級 | ✅ |

### 3.3 風控引擎 (`src/risk/`)

| 規劃 | 實際 | 差異 |
|------|------|------|
| 聲明式 `RiskRule` + function factory | ✅ 完全一致 | ✅ |
| Kill Switch (日回撤 5%) | ✅ 已串接回測主迴圈 | ✅ |
| `RiskMonitor` 即時監控 | ✅ 推送 WebSocket 告警 + 通知 | ✅ |

### 3.4 執行層 (`src/execution/`)

| 規劃 | 實際 | 差異 |
|------|------|------|
| `SimBroker` 完整 | ✅ fixed/sqrt 滑價、手續費、稅、成交量、零量拒單 | ✅ |
| `PaperBroker`：即時模擬 | ❌ 空殼 | 🔴 Phase 4 |
| 券商 Adapter | ❌ 未實作 | 🔴 Phase 4 |
| 次日成交 | ✅ `execution_delay` + open price 成交 | ✅ |

### 3.5 回測引擎 (`src/backtest/`)

| 規劃 | 實際 | 差異 |
|------|------|------|
| `BacktestEngine.run()` | ✅ 重構為 7 helper methods | ✅ |
| `analytics.py` 績效分析 | ✅ + 拒單統計 | ✅ |
| `validation.py` 品質檢查 | ✅ causality + determinism + sensitivity | ✅ |
| `walk_forward.py` WFA | ✅ rolling train/test | 🟢 規劃外額外完成 |
| 股利模擬 | ✅ enable_dividends + ex-date injection | 🟢 規劃外 |
| ffill 限制 | ✅ max_ffill_days=5 | 🟢 規劃外 |
| 滑價敏感度測試 | ✅ check_sensitivity() | ✅ |

### 3.6 資料源 (`src/data/`)

| 規劃 | 實際 | 差異 |
|------|------|------|
| Yahoo Finance | ✅ YahooFeed + ParquetDiskCache + LRU | ✅ |
| FinMind OHLCV | ✅ FinMindFeed + finmind_common 共用工具 | ✅ |
| FinMind 基本面 | ✅ PE/PB/ROE/月營收/股利/產業 | ✅ |
| FundamentalsProvider ABC | ✅ | ✅ |
| 工廠函式 create_feed() | ✅ | ✅ |
| 品質檢查 | ✅ quality.py 7 項檢查 | ✅ |
| EODHD/TEJ | ❌ 未實作 | 🟡 按需付費整合 |

### 3.7 API 層 (`src/api/`)

| 端點群組 | 狀態 | 說明 |
|----------|:----:|------|
| 認證 + 使用者管理 | ✅ | JWT + Cookie + 角色 + 帳號鎖定 |
| 投資組合 (in-memory) | ✅ | GET /portfolio, /positions |
| 投資組合 (persisted) | ✅ | CRUD + trades + rebalance-preview |
| 策略 | ✅ | GET /strategies |
| 訂單 | ✅ | GET/POST /orders |
| 回測 | ✅ | POST /backtest + walk-forward |
| 風控 | ✅ | /risk/status, /rules, /alerts |
| 系統 | ✅ | /health, /status, /metrics (Prometheus) |
| WebSocket | ✅ | 4 channels + asyncio.gather broadcast |

### 3.8 前端

| 規劃 | 實際 | 差異 |
|------|------|------|
| Web (React + Tailwind) | ✅ + Card 元件統一 + JWT 安全 | ✅ |
| 桌面 (Tauri) | ❌ 砍掉 | 🟡 可接受 |
| Mobile (React Native) | ✅ + 角色權限 + 下單表單 + i18n | ✅ |
| 共享包 @quant/shared | ✅ | ✅ |
| 前端測試 | ✅ Vitest (web) + Jest (mobile) | ✅ |

### 3.9 基礎設施

| 規劃 | 實際 | 差異 |
|------|------|------|
| PostgreSQL | ✅ + SQLite 開發模式 | ✅ |
| Alembic migrations | ✅ 4 版 | ✅ |
| Docker multi-stage | ✅ | ✅ |
| CI/CD | ✅ lint + test + typecheck + build | ✅ |
| 通知系統 | ✅ Discord + LINE + Telegram | 🟢 規劃外 |
| 排程系統 | ✅ APScheduler | 🟢 規劃外 |
| Prometheus 監控 | ✅ | 🟢 規劃外 |

---

## 4. 規劃有但未實作的功能

### 🔴 重要缺失

| 功能 | 影響 |
|------|------|
| **PaperBroker（即時模擬交易）** | 無法在即時數據上驗證策略 |
| **券商 Adapter（實盤交易）** | 無法自動下單 |
| **桌面應用 (Tauri)** | 無低延遲交易監控介面（Mobile App 部分替代） |
| **SDK 自動生成** | 前端手寫 API client |
| **Notebook 整合** | 研究員無法在 Jupyter 中操作 |

### 🟡 次要缺失

| 功能 | 影響 |
|------|------|
| 漲跌幅限制模擬 | 極端行情回測不精確 |
| 策略啟停 API | 無法從 UI 控制策略運行 |
| 訂單撤銷 | 無法取消已提交的訂單 |
| Cursor-based 分頁 | 大量數據查詢可能卡住 |
| CVXPY 投資組合優化 | 目前用簡化版 |

---

## 5. 實作有但規劃沒提的功能

| 功能 | 位置 | 價值 |
|------|------|------|
| **FinMind 基本面整合** | `src/data/sources/finmind_fundamentals.py` | PE/PB/ROE/月營收/股利/產業分類 |
| **通知系統** | `src/notifications/` | Discord/LINE/Telegram 多管道推播 |
| **排程系統** | `src/scheduler/` | APScheduler 自動觸發策略 |
| **Walk-Forward Analysis** | `src/backtest/walk_forward.py` | 策略穩健性驗證 |
| **回測品質驗證** | `src/backtest/validation.py` | 因果性/確定性/敏感度自動檢查 |
| **ParquetDiskCache** | `src/data/sources/parquet_cache.py` | 共用磁碟快取，消除重複碼 |
| **Portfolio 持久化** | `src/domain/repository.py` + migration 004 | 重啟可復原 |
| **股利模擬** | `src/backtest/engine.py` | 回測中依 ex-date 注入現金 |
| **ffill 限制** | `src/backtest/engine.py` | 防止停牌股假交易 |
| **完整使用者管理** | `src/api/routes/auth.py` | CRUD + 5 級角色 + 帳號鎖定 |
| **httpOnly Cookie** | `src/api/auth.py` | 比純 JWT Bearer 更安全 |
| **Token revocation** | migration 003 | 可撤銷 JWT |
| **i18n（中/英）** | `apps/web/src/i18n/`, `apps/mobile/src/i18n/` | 完整多語系 |
| **Mobile 角色權限** | `apps/mobile/src/hooks/useAuth.ts` | JWT 解碼 + hasRole() |
| **Mobile 下單表單** | `apps/mobile/src/components/OrderForm.tsx` | Alert 確認 + 角色保護 |
| **Prometheus 監控** | `src/api/app.py` | API + backtest metrics |
| **Card 元件統一** | `apps/web/src/shared/ui/Card.tsx` | 17 個元件統一風格 |
| **E2E 測試 (Playwright)** | `apps/web/e2e/` | 規劃只提單元/整合 |
| **策略確定性回歸測試** | `tests/unit/test_strategy_regression.py` | 固定輸入 → 精確權重 |

---

## 6. 架構偏離與取捨

### 6.1 刻意的簡化（合理）

| 規劃 | 實際 | 判斷 |
|------|------|------|
| TimescaleDB | 普通 PostgreSQL | ✅ 標的 < 1000，不需時序優化 |
| Zustand | React hooks + context | ✅ 應用不夠複雜 |
| Typer CLI | argparse | ✅ 減少依賴 |
| CVXPY | 手寫 equal/signal/risk_parity | ✅ 先跑起來 |

### 6.2 意外偏離→已修復

| 原始偏離 | 現狀 |
|----------|------|
| Kill switch 未串接 | ✅ 已修復 |
| validation.py 未實作 | ✅ 已實作 |
| 持倉不持久化 | ✅ 已實作 |
| 滑價模型太簡化 | ✅ 已升級 sqrt model |
| 回測引擎無直接測試 | ✅ 已有完整測試 |

### 6.3 仍存在的偏離

| 規劃 | 實際 | 影響 |
|------|------|------|
| `Instrument` 含完整資產資訊 | 僅 `symbol` 字串 | 加期貨/選擇權時需重構 |
| `Order.strategy_id` | 訂單無策略來源 | 多策略時無法歸因 |
| 回測獨立進程 | API 內 ThreadPoolExecutor | 大回測可能拖慢 API |

---

## 7. 開發路線圖進度

### Phase 0 — 地基 ✅ 完成
### Phase 1 — 能跑回測 ✅ 完成
### Phase 2 — API 和基礎 UI ✅ 完成（超出規劃）
### Phase 3 — 風控 + 紙上交易 ⚠️ 風控完成、紙上交易未做

| 項目 | 狀態 |
|------|:----:|
| 風控引擎 + 規則 + kill switch | ✅ |
| WebSocket + 通知 | ✅ |
| PaperBroker | ❌ |
| 即時行情接入 | ❌ |

### Phase 4 — 實盤 ❌ 未開始
### Phase 5 — 打磨 ⚠️ 部分跳躍完成

| 項目 | 狀態 |
|------|:----:|
| Mobile App | ✅ |
| 投資組合優化器 | ❌ |
| TCA 分析 | ❌ |
| 績效歸因 | ❌ |

---

## 8. 結論

### 做得好的地方

1. **設計哲學貫徹** — v3 簡化原則完全遵循
2. **策略框架** — 完美實現 + 加入基本面因子
3. **風控引擎** — function factory + kill switch 完整串接
4. **回測品質** — validation + WFA + sqrt 滑價 + 次日成交
5. **實用化基礎設施** — 持久化、通知、排程全部到位
6. **超出規劃** — 通知系統、WFA、回測驗證、Prometheus、股利模擬

### 主要偏離

1. **Phase 3/4 的 PaperBroker / 實盤** — 核心目標但未動
2. **桌面應用砍掉** — Mobile App 部分替代
3. **Notebook 整合未做** — 研究員必須用 Web UI

### 一句話總結

> 系統已從「回測研究平台」成功進化為「實用的投資輔助工具」。Phase 0-2 完整完成、Phase 3 的基礎設施（持久化、通知、排程）到位。距離「半自動化投資」只差券商 API 介接（Phase 4）。架構品質高，349+ 測試覆蓋，基本面策略可用。
