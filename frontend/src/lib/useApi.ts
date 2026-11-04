import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage } from "./api";

/** Load `path` (null = don't load), optionally polling. A failed poll keeps the last good data. */
export function useApi<T>(path: string | null, intervalMs?: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(path !== null);
  const latest = useRef(0);

  const reload = useCallback(async () => {
    if (path === null) return;
    const mine = ++latest.current;
    try {
      const result = await api<T>(path);
      if (mine === latest.current) {
        setData(result);
        setError(null);
      }
    } catch (err) {
      if (mine === latest.current) setError(errorMessage(err));
    } finally {
      if (mine === latest.current) setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    setData(null);
    setError(null);
    setLoading(path !== null);
    void reload();
    const timer = intervalMs ? setInterval(() => void reload(), intervalMs) : undefined;
    return () => {
      latest.current++;
      if (timer) clearInterval(timer);
    };
  }, [path, intervalMs, reload]);

  return { data, error, loading, reload };
}
