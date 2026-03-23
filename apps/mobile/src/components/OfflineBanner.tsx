import { useEffect, useState } from "react";
import { View, Text, StyleSheet } from "react-native";
import * as Network from "expo-network";
import { useT } from "@/src/i18n";
import { warning, surface } from "@/src/theme/colors";

export function OfflineBanner() {
  const { t } = useT();
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    let mounted = true;

    const check = async () => {
      try {
        const state = await Network.getNetworkStateAsync();
        if (mounted) setOffline(!state.isConnected);
      } catch {
        // Assume online if check fails
      }
    };

    check();

    // Poll every 10 seconds — expo-network does not provide a listener API
    const interval = setInterval(check, 10_000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  if (!offline) return null;

  return (
    <View style={styles.banner}>
      <Text style={styles.text}>{t.common.offline}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    backgroundColor: surface,
    paddingVertical: 6,
    paddingHorizontal: 16,
    alignItems: "center",
    borderBottomWidth: 1,
    borderBottomColor: warning,
  },
  text: {
    color: warning,
    fontSize: 12,
    fontWeight: "600",
  },
});
