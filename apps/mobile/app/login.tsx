import { useState } from "react";
import {
  View,
  Text,
  TextInput,
  Pressable,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { useAuth } from "../src/hooks/useAuth";
import { useT } from "@/src/i18n";
import { bg, textPrimary, textMuted, textSecondary, surface, surfaceLight, textPlaceholder, warning, danger, blue, white } from "@/src/theme/colors";

export default function LoginScreen() {
  const { t } = useT();
  const [serverUrl, setServerUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const { login, loading, error } = useAuth();

  const handleLogin = async () => {
    if (serverUrl && apiKey) {
      await login(serverUrl, apiKey);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <View style={styles.inner}>
        <Text style={styles.title}>{t.login.title}</Text>
        <Text style={styles.subtitle}>{t.login.subtitle}</Text>

        <Text style={styles.label}>{t.login.serverUrl}</Text>
        <TextInput
          style={styles.input}
          value={serverUrl}
          onChangeText={setServerUrl}
          placeholder="https://your-server:8000"
          placeholderTextColor={textPlaceholder}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
        />
        {serverUrl.startsWith("http://") && !serverUrl.includes("localhost") && !serverUrl.includes("127.0.0.1") && (
          <Text style={styles.warning}>{t.login.insecureWarning}</Text>
        )}

        <Text style={styles.label}>{t.login.apiKey}</Text>
        <TextInput
          style={styles.input}
          value={apiKey}
          onChangeText={setApiKey}
          placeholder={t.login.apiKeyPlaceholder}
          placeholderTextColor={textPlaceholder}
          autoCapitalize="none"
          autoCorrect={false}
          secureTextEntry
        />

        {error && <Text style={styles.error}>{error}</Text>}

        <Pressable
          style={[styles.button, (!serverUrl || !apiKey) && styles.disabled]}
          onPress={handleLogin}
          disabled={loading || !serverUrl || !apiKey}
        >
          {loading ? (
            <ActivityIndicator color={white} />
          ) : (
            <Text style={styles.btnText}>{t.login.connect}</Text>
          )}
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: bg,
    justifyContent: "center",
  },
  inner: {
    paddingHorizontal: 32,
  },
  title: {
    color: textPrimary,
    fontSize: 32,
    fontWeight: "800",
    textAlign: "center",
    marginBottom: 4,
  },
  subtitle: {
    color: textMuted,
    fontSize: 14,
    textAlign: "center",
    marginBottom: 40,
  },
  label: {
    color: textSecondary,
    fontSize: 13,
    fontWeight: "600",
    marginBottom: 6,
    marginTop: 16,
  },
  input: {
    backgroundColor: surface,
    borderRadius: 10,
    padding: 14,
    color: textPrimary,
    fontSize: 16,
    borderWidth: 1,
    borderColor: surfaceLight,
  },
  warning: {
    color: warning,
    fontSize: 12,
    marginTop: 6,
  },
  error: {
    color: danger,
    fontSize: 13,
    marginTop: 12,
    textAlign: "center",
  },
  button: {
    backgroundColor: blue,
    borderRadius: 10,
    padding: 16,
    alignItems: "center",
    marginTop: 32,
  },
  disabled: {
    opacity: 0.5,
  },
  btnText: {
    color: white,
    fontSize: 16,
    fontWeight: "700",
  },
});
