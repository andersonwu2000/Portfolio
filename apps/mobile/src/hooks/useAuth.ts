import { createContext, useContext, useState, useCallback, useEffect, createElement } from "react";
import type { ReactNode } from "react";
import * as SecureStore from "expo-secure-store";
import {
  saveApiKey,
  saveToken,
  clearToken,
  setBaseUrl,
  getApiKey,
  getToken,
} from "../api/client";
import { system, auth } from "@quant/shared";
import type { UserRole } from "@quant/shared";

const ROLE_HIERARCHY: Record<UserRole, number> = {
  viewer: 0,
  researcher: 1,
  trader: 2,
  risk_manager: 3,
  admin: 4,
};

/**
 * Extract role from a JWT access_token (base64-decode the payload).
 * Returns "viewer" if decoding fails or role is missing.
 */
export function extractRoleFromJwt(token: string): UserRole {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return "viewer";
    // Handle base64url encoding: replace URL-safe chars and pad
    let b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    while (b64.length % 4 !== 0) b64 += "=";
    const payload = JSON.parse(atob(b64));
    const role = payload.role;
    if (typeof role === "string" && role in ROLE_HIERARCHY) return role as UserRole;
    return "viewer";
  } catch {
    return "viewer";
  }
}

export interface AuthState {
  authenticated: boolean;
  loading: boolean;
  error: string | null;
  role: UserRole;
}

interface AuthContextValue extends AuthState {
  login: (serverUrl: string, apiKey: string) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (minRole: UserRole) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const SAVED_URL_KEY = "server_url";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    authenticated: false,
    loading: true,
    error: null,
    role: "viewer",
  });

  const hasRole = useCallback(
    (minRole: UserRole): boolean => {
      return ROLE_HIERARCHY[state.role] >= ROLE_HIERARCHY[minRole];
    },
    [state.role],
  );

  const deriveRole = async (): Promise<UserRole> => {
    const token = await getToken();
    if (token) {
      return extractRoleFromJwt(token);
    }
    return "viewer";
  };

  const login = useCallback(
    async (serverUrl: string, apiKey: string) => {
      setState({ authenticated: false, loading: true, error: null, role: "viewer" });
      try {
        setBaseUrl(serverUrl);
        await SecureStore.setItemAsync(SAVED_URL_KEY, serverUrl);
        await saveApiKey(apiKey);
        const { access_token } = await auth.login(apiKey);
        await saveToken(access_token);
        const role = extractRoleFromJwt(access_token);
        setState({ authenticated: true, loading: false, error: null, role });
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Connection failed";
        setState({ authenticated: false, loading: false, error: message, role: "viewer" });
      }
    },
    [],
  );

  const logout = useCallback(async () => {
    await clearToken();
    await SecureStore.deleteItemAsync("api_key");
    setState({ authenticated: false, loading: false, error: null, role: "viewer" });
  }, []);

  // Check for existing session on mount
  useEffect(() => {
    (async () => {
      // Restore saved base URL first (C3)
      const savedUrl = await SecureStore.getItemAsync(SAVED_URL_KEY);
      if (savedUrl) {
        setBaseUrl(savedUrl);
      }

      const apiKey = await getApiKey();
      if (apiKey) {
        try {
          await system.health();
          const role = await deriveRole();
          setState({ authenticated: true, loading: false, error: null, role });
        } catch {
          setState({ authenticated: false, loading: false, error: null, role: "viewer" });
        }
      } else {
        setState({ authenticated: false, loading: false, error: null, role: "viewer" });
      }
    })();
  }, []);

  return createElement(AuthContext.Provider, { value: { ...state, login, logout, hasRole } }, children);
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
