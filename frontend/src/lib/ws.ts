type EventHandler = (event: Record<string, unknown>) => void;

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/query";

export class QueryWebSocket {
  private ws: WebSocket | null = null;
  private apiKey: string;
  private onEvent: EventHandler;

  constructor(apiKey: string, onEvent: EventHandler) {
    this.apiKey = apiKey;
    this.onEvent = onEvent;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      let settled = false;
      const settle = (fn: () => void) => {
        if (!settled) {
          settled = true;
          fn();
        }
      };

      this.ws = new WebSocket(WS_URL);

      this.ws.onopen = () => {
        this.ws!.send(JSON.stringify({ type: "auth", api_key: this.apiKey }));
      };

      this.ws.onmessage = (e) => {
        let event: Record<string, unknown>;
        try {
          event = JSON.parse(e.data) as Record<string, unknown>;
        } catch {
          return; // ignore non-JSON frames
        }
        if (event.type === "authenticated") {
          settle(resolve);
        } else {
          this.onEvent(event);
        }
      };

      this.ws.onerror = () =>
        settle(() => reject(new Error("WebSocket connection error")));
      this.ws.onclose = () =>
        settle(() =>
          reject(new Error("WebSocket closed before authentication"))
        );
    });
  }

  sendQuery(query: string, dsn: string, domain = "general", focusTable?: string): void {
    this.ws?.send(JSON.stringify({ type: "query", query, dsn, domain, focus_table: focusTable }));
  }

  disconnect(): void {
    this.ws?.close();
  }
}
