import { useEffect } from "react";
import { ActivityIndicator, View } from "react-native";
import { Stack, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { AuthProvider, useAuth } from "../src/hooks/useAuth";

function RootNavigator() {
  const { authenticated, loading } = useAuth();
  const router = useRouter();
  const segments = useSegments();

  // Redirect based on auth state (C2: proper Expo Router pattern)
  useEffect(() => {
    if (loading) return;

    const inAuthScreen = segments[0] === "login";

    if (!authenticated && !inAuthScreen) {
      router.replace("/login");
    } else if (authenticated && inAuthScreen) {
      router.replace("/(tabs)");
    }
  }, [authenticated, loading, segments, router]);

  if (loading) {
    return (
      <View style={{ flex: 1, backgroundColor: "#0F172A", justifyContent: "center", alignItems: "center" }}>
        <StatusBar style="light" />
        <ActivityIndicator size="large" color="#3B82F6" />
      </View>
    );
  }

  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: "#0F172A" },
          headerTintColor: "#F1F5F9",
          contentStyle: { backgroundColor: "#0F172A" },
        }}
      >
        <Stack.Screen name="login" options={{ headerShown: false }} />
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      </Stack>
    </>
  );
}

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <RootNavigator />
      </AuthProvider>
    </SafeAreaProvider>
  );
}
