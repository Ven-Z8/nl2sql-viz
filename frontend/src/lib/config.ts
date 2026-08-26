/**
 * Central runtime configuration — the ONLY place that reads NEXT_PUBLIC_*.
 *
 * These variables are inlined at build time (static export), so "runtime"
 * effectively means build time. If NEXT_PUBLIC_API_URL is missing we refuse
 * to fall back to localhost: the deployed bundle must never point at a
 * developer machine. Instead the app renders a setup-required card.
 */

const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL;

/** True when the app was built with a backend URL configured. */
export function isApiConfigured(): boolean {
  return Boolean(RAW_API_BASE);
}

/** Backend origin without trailing slash, e.g. "https://api.example.com". */
export const API_BASE: string = (RAW_API_BASE ?? "").replace(/\/+$/, "");

/**
 * Resolve a backend-relative path to an absolute URL.
 * Throws when the app is unconfigured — callers above the setup gate should
 * never hit this, and hitting it anywhere else should fail loudly.
 */
export function apiUrl(path: string): string {
  if (!API_BASE) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is not configured — cannot call backend API"
    );
  }
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

/**
 * WebSocket endpoint for the query stream.
 * Explicit NEXT_PUBLIC_WS_URL wins; otherwise derive from the API base by
 * swapping the scheme (https:// → wss://, http:// → ws://) and appending
 * /ws/query. Null when unconfigured.
 */
export const WS_URL: string | null = (() => {
  const explicit = process.env.NEXT_PUBLIC_WS_URL;
  if (explicit) return explicit;
  if (!RAW_API_BASE) return null;
  const base = RAW_API_BASE.replace(/\/+$/, "");
  if (base.startsWith("https://")) return `wss://${base.slice(8)}/ws/query`;
  if (base.startsWith("http://")) return `ws://${base.slice(7)}/ws/query`;
  return `${base}/ws/query`;
})();

// Fail loudly, once, at load time when the deployment is misconfigured.
if (!RAW_API_BASE && typeof console !== "undefined") {
  console.error(
    "[DataLens] NEXT_PUBLIC_API_URL is not set. " +
      "Rebuild the frontend with NEXT_PUBLIC_API_URL pointing at your backend " +
      "(e.g. NEXT_PUBLIC_API_URL=https://your-backend.onrender.com npm run build). " +
      "The app will show a setup-required screen."
  );
}
