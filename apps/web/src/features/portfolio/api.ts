import { get } from "@core/api";
import type { Portfolio, Position } from "@quant/shared";

export const portfolioApi = {
  get: () => get<Portfolio>("/api/v1/portfolio"),
  positions: () => get<Position[]>("/api/v1/portfolio/positions"),
};
