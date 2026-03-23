import { View, Text, FlatList, RefreshControl, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { usePortfolio } from "../../src/hooks/usePortfolio";
import { MetricCard } from "../../src/components/MetricCard";
import { PositionRow } from "../../src/components/PositionRow";
import { fmtCurrency, fmtPct, pnlColor } from "../../src/utils/format";
import { useMemo } from "react";

export default function DashboardScreen() {
  const { data, loading, error, refresh } = usePortfolio();

  const topPositions = useMemo(
    () =>
      data?.positions
        .slice()
        .sort((a, b) => Math.abs(b.market_value) - Math.abs(a.market_value))
        .slice(0, 10) ?? [],
    [data?.positions],
  );

  if (!data) {
    return (
      <SafeAreaView style={styles.center} edges={["top"]}>
        {error ? (
          <Text style={styles.error}>{error}</Text>
        ) : (
          <Text style={styles.loading}>Loading...</Text>
        )}
      </SafeAreaView>
    );
  }

  const dailyColor = pnlColor(data.daily_pnl);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: "#0F172A" }} edges={["top"]}>
      <FlatList
        data={topPositions}
        keyExtractor={(item) => item.symbol}
        renderItem={({ item }) => <PositionRow position={item} />}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={refresh} tintColor="#3B82F6" />
        }
        ListHeaderComponent={
          <>
            <View style={styles.navHeader}>
              <Text style={styles.navLabel}>Net Asset Value</Text>
              <Text style={styles.navValue}>{fmtCurrency(data.nav)}</Text>
              <Text style={[styles.dailyPnl, { color: dailyColor }]}>
                {fmtCurrency(data.daily_pnl)} ({fmtPct(data.daily_pnl_pct)}) today
              </Text>
            </View>
            <View style={styles.metricsRow}>
              <MetricCard label="Cash" value={fmtCurrency(data.cash)} small />
              <MetricCard label="Exposure" value={fmtCurrency(data.gross_exposure)} small />
              <MetricCard label="Positions" value={String(data.positions_count)} small />
            </View>
            <Text style={styles.sectionTitle}>Positions</Text>
          </>
        }
        ListEmptyComponent={<Text style={styles.empty}>No open positions</Text>}
        contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#0F172A" },
  loading: { color: "#64748B", fontSize: 16 },
  error: { color: "#EF4444", fontSize: 14, textAlign: "center", padding: 24 },
  navHeader: { alignItems: "center", paddingVertical: 24 },
  navLabel: { color: "#94A3B8", fontSize: 14 },
  navValue: { color: "#F1F5F9", fontSize: 36, fontWeight: "800", marginTop: 4 },
  dailyPnl: { fontSize: 14, fontWeight: "600", marginTop: 4 },
  metricsRow: { flexDirection: "row", marginBottom: 24 },
  sectionTitle: { color: "#F1F5F9", fontSize: 18, fontWeight: "700", marginBottom: 12 },
  empty: { color: "#64748B", fontSize: 14, textAlign: "center", padding: 24 },
});
