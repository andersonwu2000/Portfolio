import { View, StyleSheet } from "react-native";
import {
  VictoryChart,
  VictoryLine,
  VictoryAxis,
} from "victory-native";
import { surface, textMuted, blue } from "@/src/theme/colors";

interface NavPoint {
  date: string;
  nav: number;
}

interface Props {
  data: NavPoint[];
}

const CHART_HEIGHT = 220;
const CHART_PADDING = { top: 16, bottom: 40, left: 56, right: 16 };

export function BacktestChart({ data }: Props) {
  if (data.length < 2) return null;

  // Sample data if too many points (keep ~60 for mobile performance)
  const maxPoints = 60;
  const step = data.length > maxPoints ? Math.ceil(data.length / maxPoints) : 1;
  const sampled = step > 1
    ? data.filter((_, i) => i % step === 0 || i === data.length - 1)
    : data;

  return (
    <View style={styles.container}>
      <VictoryChart height={CHART_HEIGHT} padding={CHART_PADDING}>
        <VictoryAxis
          style={{
            axis: { stroke: textMuted, strokeWidth: 0.5 },
            tickLabels: { fill: textMuted, fontSize: 9, padding: 6, angle: -30 },
            grid: { stroke: "none" },
          }}
          tickCount={5}
          tickFormat={(t: string) => {
            // Show YYYY-MM
            return t.slice(0, 7);
          }}
        />
        <VictoryAxis
          dependentAxis
          style={{
            axis: { stroke: "none" },
            tickLabels: { fill: textMuted, fontSize: 9, padding: 4 },
            grid: { stroke: textMuted, strokeWidth: 0.3, strokeDasharray: "4,4" },
          }}
          tickCount={5}
          tickFormat={(t: number) =>
            t >= 1_000_000
              ? `${(t / 1_000_000).toFixed(1)}M`
              : t >= 1_000
                ? `${(t / 1_000).toFixed(0)}K`
                : String(t)
          }
        />
        <VictoryLine
          data={sampled.map((p) => ({ x: p.date, y: p.nav }))}
          style={{
            data: { stroke: blue, strokeWidth: 2 },
          }}
        />
      </VictoryChart>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: surface,
    borderRadius: 12,
    paddingTop: 8,
    paddingHorizontal: 4,
    marginTop: 16,
    marginBottom: 8,
  },
});
