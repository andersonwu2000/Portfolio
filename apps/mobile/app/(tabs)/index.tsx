import { View, Text, FlatList, RefreshControl, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { usePortfolio } from "../../src/hooks/usePortfolio";
import { MetricCard } from "../../src/components/MetricCard";
import { PositionRow } from "../../src/components/PositionRow";
import { NavChart } from "../../src/components/NavChart";
import { fmtCurrency, fmtPct, pnlColor } from "../../src/utils/format";
import { useT } from "@/src/i18n";
import { useMemo } from "react";
import { bg, textMuted, danger, textSecondary, textPrimary, blue } from "@/src/theme/colors";

export default function DashboardScreen() {
  const { t } = useT();
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
          <Text style={styles.loading}>{t.dashboard.loading}</Text>
        )}
      </SafeAreaView>
    );
  }

  const dailyColor = pnlColor(data.daily_pnl);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: bg }} edges={["top"]}>
      <FlatList
        data={topPositions}
        keyExtractor={(item) => item.symbol}
        renderItem={({ item }) => <PositionRow position={item} />}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={refresh} tintColor={blue} />
        }
        ListHeaderComponent={
          <>
            <View style={styles.navHeader}>
              <Text style={styles.navLabel}>{t.dashboard.netAssetValue}</Text>
              <Text style={styles.navValue}>{fmtCurrency(data.nav)}</Text>
              <Text style={[styles.dailyPnl, { color: dailyColor }]}>
                {fmtCurrency(data.daily_pnl)} ({fmtPct(data.daily_pnl_pct)}) {t.dashboard.today}
              </Text>
            </View>
            {data.nav_history && data.nav_history.length > 1 && (
              <NavChart data={data.nav_history} />
            )}
            <View style={styles.metricsRow}>
              <MetricCard label={t.dashboard.cash} value={fmtCurrency(data.cash)} small />
              <MetricCard label={t.dashboard.exposure} value={fmtCurrency(data.gross_exposure)} small />
              <MetricCard label={t.dashboard.positions} value={String(data.positions_count)} small />
            </View>
            <Text style={styles.sectionTitle}>{t.dashboard.positions}</Text>
          </>
        }
        ListEmptyComponent={<Text style={styles.empty}>{t.dashboard.noPositions}</Text>}
        contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: bg },
  loading: { color: textMuted, fontSize: 16 },
  error: { color: danger, fontSize: 14, textAlign: "center", padding: 24 },
  navHeader: { alignItems: "center", paddingVertical: 24 },
  navLabel: { color: textSecondary, fontSize: 14 },
  navValue: { color: textPrimary, fontSize: 36, fontWeight: "800", marginTop: 4 },
  dailyPnl: { fontSize: 14, fontWeight: "600", marginTop: 4 },
  metricsRow: { flexDirection: "row", marginBottom: 24 },
  sectionTitle: { color: textPrimary, fontSize: 18, fontWeight: "700", marginBottom: 12 },
  empty: { color: textMuted, fontSize: 14, textAlign: "center", padding: 24 },
});
