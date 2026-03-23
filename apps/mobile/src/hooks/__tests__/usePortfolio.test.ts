import { renderHook, waitFor } from "@testing-library/react-native";
import type { Portfolio } from "@quant/shared";

// Mock the shared API before importing the hook
const mockGet = jest.fn<Promise<Portfolio>, []>();
jest.mock("@quant/shared", () => ({
  portfolio: { get: () => mockGet() },
  WSManager: jest.fn().mockImplementation(() => ({
    connect: jest.fn(),
    disconnect: jest.fn(),
    subscribe: jest.fn(() => jest.fn()),
  })),
}));

// Mock react-native: selectively override AppState without spreading the full
// module (which triggers lazy getters that require unavailable TurboModules).
const mockAppState = {
  addEventListener: jest.fn(() => ({ remove: jest.fn() })),
  currentState: "active" as string,
};
jest.mock("react-native", () => {
  const rn = jest.requireActual("react-native/index");
  // Only override specific properties to avoid triggering lazy getters
  Object.defineProperty(rn, "AppState", {
    get: () => mockAppState,
    configurable: true,
  });
  return rn;
});

import { usePortfolio } from "../usePortfolio";

const samplePortfolio: Portfolio = {
  nav: 100000,
  cash: 50000,
  gross_exposure: 0.5,
  net_exposure: 0.5,
  positions_count: 3,
  daily_pnl: 1200,
  daily_pnl_pct: 0.012,
  positions: [],
  as_of: "2024-06-15T10:00:00Z",
};

describe("usePortfolio", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("starts in loading state", () => {
    mockGet.mockReturnValue(new Promise(() => {})); // never resolves
    const { result } = renderHook(() => usePortfolio());
    expect(result.current.loading).toBe(true);
  });

  it("returns portfolio data after fetch", async () => {
    mockGet.mockResolvedValue(samplePortfolio);
    const { result } = renderHook(() => usePortfolio());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual(samplePortfolio);
  });

  it("sets error on fetch failure", async () => {
    mockGet.mockRejectedValue(new Error("Network error"));
    const { result } = renderHook(() => usePortfolio());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe("Network error");
  });

  it("has null data initially", () => {
    mockGet.mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(() => usePortfolio());
    expect(result.current.data).toBeNull();
  });
});
