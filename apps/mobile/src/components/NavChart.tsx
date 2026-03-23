import { View, Text, StyleSheet } from "react-native";
import { useState } from "react";
import {
  VictoryChart,
  VictoryLine,
  VictoryAxis,
  VictoryVoronoiContainer,
  VictoryTooltip,
} from "victory-native";
import { surface, textSecondary, textMuted, blue, textPrimary } from "@/src/theme/colors";

interface NavPoint {
  date: string;
  nav: number;
}

interface Props {
  data: NavPoint[];
}

const CHART_HEIGHT = 140;
const CHART_PADDING = { top: 10, bottom: 30, left: 50, right: 16 };

export function NavChart({ data }: Props) {
  const [tooltip, setTooltip] = useState<NavPoint | null>(null);

  if (data.length < 2) return null;

  // Take last 30 points
  const points = data.slice(-30);

  return (
    <View style={styles.container}>
      {tooltip && (
        <View style={styles.tooltipRow}>
          <Text style={styles.tooltipDate}>{tooltip.date}</Text>
          <Text style={styles.tooltipValue}>{tooltip.nav.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</Text>
        </View>
      )}
      <VictoryChart
        height={CHART_HEIGHT}
        padding={CHART_PADDING}
        containerComponent={
          <VictoryVoronoiContainer
            onActivated={(points) => {
              if (points.length > 0) {
                const p = points[0] as { datum: { x: string; y: number } };
                setTooltip({ date: p.datum.x, nav: p.datum.y });
              }
            }}
            onDeactivated={() => setTooltip(null)}
          />
        }
      >
        <VictoryAxis
          style={{
            axis: { stroke: textMuted, strokeWidth: 0.5 },
            tickLabels: { fill: textMuted, fontSize: 9, padding: 4 },
            grid: { stroke: "none" },
          }}
          tickCount={4}
          tickFormat={(t: string) => {
            const d = t.slice(5); // MM-DD
            return d;
          }}
        />
        <VictoryAxis
          dependentAxis
          style={{
            axis: { stroke: "none" },
            tickLabels: { fill: textMuted, fontSize: 9, padding: 4 },
            grid: { stroke: textMuted, strokeWidth: 0.3, strokeDasharray: "4,4" },
          }}
          tickCount={3}
          tickFormat={(t: number) =>
            t >= 1_000_000 ? `${(t / 1_000_000).toFixed(1)}M` : t >= 1_000 ? `${(t / 1_000).toFixed(0)}K` : String(t)
          }
        />
        <VictoryLine
          data={points.map((p) => ({ x: p.date, y: p.nav }))}
          style={{
            data: { stroke: blue, strokeWidth: 2 },
          }}
          labelComponent={<VictoryTooltip style={{ fill: textPrimary }} flyoutStyle={{ display: "none" }} />}
        />
      </VictoryChart>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: surface,
    borderRadius: 12,
    paddingTop: 12,
    paddingHorizontal: 4,
    marginBottom: 16,
  },
  tooltipRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingHorizontal: 12,
    marginBottom: 4,
  },
  tooltipDate: { color: textSecondary, fontSize: 11 },
  tooltipValue: { color: textPrimary, fontSize: 11, fontWeight: "600" },
});
