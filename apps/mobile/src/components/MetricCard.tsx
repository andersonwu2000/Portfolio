import { View, Text, StyleSheet } from "react-native";
import { surface, textSecondary, textPrimary } from "@/src/theme/colors";

interface Props {
  label: string;
  value: string;
  color?: string;
  small?: boolean;
}

export function MetricCard({ label, value, color, small }: Props) {
  return (
    <View style={[styles.card, small && styles.cardSmall]}>
      <Text style={styles.label}>{label}</Text>
      <Text style={[styles.value, small && styles.valueSmall, color ? { color } : null]}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: surface,
    borderRadius: 12,
    padding: 16,
    flex: 1,
    marginHorizontal: 4,
  },
  cardSmall: {
    padding: 12,
  },
  label: {
    color: textSecondary,
    fontSize: 12,
    fontWeight: "500",
    marginBottom: 4,
  },
  value: {
    color: textPrimary,
    fontSize: 20,
    fontWeight: "700",
  },
  valueSmall: {
    fontSize: 16,
  },
});
