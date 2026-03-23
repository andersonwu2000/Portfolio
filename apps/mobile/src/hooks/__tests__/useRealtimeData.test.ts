import { renderHook, waitFor } from "@testing-library/react-native";

// Track WSManager instances for assertions
const mockConnect = jest.fn();
const mockDisconnect = jest.fn();
let subscribeCb: ((data: unknown) => void) | null = null;
const mockSubscribe = jest.fn((cb: (data: unknown) => void) => {
  subscribeCb = cb;
  return jest.fn(); // unsubscribe
});

jest.mock("@quant/shared", () => ({
  WSManager: jest.fn().mockImplementation(() => ({
    connect: mockConnect,
    disconnect: mockDisconnect,
    subscribe: mockSubscribe,
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
  Object.defineProperty(rn, "AppState", {
    get: () => mockAppState,
    configurable: true,
  });
  return rn;
});

import { useRealtimeData } from "../useRealtimeData";

describe("useRealtimeData", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    subscribeCb = null;
  });

  it("fetches initial data on mount", async () => {
    const fetchFn = jest.fn().mockResolvedValue({ count: 42 });
    const mergeFn = jest.fn();

    const { result } = renderHook(() =>
      useRealtimeData(fetchFn, "portfolio", mergeFn, null),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(result.current.data).toEqual({ count: 42 });
  });

  it("sets error when fetch fails", async () => {
    const fetchFn = jest.fn().mockRejectedValue(new Error("Fetch failed"));
    const mergeFn = jest.fn();

    const { result } = renderHook(() =>
      useRealtimeData(fetchFn, "portfolio", mergeFn, null),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe("Fetch failed");
  });

  it("connects WebSocket on mount", async () => {
    const fetchFn = jest.fn().mockResolvedValue("data");
    const mergeFn = jest.fn();

    renderHook(() => useRealtimeData(fetchFn, "alerts", mergeFn, null));

    expect(mockConnect).toHaveBeenCalled();
  });

  it("subscribes to WebSocket messages", async () => {
    const fetchFn = jest.fn().mockResolvedValue("initial");
    const mergeFn = jest.fn();

    renderHook(() => useRealtimeData(fetchFn, "portfolio", mergeFn, null));

    expect(mockSubscribe).toHaveBeenCalled();
  });
});
