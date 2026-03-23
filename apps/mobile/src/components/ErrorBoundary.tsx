import { Component } from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import type { ReactNode, ErrorInfo } from "react";
import { bg, warning, textPrimary, textSecondary, blueDark, white } from "@/src/theme/colors";

interface Props { children: ReactNode; }
interface State { hasError: boolean; error: Error | null; }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };
  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary:", error, info.componentStack);
  }
  render() {
    if (this.state.hasError) {
      return (
        <View style={styles.container}>
          <Text style={styles.icon}>!</Text>
          <Text style={styles.title}>Something went wrong</Text>
          <Text style={styles.message}>{this.state.error?.message}</Text>
          <TouchableOpacity style={styles.button}
            onPress={() => this.setState({ hasError: false, error: null })}>
            <Text style={styles.buttonText}>Try Again</Text>
          </TouchableOpacity>
        </View>
      );
    }
    return this.props.children;
  }
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: bg, justifyContent: "center", alignItems: "center", padding: 24 },
  icon: { fontSize: 48, color: warning, fontWeight: "800", marginBottom: 16 },
  title: { color: textPrimary, fontSize: 20, fontWeight: "700", marginBottom: 8 },
  message: { color: textSecondary, fontSize: 14, textAlign: "center", marginBottom: 24 },
  button: { backgroundColor: blueDark, borderRadius: 10, paddingHorizontal: 24, paddingVertical: 12 },
  buttonText: { color: white, fontWeight: "600", fontSize: 15 },
});
