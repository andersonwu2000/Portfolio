import { renderHook, waitFor } from "@testing-library/react-native";
import type { OrderInfo } from "@quant/shared";

const mockList = jest.fn<Promise<OrderInfo[]>, [string | undefined]>();
jest.mock("@quant/shared", () => ({
  orders: { list: (filter?: string) => mockList(filter) },
}));

import { useOrders } from "../useOrders";

const sampleOrders: OrderInfo[] = [
  {
    id: "o1",
    symbol: "AAPL",
    side: "BUY",
    quantity: 100,
    price: 150,
    status: "filled",
    filled_qty: 100,
    filled_avg_price: 150,
    commission: 0.21,
    created_at: "2024-06-15T10:00:00Z",
    strategy_id: "momentum",
  },
  {
    id: "o2",
    symbol: "MSFT",
    side: "SELL",
    quantity: 50,
    price: null,
    status: "open",
    filled_qty: 0,
    filled_avg_price: 0,
    commission: 0,
    created_at: "2024-06-15T11:00:00Z",
    strategy_id: "mean_revert",
  },
];

describe("useOrders", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("starts in loading state", () => {
    mockList.mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(() => useOrders());
    expect(result.current.loading).toBe(true);
  });

  it("returns order data after fetch", async () => {
    mockList.mockResolvedValue(sampleOrders);
    const { result } = renderHook(() => useOrders());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual(sampleOrders);
  });

  it("sets error on fetch failure", async () => {
    mockList.mockRejectedValue(new Error("Server error"));
    const { result } = renderHook(() => useOrders());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe("Server error");
  });

  it("passes open filter to API", async () => {
    mockList.mockResolvedValue([]);
    renderHook(() => useOrders("open"));
    await waitFor(() => expect(mockList).toHaveBeenCalledWith("open"));
  });

  it("passes undefined for 'all' filter", async () => {
    mockList.mockResolvedValue([]);
    renderHook(() => useOrders("all"));
    await waitFor(() => expect(mockList).toHaveBeenCalledWith(undefined));
  });

  it("starts with empty data array", () => {
    mockList.mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(() => useOrders());
    expect(result.current.data).toEqual([]);
  });
});
