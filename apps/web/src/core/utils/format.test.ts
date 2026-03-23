import { describe, it, expect } from "vitest";
import { fmtCurrency, fmtPct, fmtNum } from "./format";

describe("fmtCurrency", () => {
  it("formats millions", () => {
    expect(fmtCurrency(1_500_000)).toBe("$1.50M");
  });
  it("formats thousands", () => {
    expect(fmtCurrency(12_300)).toBe("$12.3K");
  });
  it("formats small values", () => {
    expect(fmtCurrency(42)).toBe("$42.00");
  });
});

describe("fmtPct", () => {
  it("formats positive", () => {
    expect(fmtPct(0.125)).toBe("+12.50%");
  });
  it("formats negative", () => {
    expect(fmtPct(-0.03)).toBe("-3.00%");
  });
  it("formats zero", () => {
    expect(fmtPct(0)).toBe("+0.00%");
  });
});

describe("fmtNum", () => {
  it("formats with defaults", () => {
    const result = fmtNum(1234.5678);
    expect(result).toContain("1");
    expect(result).toContain("234");
  });
});
