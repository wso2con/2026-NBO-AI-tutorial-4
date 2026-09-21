import { useCallback, useEffect, useRef, useState } from "react";

// Polls one agent's /health endpoint on an interval and on demand (check()).
// `getUrl` is read fresh on every check so edits to the URL field take effect immediately.
// `apiKey`, when provided, is attached as `x-api-key` — same header streamChat()
// uses for /chat — since a gateway-fronted agent's /health can require it too.
export function useHealth(getUrl, { intervalMs = 8000, apiKey } = {}) {
  const [status, setStatus] = useState({ state: "checking", label: "checking…" });
  const getUrlRef = useRef(getUrl);
  getUrlRef.current = getUrl;

  const check = useCallback(async () => {
    const base = getUrlRef.current().trim().replace(/\/+$/, "");
    try {
      const headers = apiKey ? { "x-api-key": apiKey } : undefined;
      const res = await fetch(base + "/health", { cache: "no-store", headers });
      if (!res.ok) {
        setStatus({ state: "down", label: "" });
        return;
      }
      const data = await res.json().catch(() => ({}));
      setStatus({
        state: "up",
        label: (data.stage || "agent") + " / " + (data.agent || "agent") + (data.governed ? " / governed" : " / direct"),
      });
    } catch {
      setStatus({ state: "down", label: "" });
    }
  }, []);

  useEffect(() => {
    check();
    const id = setInterval(check, intervalMs);
    return () => clearInterval(id);
  }, [check, intervalMs]);

  return { status, check };
}
