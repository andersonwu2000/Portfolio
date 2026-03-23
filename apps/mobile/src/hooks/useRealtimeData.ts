import { useState, useEffect, useCallback, useRef } from "react";
import { AppState as RNAppState } from "react-native";
import { WSManager } from "@quant/shared";
import { getCached, setCache } from "../utils/cache";

type Channel = ConstructorParameters<typeof WSManager>[0];

export function useRealtimeData<T>(
  fetchFn: () => Promise<T>,
  channel: Channel,
  mergeFn: (prev: T, update: unknown) => T,
  initialValue: T,
) {
  const [data, setData] = useState<T>(initialValue);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WSManager | null>(null);
  const fetchRef = useRef(fetchFn);
  const mergeRef = useRef(mergeFn);
  fetchRef.current = fetchFn;
  mergeRef.current = mergeFn;

  const refresh = useCallback(async () => {
    try {
      const result = await fetchRef.current();
      setData(result);
      setError(null);
      setCache(channel, result).catch(() => {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
      // On fetch error, try to return cached data
      try {
        const cached = await getCached<T>(channel);
        if (cached !== null) setData(cached);
      } catch {
        // ignore cache read errors
      }
    } finally {
      setLoading(false);
    }
  }, [channel]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const ws = new WSManager(channel);
    wsRef.current = ws;
    ws.connect();
    const unsubscribe = ws.subscribe((update) => {
      setData((prev) => mergeRef.current(prev, update));
    });

    const sub = RNAppState.addEventListener("change", (state) => {
      if (state === "active") {
        ws.connect();
        refresh();
      } else if (state === "background") {
        ws.disconnect();
      }
    });

    return () => {
      sub.remove();
      unsubscribe();
      ws.disconnect();
    };
  }, [channel, refresh]);

  return { data, loading, error, refresh };
}
