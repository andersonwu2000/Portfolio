import { get, post } from "@core/api";
import type { StrategyInfo } from "@quant/shared";

export const strategiesApi = {
  list: () => get<{ strategies: StrategyInfo[] }>("/api/v1/strategies").then((r) => r.strategies),
  get: (id: string) => get<StrategyInfo>(`/api/v1/strategies/${id}`),
  start: (id: string) => post<StrategyInfo>(`/api/v1/strategies/${id}/start`),
  stop: (id: string) => post<StrategyInfo>(`/api/v1/strategies/${id}/stop`),
};
