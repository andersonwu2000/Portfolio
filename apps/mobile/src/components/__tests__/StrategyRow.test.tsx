import React from "react";
import { render, screen, fireEvent } from "@testing-library/react-native";
import { StrategyRow } from "../StrategyRow";
import type { StrategyInfo } from "@quant/shared";

jest.mock("../../utils/format", () => ({
  fmtCurrency: (v: number) => (v >= 0 ? `$${v.toFixed(2)}` : `-$${Math.abs(v).toFixed(2)}`),
  pnlColor: (v: number) => {
    if (v > 0) return "#22C55E";
    if (v < 0) return "#EF4444";
    return "#94A3B8";
  },
}));

describe("StrategyRow", () => {
  const runningStrategy: StrategyInfo = {
    name: "Momentum",
    status: "running",
    pnl: 2500,
  };

  const stoppedStrategy: StrategyInfo = {
    name: "MeanReversion",
    status: "stopped",
    pnl: -400,
  };

  it("renders strategy name", () => {
    render(<StrategyRow strategy={runningStrategy} onToggle={jest.fn()} />);
    expect(screen.getByText("Momentum")).toBeTruthy();
  });

  it("shows 'running' status text for a running strategy", () => {
    render(<StrategyRow strategy={runningStrategy} onToggle={jest.fn()} />);
    expect(screen.getByText("running")).toBeTruthy();
  });

  it("shows 'stopped' status text for a stopped strategy", () => {
    render(<StrategyRow strategy={stoppedStrategy} onToggle={jest.fn()} />);
    expect(screen.getByText("stopped")).toBeTruthy();
  });

  it("shows Stop button when strategy is running", () => {
    render(<StrategyRow strategy={runningStrategy} onToggle={jest.fn()} />);
    expect(screen.getByText("Stop")).toBeTruthy();
  });

  it("shows Start button when strategy is stopped", () => {
    render(<StrategyRow strategy={stoppedStrategy} onToggle={jest.fn()} />);
    expect(screen.getByText("Start")).toBeTruthy();
  });

  it("calls onToggle with name and running=true when stopping", () => {
    const onToggle = jest.fn();
    render(<StrategyRow strategy={runningStrategy} onToggle={onToggle} />);
    fireEvent.press(screen.getByText("Stop"));
    expect(onToggle).toHaveBeenCalledWith("Momentum", true);
  });

  it("calls onToggle with name and running=false when starting", () => {
    const onToggle = jest.fn();
    render(<StrategyRow strategy={stoppedStrategy} onToggle={onToggle} />);
    fireEvent.press(screen.getByText("Start"));
    expect(onToggle).toHaveBeenCalledWith("MeanReversion", false);
  });

  it("renders PnL value", () => {
    render(<StrategyRow strategy={runningStrategy} onToggle={jest.fn()} />);
    expect(screen.getByText("$2500.00")).toBeTruthy();
  });
});
