import { useCallback, useEffect, useState } from "react";
import { API_BASE, apiUrl } from "@/lib/config";
import type { DemoSession } from "@/lib/types";

export interface BackendSession {
  apiKey: string;
  connectionId: string;
  focusTable?: string;
}

/**
 * Bootstraps the demo session: POST /api/demo/session → {username, api_key,
 * connection_id, dataset, focus_table}. Owns the human-readable connection
 * label shown in the workspace card and adopts new connection_ids returned
 * by later calls (bring-your-own-db / dataset loads).
 */
export function useBackendSession(enabled: boolean) {
  const [session, setSession] = useState<BackendSession | null>(null);
  const [connectionLabel, setConnectionLabel] = useState("Starting demo session…");

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;

    const start = async () => {
      // Ping /health FIRST so the free Render tier starts waking up before
      // we try to open a session. Without this, the first user waits the
      // full 30-60s cold-start before anything useful appears.
      try {
        await fetch(apiUrl("/health"), { method: "GET", cache: "no-store" });
      } catch {
        // best-effort; even if this fails, the session call will retry
      }
      try {
        const resp = await fetch(apiUrl("/api/demo/session"), { method: "POST" });
        const body = (await resp.json().catch(() => ({}))) as Partial<DemoSession> & {
          detail?: string;
        };
        if (!resp.ok || !body.api_key || !body.connection_id) {
          throw new Error(body.detail ?? "Could not start a demo session");
        }
        if (cancelled) return;
        setSession({
          apiKey: body.api_key,
          connectionId: body.connection_id,
          focusTable: body.focus_table,
        });
        try {
          setConnectionLabel(new URL(API_BASE).host);
        } catch {
          setConnectionLabel(API_BASE);
        }
      } catch (e) {
        if (!cancelled) {
          setConnectionLabel(
            e instanceof Error ? e.message : "Could not start a demo session"
          );
        }
      }
    };

    void start();
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  /** Swap in a fresh connection_id (and optional label) from any endpoint. */
  const adoptConnection = useCallback((id: string, label?: string) => {
    if (!id) return;
    setSession((prev) => (prev ? { ...prev, connectionId: id } : prev));
    if (label) setConnectionLabel(label);
  }, []);

  return { session, connectionLabel, adoptConnection };
}
