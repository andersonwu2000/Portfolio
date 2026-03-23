import { useCallback } from "react";
import type { RiskAlert } from "@quant/shared";
import { risk } from "@quant/shared";
import { useRealtimeData } from "./useRealtimeData";

const MAX_ALERTS = 200;

const mergeAlert = (prev: RiskAlert[], update: unknown) =>
  [update as RiskAlert, ...prev].slice(0, MAX_ALERTS);

const fetchAlerts = () => risk.alerts().then((r) => r.slice(0, MAX_ALERTS));

export function useAlerts() {
  const fetcher = useCallback(() => fetchAlerts(), []);
  const { data: alerts, loading, refresh } = useRealtimeData<RiskAlert[]>(fetcher, "alerts", mergeAlert, []);
  return { alerts, loading, refresh };
}
