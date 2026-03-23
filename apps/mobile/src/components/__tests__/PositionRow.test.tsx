import React from "react";
import { render, screen } from "@testing-library/react-native";
import { PositionRow } from "../PositionRow";
import type { Position } from "@quant/shared";
import { success, danger, textSecondary } from "@/src/theme/colors";

// Mock the format utils to isolate component behavior
jest.mock("../../utils/format", () => ({
  fmtCurrency: (v: number) => (v >= 0 ? `$${v.toFixed(2)}` : `-$${Math.abs(v).toFixed(2)}`),
  fmtPct: (v: number) => `${(v * 100).toFixed(2)}%`,
  pnlColor: (v: number) => {
    if (v > 0) return "#22C55E";
    if (v < 0) return "#EF4444";
    return "#94A3B8";
  },
}));

const makePosition = (overrides: Partial<Position> = {}): Position => ({
  symbol: "AAPL",
  quantity: 100,
  avg_cost: 150.0,
  market_price: 160.0,
  market_value: 16000.0,
  unrealized_pnl: 1000.0,
  weight: 0.25,
  ...overrides,
});

describe("PositionRow", () => {
  it("renders the stock symbol", () => {
    render(<PositionRow position={makePosition()} />);
    expect(screen.getByText("AAPL")).toBeTruthy();
  });

  it("renders quantity and avg cost", () => {
    render(<PositionRow position={makePosition()} />);
    expect(screen.getByText("100 shares @ $150.00")).toBeTruthy();
  });

  it("renders unrealized PnL value", () => {
    render(<PositionRow position={makePosition({ unrealized_pnl: 1000 })} />);
    expect(screen.getByText("$1000.00")).toBeTruthy();
  });

  it("uses green color for positive PnL", () => {
    render(<PositionRow position={makePosition({ unrealized_pnl: 500 })} />);
    const pnlEl = screen.getByText("$500.00");
    const style = Array.isArray(pnlEl.props.style)
      ? Object.assign({}, ...pnlEl.props.style.filter(Boolean))
      : pnlEl.props.style;
    expect(style.color).toBe(success);
  });

  it("uses red color for negative PnL", () => {
    render(
      <PositionRow
        position={makePosition({
          unrealized_pnl: -300,
          market_price: 147,
        })}
      />,
    );
    const pnlEl = screen.getByText("-$300.00");
    const style = Array.isArray(pnlEl.props.style)
      ? Object.assign({}, ...pnlEl.props.style.filter(Boolean))
      : pnlEl.props.style;
    expect(style.color).toBe(danger);
  });

  it("uses neutral color for zero PnL", () => {
    render(
      <PositionRow
        position={makePosition({
          unrealized_pnl: 0,
          market_price: 150,
        })}
      />,
    );
    const pnlEl = screen.getByText("$0.00");
    const style = Array.isArray(pnlEl.props.style)
      ? Object.assign({}, ...pnlEl.props.style.filter(Boolean))
      : pnlEl.props.style;
    expect(style.color).toBe(textSecondary);
  });
});
