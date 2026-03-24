import { useState } from "react";
import { PieChart, BarChart3, TrendingUp, Activity } from "lucide-react";
import { useT } from "@core/i18n";
import { allocation as allocationApi } from "@core/api";
import { Card, ErrorAlert, Skeleton } from "@shared/ui";
import type { TacticalRequest, TacticalResponse, TacticalWeightItem } from "@core/api";

const ASSET_COLORS: Record<string, string> = {
  EQUITY: "bg-blue-500",
  ETF: "bg-emerald-500",
  FUTURE: "bg-amber-500",
};

const ASSET_LABELS: Record<string, string> = {
  EQUITY: "Equities",
  ETF: "ETFs (Bond/Commodity)",
  FUTURE: "Futures",
};

const REGIME_LABELS: Record<string, { label: string; color: string }> = {
  bull: { label: "Bull", color: "text-green-600 dark:text-green-400" },
  bear: { label: "Bear", color: "text-red-600 dark:text-red-400" },
  sideways: { label: "Sideways", color: "text-yellow-600 dark:text-yellow-400" },
};

export function AllocationPage() {
  const { t } = useT();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TacticalResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [maxDeviation, setMaxDeviation] = useState(0.15);
  const [macroWeight, setMacroWeight] = useState(0.5);
  const [crossAssetWeight, setCrossAssetWeight] = useState(0.3);
  const [regimeWeight, setRegimeWeight] = useState(0.2);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const req: TacticalRequest = {
        max_deviation: maxDeviation,
        macro_weight: macroWeight,
        cross_asset_weight: crossAssetWeight,
        regime_weight: regimeWeight,
      };
      const resp = await allocationApi.compute(req);
      setResult(resp);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <h2 className="text-2xl font-bold">{t.allocation?.title ?? "Tactical Allocation"}</h2>
      <p className="text-slate-500 dark:text-slate-400 text-sm">
        {t.allocation?.subtitle ?? "Compute tactical asset class weights based on macro factors, cross-asset signals, and market regime."}
      </p>

      {/* Config */}
      <Card className="p-5 space-y-4">
        <h3 className="font-semibold text-sm uppercase tracking-wider text-slate-500 dark:text-slate-400">
          Parameters
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">Max Deviation</label>
            <input type="number" step="0.01" min="0.01" max="0.5"
              value={maxDeviation} onChange={e => setMaxDeviation(+e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-surface-light bg-white dark:bg-surface text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">Macro Weight</label>
            <input type="number" step="0.1" min="0" max="1"
              value={macroWeight} onChange={e => setMacroWeight(+e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-surface-light bg-white dark:bg-surface text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">Cross-Asset Weight</label>
            <input type="number" step="0.1" min="0" max="1"
              value={crossAssetWeight} onChange={e => setCrossAssetWeight(+e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-surface-light bg-white dark:bg-surface text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 dark:text-slate-300 mb-1">Regime Weight</label>
            <input type="number" step="0.1" min="0" max="1"
              value={regimeWeight} onChange={e => setRegimeWeight(+e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-surface-light bg-white dark:bg-surface text-sm" />
          </div>
        </div>

        <button
          onClick={run}
          disabled={loading}
          className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50 transition-colors"
        >
          {loading ? "Computing..." : "Compute Allocation"}
        </button>
      </Card>

      {error && <ErrorAlert message={error} />}

      {/* Results */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-32" />)}
        </div>
      )}

      {result && !loading && (
        <div className="space-y-6">
          {/* Regime */}
          <Card className="p-5 flex items-center gap-4">
            <Activity size={20} className="text-slate-400" />
            <div>
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase">Market Regime</p>
              <p className={`text-lg font-bold ${REGIME_LABELS[result.regime]?.color ?? "text-slate-700 dark:text-slate-200"}`}>
                {REGIME_LABELS[result.regime]?.label ?? result.regime}
              </p>
            </div>
          </Card>

          {/* Tactical Weights */}
          <Card className="p-5">
            <div className="flex items-center gap-2 mb-4">
              <PieChart size={18} className="text-slate-400" />
              <h3 className="font-semibold">Tactical Weights</h3>
            </div>
            <div className="space-y-3">
              {result.weights.map((w: TacticalWeightItem) => (
                <div key={w.asset_class}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium">{ASSET_LABELS[w.asset_class] ?? w.asset_class}</span>
                    <div className="flex items-center gap-3 text-sm">
                      <span className="text-slate-500 dark:text-slate-400">
                        Strategic: {(w.strategic_weight * 100).toFixed(1)}%
                      </span>
                      <span className="font-semibold">
                        Tactical: {(w.tactical_weight * 100).toFixed(1)}%
                      </span>
                      <span className={`text-xs font-medium ${w.deviation > 0 ? "text-green-600" : w.deviation < 0 ? "text-red-500" : "text-slate-400"}`}>
                        {w.deviation > 0 ? "+" : ""}{(w.deviation * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  <div className="flex h-3 rounded-full overflow-hidden bg-slate-100 dark:bg-surface">
                    <div
                      className={`${ASSET_COLORS[w.asset_class] ?? "bg-slate-500"} rounded-full transition-all`}
                      style={{ width: `${Math.max(w.tactical_weight * 100, 2)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Macro Signals */}
          <Card className="p-5">
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp size={18} className="text-slate-400" />
              <h3 className="font-semibold">Macro Signals</h3>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {result.macro_signals.map((s) => (
                <div key={s.name} className="text-center p-3 rounded-lg bg-slate-50 dark:bg-surface">
                  <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase mb-1">{s.name}</p>
                  <p className={`text-xl font-bold ${s.value > 0 ? "text-green-600 dark:text-green-400" : s.value < 0 ? "text-red-500 dark:text-red-400" : "text-slate-500"}`}>
                    {s.value > 0 ? "+" : ""}{s.value.toFixed(2)}
                  </p>
                </div>
              ))}
            </div>
          </Card>

          {/* Cross-Asset Signals */}
          <Card className="p-5">
            <div className="flex items-center gap-2 mb-4">
              <BarChart3 size={18} className="text-slate-400" />
              <h3 className="font-semibold">Cross-Asset Signals</h3>
            </div>
            <div className="grid grid-cols-3 gap-4">
              {Object.entries(result.cross_asset_signals).map(([cls, rawVal]) => {
                const val = Number(rawVal);
                return (
                  <div key={cls} className="text-center p-3 rounded-lg bg-slate-50 dark:bg-surface">
                    <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase mb-1">
                      {ASSET_LABELS[cls] ?? cls}
                    </p>
                    <p className={`text-xl font-bold ${val > 0 ? "text-green-600" : val < 0 ? "text-red-500" : "text-slate-500"}`}>
                      {val > 0 ? "+" : ""}{val.toFixed(2)}
                    </p>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
