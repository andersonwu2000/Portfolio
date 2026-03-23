import React from "react";
import { render, screen } from "@testing-library/react-native";
import { OrderRow } from "../OrderRow";
import type { OrderInfo } from "@quant/shared";
import { success, danger } from "@/src/theme/colors";

const makeOrder = (overrides: Partial<OrderInfo> = {}): OrderInfo => ({
  id: "order-1",
  symbol: "TSLA",
  side: "BUY",
  quantity: 50,
  price: 250.0,
  status: "filled",
  filled_qty: 50,
  filled_avg_price: 250.0,
  commission: 0.35,
  created_at: "2024-06-15T10:30:00Z",
  strategy_id: "momentum",
  ...overrides,
});

describe("OrderRow", () => {
  it("renders the order symbol", () => {
    render(<OrderRow order={makeOrder()} />);
    expect(screen.getByText("TSLA")).toBeTruthy();
  });

  it("renders BUY side text", () => {
    render(<OrderRow order={makeOrder({ side: "BUY" })} />);
    expect(screen.getByText("BUY")).toBeTruthy();
  });

  it("renders SELL side text", () => {
    render(<OrderRow order={makeOrder({ side: "SELL" })} />);
    expect(screen.getByText("SELL")).toBeTruthy();
  });

  it("applies green color for BUY side", () => {
    render(<OrderRow order={makeOrder({ side: "BUY" })} />);
    const sideEl = screen.getByText("BUY");
    const style = Array.isArray(sideEl.props.style)
      ? Object.assign({}, ...sideEl.props.style.filter(Boolean))
      : sideEl.props.style;
    expect(style.color).toBe(success);
  });

  it("applies red color for SELL side", () => {
    render(<OrderRow order={makeOrder({ side: "SELL" })} />);
    const sideEl = screen.getByText("SELL");
    const style = Array.isArray(sideEl.props.style)
      ? Object.assign({}, ...sideEl.props.style.filter(Boolean))
      : sideEl.props.style;
    expect(style.color).toBe(danger);
  });

  it("renders quantity and price", () => {
    render(<OrderRow order={makeOrder({ quantity: 50, price: 250 })} />);
    expect(screen.getByText("50 @ $250.00")).toBeTruthy();
  });

  it("renders MKT for null price (market orders)", () => {
    render(<OrderRow order={makeOrder({ price: null })} />);
    expect(screen.getByText("50 @ MKT")).toBeTruthy();
  });

  it("renders order status", () => {
    render(<OrderRow order={makeOrder({ status: "filled" })} />);
    expect(screen.getByText("filled")).toBeTruthy();
  });
});
