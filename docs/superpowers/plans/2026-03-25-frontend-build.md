# DataLens AI Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full DataLens AI frontend UI per the design spec — dark two-panel layout with real-time WebSocket streaming, Vega-Lite chart rendering, activity log, and query history — then verify the complete backend + frontend stack with a full round-trip test.

**Architecture:** Five new components (`TopBar`, `LeftPanel`, `LogStream`, `RightPanel`) plus a full rewrite of `page.tsx` as the state + WS orchestrator. All WebSocket event routing, state management, and log lifecycle live exclusively in `page.tsx`. Components are pure/dumb — they receive props and emit callbacks. VegaChart and ws.ts are kept as-is.

**Tech Stack:** Next.js 14 (App Router), TypeScript, Tailwind CSS v4, vega-embed v5, Python/FastAPI backend (pytest + Starlette TestClient for integration tests)

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `frontend/src/app/globals.css` | DataLens color tokens + body/html full-height reset |
| Modify | `frontend/src/app/layout.tsx` | Title → "DataLens AI", html/body fill viewport |
| Create | `frontend/src/components/TopBar.tsx` | Logo + connection status pill |
| Create | `frontend/src/components/LogStream.tsx` | Scrolling activity log with icons and blink cursor |
| Create | `frontend/src/components/LeftPanel.tsx` | Query textarea + Ask button + LogStream + history list |
| Create | `frontend/src/components/RightPanel.tsx` | Chart area + collapsible SQL panel |
| Modify | `frontend/src/app/page.tsx` | Full rewrite: WS state, event routing, layout shell |
| Delete | `frontend/src/components/QueryInput.tsx` | Absorbed into LeftPanel; verify no remaining imports first |
| Keep   | `frontend/src/components/VegaChart.tsx` | Unchanged |
| Keep   | `frontend/src/lib/ws.ts` | Unchanged |

---

## Task 1 — CSS Tokens + Layout Reset

**Files:**
- Modify: `frontend/src/app/globals.css`
- Modify: `frontend/src/app/layout.tsx`

### Context

`globals.css` currently has a light/dark media query with generic variables. Replace it with the DataLens color token set. `layout.tsx` needs its title updated and `html`/`body` must fill the full viewport (the two-panel layout is fixed-height — no page scroll).

- [ ] **Step 1: Rewrite `globals.css`**

  ```css
  @import "tailwindcss";

  :root {
    --bg:           #070b10;
    --bg-panel:     #0d1117;
    --bg-input:     #161b22;
    --bg-log:       #0a0e14;
    --border:       #30363d;
    --border-subtle:#21262d;

    --text-primary:   #e6edf3;
    --text-secondary: #8b949e;
    --text-muted:     #484f58;

    --accent:      #06b6d4;
    --accent-deep: #0891b2;
    --accent-glow: #06b6d422;
    --accent-dim:  #06b6d444;
    --accent-hist: #071922;

    --green:   #3fb950;

    --kw-color:  #06b6d4;
    --fn-color:  #a5f3fc;
    --id-color:  #67e8f9;
    --lit-color: #cffafe;
  }

  html, body {
    height: 100%;
    overflow: hidden;
    background: var(--bg);
    color: var(--text-primary);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  }

  @keyframes blink {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0; }
  }

  .kw  { color: var(--kw-color); }
  .fn  { color: var(--fn-color); }
  .id  { color: var(--id-color); }
  .lit { color: var(--lit-color); }
  ```

- [ ] **Step 2: Update `layout.tsx`**

  Change title metadata to `"DataLens AI"` and make `html`/`body` fill the viewport:

  ```tsx
  import type { Metadata } from "next";
  import "./globals.css";

  export const metadata: Metadata = {
    title: "DataLens AI",
    description: "Ask natural language questions about your database.",
  };

  export default function RootLayout({
    children,
  }: Readonly<{ children: React.ReactNode }>) {
    return (
      <html lang="en" className="h-full">
        <body className="h-full flex flex-col overflow-hidden">{children}</body>
      </html>
    );
  }
  ```

  Note: Remove the Geist font imports — they're unused in the new design (CSS variables handle fonts).

- [ ] **Step 3: TypeScript check**

  ```bash
  cd /Volumes/VeN/Claude-Code-Work/projects/nl2sql-viz/frontend
  npx tsc --noEmit
  ```

  Expected: No errors.

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/app/globals.css frontend/src/app/layout.tsx
  git commit -m "style: DataLens color tokens, full-height body reset, remove Geist fonts

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
  ```

---

## Task 2 — `TopBar.tsx`

**Files:**
- Create: `frontend/src/components/TopBar.tsx`

### Context

Simple header bar with a teal hex-icon logo, "DataLens AI" wordmark, and a `connected` status pill. No interactivity — pure display.

- [ ] **Step 1: Create `TopBar.tsx`**

  ```tsx
  interface TopBarProps {
    connected: boolean;
  }

  export default function TopBar({ connected }: TopBarProps) {
    return (
      <header
        style={{
          background: "var(--bg-panel)",
          borderBottom: "1px solid var(--border-subtle)",
          padding: "0 20px",
          height: "48px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexShrink: 0,
        }}
      >
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span
            style={{
              fontSize: "20px",
              background: "linear-gradient(135deg, var(--accent), var(--accent-deep))",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            ⬡
          </span>
          <span
            style={{
              fontWeight: 600,
              fontSize: "15px",
              color: "var(--text-primary)",
              letterSpacing: "-0.01em",
            }}
          >
            DataLens AI
          </span>
        </div>

        {/* Status pill */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            padding: "4px 10px",
            borderRadius: "999px",
            background: connected ? "#0d2b14" : "var(--bg-input)",
            border: `1px solid ${connected ? "#238636" : "var(--border)"}`,
            fontSize: "12px",
            color: connected ? "var(--green)" : "var(--text-muted)",
          }}
        >
          <span
            style={{
              width: "6px",
              height: "6px",
              borderRadius: "50%",
              background: connected ? "var(--green)" : "var(--text-muted)",
              flexShrink: 0,
            }}
          />
          {connected ? "Connected" : "Disconnected"}
        </div>
      </header>
    );
  }
  ```

- [ ] **Step 2: TypeScript check**

  ```bash
  cd /Volumes/VeN/Claude-Code-Work/projects/nl2sql-viz/frontend
  npx tsc --noEmit
  ```

  Expected: No errors.

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/components/TopBar.tsx
  git commit -m "feat: add TopBar component with logo and connection status pill

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
  ```

---

## Task 3 — `LogStream.tsx`

**Files:**
- Create: `frontend/src/components/LogStream.tsx`

### Context

Renders a scrollable monospace log box. Each entry has a time string, an icon (`done`/`run`/`sql`), and a text field. The most recent active entry shows a blinking cursor. Auto-scrolls to bottom whenever entries change.

- [ ] **Step 1: Create `LogStream.tsx`**

  ```tsx
  "use client";
  import { useEffect, useRef } from "react";

  export type LogEntry = {
    time: string;
    icon: "done" | "run" | "sql";
    text: string;
    active?: boolean;
  };

  interface LogStreamProps {
    logs: LogEntry[];
  }

  const ICON: Record<LogEntry["icon"], { char: string; color: string }> = {
    done: { char: "✓", color: "var(--green)" },
    run:  { char: "⏳", color: "var(--accent)" },
    sql:  { char: "⬡", color: "var(--accent)" },
  };

  export default function LogStream({ logs }: LogStreamProps) {
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [logs]);

    return (
      <div
        style={{
          background: "var(--bg-log)",
          borderRadius: "6px",
          padding: "8px",
          height: "110px",
          overflowY: "auto",
          fontFamily: "'SF Mono', 'Fira Code', 'JetBrains Mono', Menlo, Consolas, monospace",
          fontSize: "11px",
          lineHeight: "1.7",
          color: "var(--text-secondary)",
        }}
      >
        {logs.length === 0 && (
          <span style={{ color: "var(--text-muted)" }}>Waiting for query…</span>
        )}
        {logs.map((entry, i) => {
          const ic = ICON[entry.icon];
          return (
            <div key={i} style={{ display: "flex", gap: "6px", alignItems: "flex-start" }}>
              <span style={{ color: "var(--text-muted)", flexShrink: 0 }}>{entry.time}</span>
              <span style={{ color: ic.color, flexShrink: 0 }}>{ic.char}</span>
              <span style={{ color: entry.active ? "var(--text-primary)" : undefined }}>
                {entry.text}
                {entry.active && (
                  <span
                    style={{
                      display: "inline-block",
                      marginLeft: "2px",
                      color: "var(--accent)",
                      animation: "blink 1s step-end infinite",
                    }}
                  >
                    ▋
                  </span>
                )}
              </span>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    );
  }
  ```

- [ ] **Step 2: TypeScript check**

  ```bash
  cd /Volumes/VeN/Claude-Code-Work/projects/nl2sql-viz/frontend
  npx tsc --noEmit
  ```

  Expected: No errors.

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/components/LogStream.tsx
  git commit -m "feat: add LogStream component with icon rows and blink cursor

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
  ```

---

## Task 4 — `LeftPanel.tsx`

**Files:**
- Create: `frontend/src/components/LeftPanel.tsx`

### Context

280px fixed-width left column. Three sections divided by subtle borders:
1. Query textarea (72px) + "Ask DataLens →" button
2. Activity label + `<LogStream>`
3. History label + scrollable list of past queries

History items show query text (truncated, one line) + timestamp below. Clicking populates the textarea but does NOT re-submit. The currently active result in history (index 0 = most recent) gets a teal border + dark background.

- [ ] **Step 1: Create `LeftPanel.tsx`**

  ```tsx
  "use client";
  import LogStream, { LogEntry } from "./LogStream";

  export type HistoryItem = { query: string; timestamp: string };

  interface LeftPanelProps {
    query: string;
    onQueryChange: (q: string) => void;
    onSubmit: () => void;
    isLoading: boolean;
    logs: LogEntry[];
    history: HistoryItem[];
    activeHistoryIndex: number | null;
    onHistoryClick: (q: string) => void;
  }

  export default function LeftPanel({
    query,
    onQueryChange,
    onSubmit,
    isLoading,
    logs,
    history,
    activeHistoryIndex,
    onHistoryClick,
  }: LeftPanelProps) {
    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        if (query.trim() && !isLoading) onSubmit();
      }
    };

    return (
      <aside
        style={{
          width: "280px",
          flexShrink: 0,
          background: "var(--bg-panel)",
          borderRight: "1px solid var(--border-subtle)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Query section */}
        <div style={{ padding: "16px", borderBottom: "1px solid var(--border-subtle)" }}>
          <textarea
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            placeholder="Ask a question about your data…"
            style={{
              width: "100%",
              height: "72px",
              background: "var(--bg-input)",
              border: "1px solid var(--border)",
              borderRadius: "6px",
              padding: "8px 10px",
              fontSize: "13px",
              color: "var(--text-primary)",
              resize: "none",
              outline: "none",
              fontFamily: "inherit",
              boxSizing: "border-box",
              transition: "border-color 0.15s, box-shadow 0.15s",
            }}
            onFocus={(e) => {
              e.target.style.borderColor = "var(--accent)";
              e.target.style.boxShadow = "0 0 0 3px var(--accent-glow)";
            }}
            onBlur={(e) => {
              e.target.style.borderColor = "var(--border)";
              e.target.style.boxShadow = "none";
            }}
          />
          <button
            onClick={onSubmit}
            disabled={isLoading || !query.trim()}
            style={{
              marginTop: "8px",
              width: "100%",
              padding: "8px",
              background: isLoading || !query.trim()
                ? "var(--bg-input)"
                : "linear-gradient(90deg, var(--accent), var(--accent-deep))",
              border: "none",
              borderRadius: "6px",
              color: isLoading || !query.trim() ? "var(--text-muted)" : "#fff",
              fontSize: "13px",
              fontWeight: 500,
              cursor: isLoading || !query.trim() ? "not-allowed" : "pointer",
              transition: "opacity 0.15s",
            }}
          >
            {isLoading ? "Running…" : "Ask DataLens →"}
          </button>
        </div>

        {/* Activity log section */}
        <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border-subtle)" }}>
          <div
            style={{
              fontSize: "11px",
              fontWeight: 600,
              color: "var(--text-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: "8px",
            }}
          >
            Activity
          </div>
          <LogStream logs={logs} />
        </div>

        {/* History section */}
        <div style={{ flex: 1, overflowY: "auto", padding: "12px 16px" }}>
          <div
            style={{
              fontSize: "11px",
              fontWeight: 600,
              color: "var(--text-muted)",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: "8px",
            }}
          >
            History
          </div>
          {history.length === 0 && (
            <p style={{ fontSize: "12px", color: "var(--text-muted)" }}>No queries yet.</p>
          )}
          {history.map((item, i) => {
            const isActive = i === activeHistoryIndex;
            return (
              <div
                key={i}
                onClick={() => onHistoryClick(item.query)}
                style={{
                  padding: "8px 10px",
                  borderRadius: "6px",
                  marginBottom: "4px",
                  cursor: "pointer",
                  background: isActive ? "var(--accent-hist)" : "transparent",
                  border: `1px solid ${isActive ? "var(--accent-dim)" : "transparent"}`,
                  transition: "background 0.1s",
                }}
                onMouseEnter={(e) => {
                  if (!isActive)
                    (e.currentTarget as HTMLDivElement).style.background = "var(--bg-input)";
                }}
                onMouseLeave={(e) => {
                  if (!isActive)
                    (e.currentTarget as HTMLDivElement).style.background = "transparent";
                }}
              >
                <div
                  style={{
                    fontSize: "12px",
                    color: "var(--text-primary)",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {item.query}
                </div>
                <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
                  {item.timestamp}
                </div>
              </div>
            );
          })}
        </div>
      </aside>
    );
  }
  ```

- [ ] **Step 2: TypeScript check**

  ```bash
  cd /Volumes/VeN/Claude-Code-Work/projects/nl2sql-viz/frontend
  npx tsc --noEmit
  ```

  Expected: No errors.

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/components/LeftPanel.tsx
  git commit -m "feat: add LeftPanel with query input, activity log, and query history

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
  ```

---

## Task 5 — `RightPanel.tsx`

**Files:**
- Create: `frontend/src/components/RightPanel.tsx`

### Context

Right panel takes the remaining width. Header: result title (left) + "SQL ▾" / "SQL ▴" toggle (right). Chart area: centered, max-width 600px, shows VegaChart when `vegaSpec` is not null, otherwise a muted placeholder. SQL panel: fixed at bottom, collapses/expands via `sqlVisible`.

SQL syntax highlighting uses the CSS classes `.kw .fn .id .lit` already defined in globals.css. A simple regex highlighter is applied client-side before rendering.

- [ ] **Step 1: Create `RightPanel.tsx`**

  ```tsx
  "use client";
  import VegaChart from "./VegaChart";

  interface RightPanelProps {
    title: string;
    vegaSpec: string | null;
    sql: string;
    sqlVisible: boolean;
    onToggleSql: () => void;
  }

  function highlightSQL(sql: string): string {
    const keywords = /\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|HAVING|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AS|AND|OR|NOT|IN|LIKE|LIMIT|OFFSET|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|WITH|UNION|DISTINCT|COUNT|SUM|AVG|MIN|MAX|CASE|WHEN|THEN|ELSE|END|NULL|IS|BY|ASC|DESC)\b/gi;
    const functions = /\b(count|sum|avg|min|max|coalesce|nullif|cast|extract|date_trunc|now|current_date|round|floor|ceil|abs|length|lower|upper|trim|substr|replace)\b/gi;
    const strings = /('(?:[^']|'')*')/g;
    const numbers = /\b(\d+(?:\.\d+)?)\b/g;

    return sql
      .replace(strings, '<span class="lit">$1</span>')
      .replace(numbers, '<span class="lit">$1</span>')
      .replace(functions, '<span class="fn">$&</span>')
      .replace(keywords, '<span class="kw">$&</span>');
  }

  export default function RightPanel({
    title,
    vegaSpec,
    sql,
    sqlVisible,
    onToggleSql,
  }: RightPanelProps) {
    return (
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          background: "var(--bg)",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "14px 24px",
            borderBottom: "1px solid var(--border-subtle)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexShrink: 0,
          }}
        >
          <span
            style={{
              fontSize: "14px",
              fontWeight: 600,
              color: title ? "var(--text-primary)" : "var(--text-muted)",
            }}
          >
            {title || "Results"}
          </span>
          {sql && (
            <button
              onClick={onToggleSql}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                color: "var(--accent)",
                fontSize: "13px",
                fontWeight: 500,
                padding: "4px 8px",
                borderRadius: "4px",
              }}
            >
              SQL {sqlVisible ? "▴" : "▾"}
            </button>
          )}
        </div>

        {/* Chart area */}
        <div
          style={{
            flex: 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "24px",
            overflow: "hidden",
          }}
        >
          {vegaSpec ? (
            <div style={{ width: "100%", maxWidth: "600px" }}>
              <VegaChart spec={vegaSpec} />
            </div>
          ) : (
            <p
              style={{
                color: "var(--text-muted)",
                fontSize: "14px",
                textAlign: "center",
              }}
            >
              Ask a question to see results
            </p>
          )}
        </div>

        {/* SQL panel */}
        {sqlVisible && sql && (
          <div
            style={{
              flexShrink: 0,
              borderTop: "1px solid var(--border-subtle)",
              background: "var(--bg-panel)",
              padding: "12px 24px",
              maxHeight: "160px",
              overflowY: "auto",
              fontFamily: "'SF Mono', 'Fira Code', Menlo, Consolas, monospace",
              fontSize: "12px",
              lineHeight: "1.7",
              color: "var(--text-secondary)",
              whiteSpace: "pre-wrap",
            }}
            dangerouslySetInnerHTML={{ __html: highlightSQL(sql) }}
          />
        )}
      </div>
    );
  }
  ```

- [ ] **Step 2: TypeScript check**

  ```bash
  cd /Volumes/VeN/Claude-Code-Work/projects/nl2sql-viz/frontend
  npx tsc --noEmit
  ```

  Expected: No errors.

- [ ] **Step 3: Commit**

  ```bash
  git add frontend/src/components/RightPanel.tsx
  git commit -m "feat: add RightPanel with Vega chart, SQL toggle, and syntax highlighting

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
  ```

---

## Task 6 — `page.tsx` Rewrite

**Files:**
- Modify: `frontend/src/app/page.tsx` (full rewrite)
- Delete: `frontend/src/components/QueryInput.tsx`

### Context

`page.tsx` is the single source of truth for all state and WebSocket event routing. It mounts the WS on load, routes each incoming message type to the appropriate state update, and passes everything down as props. The log lifecycle rule:
- `progress` event: mark previous active entry `done`, append new `{ icon: 'run', active: true }`
- `sql` event: append `{ icon: 'sql', active: false }`, update `sql` state
- `result` event: mark last active entry done, set `vegaSpec`, set `isLoading: false`
- `error` event: mark last active entry done, append error entry, set `isLoading: false`

The `connected` flag is set to `true` after `ws.connect()` resolves and `false` on cleanup. It does NOT update mid-session (out of scope per spec).

`activeHistoryIndex` is always `0` after a successful submit (most recent result = index 0 in history array). It stays `0` until the next submit.

- [ ] **Step 1: Rewrite `page.tsx`**

  ```tsx
  "use client";
  import { useState, useEffect, useRef, useCallback } from "react";
  import { QueryWebSocket } from "@/lib/ws";
  import TopBar from "@/components/TopBar";
  import LeftPanel, { HistoryItem } from "@/components/LeftPanel";
  import RightPanel from "@/components/RightPanel";
  import { LogEntry } from "@/components/LogStream";

  const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";
  const DSN = process.env.NEXT_PUBLIC_DSN ?? "";

  function now(): string {
    return new Date().toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }

  export default function Home() {
    const [query, setQuery] = useState("");
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [history, setHistory] = useState<HistoryItem[]>([]);
    const [vegaSpec, setVegaSpec] = useState<string | null>(null);
    const [sql, setSql] = useState("");
    const [sqlVisible, setSqlVisible] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [connected, setConnected] = useState(false);
    const [resultTitle, setResultTitle] = useState("");

    const wsRef = useRef<QueryWebSocket | null>(null);

    // Mark the last active log entry as done
    const markLastDone = useCallback(() => {
      setLogs((prev) =>
        prev.map((e, i) =>
          i === prev.length - 1 && e.active ? { ...e, active: false, icon: "done" as const } : e
        )
      );
    }, []);

    useEffect(() => {
      if (!API_KEY) return;

      const ws = new QueryWebSocket(API_KEY, (event) => {
        if (event.type === "progress") {
          const msg = event.message as string;
          setLogs((prev) => {
            const updated = prev.map((e, i) =>
              i === prev.length - 1 && e.active ? { ...e, active: false, icon: "done" as const } : e
            );
            return [...updated, { time: now(), icon: "run" as const, text: msg, active: true }];
          });
        }

        if (event.type === "sql") {
          const rawSql = event.sql as string;
          setSql(rawSql);
          setLogs((prev) => [
            ...prev,
            {
              time: now(),
              icon: "sql" as const,
              text: rawSql.slice(0, 40) + (rawSql.length > 40 ? "…" : ""),
              active: false,
            },
          ]);
        }

        if (event.type === "result") {
          setLogs((prev) =>
            prev.map((e, i) =>
              i === prev.length - 1 && e.active ? { ...e, active: false, icon: "done" as const } : e
            )
          );
          setVegaSpec(event.vega_spec as string);
          if (event.sql) setSql(event.sql as string);
          setIsLoading(false);
        }

        if (event.type === "error") {
          setLogs((prev) => {
            const updated = prev.map((e, i) =>
              i === prev.length - 1 && e.active ? { ...e, active: false, icon: "done" as const } : e
            );
            return [
              ...updated,
              {
                time: now(),
                icon: "run" as const,
                text: `Error: ${event.message as string}`,
                active: false,
              },
            ];
          });
          setIsLoading(false);
        }
      });

      ws.connect()
        .then(() => {
          wsRef.current = ws;
          setConnected(true);
        })
        .catch(() => setConnected(false));

      return () => {
        ws.disconnect();
        setConnected(false);
      };
    }, [markLastDone]);

    const handleSubmit = () => {
      if (!query.trim() || isLoading) return;

      if (!DSN) {
        setLogs((prev) => [
          ...prev,
          { time: now(), icon: "run", text: "Missing DSN — set NEXT_PUBLIC_DSN", active: false },
        ]);
        return;
      }

      // Reset result state
      setLogs([]);
      setVegaSpec(null);
      setSql("");
      setSqlVisible(false);
      setIsLoading(true);
      setResultTitle(query);

      // Prepend to history
      setHistory((prev) => [{ query, timestamp: now() }, ...prev]);

      wsRef.current?.sendQuery(query, DSN);
    };

    return (
      <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
        <TopBar connected={connected} />
        <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
          <LeftPanel
            query={query}
            onQueryChange={setQuery}
            onSubmit={handleSubmit}
            isLoading={isLoading}
            logs={logs}
            history={history}
            activeHistoryIndex={history.length > 0 ? 0 : null}
            onHistoryClick={(q) => setQuery(q)}
          />
          <RightPanel
            title={resultTitle}
            vegaSpec={vegaSpec}
            sql={sql}
            sqlVisible={sqlVisible}
            onToggleSql={() => setSqlVisible((v) => !v)}
          />
        </div>
      </div>
    );
  }
  ```

- [ ] **Step 2: Delete `QueryInput.tsx`**

  It is only imported in the old `page.tsx`. After rewriting `page.tsx`, it has no consumers. Delete it:

  ```bash
  rm /Volumes/VeN/Claude-Code-Work/projects/nl2sql-viz/frontend/src/components/QueryInput.tsx
  ```

- [ ] **Step 3: TypeScript check**

  ```bash
  cd /Volumes/VeN/Claude-Code-Work/projects/nl2sql-viz/frontend
  npx tsc --noEmit
  ```

  Expected: No errors (including no "cannot find module QueryInput" — it should have no remaining imports).

- [ ] **Step 4: Build check**

  ```bash
  cd /Volumes/VeN/Claude-Code-Work/projects/nl2sql-viz/frontend
  npm run build
  ```

  Expected: Build succeeds with no errors. Warnings about `dangerouslySetInnerHTML` are acceptable.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/src/app/page.tsx
  git rm frontend/src/components/QueryInput.tsx
  git commit -m "feat: rewrite page.tsx as DataLens AI shell; remove QueryInput

  Full two-panel layout with TopBar, LeftPanel, RightPanel wired to WS.
  Log lifecycle: progress→run/done, sql→sql entry, result/error→mark done.
  History prepends on each submit; history click populates textarea only.

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
  ```

---

## Task 7 — Full Round-Trip Test

**Goal:** Verify backend unit tests, backend integration tests (real Postgres + Claude API), and frontend build all pass. Then confirm the live UI works end-to-end.

### 7A — Backend Unit Tests

- [ ] **Step 1: Run all unit tests**

  ```bash
  cd /Volumes/VeN/Claude-Code-Work/projects/nl2sql-viz
  uv run pytest tests/unit/ -v
  ```

  Expected: All tests pass. Key tests to confirm:
  - `test_sql_agent.py` — AsyncAnthropic, SQL generation
  - `test_viz_agent.py` — AsyncAnthropic, Vega-Lite JSON
  - `test_user_store.py` — SQLite register/verify
  - `test_request_guard.py` — rate limit logic
  - `test_coordinator_routing.py` — sql_only vs needs_transform routing
  - `test_auth.py` — key generation and verification

### 7B — Backend Integration Tests

Requires: Docker Postgres running + `ANTHROPIC_API_KEY` set in `.env`.

- [ ] **Step 2: Start Postgres**

  ```bash
  cd /Volumes/VeN/Claude-Code-Work/projects/nl2sql-viz
  docker compose up -d
  sleep 3  # wait for Postgres to be ready
  ```

- [ ] **Step 3: Run integration tests**

  ```bash
  cd /Volumes/VeN/Claude-Code-Work/projects/nl2sql-viz
  uv run pytest tests/integration/ -v
  ```

  Expected: All pass. Key tests:
  - `test_websocket.py::test_register_and_query_via_websocket` — full NL→SQL→Vega pipeline
  - `test_websocket.py::test_websocket_rejects_bad_api_key` — auth rejection
  - `test_sql_agent.py` (integration) — real Postgres query execution
  - `test_schema_agent.py` — real schema introspection

### 7C — Frontend Build

- [ ] **Step 4: Build frontend**

  ```bash
  cd /Volumes/VeN/Claude-Code-Work/projects/nl2sql-viz/frontend
  npm run build
  ```

  Expected: Build succeeds. Zero TS errors. Zero missing module errors.

### 7D — Live Smoke Test

- [ ] **Step 5: Start backend**

  ```bash
  cd /Volumes/VeN/Claude-Code-Work/projects/nl2sql-viz
  uv run uvicorn app.main:app --reload --port 8000
  ```

- [ ] **Step 6: Register a user**

  ```bash
  curl -s -X POST http://localhost:8000/api/register \
    -H "Content-Type: application/json" \
    -d '{"username": "smoketest"}' | python3 -m json.tool
  ```

  Expected: `{ "api_key": "nlq_...", "username": "smoketest" }`

- [ ] **Step 7: Set env vars and start frontend**

  Create/update `frontend/.env.local`:
  ```
  NEXT_PUBLIC_API_KEY=nlq_<from_step_6>
  NEXT_PUBLIC_DSN=postgresql://testuser:testpass@localhost:5432/testdb
  NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws/query
  ```

  ```bash
  cd /Volumes/VeN/Claude-Code-Work/projects/nl2sql-viz/frontend
  npm run dev
  ```

- [ ] **Step 8: Manual verification checklist**

  Open `http://localhost:3000` and verify:

  - [ ] TopBar shows "DataLens AI" + green "Connected" pill
  - [ ] Left panel has textarea, "Ask DataLens →" button, Activity section, History section
  - [ ] Type a question (e.g. "What is the total sales amount per region?") and click Ask
  - [ ] Button changes to "Running…" and is disabled
  - [ ] Activity log shows streaming progress entries with `⏳` icon
  - [ ] A `⬡` log entry appears with the first 40 chars of SQL
  - [ ] Chart renders in the right panel (Vega-Lite bar chart)
  - [ ] SQL toggle button appears; clicking it reveals syntax-highlighted SQL
  - [ ] Query appears in History list with timestamp
  - [ ] Clicking a history item populates textarea but does NOT re-submit
  - [ ] Completed log entries show `✓` icon

- [ ] **Step 9: Final commit**

  ```bash
  cd /Volumes/VeN/Claude-Code-Work/projects/nl2sql-viz
  git add -A
  git commit -m "chore: full round-trip verified — frontend + backend + integration tests passing

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
  ```
