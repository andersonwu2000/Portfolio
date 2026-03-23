import { useMemo } from "react";
import { View, StyleSheet } from "react-native";
import { VictoryPie } from "victory-native";
import { surface, textPrimary, blue, success, warning, danger } from "@/src/theme/colors";

interface Props {
  positions: { symbol: string; weight: number }[];
}

const PALETTE = [
  blue,
  success,
  warning,
  danger,
  "#8B5CF6", // violet
  "#06B6D4", // cyan
  "#EC4899", // pink
  "#F97316", // orange
  "#14B8A6", // teal
  "#A855F7", // purple
];

const CHART_SIZE = 220;

export function PositionPieChart({ positions }: Props) {
  const slices = useMemo(() => {
    if (positions.length === 0) return [];
    const sorted = positions.slice().sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight));
    const top = sorted.slice(0, 9);
    const rest = sorted.slice(9);
    const otherWeight = rest.reduce((sum, p) => sum + Math.abs(p.weight), 0);
    const s = top.map((p) => ({ x: p.symbol, y: Math.abs(p.weight) }));
    if (otherWeight > 0) s.push({ x: "Other", y: otherWeight });
    return s;
  }, [positions]);

  if (slices.length === 0) return null;

  return (
    <View style={styles.container}>
      <VictoryPie
        data={slices}
        width={CHART_SIZE}
        height={CHART_SIZE}
        innerRadius={40}
        padAngle={2}
        colorScale={PALETTE}
        labels={({ datum }: { datum: { x: string; y: number } }) =>
          `${datum.x}\n${(datum.y * 100).toFixed(1)}%`
        }
        style={{
          labels: { fill: textPrimary, fontSize: 9, fontWeight: "500" },
        }}
        labelRadius={({ innerRadius }) => ((innerRadius as number) || 40) + 32}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: surface,
    borderRadius: 12,
    alignItems: "center",
    paddingVertical: 12,
    marginBottom: 16,
  },
});
