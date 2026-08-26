import { WS_URL } from "./config";

/**
 * Resilient query WebSocket.
 *
 * Contract (agreed with backend):
 *  - outbound query: { type:"query", query, connection_id, domain?, focus_table?,
 *    thread_id? } — contract v3: thread_id is sent only when continuing an
 *    existing conversation; omitted (or null) starts a new topic.
 *  - outbound clarification: { type:"clarification_response", choice }
 *    — answers an inbound "clarify" event over the same socket.
 *  - inbound: auth handshake unchanged ("auth" → "authenticated"), then
 *    progress/sql/result/error/clarify events forwarded verbatim to onEvent.
 *
 * Reconnect policy: exponential backoff starting at 1s, capped at 15s,
 * retrying indefinitely while the page is visible. While the tab is hidden
 * retries pause; returning to the tab resumes them immediately. close() is
 * the only way to stop the loop permanently.
 */

export type WsStatus = "connecting" | "open" | "retrying" | "closed";

const BACKOFF_BASE_MS = 1_000;
const BACKOFF_CAP_MS = 15_000;
/** If the server accepts the socket but never answers "auth", recycle it. */
const AUTH_TIMEOUT_MS = 10_000;

export interface QuerySendOptions {
  connectionId: string;
  domain?: string;
  focusTable?: string;
  /** Contract v3 — set to the active thread's id to continue a conversation.
   *  Null/undefined omits the field entirely (new topic). */
  threadId?: string | null;
}

interface QueryWebSocketHandlers {
  /** Pipeline/result/error events (never the internal auth handshake). */
  onEvent: (event: Record<string, unknown>) => void;
  /** Connection lifecycle notifications for UI status surfaces. */
  onStatus?: (status: WsStatus) => void;
}

export class QueryWebSocket {
  private ws: WebSocket | null = null;
  private attempts = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private authTimer: ReturnType<typeof setTimeout> | null = null;
  private visibilityHandler: (() => void) | null = null;
  private disposed = false;
  private currentStatus: WsStatus = "closed";
  private readonly statusListeners = new Set<(s: WsStatus) => void>();

  constructor(
    private apiKey: string,
    private handlers: QueryWebSocketHandlers
  ) {}

  /** Current lifecycle status (also pushed via subscribe/onStatus). */
  get status(): WsStatus {
    return this.currentStatus;
  }

  /** Subscribe to status changes. Returns an unsubscribe function. */
  subscribe(fn: (status: WsStatus) => void): () => void {
    this.statusListeners.add(fn);
    fn(this.currentStatus);
    return () => this.statusListeners.delete(fn);
  }

  /** Start connecting. Safe to call once per instance. */
  connect(): void {
    if (this.disposed) return;
    this.attempts = 0;
    this.clearTimer();
    this.installVisibilityResume();
    this.open();
  }

  /**
   * Send a query over an open socket.
   * Never throws into the caller — returns false when the socket isn't
   * ready so the UI can surface an honest message instead of crashing.
   */
  sendQuery(query: string, options: QuerySendOptions): boolean {
    const ws = this.ws;
    if (!ws || ws.readyState !== WebSocket.OPEN || this.disposed) {
      return false;
    }
    const payload: Record<string, unknown> = {
      type: "query",
      query,
      connection_id: options.connectionId,
    };
    if (options.domain) payload.domain = options.domain;
    if (options.focusTable) payload.focus_table = options.focusTable;
    // Contract v3: omit thread_id entirely when starting a new topic.
    if (options.threadId) payload.thread_id = options.threadId;
    ws.send(JSON.stringify(payload));
    return true;
  }

  /**
   * Answer an inbound "clarify" event (contract v2). `choice` is the 0-based
   * index of the picked option. Returns false when the socket isn't ready —
   * the server's ~120s timeout is the safety net either way.
   */
  sendClarificationResponse(choice: number): boolean {
    const ws = this.ws;
    if (!ws || ws.readyState !== WebSocket.OPEN || this.disposed) {
      return false;
    }
    ws.send(JSON.stringify({ type: "clarification_response", choice }));
    return true;
  }

  /** Permanently close and stop reconnecting. */
  close(): void {
    this.disposed = true;
    this.clearTimer();
    this.clearAuthTimer();
    this.removeVisibilityResume();
    const ws = this.ws;
    this.ws = null;
    if (ws) {
      ws.onopen = null;
      ws.onmessage = null;
      ws.onerror = null;
      ws.onclose = null;
      try {
        ws.close();
      } catch {
        // already closed
      }
    }
    this.setStatus("closed");
  }

  // ── internals ────────────────────────────────────────────────

  private open(): void {
    if (this.disposed || typeof WebSocket === "undefined") return;
    if (!WS_URL) {
      this.setStatus("closed");
      return;
    }
    this.clearAuthTimer();
    this.setStatus(this.attempts === 0 ? "connecting" : "retrying");

    let socket: WebSocket;
    try {
      socket = new WebSocket(WS_URL);
    } catch {
      this.scheduleRetry();
      return;
    }
    this.ws = socket;

    socket.onopen = () => {
      socket.send(JSON.stringify({ type: "auth", api_key: this.apiKey }));
      // Recycle silent sockets so the UI lands in honest "retrying" state.
      this.authTimer = setTimeout(() => {
        try {
          socket.close();
        } catch {
          // noop — retry path handles the rest
        }
      }, AUTH_TIMEOUT_MS);
    };

    socket.onmessage = (e: MessageEvent) => {
      let event: Record<string, unknown>;
      try {
        event = JSON.parse(e.data as string) as Record<string, unknown>;
      } catch {
        return; // ignore non-JSON frames
      }
      if (event.type === "authenticated") {
        this.clearAuthTimer();
        this.attempts = 0;
        this.setStatus("open");
        return;
      }
      this.handlers.onEvent(event);
    };

    socket.onerror = () => {
      // onclose always follows; all recovery lives there.
    };

    socket.onclose = () => {
      this.clearAuthTimer();
      if (this.ws === socket) this.ws = null;
      if (this.disposed) return;
      this.scheduleRetry();
    };
  }

  private scheduleRetry(): void {
    if (this.disposed || this.closedByUser()) return;
    // Pause while hidden; visibility handler resumes on return.
    if (
      typeof document !== "undefined" &&
      document.visibilityState === "hidden"
    ) {
      this.setStatus("retrying");
      return;
    }
    const delay = Math.min(
      BACKOFF_BASE_MS * 2 ** Math.min(this.attempts, 10),
      BACKOFF_CAP_MS
    );
    this.attempts += 1;
    this.setStatus("retrying");
    this.clearTimer();
    this.timer = setTimeout(() => this.open(), delay);
  }

  private closedByUser(): boolean {
    return this.disposed;
  }

  private installVisibilityResume(): void {
    if (typeof document === "undefined" || this.visibilityHandler) return;
    this.visibilityHandler = () => {
      if (this.disposed) return;
      if (
        document.visibilityState === "visible" &&
        (!this.ws || this.ws.readyState >= WebSocket.CLOSING) &&
        !this.timer
      ) {
        // Resume immediately when coming back to a visible tab.
        this.open();
      }
    };
    document.addEventListener("visibilitychange", this.visibilityHandler);
  }

  private removeVisibilityResume(): void {
    if (this.visibilityHandler && typeof document !== "undefined") {
      document.removeEventListener("visibilitychange", this.visibilityHandler);
    }
    this.visibilityHandler = null;
  }

  private clearTimer(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
  }

  private clearAuthTimer(): void {
    if (this.authTimer) clearTimeout(this.authTimer);
    this.authTimer = null;
  }

  private setStatus(status: WsStatus): void {
    this.currentStatus = status;
    this.handlers.onStatus?.(status);
    this.statusListeners.forEach((fn) => fn(status));
  }
}
