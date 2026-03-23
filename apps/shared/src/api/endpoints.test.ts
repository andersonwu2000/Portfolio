import { auth, system, portfolio, strategies, orders, backtest, risk } from "./endpoints";

// Mock the client module
vi.mock("./client", () => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
}));

import { get, post, put } from "./client";
const mockGet = get as ReturnType<typeof vi.fn>;
const mockPost = post as ReturnType<typeof vi.fn>;
const mockPut = put as ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
});

describe("auth endpoints", () => {
  it("login posts api_key to /api/v1/auth/login", async () => {
    mockPost.mockResolvedValue({ access_token: "tok", token_type: "bearer" });
    const result = await auth.login("my-key");
    expect(mockPost).toHaveBeenCalledWith("/api/v1/auth/login", { api_key: "my-key" });
    expect(result).toEqual({ access_token: "tok", token_type: "bearer" });
  });

  it("logout posts to /api/v1/auth/logout", async () => {
    mockPost.mockResolvedValue({ detail: "ok" });
    await auth.logout();
    expect(mockPost).toHaveBeenCalledWith("/api/v1/auth/logout", {});
  });
});

describe("system endpoints", () => {
  it("health calls GET /api/v1/system/health", async () => {
    mockGet.mockResolvedValue({ status: "ok" });
    const result = await system.health();
    expect(mockGet).toHaveBeenCalledWith("/api/v1/system/health");
    expect(result).toEqual({ status: "ok" });
  });

  it("status calls GET /api/v1/system/status", async () => {
    mockGet.mockResolvedValue({ uptime: 100 });
    await system.status();
    expect(mockGet).toHaveBeenCalledWith("/api/v1/system/status");
  });
});

describe("portfolio endpoints", () => {
  it("get calls GET /api/v1/portfolio", async () => {
    mockGet.mockResolvedValue({ cash: 10000 });
    const result = await portfolio.get();
    expect(mockGet).toHaveBeenCalledWith("/api/v1/portfolio");
    expect(result).toEqual({ cash: 10000 });
  });

  it("positions calls GET /api/v1/portfolio/positions", async () => {
    mockGet.mockResolvedValue([{ symbol: "AAPL" }]);
    const result = await portfolio.positions();
    expect(mockGet).toHaveBeenCalledWith("/api/v1/portfolio/positions");
    expect(result).toEqual([{ symbol: "AAPL" }]);
  });
});

describe("strategies endpoints", () => {
  it("list unwraps strategies array", async () => {
    mockGet.mockResolvedValue({ strategies: [{ name: "momentum" }] });
    const result = await strategies.list();
    expect(mockGet).toHaveBeenCalledWith("/api/v1/strategies");
    expect(result).toEqual([{ name: "momentum" }]);
  });

  it("get fetches a single strategy by id", async () => {
    mockGet.mockResolvedValue({ name: "momentum" });
    await strategies.get("abc");
    expect(mockGet).toHaveBeenCalledWith("/api/v1/strategies/abc");
  });
});

describe("orders endpoints", () => {
  it("list calls GET /api/v1/orders without filter", async () => {
    mockGet.mockResolvedValue([]);
    await orders.list();
    expect(mockGet).toHaveBeenCalledWith("/api/v1/orders");
  });

  it("list calls GET /api/v1/orders?status=open with filter", async () => {
    mockGet.mockResolvedValue([]);
    await orders.list("open");
    expect(mockGet).toHaveBeenCalledWith("/api/v1/orders?status=open");
  });

  it("create posts order to /api/v1/orders", async () => {
    const req = { symbol: "AAPL", side: "buy", quantity: 10 };
    mockPost.mockResolvedValue({ id: "1" });
    await orders.create(req as any);
    expect(mockPost).toHaveBeenCalledWith("/api/v1/orders", req);
  });
});

describe("backtest endpoints", () => {
  it("submit posts backtest request", async () => {
    const req = { strategy: "momentum", universes: ["AAPL"] };
    mockPost.mockResolvedValue({ task_id: "t1" });
    await backtest.submit(req as any);
    expect(mockPost).toHaveBeenCalledWith("/api/v1/backtest", req);
  });

  it("status gets backtest status by task id", async () => {
    mockGet.mockResolvedValue({ task_id: "t1", status: "running" });
    await backtest.status("t1");
    expect(mockGet).toHaveBeenCalledWith("/api/v1/backtest/t1");
  });

  it("result gets backtest result by task id", async () => {
    mockGet.mockResolvedValue({ returns: [] });
    await backtest.result("t1");
    expect(mockGet).toHaveBeenCalledWith("/api/v1/backtest/t1/result");
  });
});

describe("risk endpoints", () => {
  it("rules calls GET /api/v1/risk/rules", async () => {
    mockGet.mockResolvedValue([{ name: "max_position" }]);
    await risk.rules();
    expect(mockGet).toHaveBeenCalledWith("/api/v1/risk/rules");
  });

  it("toggleRule puts enabled state", async () => {
    mockPut.mockResolvedValue({ name: "max_position", enabled: false });
    await risk.toggleRule("max_position", false);
    expect(mockPut).toHaveBeenCalledWith("/api/v1/risk/rules/max_position", { enabled: false });
  });

  it("alerts calls GET /api/v1/risk/alerts", async () => {
    mockGet.mockResolvedValue([]);
    await risk.alerts();
    expect(mockGet).toHaveBeenCalledWith("/api/v1/risk/alerts");
  });

  it("killSwitch posts to /api/v1/risk/kill-switch", async () => {
    mockPost.mockResolvedValue({ detail: "activated" });
    await risk.killSwitch();
    expect(mockPost).toHaveBeenCalledWith("/api/v1/risk/kill-switch");
  });
});
