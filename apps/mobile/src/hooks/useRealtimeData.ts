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
  const mountedRef = useRef(true);
  const fetchRef = useRef(fetchFn);
  const mergeRef = useRef(mergeFn);
  fetchRef.current = fetchFn;
  mergeRef.current = mergeFn;

  const refresh = useCallback(async () => {
    try {
      const result = await fetchRef.current();
      if (!mountedRef.current) return;
      setData(result);
      setError(null);
      setCache(channel, result).catch(() => {});
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err.message : "Request failed");
      try {
        const cached = await getCached<T>(channel);
        if (cached !== null && mountedRef.current) setData(cached);
      } catch {
        // ignore cache read errors
      }
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, [channel]);

  useEffect(() => {
    mountedRef.current = true;
    refresh();

    const ws = new WSManager(channel);
    ws.connect();
    const unsubscribe = ws.subscribe((update) => {
      if (mountedRef.current) {
        setData((prev) => mergeRef.current(prev, update));
      }
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
      mountedRef.current = false;
      sub.remove();
      unsubscribe();
      ws.disconnect();
    };
  }, [channel, refresh]);

  return { data, loading, error, refresh };
}
