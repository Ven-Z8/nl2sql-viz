/**
 * Shared domain types for the DataLens frontend.
 * Mirrors the WS/REST contract agreed with the backend (see lib/config.ts).
 */

export type ResultRow = Record<string, unknown>;

/** A single grounded metric inside an answer. */
export interface Metric {
  label: string;
  value: number;
  unit: string;
}

export interface SubQuery {
  id: string;
  question: string;
}

/** Narrative answer attached to a result event. */
export interface Answer {
  text: string;
  metrics: Metric[];
  sub_queries: SubQuery[];
  key_points?: string[];
  sections?: { title: string; text: string; metrics: Metric[] }[];
}

/**
 * Backend-decided chart configuration. The frontend renders exactly what the
 * backend asks for — no client-side column sniffing.
 */
export interface ChartHint {
  kind:
    | "bar"
    | "stacked_bar"
    | "grouped_bar"
    | "line"
    | "area"
    | "pie"
    | "scatter"
    | "histogram"
    | "kpi";
  x: string | null;
  y: string[];
  title: string | null;
  limit_applied: number | null;
  /** Categorical kinds only — order categories desc by y[0] before drawing. */
  sort?: string | null;
  /** Truncate to the leading N categories after sorting. */
  top_n?: number | null;
  /** Series dimension — pivot column for stacked/grouped bars, or the
   *  long-format split that turns one line/area into N series. */
  color?: string | null;
}

/**
 * One traced metric inside a result payload (contract v2). `query_index`
 * points into result.queries; `row_index` optionally pinpoints the exact row
 * that produced the number.
 */
export interface ProvenanceEntry {
  metric: string;
  value: number | string;
  query_index: number;
  row_index: number | null;
}

/** A synthesized query executed by the backend (contract v2; final first). */
export interface QueryEntry {
  sql: string;
  row_count: number;
  /** Beyond-contract extra: per-query rows, rendered when provided. */
  rows?: ResultRow[];
}

/** Inbound `clarify` event payload (contract v2) — pipeline pauses until
 *  the client answers via { type:"clarification_response", choice }.
 *  Timeout handling is server-side (~120s); the client just renders. */
export interface ClarifyEventPayload {
  type: "clarify";
  question: string;
  options: string[];
  thread_id: string | null;
}

/** Inbound `result` event payload (subset we consume). */
export interface ResultEventPayload {
  query?: string;
  sql?: string;
  answer?: Answer;
  rows?: ResultRow[];
  row_count?: number;
  execution_time_ms?: number;
  cached?: boolean;
  chart_hint?: ChartHint | null;
  /** Contract v2 — both may be null on older payloads; render gracefully. */
  provenance?: ProvenanceEntry[] | null;
  queries?: QueryEntry[] | null;
  /** Contract v3 — conversation threading. `thread_id` identifies the
   *  conversation; `turn_index` is 1-based within it; `is_follow_up` is true
   *  exactly when the client sent a thread_id on the query. All three may be
   *  absent on pre-v3 backends — the client degrades to v2 semantics. */
  thread_id?: string;
  turn_index?: number;
  is_follow_up?: boolean;
}

export type SuggestedTier =
  | "easy"
  | "medium"
  | "hard"
  | "very_complex";

export interface SuggestedQuestion {
  id: string;
  question: string;
  category: string;
  tier?: SuggestedTier;
}

export interface HistoryItem {
  query: string;
  timestamp: string;
}

export interface UploadedDataset {
  table_name: string;
  row_count: number;
  columns: string[];
  domain: string;
}

export interface CatalogItem {
  id: string;
  name: string;
  domain: string;
  description: string;
}

/** POST /api/demo/session response (contract: connection_id, no dsn). */
export interface DemoSession {
  username: string;
  api_key: string;
  connection_id: string;
  dataset: string;
  focus_table?: string;
}
