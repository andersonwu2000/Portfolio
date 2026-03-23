import type { Page } from "@playwright/test";

/**
 * Mock API responses using Playwright's native route interception.
 * Replaces the previous MSW-based approach which doesn't work in Playwright's browser context.
 */
export async function setupApiMocks(page: Page) {
  // ── Auth ──────────────────────────────────────────────────────────
  await page.route("**/api/v1/auth/login", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: "test.eyJyb2xlIjoiYWRtaW4ifQ.sig",
        token_type: "bearer",
      }),
    }),
  );

  await page.route("**/api/v1/auth/logout", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ detail: "logged out" }),
    }),
  );

  // ── System ────────────────────────────────────────────────────────
  await page.route("**/api/v1/system/health", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok", version: "0.1.0" }),
    }),
  );

  await page.route("**/api/v1/system/status", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        mode: "paper",
        uptime_seconds: 9000,
        strategies_running: 2,
        data_source: "yahoo",
        database: "connected",
      }),
    }),
  );

  await page.route("**/api/v1/system/metrics", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        uptime_seconds: 9000,
        total_requests: 1234,
        active_ws_connections: 3,
        strategies_running: 2,
        active_backtests: 0,
      }),
    }),
  );

  // ── Portfolio ─────────────────────────────────────────────────────
  await page.route("**/api/v1/portfolio", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        nav: 1_052_340.5,
        cash: 203_120.75,
        gross_exposure: 849_219.75,
        net_exposure: 849_219.75,
        positions_count: 3,
        daily_pnl: 4_230.1,
        daily_pnl_pct: 0.004,
        positions: [
          {
            symbol: "AAPL",
            quantity: 500,
            avg_cost: 178.5,
            market_price: 192.3,
            market_value: 96_150,
            unrealized_pnl: 6_900,
            weight: 0.091,
          },
          {
            symbol: "MSFT",
            quantity: 300,
            avg_cost: 410.2,
            market_price: 425.8,
            market_value: 127_740,
            unrealized_pnl: 4_680,
            weight: 0.121,
          },
          {
            symbol: "NVDA",
            quantity: 200,
            avg_cost: 880.0,
            market_price: 950.5,
            market_value: 190_100,
            unrealized_pnl: 14_100,
            weight: 0.181,
          },
        ],
        as_of: "2024-12-20T16:00:00Z",
      }),
    }),
  );

  // ── Strategies ────────────────────────────────────────────────────
  await page.route("**/api/v1/strategies", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        strategies: [
          { name: "momentum", status: "running", pnl: 12_450.3 },
          { name: "mean_reversion", status: "stopped", pnl: -1_200.5 },
        ],
      }),
    }),
  );

  // ── Orders ────────────────────────────────────────────────────────
  await page.route("**/api/v1/orders", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "ord-new-001",
          symbol: "TSLA",
          side: "BUY",
          quantity: 50,
          price: 250.0,
          status: "pending",
          filled_qty: 0,
          filled_avg_price: 0,
          commission: 0,
          created_at: new Date().toISOString(),
          strategy_id: "manual",
        }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: "ord-001",
          symbol: "AAPL",
          side: "BUY",
          quantity: 100,
          price: 190.0,
          status: "filled",
          filled_qty: 100,
          filled_avg_price: 190.05,
          commission: 19.01,
          created_at: "2024-12-20T10:30:00Z",
          strategy_id: "momentum",
        },
        {
          id: "ord-002",
          symbol: "MSFT",
          side: "SELL",
          quantity: 50,
          price: null,
          status: "pending",
          filled_qty: 0,
          filled_avg_price: 0,
          commission: 0,
          created_at: "2024-12-20T11:00:00Z",
          strategy_id: "momentum",
        },
        {
          id: "ord-003",
          symbol: "GOOGL",
          side: "BUY",
          quantity: 75,
          price: 175.0,
          status: "cancelled",
          filled_qty: 0,
          filled_avg_price: 0,
          commission: 0,
          created_at: "2024-12-20T09:15:00Z",
          strategy_id: "mean_reversion",
        },
        {
          id: "ord-004",
          symbol: "NVDA",
          side: "BUY",
          quantity: 30,
          price: 945.0,
          status: "rejected",
          filled_qty: 0,
          filled_avg_price: 0,
          commission: 0,
          created_at: "2024-12-20T08:45:00Z",
          strategy_id: "momentum",
        },
        {
          id: "ord-005",
          symbol: "AMZN",
          side: "BUY",
          quantity: 200,
          price: 195.5,
          status: "filled",
          filled_qty: 200,
          filled_avg_price: 195.48,
          commission: 39.1,
          created_at: "2024-12-19T14:20:00Z",
          strategy_id: "mean_reversion",
        },
      ]),
    });
  });

  // ── Risk ──────────────────────────────────────────────────────────
  await page.route("**/api/v1/risk/rules", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { name: "max_position_weight", enabled: true },
        { name: "max_drawdown", enabled: true },
        { name: "sector_concentration", enabled: false },
      ]),
    }),
  );

  await page.route("**/api/v1/risk/alerts", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          timestamp: "2024-12-20T15:30:00Z",
          rule_name: "max_position_weight",
          severity: "warning",
          metric_value: 0.22,
          threshold: 0.2,
          action_taken: "order_rejected",
          message: "NVDA weight 22% exceeds 20% limit",
        },
        {
          timestamp: "2024-12-20T14:00:00Z",
          rule_name: "max_drawdown",
          severity: "info",
          metric_value: 0.035,
          threshold: 0.05,
          action_taken: "none",
          message:
            "Portfolio drawdown at 3.5%, approaching 5% kill switch",
        },
      ]),
    }),
  );

  await page.route("**/api/v1/risk/kill-switch", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Kill switch activated" }),
    }),
  );

  // ── Backtest ──────────────────────────────────────────────────────
  await page.route("**/api/v1/backtest", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          task_id: "test-1",
          status: "completed",
          strategy_name: "momentum",
          total_return: 0.234,
          annual_return: 0.187,
          sharpe: 1.85,
          max_drawdown: -0.089,
          total_trades: 42,
          progress_current: null,
          progress_total: null,
          error: null,
        }),
      });
    }
    return route.continue();
  });

  await page.route("**/api/v1/backtest/test-1", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        task_id: "test-1",
        status: "completed",
        strategy_name: "momentum",
        total_return: 0.234,
        annual_return: 0.187,
        sharpe: 1.85,
        max_drawdown: -0.089,
        total_trades: 42,
        progress_current: null,
        progress_total: null,
        error: null,
      }),
    }),
  );

  await page.route("**/api/v1/backtest/test-1/result", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        strategy_name: "momentum",
        start_date: "2023-01-01",
        end_date: "2024-01-01",
        initial_cash: 1_000_000,
        total_return: 0.234,
        annual_return: 0.187,
        sharpe: 1.85,
        sortino: 2.1,
        calmar: 2.6,
        max_drawdown: -0.089,
        max_drawdown_duration: 23,
        volatility: 0.15,
        total_trades: 42,
        win_rate: 0.62,
        total_commission: 3_420.5,
        nav_series: [
          { date: "2023-01-03", nav: 1_000_000 },
          { date: "2023-04-01", nav: 1_045_000 },
          { date: "2023-07-01", nav: 1_098_000 },
          { date: "2023-10-01", nav: 1_150_000 },
          { date: "2024-01-01", nav: 1_234_000 },
        ],
      }),
    }),
  );
}
