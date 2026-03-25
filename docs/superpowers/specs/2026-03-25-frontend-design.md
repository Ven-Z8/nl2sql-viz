# DataLens AI — Frontend Design Spec

**Goal:** Build a dark-themed, single-screen web UI for the nl2sql-viz backend that lets a user type natural-language queries and see real-time streaming logs + Vega-Lite charts without a page reload.

**Stack:** Next.js 14 (App Router), TypeScript, Tailwind CSS, vega-embed v5

---

## Layout

Single fixed-height viewport — no scroll. Two-panel split:

```
┌─────────────────────────────────────────────────────────┐
│  TopBar: logo + status pill                             │
├──────────────────┬──────────────────────────────────────┤
│  Left Panel      │  Right Panel                         │
│  280px fixed     │  flex:1                              │
│                  │                                       │
│  [Query input]   │  [Result title]           [SQL ▾]   │
│  [Ask btn]       │                                       │
│  ─────────────   │  [Vega chart — centered, max 600px]  │
│  [Activity log]  │                                       │
│  ─────────────   │  [SQL panel — bottom, collapsible]   │
│  [History list]  │                                       │
└──────────────────┴──────────────────────────────────────┘
```

## Color Palette — Light Ocean Teal

| Token | Value | Usage |
|---|---|---|
| `--accent` | `#06b6d4` | Buttons, active borders, log icons, cursor |
| `--accent-deep` | `#0891b2` | Gradient endpoint |
| `--accent-glow` | `#06b6d422` | Focus ring on textarea |
| `--accent-dim` | `#06b6d444` | History active border |
| `--accent-hist` | `#071922` | History active background |
| `--kw-color` | `#06b6d4` | SQL keywords |
| `--fn-color` | `#a5f3fc` | SQL functions |
| `--id-color` | `#67e8f9` | SQL identifiers |
| `--lit-color` | `#cffafe` | SQL literals |

Base backgrounds: `#070b10` (main), `#0d1117` (panels/cards), `#161b22` (inputs), `#0a0e14` (log box).

## Components

### `page.tsx` (shell)
- Manages WebSocket state, query history array, current result, loading flag
- Renders `<TopBar>`, `<LeftPanel>`, `<RightPanel>` — no other logic
- On WS message: routes `log` events to log buffer, `result` event to chart state

### `TopBar.tsx`
Props: `connected: boolean`

- Logo icon (teal gradient hex ⬡) + "DataLens AI" wordmark
- Status pill: green dot + "Connected" when `connected === true`, grey dot + "Disconnected" otherwise

### `LeftPanel.tsx`
Props: `query`, `onQueryChange`, `onSubmit`, `logs`, `history`, `onHistoryClick`

Sections (top to bottom, separated by `border-bottom: 1px solid #21262d`):
1. **Query** — `<textarea>` (72px, focus glow), "Ask DataLens →" button (full-width, teal gradient)
2. **Activity** — `<LogStream>` component (scrollable log box, 110px height)
3. **History** — scrollable list of past queries; clicking one calls `onHistoryClick(q)` which populates the textarea (does NOT re-submit automatically). Each item renders: query text truncated to one line (`text-overflow: ellipsis`) + timestamp string below in muted color `#484f58`. Active item (currently displayed result) gets `background: var(--accent-hist)` + `border-color: var(--accent-dim)`.

### `LogStream.tsx`
Props: `logs: LogEntry[]`
`LogEntry = { time: string; icon: 'done' | 'run' | 'sql'; text: string; active?: boolean }`

- Renders each entry as `[time] [icon] [text]`
- `done` icon: `✓` in `#3fb950`
- `run` icon: `⏳` in `#06b6d4` (progress steps)
- `sql` icon: `⬡` in `#06b6d4` (SQL display lines)
- `active: true` entry: text is `#e6edf3` + blinking `▋` cursor (`animation: blink 1s step-end infinite`)
- Auto-scrolls to bottom on each new entry (`useEffect` + `scrollTop = scrollHeight`)
- Box uses `font-family: 'SF Mono', 'Fira Code', monospace; font-size: 11px; line-height: 1.7`

### `RightPanel.tsx`
Props: `title: string`, `vegaSpec: string | null`, `sql: string`, `sqlVisible: boolean`, `onToggleSql: () => void`

- Header: result title (left) + "SQL ▾" toggle (right, teal)
- Chart area: centered, `max-width: 600px`. Renders `{vegaSpec !== null && <VegaChart spec={vegaSpec} />}` — do NOT pass `null` to `VegaChart` since its prop type is `spec: string`. When `vegaSpec` is null, show an empty state placeholder (e.g., centered muted text "Ask a question to see results").
- SQL panel: fixed at bottom, collapses/expands on toggle; syntax-highlighted using CSS classes `.kw .fn .id .lit`

### `VegaChart.tsx` (already exists — keep as-is)
- `vega-embed` instance lifecycle managed via `useEffect` + ref
- Destroys old view on spec change

### `ws.ts` — `QueryWebSocket` (already exists — keep as-is)
- Auth handshake on connect, `sendQuery(q)` method, event callbacks

## WebSocket Message Contract

Actual backend messages (from `app/agents/coordinator.py`):

```
// Progress step — emitted multiple times per query, human-readable message
{ "type": "progress", "message": string }
// Example messages: "Analyzing your database schema...",
//   "Planning query approach...", "Writing and running SQL query...",
//   "Transforming results...", "Generating visualization..."

// SQL emitted mid-pipeline (after SQL is written, before chart)
{ "type": "sql", "sql": string }

// Final result — vega_spec is a JSON *string*, not an object
{ "type": "result", "vega_spec": string, "rows": any[], "sql": string }

// Error
{ "type": "error", "message": string, "details"?: string }
```

**Icon assignment per message type:**
- `{ type: "progress" }` → `icon: 'run'` while active (most recent unfinished step); flips to `icon: 'done'` when the next `progress` message arrives
- `{ type: "sql" }` → `icon: 'sql'`, text = first 40 chars of SQL + `...`; never marked `done`, stays as-is
- All entries except the current active one have `active: false`

**Log lifecycle on `result` message:**
When `{ type: "result" }` arrives, the last `active: true` log entry (if any) flips to `active: false, icon: 'done'`. Do NOT append a new log entry for the result itself.

## State Shape (page.tsx)

```typescript
type LogEntry = { time: string; icon: 'done' | 'run' | 'sql'; text: string; active?: boolean }
type HistoryItem = { query: string; timestamp: string }  // timestamp: "HH:MM" wall clock

// useState:
query: string                    // textarea value
logs: LogEntry[]                 // current query's log stream
history: HistoryItem[]           // past queries (prepend on submit)
vegaSpec: string | null          // vega_spec JSON string from backend (passed as-is to VegaChart)
sql: string                      // generated SQL (populated from both "sql" and "result" events)
sqlVisible: boolean              // SQL panel expanded
isLoading: boolean               // disable submit while processing
connected: boolean               // true after WS auth succeeds, false after disconnect
```

**DSN:** Read from `process.env.NEXT_PUBLIC_DSN ?? ""` at module level (same pattern as existing `API_KEY`). If empty on submit, show an error log entry and return early. Pass to `ws.sendQuery(query, DSN)` as second argument.

**`connected` wiring** — `ws.ts` is kept as-is (no `onopen`/`onclose` callbacks exposed). Wire `connected` in `page.tsx` as follows:
```typescript
ws.connect()
  .then(() => { wsRef.current = ws; setConnected(true); })
  .catch(() => setConnected(false));
// cleanup in useEffect return:
return () => { ws.disconnect(); setConnected(false); };
```
Do NOT attempt to derive `connected` from `ws.readyState` — that is not reactive.

**Known limitation:** once `connected` is set to `true`, it stays `true` until component unmount. Detecting a mid-session socket drop (server restart, network failure) requires adding a post-auth `onclose` callback to `ws.ts`, which is out of scope for this spec.

## Interaction Flows

**Submit query:**
1. If `DSN` is empty: append error `LogEntry` with `icon: 'run'`, `text: "Missing DSN — set NEXT_PUBLIC_DSN"`, return
2. Clear `logs`, clear `vegaSpec`, clear `sql`, set `isLoading: true`
3. Prepend `{ query, timestamp: HH:MM }` to `history`
4. `ws.sendQuery(query, DSN)`
5. On `{ type: "progress" }`: mark previous active entry `done`, append new `LogEntry { icon: 'run', text: message, active: true }`
6. On `{ type: "sql" }`: append `LogEntry { icon: 'sql', text: event.sql.slice(0,40)+'...', active: false }`, set `sql` state to `event.sql`
7. On `{ type: "result" }`: mark last active entry done, set `vegaSpec = event.vega_spec`, set `sql = event.sql` (if not already set), `isLoading: false`
8. On `{ type: "error" }`: mark last active entry done, append error entry, `isLoading: false`

**Click history item:**
- Populate `query` textarea with that item's text
- Do NOT submit — user can edit and submit manually

**Toggle SQL panel:**
- Flip `sqlVisible`; panel slides or simply shows/hides (CSS `display: none / block` is fine for v1)

## File Structure

All changes within `frontend/src/`:

```
frontend/src/
├── app/
│   └── page.tsx          ← rewrite: state + layout shell only
├── components/
│   ├── TopBar.tsx         ← new
│   ├── LeftPanel.tsx      ← new
│   ├── LogStream.tsx      ← new
│   ├── RightPanel.tsx     ← new
│   ├── QueryInput.tsx     ← delete (absorbed into LeftPanel; verify no other file imports it first — current page.tsx does, so the page.tsx rewrite naturally removes that import)
│   └── VegaChart.tsx      ← keep unchanged
└── lib/
    └── ws.ts              ← keep unchanged
```

## Out of Scope (this spec)

- Real-time streaming via SSE (backend already sends discrete WS messages per step — no chunked text streaming needed yet)
- Authentication UI (API key passed via WS handshake, already implemented)
- Multiple chart types beyond what vega-embed handles automatically
- Mobile / responsive layout
- Dark/light theme toggle
- Export or share functionality
