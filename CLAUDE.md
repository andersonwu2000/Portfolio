# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Quantitative trading system — monorepo containing Python backend + React web + React Native mobile. Targets Taiwan stock market defaults (commission 0.1425%, sell tax 0.3%) but works with any market via Yahoo Finance or FinMind.

**Monorepo structure:**
- `src/`, `tests/`, `strategies/`, `migrations/` — Python backend (root level)
- `apps/web/` — React 18 + Vite + Tailwind dashboard
- `apps/mobile/` — React Native + Expo 52 mobile app
- `apps/shared/` — `@quant/shared` TypeScript package (types, API client, WS manager, format utils)

Frontend workspace managed by bun (`apps/package.json` workspaces).

## Commands

```bash
# === Backend ===
make test                    # pytest tests/ -v
make lint                    # ruff check + mypy strict
make dev                     # API with hot reload (port 8000)
make api                     # production API
make backtest ARGS="--strategy momentum -u AAPL -u MSFT --start 2023-01-01 --end 2024-12-31"
make migrate                 # alembic upgrade head

# Single test
pytest tests/unit/test_risk.py -v
pytest tests/unit/test_risk.py::TestMaxPositionWeight::test_approve_within_limit -v

# CLI
python -m src.cli.main backtest --strategy momentum -u AAPL --start 2023-01-01 --end 2024-12-31
python -m src.cli.main server
python -m src.cli.main status
python -m src.cli.main factors

# === Frontend ===
make install-apps            # bun install (all frontend packages)
make web                     # web dev server (port 3000)
make mobile                  # expo dev server
make web-build               # production build
make web-typecheck           # tsc --noEmit
make mobile-typecheck        # tsc --noEmit

# === Full stack ===
make start                   # backend + web in parallel
scripts/start.bat            # Windows: backend + web in separate windows

# === Docker ===
docker compose up -d         # API (port 8000) + PostgreSQL
docker compose down          # stop all services
```

## Architecture

**Data flow**: DataFeed → Strategy.on_bar() → target weights → RiskEngine → SimBroker/Broker → Trade → Portfolio update

Key design decisions:
- **Strategy returns target weight dicts** (`dict[str, float]`), not orders. `weights_to_orders()` in `src/strategy/engine.py` handles the conversion.
- **Risk rules are pure function factories** in `src/risk/rules.py` — no inheritance. Each returns a `RiskRule` dataclass. The engine runs rules sequentially; first REJECT stops evaluation.
- **Time causality**: `Context` wraps `DataFeed` + `Portfolio` and truncates data to `current_time` during backtest. `HistoricalFeed.set_current_date()` enforces this at the feed level.
- **All monetary values use `Decimal`**, never `float`.
- **Timezone handling**: All DatetimeIndex data is normalized to tz-naive UTC. Both `HistoricalFeed.load()` and `YahooFeed._download()` strip timezone info.

**Module boundaries**:
- `src/domain/models.py` — Frozen value objects (Instrument, Bar) + mutable aggregates (Position, Order, Portfolio, Trade). Portfolio supports T+N settlement (`pending_settlements`, `settled_cash`).
- `src/domain/repository.py` — `PortfolioRepository` for persisted portfolio CRUD (SQLAlchemy, single JOIN queries).
- `src/strategy/` — Strategy ABC (`on_bar()` → weights), factor library (pure functions including fundamental factors `value_pe`, `value_pb`, `quality_roe`), optimizers (equal_weight, signal_weight, risk_parity)
- `src/risk/` — RiskEngine executes declarative rules; `check_order()` for singles, `check_orders()` for batch filtering, `kill_switch()` at 5% daily drawdown (integrated into backtest loop)
- `src/execution/` — SimBroker (fixed/sqrt slippage models, commission/tax, price limits, volume checks, T+N settlement), `apply_trades()` updates Portfolio from Trade list
- `src/backtest/engine.py` — Orchestrates: download data → iterate trading dates → call strategy → risk check → execute → update portfolio. Engine `run()` delegates to 7 helper methods (`_refresh_bar_cache`, `_process_settlements`, `_execute_pending_orders`, `_execute_kill_switch`, `_inject_dividends_impl`, `_do_rebalance`, `_snap_nav`). Supports execution delay, dividend simulation, ffill limit.
- `src/backtest/walk_forward.py` — Walk-forward analysis with rolling train/test windows.
- `src/backtest/validation.py` — Causality, determinism, and sensitivity checks for backtest quality verification.
- `src/data/sources/` — `YahooFeed`, `FinMindFeed` (TW stocks), factory `create_feed()`. Shared `ParquetDiskCache` for disk caching. `FinMindFundamentals` provides PE/PB/ROE/revenue/dividends/sector.
- `src/data/fundamentals.py` — `FundamentalsProvider` ABC for fundamental data.
- `src/notifications/` — Multi-channel notifications (Discord, LINE, Telegram) with trade/rebalance/alert formatting.
- `src/scheduler/` — APScheduler-based job scheduling for daily snapshots and weekly rebalance checks.
- `src/api/` — FastAPI REST + WebSocket. `AppState` singleton holds runtime state. JWT auth with role hierarchy (viewer < researcher < trader < risk_manager < admin). Prometheus metrics via `prometheus-fastapi-instrumentator`.

**Adding a new strategy**: Create a file in `strategies/`, subclass `Strategy` from `src/strategy/base.py`, implement `name()` and `on_bar(ctx) -> dict[str, float]`. Register it in `_resolve_strategy()` in both `src/api/routes/backtest.py` and `src/cli/main.py`.

**Adding a new data source**: Create a file in `src/data/sources/`, subclass `DataFeed` from `src/data/feed.py`, implement `get_bars()`, `get_latest_price()`, `get_universe()`. Output: `DataFrame[open, high, low, close, volume]` + tz-naive `DatetimeIndex`. Register in `create_feed()` factory in `src/data/sources/__init__.py`.

## API Layer

**Routes** (`src/api/routes/`): auth, admin, portfolio, strategies, orders, backtest, risk, system — all mounted under `/api/v1`.

**Key endpoints**:
- `POST /api/v1/backtest` — Run backtest
- `POST /api/v1/backtest/walk-forward` — Walk-forward analysis
- `GET/POST/DELETE /api/v1/portfolio/saved` — Persisted portfolio CRUD
- `POST /api/v1/portfolio/saved/{id}/rebalance-preview` — Suggested trades via `weights_to_orders()`
- `GET /api/v1/portfolio/saved/{id}/trades` — Trade history

**Middleware & cross-cutting concerns**:
- `src/api/middleware.py` — AuditMiddleware logs all mutation requests (POST/PUT/DELETE) with user, path, status, duration
- `src/api/auth.py` — JWT token issuance + API key verification; role hierarchy enforcement
- Rate limiting via slowapi (60 requests/minute default, 10/minute for backtest)
- CORS configured via `QUANT_ALLOWED_ORIGINS`
- Prometheus metrics via `/metrics` endpoint

**WebSocket** (`src/api/ws.py`): channels — `portfolio`, `alerts`, `orders`, `market`. Token-based auth (optional in dev mode). Ping/pong keep-alive. Broadcast uses `asyncio.gather` with 5s timeout and dead connection cleanup.

**Logging** (`src/logging_config.py`): Structured logging via structlog. Supports `text` and `json` output formats, configured by `QUANT_LOG_FORMAT`.

## Frontend Architecture

**Shared package** (`apps/shared/`):
- `src/types/` — TypeScript interfaces matching backend Pydantic schemas
- `src/api/client.ts` — Platform-agnostic HTTP client with `ClientAdapter` injection (each platform provides its own auth/storage)
- `src/api/ws.ts` — `WSManager` with auto-reconnect and exponential backoff; URL builder injected via `initWs()`
- `src/api/endpoints.ts` — Typed API endpoint definitions (1:1 with backend routes)
- `src/utils/format.ts` — Number/currency/date formatters

**Platform adapters** (keep platform-specific code out of shared):
- Web: `apps/web/src/core/api/client.ts` — localStorage for API key, browser-relative URLs, Vite proxy
- Mobile: `apps/mobile/src/api/client.ts` — Expo SecureStore for credentials, configurable base URL
- Color helpers (`pnlColor`) stay per-platform: web uses Tailwind classes, mobile uses hex colors

**Key pattern**: Web and mobile barrel files (`@core/api/index.ts`, etc.) re-export from `@quant/shared`. Feature code imports from `@core/*` — never directly from `@quant/shared`. This keeps feature code platform-unaware while allowing platform-specific extensions.

**Web UI patterns**:
- Shared `<Card>` component for consistent card styling across all pages
- JWT role extracted from token (not localStorage) via `extractRoleFromJwt()`
- `PageSkeleton` for loading states

**Mobile patterns**:
- Role-based access control via `useAuth` hook (`role`, `hasRole()`)
- `OrderForm` component with Alert confirmation dialog
- Role-gated features: Kill Switch (risk_manager), rule toggles (risk_manager)

**Web frontend tests**: Vitest with jsdom (`apps/web/vitest.config.ts`). Test files colocated (e.g. `BacktestPage.test.tsx`, `RiskPage.test.tsx`, `AdminPage.test.tsx`).

## Infrastructure

**Database**: PostgreSQL 16 (SQLite for development). Migrations managed by Alembic (`migrations/`). 4 migrations: initial schema, users, token revocation, portfolio persistence.

**Docker**: Multi-stage Dockerfile (Python 3.12-slim, non-root user). `docker-compose.yml` runs `api` + `db` services with health checks and persistent volumes.

**CI/CD** (`.github/workflows/ci.yml`):
- `backend-lint` — ruff check + mypy strict
- `backend-test` — pytest (349 tests)
- `web-typecheck` — tsc --noEmit
- `web-build` — vite build (depends on typecheck)
- `mobile-typecheck` — tsc --noEmit

## Configuration

All config via `QUANT_` prefixed env vars or `.env` file (see `.env.example`). Defined in `src/config.py` as Pydantic Settings. Access via `get_config()` singleton; use `override_config()` in tests.

Key config additions:
- `data_source`: `"yahoo"` (default) or `"finmind"` — selects data feed
- `data_cache_size`: LRU cache size for in-memory bar data (default 128)
- `finmind_token`: FinMind API token (optional, increases rate limit)
- `tw_lot_size`: Taiwan stock lot size (default 1000 for round lots, set 1 for odd lots)
- `settlement_days`: T+N settlement simulation (default 0 = disabled)
- `max_ffill_days`: Forward-fill limit for missing data (default 5)
- `scheduler_enabled`, `rebalance_cron`: APScheduler config
- Notification config: `discord_webhook_url`, `line_notify_token`, `telegram_bot_token`, `telegram_chat_id`
