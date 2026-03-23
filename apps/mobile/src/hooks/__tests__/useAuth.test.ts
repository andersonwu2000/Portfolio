import { renderHook, act, waitFor } from "@testing-library/react-native";
import React from "react";

// Mock expo-secure-store
jest.mock("expo-secure-store", () => {
  const store: Record<string, string> = {};
  return {
    getItemAsync: jest.fn((key: string) => Promise.resolve(store[key] ?? null)),
    setItemAsync: jest.fn((key: string, value: string) => {
      store[key] = value;
      return Promise.resolve();
    }),
    deleteItemAsync: jest.fn((key: string) => {
      delete store[key];
      return Promise.resolve();
    }),
  };
});

// Mock the API client module
jest.mock("../../api/client", () => ({
  saveApiKey: jest.fn().mockResolvedValue(undefined),
  saveToken: jest.fn().mockResolvedValue(undefined),
  clearToken: jest.fn().mockResolvedValue(undefined),
  setBaseUrl: jest.fn(),
  getApiKey: jest.fn().mockResolvedValue(null),
  getToken: jest.fn().mockResolvedValue(null),
}));

const mockLogin = jest.fn();
const mockHealth = jest.fn();
jest.mock("@quant/shared", () => ({
  auth: { login: (key: string) => mockLogin(key) },
  system: { health: () => mockHealth() },
}));

import { AuthProvider, useAuth } from "../useAuth";

// Wrapper that provides AuthContext
const wrapper = ({ children }: { children: React.ReactNode }) =>
  React.createElement(AuthProvider, null, children);

describe("useAuth", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("throws when used outside AuthProvider", () => {
    // Suppress console.error for expected error
    const spy = jest.spyOn(console, "error").mockImplementation(() => {});
    expect(() => {
      renderHook(() => useAuth());
    }).toThrow("useAuth must be used within an AuthProvider");
    spy.mockRestore();
  });

  it("starts in loading state", () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    expect(result.current.loading).toBe(true);
    expect(result.current.authenticated).toBe(false);
  });

  it("finishes loading when no saved credentials exist", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.authenticated).toBe(false);
  });

  it("sets error on login failure", async () => {
    mockLogin.mockRejectedValue(new Error("Invalid API key"));
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.login("http://localhost:8000", "bad-key");
    });

    expect(result.current.error).toBe("Invalid API key");
    expect(result.current.authenticated).toBe(false);
  });
});
