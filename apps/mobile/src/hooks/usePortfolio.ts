import { useCallback } from "react";
import type { Portfolio } from "@quant/shared";
import { portfolio as portfolioApi } from "@quant/shared";
import { useRealtimeData } from "./useRealtimeData";

const mergePortfolio = (prev: Portfolio | null, update: unknown) =>
  prev ? { ...prev, ...(update as Partial<Portfolio>) } : prev;

export function usePortfolio() {
  const fetchPortfolio = useCallback(() => portfolioApi.get(), []);
  return useRealtimeData<Portfolio | null>(fetchPortfolio, "portfolio", mergePortfolio, null);
}
