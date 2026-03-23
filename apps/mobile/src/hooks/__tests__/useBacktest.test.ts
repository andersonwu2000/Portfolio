import { renderHook, act, waitFor } from "@testing-library/react-native";
import type { BacktestRequest, BacktestSummary, BacktestResult } from "@quant/shared";

const mockSubmit = jest.fn<Promise<BacktestSummary>, [BacktestRequest]>();
const mockPoll = jest.fn();

jest.mock("@quant/shared", () => ({
  backtest: { submit: (req: BacktestRequest) => mockSubmit(req) },
  pollBacktestResult: (...args: unknown[]) => mockPoll(...args),
}));

import { useBacktest } from "../useBacktest";

const sampleRequest: BacktestRequest = {
  strategy: "momentum",
  universe: ["AAPL", "MSFT"],
  start: "2023-01-01",
  end: "2024-01-01",
  initial_cash: 100000,
  params: {},
  slippage_bps: 5,
  commission_rate: 0.001425,
  rebalance_freq: "daily",
};

const sampleSummary: BacktestSummary = {
  task_id: "task-1",
  status: "running",
  strategy_name: "momentum",
  total_return: null,
  annual_return: null,
  sharpe: null,
  max_drawdown: null,
  total_trades: null,
  progress_current: null,
  progress_total: null,
  error: null,
};

const sampleResult: BacktestResult = {
  strategy_name: "momentum",
  start_date: "2023-01-01",
  end_date: "2024-01-01",
  initial_cash: 100000,
  total_return: 0.25,
  annual_return: 0.25,
  sharpe: 1.5,
  sortino: 2.0,
  calmar: 1.8,
  max_drawdown: -0.1,
  max_drawdown_duration: 30,
  volatility: 0.15,
  total_trades: 120,
  win_rate: 0.55,
  total_commission: 170,
  nav_series: null,
};

describe("useBacktest", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("starts with running=false and no result", () => {
    const { result } = renderHook(() => useBacktest());
    expect(result.current.running).toBe(false);
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("sets running=true during submission", async () => {
    mockSubmit.mockReturnValue(new Promise(() => {})); // never resolves
    const { result } = renderHook(() => useBacktest());
    act(() => {
      result.current.submit(sampleRequest);
    });
    expect(result.current.running).toBe(true);
  });

  it("returns result on successful backtest", async () => {
    mockSubmit.mockResolvedValue(sampleSummary);
    mockPoll.mockResolvedValue({ status: "completed", result: sampleResult });

    const { result } = renderHook(() => useBacktest());
    await act(async () => {
      await result.current.submit(sampleRequest);
    });

    expect(result.current.result).toEqual(sampleResult);
    expect(result.current.running).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("sets error on timeout", async () => {
    mockSubmit.mockResolvedValue(sampleSummary);
    mockPoll.mockResolvedValue({ status: "timeout" });

    const { result } = renderHook(() => useBacktest());
    await act(async () => {
      await result.current.submit(sampleRequest);
    });

    expect(result.current.error).toBe("Backtest timed out");
    expect(result.current.result).toBeNull();
  });

  it("sets error on failure", async () => {
    mockSubmit.mockResolvedValue(sampleSummary);
    mockPoll.mockResolvedValue({ status: "failed" });

    const { result } = renderHook(() => useBacktest());
    await act(async () => {
      await result.current.submit(sampleRequest);
    });

    expect(result.current.error).toBe("Backtest failed");
  });

  it("sets error on submit rejection", async () => {
    mockSubmit.mockRejectedValue(new Error("API unreachable"));

    const { result } = renderHook(() => useBacktest());
    await act(async () => {
      await result.current.submit(sampleRequest);
    });

    expect(result.current.error).toBe("API unreachable");
    expect(result.current.running).toBe(false);
  });
});
