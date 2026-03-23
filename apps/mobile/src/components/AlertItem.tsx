import { View, Text, StyleSheet } from "react-native";
import type { RiskAlert } from "@quant/shared";
import { fmtTime } from "../utils/format";
import { warning, danger, blue, textSecondary, surface, white, textPrimary, textMuted } from "@/src/theme/colors";

interface Props {
  alert: RiskAlert;
}

const severityColors: Record<string, string> = {
  WARNING: warning,
  CRITICAL: danger,
  INFO: blue,
};

export function AlertItem({ alert }: Props) {
  const color = severityColors[alert.severity] || textSecondary;

  return (
    <View style={styles.row}>
      <View style={[styles.badge, { backgroundColor: color }]}>
        <Text style={styles.badgeText}>{alert.severity}</Text>
      </View>
      <View style={styles.content}>
        <Text style={styles.rule}>{alert.rule_name}</Text>
        <Text style={styles.message} numberOfLines={2}>
          {alert.message}
        </Text>
      </View>
      <Text style={styles.time}>{fmtTime(alert.timestamp)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: surface,
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
    marginRight: 10,
  },
  badgeText: { color: white, fontSize: 10, fontWeight: "700" },
  content: { flex: 1 },
  rule: { color: textPrimary, fontSize: 14, fontWeight: "600" },
  message: { color: textSecondary, fontSize: 12, marginTop: 2 },
  time: { color: textMuted, fontSize: 11 },
});
