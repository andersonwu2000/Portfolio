import { View, Text, FlatList, RefreshControl, Pressable, Alert, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useAlerts } from "../../src/hooks/useAlerts";
import { AlertItem } from "../../src/components/AlertItem";
import { risk } from "@quant/shared";

export default function AlertsScreen() {
  const { alerts, loading, refresh } = useAlerts();

  const handleKillSwitch = () => {
    Alert.alert(
      "Kill Switch",
      "This will stop ALL strategies and cancel ALL pending orders. Are you sure?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Confirm",
          style: "destructive",
          onPress: async () => {
            try {
              await risk.killSwitch();
              Alert.alert("Kill Switch", "All strategies stopped, all orders cancelled.");
            } catch (err) {
              Alert.alert("Error", err instanceof Error ? err.message : "Failed");
            }
          },
        },
      ],
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <FlatList
        data={alerts}
        keyExtractor={(item, i) => `${item.timestamp}-${i}`}
        renderItem={({ item }) => <AlertItem alert={item} />}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={refresh} tintColor="#3B82F6" />
        }
        ListEmptyComponent={<Text style={styles.empty}>No risk alerts</Text>}
        ListFooterComponent={
          <Pressable
            style={styles.killButton}
            onLongPress={handleKillSwitch}
            delayLongPress={1000}
          >
            <Text style={styles.killText}>KILL SWITCH</Text>
            <Text style={styles.killHint}>Long press to activate</Text>
          </Pressable>
        }
        contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0F172A" },
  killButton: {
    backgroundColor: "#DC2626",
    borderRadius: 10,
    padding: 14,
    alignItems: "center",
    marginTop: 24,
  },
  killText: { color: "#FFFFFF", fontSize: 16, fontWeight: "800", letterSpacing: 1 },
  killHint: { color: "#FCA5A5", fontSize: 11, marginTop: 4 },
  empty: { color: "#64748B", fontSize: 14, textAlign: "center", padding: 24 },
});
