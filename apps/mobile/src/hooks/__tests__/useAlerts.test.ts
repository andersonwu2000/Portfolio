import { renderHook, waitFor } from "@testing-library/react-native";
import type { RiskAlert } from "@quant/shared";

const mockAlerts = jest.fn<Promise<RiskAlert[]>, []>();

jest.mock("@quant/shared", () => ({
  risk: { alerts: () => mockAlerts() },
  WSManager: jest.fn().mockImplementation(() => ({
    connect: jest.fn(),
    disconnect: jest.fn(),
    subscribe: jest.fn(() => jest.fn()),
  })),
}));

jest.mock("react-native", () => {
  const rn = jest.requireActual("react-native");
  return {
    ...rn,
    AppState: {
      addEventListener: jest.fn(() => ({ remove: jest.fn() })),
      currentState: "active",
    },
  };
});

import { useAlerts } from "../useAlerts";

const sampleAlerts: RiskAlert[] = [
  {
    timestamp: "2024-06-15T14:30:00Z",
    rule_name: "max_position_weight",
    severity: "WARNING",
    metric_value: 0.35,
    threshold: 0.3,
    action_taken: "REJECT",
    message: "Position weight exceeds limit",
  },
  {
    timestamp: "2024-06-15T14:25:00Z",
    rule_name: "daily_loss_limit",
    severity: "CRITICAL",
    metric_value: -0.06,
    threshold: -0.05,
    action_taken: "KILL_SWITCH",
    message: "Daily loss exceeded threshold",
  },
];

describe("useAlerts", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("starts in loading state with empty alerts", () => {
    mockAlerts.mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(() => useAlerts());
    expect(result.current.loading).toBe(true);
    expect(result.current.alerts).toEqual([]);
  });

  it("returns alerts after fetch", async () => {
    mockAlerts.mockResolvedValue(sampleAlerts);
    const { result } = renderHook(() => useAlerts());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.alerts).toEqual(sampleAlerts);
  });

  it("provides a refresh function", () => {
    mockAlerts.mockResolvedValue([]);
    const { result } = renderHook(() => useAlerts());
    expect(typeof result.current.refresh).toBe("function");
  });
});
