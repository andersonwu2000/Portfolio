// Re-export platform-agnostic formatters from shared
export { fmtCurrency, fmtPct, fmtNum, fmtDate, fmtTime } from "@quant/shared";

import { success, danger, textSecondary } from "@/src/theme/colors";

// Mobile-specific: hex color helpers (not shareable with web's Tailwind classes)
export function pnlColor(value: number): string {
  if (value > 0) return success;
  if (value < 0) return danger;
  return textSecondary;
}
