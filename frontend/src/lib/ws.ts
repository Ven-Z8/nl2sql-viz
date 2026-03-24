type EventHandler = (event: Record<string, unknown>) => void;

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
      this.ws = new WebSocket("ws://localhost:8000/ws/query");

      this.ws.onopen = () => {
        this.ws!.send(JSON.stringify({ type: "auth", api_key: this.apiKey }));
      };

      this.ws.onmessage = (e) => {
        const event = JSON.parse(e.data);
        if (event.type === "authenticated") {
          resolve();
        } else {
          this.onEvent(event);
        }
      };

      this.ws.onerror = reject;
    });
  }

  sendQuery(query: string, dsn: string): void {
    this.ws?.send(JSON.stringify({ type: "query", query, dsn }));
  }

  disconnect(): void {
    this.ws?.close();
  }
}
