import React from "react";
import { render, screen } from "@testing-library/react-native";
import { AlertItem } from "../AlertItem";
import type { RiskAlert } from "@quant/shared";
import { warning, danger, blue } from "@/src/theme/colors";

jest.mock("../../utils/format", () => ({
  fmtTime: (ts: string) => new Date(ts).toLocaleTimeString(),
}));

const makeAlert = (overrides: Partial<RiskAlert> = {}): RiskAlert => ({
  timestamp: "2024-06-15T14:30:00Z",
  rule_name: "max_position_weight",
  severity: "WARNING",
  metric_value: 0.35,
  threshold: 0.3,
  action_taken: "REJECT",
  message: "Position weight 35% exceeds limit 30%",
  ...overrides,
});

describe("AlertItem", () => {
  it("renders the rule name", () => {
    render(<AlertItem alert={makeAlert()} />);
    expect(screen.getByText("max_position_weight")).toBeTruthy();
  });

  it("renders the alert message", () => {
    render(<AlertItem alert={makeAlert()} />);
    expect(screen.getByText("Position weight 35% exceeds limit 30%")).toBeTruthy();
  });

  it("renders severity badge text", () => {
    render(<AlertItem alert={makeAlert({ severity: "CRITICAL" })} />);
    expect(screen.getByText("CRITICAL")).toBeTruthy();
  });

  it("renders WARNING severity badge", () => {
    render(<AlertItem alert={makeAlert({ severity: "WARNING" })} />);
    expect(screen.getByText("WARNING")).toBeTruthy();
  });

  it("renders INFO severity badge", () => {
    render(<AlertItem alert={makeAlert({ severity: "INFO" })} />);
    expect(screen.getByText("INFO")).toBeTruthy();
  });

  it("renders different rule names correctly", () => {
    render(<AlertItem alert={makeAlert({ rule_name: "kill_switch" })} />);
    expect(screen.getByText("kill_switch")).toBeTruthy();
  });
});
