import AsyncStorage from "@react-native-async-storage/async-storage";

const CACHE_PREFIX = "quant_cache_";
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

export async function getCached<T>(key: string): Promise<T | null> {
  const raw = await AsyncStorage.getItem(CACHE_PREFIX + key);
  if (!raw) return null;
  const { data, timestamp } = JSON.parse(raw);
  if (Date.now() - timestamp > CACHE_TTL) return null;
  return data as T;
}

export async function setCache<T>(key: string, data: T): Promise<void> {
  await AsyncStorage.setItem(
    CACHE_PREFIX + key,
    JSON.stringify({ data, timestamp: Date.now() }),
  );
}
