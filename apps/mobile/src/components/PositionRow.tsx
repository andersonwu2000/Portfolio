import { View, Text, StyleSheet } from "react-native";
import type { Position } from "@quant/shared";
import { fmtCurrency, fmtPct, pnlColor } from "../utils/format";
import { surface, textPrimary, textMuted } from "@/src/theme/colors";

interface Props {
  position: Position;
}

export function PositionRow({ position }: Props) {
  const color = pnlColor(position.unrealized_pnl);

  return (
    <View style={styles.row}>
      <View style={styles.left}>
        <Text style={styles.symbol}>{position.symbol}</Text>
        <Text style={styles.detail}>
          {position.quantity} shares @ {fmtCurrency(position.avg_cost)}
        </Text>
      </View>
      <View style={styles.right}>
        <Text style={[styles.pnl, { color }]}>
          {fmtCurrency(position.unrealized_pnl)}
        </Text>
        <Text style={[styles.pnlPct, { color }]}>
          {fmtPct(
            position.avg_cost > 0
              ? (position.market_price - position.avg_cost) / position.avg_cost
              : 0,
          )}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: surface,
    borderRadius: 10,
    padding: 14,
    marginBottom: 8,
  },
  left: {
    flex: 1,
  },
  right: {
    alignItems: "flex-end",
  },
  symbol: {
    color: textPrimary,
    fontSize: 16,
    fontWeight: "700",
  },
  detail: {
    color: textMuted,
    fontSize: 12,
    marginTop: 2,
  },
  pnl: {
    fontSize: 16,
    fontWeight: "600",
  },
  pnlPct: {
    fontSize: 12,
    marginTop: 2,
  },
});
