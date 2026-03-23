import { View, Text, TextInput, ScrollView, TouchableOpacity, StyleSheet, ActivityIndicator } from "react-native";
import { useState, useEffect } from "react";
import { useBacktest } from "@/src/hooks/useBacktest";
import { useT } from "@/src/i18n";
import { strategies as strategiesApi } from "@quant/shared";
import type { BacktestRequest, StrategyInfo } from "@quant/shared";
import { MetricCard } from "@/src/components/MetricCard";
import { fmtPct, fmtNum } from "@/src/utils/format";
import { bg, surface, textSecondary, textPrimary, textMuted, blueAlpha, blueLight, blueDark, white, danger } from "@/src/theme/colors";

export default function BacktestScreen() {
  const { t } = useT();
  const { running, result, error, progress, submit } = useBacktest();
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [form, setForm] = useState<BacktestRequest>({
    strategy: "momentum",
    universe: ["AAPL", "MSFT", "GOOGL"],
    start: "2023-01-01",
    end: "2024-01-01",
    initial_cash: 1000000,
    params: {},
    slippage_bps: 5,
    commission_rate: 0.001,
    rebalance_freq: "weekly",
  });

  useEffect(() => {
    strategiesApi.list().then(setStrategies).catch(() => {});
  }, []);

  const set = (key: keyof BacktestRequest, val: unknown) =>
    setForm((f) => ({ ...f, [key]: val }));

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.sectionTitle}>{t.backtest.strategy}</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipRow}>
        {strategies.map((s) => (
          <TouchableOpacity
            key={s.name}
            onPress={() => set("strategy", s.name)}
            style={[styles.chip, form.strategy === s.name && styles.chipActive]}
          >
            <Text style={[styles.chipText, form.strategy === s.name && styles.chipTextActive]}>{s.name}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <Text style={styles.sectionTitle}>{t.backtest.universe}</Text>
      <TextInput
        style={styles.input}
        value={form.universe.join(", ")}
        onChangeText={(v) => set("universe", v.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean))}
        placeholder="AAPL, MSFT, GOOGL"
        placeholderTextColor={textMuted}
      />

      <View style={styles.row}>
        <View style={styles.half}>
          <Text style={styles.sectionTitle}>{t.backtest.start}</Text>
          <TextInput style={styles.input} value={form.start}
            onChangeText={(v) => set("start", v)} placeholder="2023-01-01" placeholderTextColor={textMuted} />
        </View>
        <View style={styles.half}>
          <Text style={styles.sectionTitle}>{t.backtest.end}</Text>
          <TextInput style={styles.input} value={form.end}
            onChangeText={(v) => set("end", v)} placeholder="2024-01-01" placeholderTextColor={textMuted} />
        </View>
      </View>

      <TouchableOpacity
        style={[styles.submitBtn, running && styles.submitDisabled]}
        onPress={() => submit(form)}
        disabled={running}
      >
        {running ? (
          <View style={styles.runningRow}>
            <ActivityIndicator size="small" color={white} />
            <Text style={styles.submitText}>
              {progress ? `${progress.current}/${progress.total}` : t.backtest.running}
            </Text>
          </View>
        ) : (
          <Text style={styles.submitText}>{t.backtest.run}</Text>
        )}
      </TouchableOpacity>

      {error && <Text style={styles.error}>{error}</Text>}

      {result && (
        <View style={styles.results}>
          <Text style={styles.resultsTitle}>{result.strategy_name}</Text>
          <View style={styles.metricsGrid}>
            <MetricCard label={t.backtest.totalReturn} value={fmtPct(result.total_return)} small />
            <MetricCard label={t.backtest.annualReturn} value={fmtPct(result.annual_return)} small />
            <MetricCard label={t.backtest.sharpe} value={fmtNum(result.sharpe)} small />
            <MetricCard label={t.backtest.maxDrawdown} value={fmtPct(result.max_drawdown)} small />
            <MetricCard label={t.backtest.sortino} value={fmtNum(result.sortino)} small />
            <MetricCard label={t.backtest.winRate} value={fmtPct(result.win_rate)} small />
          </View>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: bg },
  content: { padding: 16 },
  sectionTitle: { color: textSecondary, fontSize: 12, fontWeight: "500", marginBottom: 6, marginTop: 12 },
  input: { backgroundColor: surface, borderRadius: 8, padding: 12, color: textPrimary, fontSize: 14 },
  chipRow: { flexDirection: "row", marginBottom: 4 },
  chip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8, backgroundColor: surface, marginRight: 8 },
  chipActive: { backgroundColor: blueAlpha },
  chipText: { color: textSecondary, fontSize: 13, fontWeight: "500" },
  chipTextActive: { color: blueLight },
  row: { flexDirection: "row", gap: 12 },
  half: { flex: 1 },
  submitBtn: { backgroundColor: blueDark, borderRadius: 10, padding: 14, alignItems: "center", marginTop: 20 },
  submitDisabled: { opacity: 0.6 },
  submitText: { color: white, fontWeight: "600", fontSize: 15 },
  runningRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  error: { color: danger, marginTop: 12, fontSize: 13 },
  results: { marginTop: 20 },
  resultsTitle: { color: textPrimary, fontSize: 16, fontWeight: "700", marginBottom: 12 },
  metricsGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
});
