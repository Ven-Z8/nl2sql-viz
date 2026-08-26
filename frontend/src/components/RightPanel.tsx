"use client";
import { useState, type ReactNode } from "react";
import Banner from "./Banner";
import AnswerCard from "./right-panel/AnswerCard";
import ClarifyCard from "./right-panel/ClarifyCard";
import ResultTable from "./right-panel/ResultTable";
import DataChart from "./DataChart";
import { copyText } from "@/lib/clipboard";
import { downloadRowsCsv } from "@/lib/csv";
import { fmtDuration, fmtNumber } from "@/lib/format";
import { highlightSQL } from "@/lib/sqlHighlight";
import type { QueryEntry, ResultRow } from "@/lib/types";
import type {
  PendingClarify,
  QueryPhase,
  ThreadSlot,
} from "@/hooks/useQueryStream";

interface RightPanelProps {
  /** One card per topic; a follow-up morphs its slot in place (contract v3). */
  slots: ThreadSlot[];
  activeThreadId: string | null;
  /** Thread id whose card is awaiting a follow-up result; null while a new
   *  topic is loading or the panel is idle. */
  loadingThreadId: string | null;
  /** Optimistic header title while a new topic is in flight. */
  pendingTitle: string | null;
  /** SQL streamed before a brand-new topic's first result lands. */
  draftSql: string | null;
  pendingClarify: PendingClarify | null;
  onRespondClarify: (choice: number) => void;
  sqlVisible: boolean;
  onToggleSql: () => void;
  isLoading: boolean;
  phase: QueryPhase;
  error: string | null;
  onDismissError: () => void;
  /** Contract v3 — clears the active thread; next question starts fresh. */
  onNewTopic: () => void;
  /** Slot for global notices (e.g. backend-retrying banner). */
  notice?: ReactNode;
}

const PILL: React.CSSProperties = {
  fontSize: "10.5px",
  fontWeight: 600,
  letterSpacing: "0.05em",
  borderRadius: "var(--radius-pill)",
  padding: "3px 10px",
  fontFamily: "var(--font-mono)",
  border: "1px solid var(--color-border-subtle)",
  color: "var(--color-ink-dim)",
  background: "var(--color-paper-3)",
  whiteSpace: "nowrap",
};

const THREAD_PILL: React.CSSProperties = {
  ...PILL,
  color: "var(--color-accent)",
  borderColor: "var(--color-accent-dim)",
  background: "var(--color-accent-dim)",
};

/** One answer card in the conversation column: topic headline + follow-up
 *  chips + the thread's latest result. The inner content div is keyed by
 *  turn index so a morph remounts ONLY the swapped content — the 150ms
 *  `morph-in` animation plays there, never on the surrounding layout. */
function AnswerSlotCard({
  slot,
  awaitingFollowUp,
}: {
  slot: ThreadSlot;
  awaitingFollowUp: boolean;
}) {
  const meta = slot.result.meta;
  const metrics = slot.result.answer?.metrics ?? [];
  const rowCount = meta?.rowCount ?? null;
  const truncated =
    rowCount != null && slot.result.rows.length > 0 && slot.result.rows.length < rowCount;

  return (
    <section
      aria-label={`Topic: ${slot.question}`}
      style={{
        border: "1px solid var(--color-border-subtle)",
        borderRadius: "var(--radius-lg)",
        background: "var(--color-paper-2)",
        padding: "var(--space-4) var(--space-5) var(--space-5)",
        opacity: awaitingFollowUp ? 0.72 : 1,
        transition: "opacity var(--dur-fast) var(--ease-out)",
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-4)",
      }}
    >
      {/* Headline: the original question never changes across turns */}
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: "var(--space-3)",
        }}
      >
        <h3
          style={{
            margin: 0,
            fontSize: "13.5px",
            fontWeight: 700,
            letterSpacing: "-0.01em",
            color: "var(--color-ink)",
            lineHeight: 1.45,
            overflowWrap: "anywhere",
          }}
        >
          {slot.question}
        </h3>
        {awaitingFollowUp && (
          <span style={{ ...PILL, flexShrink: 0 }} aria-live="polite">
            updating…
          </span>
        )}
      </div>

      {/* Follow-up trail: reads as conversation, not data loss */}
      {(slot.followUps.length > 0 || awaitingFollowUp) && (
        <div
          style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "-6px" }}
        >
          {slot.followUps.map((fu) => (
            <span
              key={fu.turnIndex}
              style={{
                fontSize: "11px",
                color: "var(--color-ink-dim)",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-pill)",
                padding: "3px 10px",
                fontFamily: "var(--font-mono)",
                overflowWrap: "anywhere",
              }}
            >
              ↳ {fu.question}
            </span>
          ))}
          {awaitingFollowUp && (
            <span
              style={{
                fontSize: "11px",
                color: "var(--color-accent)",
                border: "1px dashed var(--color-accent-dim)",
                borderRadius: "var(--radius-pill)",
                padding: "3px 10px",
                fontFamily: "var(--font-mono)",
              }}
            >
              ↳ …
            </span>
          )}
        </div>
      )}

      {/* Swappable content — keyed by turn so morphs animate in place */}
      <div
        key={slot.result.turnIndex ?? "single"}
        className="morph-in"
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-4)",
        }}
      >
        {/* Truth badges: timing · cache · read-only */}
        {meta && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
            {meta.executionTimeMs > 0 && (
              <span style={PILL}>⚡ {fmtDuration(meta.executionTimeMs)}</span>
            )}
            {meta.cached && (
              <span
                style={{
                  ...PILL,
                  color: "var(--color-success)",
                  borderColor: "var(--color-success-dim)",
                  background: "var(--color-success-dim)",
                }}
              >
                ↺ cache hit
              </span>
            )}
            <span style={PILL}>read-only</span>
          </div>
        )}

        {/* Grounded answer narrative */}
        {slot.result.answer && (
          <AnswerCard
            answer={slot.result.answer}
            provenance={slot.result.provenance}
            queries={slot.result.queries}
          />
        )}

        {/* Dedicated zero-rows state */}
        {slot.result.rows.length === 0 && metrics.length === 0 && (
          <div
            role="status"
            style={{
              textAlign: "center",
              maxWidth: "420px",
              margin: "8px auto",
              border: "1px dashed var(--color-border)",
              borderRadius: "var(--radius-lg)",
              background: "var(--color-paper-2)",
              padding: "var(--space-6) var(--space-5)",
            }}
          >
            <div
              style={{
                fontSize: "26px",
                marginBottom: "var(--space-3)",
                opacity: 0.5,
              }}
              aria-hidden
            >
              ∅
            </div>
            <div
              style={{
                fontSize: "14px",
                fontWeight: 700,
                color: "var(--color-ink)",
                marginBottom: "6px",
              }}
            >
              No rows returned
            </div>
            <div
              style={{
                fontSize: "13px",
                color: "var(--color-ink-dim)",
                lineHeight: 1.6,
              }}
            >
              {slot.result.answer?.text
                ? `“${slot.result.answer.text}” — try a broader question.`
                : "Query returned zero rows. Try a broader question."}
            </div>
          </div>
        )}

        {/* The one chart renderer */}
        {(slot.result.rows.length > 0 || metrics.length > 0) && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              minHeight: 320,
              border: "1px solid var(--color-border-subtle)",
              borderRadius: "var(--radius-xl)",
              background: "var(--color-paper-2)",
              overflow: "hidden",
            }}
          >
            <DataChart
              hint={meta?.chartHint ?? null}
              rows={slot.result.rows}
              rowCount={rowCount}
              metrics={metrics}
              provenance={slot.result.provenance}
            />
          </div>
        )}

        {/* Sortable result table */}
        {slot.result.rows.length > 0 && <ResultTable rows={slot.result.rows} />}
      </div>
    </section>
  );
}

export default function RightPanel({
  slots,
  activeThreadId,
  loadingThreadId,
  pendingTitle,
  draftSql,
  pendingClarify,
  onRespondClarify,
  sqlVisible,
  onToggleSql,
  isLoading,
  phase,
  error,
  onDismissError,
  onNewTopic,
  notice,
}: RightPanelProps) {
  const [copiedSql, setCopiedSql] = useState(false);
  // Active tab inside the SQL & Queries drawer (final first).
  const [queryTab, setQueryTab] = useState(0);

  // The card the header acts on: the active thread's slot, else the newest.
  const activeSlot =
    slots.find((s) => s.threadId === activeThreadId) ??
    slots[slots.length - 1] ??
    null;

  const newTopicLoading = isLoading && loadingThreadId == null;
  const hasResult = phase === "done" || phase === "error";

  // ── header stats (operate on the active slot) ──────────────
  const rows: ResultRow[] = activeSlot?.result.rows ?? [];
  const rowCount = activeSlot?.result.meta?.rowCount ?? null;
  const truncated =
    rowCount != null && rows.length > 0 && rows.length < rowCount;

  // ── SQL & Queries drawer sources ───────────────────────────
  const activeQueries: QueryEntry[] = activeSlot?.result.queries ?? [];
  const hasQueries = activeQueries.length > 0;
  const activeQueryIdx = hasQueries
    ? Math.min(queryTab, activeQueries.length - 1)
    : 0;
  const activeQuery = activeQueries[activeQueryIdx] ?? null;
  // While a brand-new topic streams its first SQL there is no slot yet —
  // show the live draft instead of the previous card's query.
  const drawerSql = newTopicLoading
    ? (draftSql ?? "")
    : hasQueries
      ? (activeQuery?.sql ?? "")
      : (activeSlot?.result.sql ?? "");
  const drawerOpen = sqlVisible && drawerSql.trim().length > 0;

  const handleCopySql = async () => {
    if (!drawerSql) return;
    const ok = await copyText(drawerSql);
    if (ok) {
      setCopiedSql(true);
      setTimeout(() => setCopiedSql(false), 2000);
    }
  };

  // ── thread pill state (F3) ─────────────────────────────────
  const activeThreadSlot = activeThreadId
    ? (slots.find((s) => s.threadId === activeThreadId) ?? null)
    : null;
  const threadTurns = activeThreadSlot
    ? (activeThreadSlot.result.turnIndex ??
      activeThreadSlot.followUps.length + 1)
    : 0;
  const showThreadPill = threadTurns >= 2;

  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        background: "var(--color-paper)",
        minWidth: 0,
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "var(--space-4) var(--space-6)",
          borderBottom: "1px solid var(--color-border-subtle)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "var(--space-3)",
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontSize: "14px",
            fontWeight: 600,
            letterSpacing: "-0.01em",
            color:
              pendingTitle || activeSlot
                ? "var(--color-ink)"
                : "var(--color-ink-faint)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {pendingTitle || activeSlot?.result.title || "Results"}
        </span>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-2)",
            flexShrink: 0,
          }}
        >
          {activeSlot?.result.queryType && (
            <span
              style={{
                ...PILL,
                color: "var(--color-accent)",
                borderColor: "var(--color-accent-dim)",
                background: "transparent",
                textTransform: "uppercase",
              }}
            >
              {activeSlot.result.queryType}
            </span>
          )}
          {truncated ? (
            <span
              style={{ ...PILL }}
              title="The preview shows a subset; row_count is the full result size."
            >
              showing {rows.length} of {rowCount}
            </span>
          ) : (
            rows.length > 0 && <span style={{ ...PILL }}>{rows.length} rows</span>
          )}
          {rows.length > 0 && (
            <button
              onClick={() =>
                downloadRowsCsv(
                  rows,
                  activeSlot?.result.title || "results"
                )
              }
              title="Download the current preview rows as CSV"
              style={ACTION_BUTTON}
            >
              ↓ CSV
            </button>
          )}
          {drawerSql.trim().length > 0 && (
            <>
              <button
                onClick={handleCopySql}
                title="Copy the generated SQL to the clipboard"
                style={ACTION_BUTTON}
              >
                {copiedSql ? "Copied ✓" : "Copy SQL"}
              </button>
              <button
                onClick={onToggleSql}
                title={
                  hasQueries
                    ? `Show all ${hasQueries ? activeQueries.length : 1} executed queries (final first)`
                    : "Show the generated SQL"
                }
                style={ACTION_BUTTON}
              >
                {hasQueries && activeQueries.length > 1 ? "SQL & Queries" : "SQL"}{" "}
                {sqlVisible ? "▴" : "▾"}
              </button>
            </>
          )}
        </div>
      </div>

      <div
        className="stagger"
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          overflow: "auto",
          padding: "var(--space-6)",
          gap: "var(--space-5)",
        }}
      >
        {/* Backend-wake notice (replaces the old misleading API-key message) */}
        {!isLoading && notice}

        {/* Contract v2 clarify card — pipeline paused, waiting on the user */}
        {pendingClarify && (
          <ClarifyCard clarify={pendingClarify} onRespond={onRespondClarify} />
        )}

        {/* Dismissible error banner */}
        {!isLoading && error && (
          <Banner tone="error" message={error} onDismiss={onDismissError} />
        )}

        {/* Contract v3 thread status row — pill once the conversation has
            ≥2 turns, plus the explicit escape hatch to start fresh. */}
        {showThreadPill && !isLoading && (
          <div
            role="status"
            aria-label={`Active thread: ${threadTurns} turns`}
            style={{
              display: "flex",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "var(--space-2)",
            }}
          >
            <span style={THREAD_PILL}>Thread · {threadTurns} turns</span>
            <button
              type="button"
              onClick={onNewTopic}
              aria-label="Start a new topic — your next question won't continue this thread"
              title="Next question starts a new topic (this conversation stays on screen)"
              style={NEW_TOPIC_BUTTON}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "var(--color-accent)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "var(--color-border)";
              }}
            >
              New topic
            </button>
          </div>
        )}

        {/* Conversation column — one card per topic; follow-ups morphed
            into their card by useQueryStream before they get here. */}
        {slots.map((slot) => (
          <AnswerSlotCard
            key={slot.key}
            slot={slot}
            awaitingFollowUp={
              isLoading && loadingThreadId === slot.threadId
            }
          />
        ))}

        {/* Loading skeletons — only for a brand-new topic now; follow-ups
            morph their existing card instead (subtle "updating…" treatment).
            Suppressed while paused on a clarify, where the honest state is
            "waiting on you", not "working". */}
        {newTopicLoading && !pendingClarify && (
          <>
            <div className="skeleton" style={{ height: "72px", width: "100%" }} />
            <div className="skeleton" style={{ height: 300, width: "100%" }} />
            <div className="skeleton" style={{ height: 120, width: "100%" }} />
          </>
        )}

        {/* Idle empty state (no stale 3D promises here) */}
        {!isLoading &&
          !hasResult &&
          slots.length === 0 &&
          !notice &&
          !pendingClarify && (
            <div
              style={{ textAlign: "center", maxWidth: "340px", margin: "40px auto" }}
            >
              <div
                style={{
                  fontSize: "13px",
                  color: "var(--color-ink-faint)",
                  lineHeight: 1.6,
                }}
              >
                Ask a question to see results. Charts adapt to your data — trends,
                breakdowns, comparisons, distributions, and KPIs.
              </div>
            </div>
          )}
      </div>

      {/* SQL & Queries drawer — contract v2: every synthesized result set,
          final first; legacy payloads fall back to the single-SQL view.
          While a brand-new topic streams, shows its live draft SQL. */}
      {drawerOpen && (
        <div
          style={{
            flexShrink: 0,
            borderTop: "1px solid var(--color-border-subtle)",
            background: "var(--color-paper-2)",
            padding: "14px var(--space-6)",
            maxHeight: "220px",
            overflowY: "auto",
          }}
        >
          {!newTopicLoading && hasQueries && (
            <div
              role="tablist"
              aria-label="Executed queries"
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "4px",
                marginBottom: "10px",
              }}
            >
              {activeQueries.map((q, i) => {
                const selected = i === activeQueryIdx;
                return (
                  <button
                    key={i}
                    role="tab"
                    aria-selected={selected}
                    onClick={() => setQueryTab(i)}
                    title={`Query ${i + 1}${i === 0 ? " (final answer)" : ""} · ${q.row_count} rows`}
                    style={{
                      background: selected
                        ? "var(--color-accent-dim)"
                        : "transparent",
                      border: `1px solid ${selected ? "var(--color-accent-dim)" : "var(--color-border-subtle)"}`,
                      borderRadius: "var(--radius-pill)",
                      padding: "3px 11px",
                      fontSize: "10.5px",
                      fontWeight: 600,
                      fontFamily: "var(--font-mono)",
                      color: selected
                        ? "var(--color-accent)"
                        : "var(--color-ink-dim)",
                      cursor: "pointer",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {i === 0 ? "final" : `#${i + 1}`} ·{" "}
                    {fmtNumber(q.row_count)} rows
                  </button>
                );
              })}
            </div>
          )}
          <div
            role={!newTopicLoading && hasQueries ? "tabpanel" : undefined}
            aria-label={
              !newTopicLoading && hasQueries
                ? `SQL for query ${activeQueryIdx + 1}`
                : undefined
            }
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "12px",
              lineHeight: "1.8",
              color: "var(--color-ink-dim)",
              whiteSpace: "pre-wrap",
            }}
            dangerouslySetInnerHTML={{
              __html: highlightSQL(drawerSql),
            }}
          />
        </div>
      )}
    </div>
  );
}

const ACTION_BUTTON: React.CSSProperties = {
  background: "none",
  border: "none",
  cursor: "pointer",
  color: "var(--color-accent)",
  fontSize: "12px",
  fontWeight: 500,
  padding: "4px 8px",
  borderRadius: "var(--radius-sm)",
  fontFamily: "var(--font-mono)",
  whiteSpace: "nowrap",
};

const NEW_TOPIC_BUTTON: React.CSSProperties = {
  background: "none",
  border: "1px solid var(--color-border)",
  cursor: "pointer",
  color: "var(--color-ink-dim)",
  fontSize: "11px",
  fontWeight: 600,
  padding: "3px 12px",
  borderRadius: "var(--radius-pill)",
  fontFamily: "var(--font-mono)",
  whiteSpace: "nowrap",
  transition: "border-color var(--dur-fast) var(--ease-out)",
};
