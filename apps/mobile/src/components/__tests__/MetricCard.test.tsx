import React from "react";
import { render, screen } from "@testing-library/react-native";
import { MetricCard } from "../MetricCard";
import { success, danger, textPrimary } from "@/src/theme/colors";

describe("MetricCard", () => {
  it("renders label text", () => {
    render(<MetricCard label="Total P&L" value="$1,234" />);
    expect(screen.getByText("Total P&L")).toBeTruthy();
  });

  it("renders value text", () => {
    render(<MetricCard label="NAV" value="$100,000" />);
    expect(screen.getByText("$100,000")).toBeTruthy();
  });

  it("applies custom color to value when provided", () => {
    render(<MetricCard label="P&L" value="+$500" color={success} />);
    const valueEl = screen.getByText("+$500");
    const style = Array.isArray(valueEl.props.style)
      ? Object.assign({}, ...valueEl.props.style.filter(Boolean))
      : valueEl.props.style;
    expect(style.color).toBe(success);
  });

  it("uses default text color when no color prop is given", () => {
    render(<MetricCard label="Cash" value="$50,000" />);
    const valueEl = screen.getByText("$50,000");
    const style = Array.isArray(valueEl.props.style)
      ? Object.assign({}, ...valueEl.props.style.filter(Boolean))
      : valueEl.props.style;
    expect(style.color).toBe(textPrimary);
  });

  it("applies positive color for gains", () => {
    render(<MetricCard label="P&L" value="+$500" color={success} />);
    const valueEl = screen.getByText("+$500");
    const flatStyle = Array.isArray(valueEl.props.style)
      ? Object.assign({}, ...valueEl.props.style.filter(Boolean))
      : valueEl.props.style;
    expect(flatStyle.color).toBe(success);
  });

  it("applies negative color for losses", () => {
    render(<MetricCard label="P&L" value="-$300" color={danger} />);
    const valueEl = screen.getByText("-$300");
    const flatStyle = Array.isArray(valueEl.props.style)
      ? Object.assign({}, ...valueEl.props.style.filter(Boolean))
      : valueEl.props.style;
    expect(flatStyle.color).toBe(danger);
  });

  it("renders smaller variant when small prop is true", () => {
    render(<MetricCard label="Win Rate" value="65%" small />);
    expect(screen.getByText("Win Rate")).toBeTruthy();
    expect(screen.getByText("65%")).toBeTruthy();
  });
});
