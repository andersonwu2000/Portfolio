import { useEffect, useRef } from "react";
import { useApi } from "@core/hooks";
import { useT } from "@core/i18n";
import { fmtUptime } from "@core/utils";
import { MetricCard, MetricCardSkeleton } from "@shared/ui";
import { systemApi } from "../api";

const REFRESH_INTERVAL_MS = 30_000;

export function SystemMetrics() {
  const { t } = useT();
  const { data: metrics, loading, refresh } = useApi(systemApi.metrics);
  const intervalRef = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => {
    const start = () => { intervalRef.current = setInterval(refresh, REFRESH_INTERVAL_MS); };
    const stop = () => clearInterval(intervalRef.current);
    const onVisibility = () => { document.hidden ? stop() : start(); };

    start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => { stop(); document.removeEventListener("visibilitychange", onVisibility); };
  }, [refresh]);

  if (loading && !metrics) {
    return (
      <div>
        <p className="text-sm font-medium text-slate-400 mb-3">{t.settings.metrics}</p>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCardSkeleton /><MetricCardSkeleton /><MetricCardSkeleton /><MetricCardSkeleton />
        </div>
      </div>
    );
  }

  if (!metrics) return null;

  return (
    <div>
      <p className="text-sm font-medium text-slate-400 mb-3">{t.settings.metrics}</p>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard label={t.settings.uptime} value={fmtUptime(metrics.uptime_seconds)} />
        <MetricCard label={t.settings.requestCount} value={String(metrics.total_requests)} />
        <MetricCard label={t.settings.wsConnections} value={String(metrics.active_ws_connections)} />
        <MetricCard label={t.settings.strategiesRunning} value={String(metrics.strategies_running)} />
        <MetricCard label={t.settings.activeBacktests} value={String(metrics.active_backtests)} />
      </div>
    </div>
  );
}
