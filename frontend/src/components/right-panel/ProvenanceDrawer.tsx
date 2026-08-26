"use client";
import { useEffect, useRef } from "react";
import { highlightSQL } from "@/lib/sqlHighlight";
import { fmtNumber, titleCase } from "@/lib/format";
import type { ProvenanceEntry, QueryEntry, ResultRow } from "@/lib/types";

interface ProvenanceDrawerProps {
  entry: ProvenanceEntry;
  /** queries[entry.query_index] when in range; null otherwise. */
  query: QueryEntry | null;
  onClose: () => void;
  /** "segment" = the cited metric label IS a category value from a grouped
   *  answer (e.g. "Pro" in "Churned by Plan Tier"); the segment name then
   *  renders prominently as the drawer's headline. Defaults to "metric". */
  variant?: "metric" | "segment";
}

const LABEL: React.CSSProperties = {
  fontSize: "10.5px",
  fontWeight: 600,
  color: "var(--color-ink-faint)",
  textTransform: "uppercase",
  letterSpacing: "0.1em",
  fontFamily: "var(--font-mono)",
  marginBottom: "6px",
};

/**
 * Side drawer behind every clickable cited number in the AnswerCard
 * (provenance feature, contract v2). Shows the metric + value, a "traced to
 * executed query" badge, the producing SQL (syntax-highlighted), and — when
 * the backend supplies per-query rows and row_index is set — the exact row.
 */
export default function ProvenanceDrawer({
  entry,
  query,
  onClose,
  variant = "metric",
}: ProvenanceDrawerProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  // Escape closes; focus lands on the dialog so keyboard users aren't lost.
  useEffect(() => {
    dialogRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const valueText =
    typeof entry.value === "number" ? fmtNumber(entry.value) : String(entry.value);

  const row: ResultRow | null =
    query && entry.row_index != null && Array.isArray(query.rows)
      ? (query.rows[entry.row_index] ?? null)
      : null;

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 60 }}>
      {/* Backdrop — click to dismiss */}
      <div
        onClick={onClose}
        aria-hidden
        style={{
          position: "absolute",
          inset: 0,
          background:
            "color-mix(in srgb, var(--color-ink) 30%, transparent)",
        }}
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={`${variant === "segment" ? "Segment" : "Metric"} ${entry.metric} provenance`}
        tabIndex={-1}
        style={{
          position: "absolute",
          top: 0,
          right: 0,
          bottom: 0,
          width: "min(430px, 92vw)",
          background: "var(--color-paper)",
          borderLeft: "1px solid var(--color-border-subtle)",
          boxShadow: "-16px 0 48px color-mix(in srgb, var(--color-ink) 22%, transparent)",
          display: "flex",
          flexDirection: "column",
          outline: "none",
          animation: "fade-up var(--dur-fast) var(--ease-out) both",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "var(--space-3)",
            padding: "var(--space-4) var(--space-5)",
            borderBottom: "1px solid var(--color-border-subtle)",
            flexShrink: 0,
          }}
        >
          <span style={{ ...LABEL, marginBottom: 0 }}>Provenance</span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close provenance details"
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--color-ink-dim)",
              fontSize: "14px",
              padding: "4px 8px",
              borderRadius: "var(--radius-sm)",
              fontFamily: "var(--font-mono)",
            }}
          >
            ✕
          </button>
        </div>

        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "var(--space-5)",
            display: "flex",
            flexDirection: "column",
            gap: "var(--space-5)",
          }}
        >
          {/* Metric + value — segmented answers headline the category name
              ("Pro") with the number directly under it. */}
          <section>
            <div style={LABEL}>
              {variant === "segment" ? "Segment" : "Metric"}
            </div>
            {variant === "segment" ? (
              <>
                <div
                  style={{
                    fontSize: "20px",
                    fontWeight: 700,
                    letterSpacing: "-0.02em",
                    color: "var(--color-ink)",
                    marginBottom: "2px",
                    overflowWrap: "anywhere",
                  }}
                >
                  {entry.metric}
                </div>
                {titleCase(entry.metric) !== entry.metric && (
                  <div style={{ fontSize: "12px", color: "var(--color-ink-faint)", marginBottom: "4px" }}>
                    {titleCase(entry.metric)}
                  </div>
                )}
              </>
            ) : (
              <div
                style={{
                  fontSize: "13px",
                  fontWeight: 600,
                  color: "var(--color-ink-dim)",
                  marginBottom: "2px",
                }}
              >
                {titleCase(entry.metric)}
              </div>
            )}
            <div
              style={{
                fontSize: "30px",
                fontWeight: 700,
                letterSpacing: "-0.03em",
                fontFamily: "var(--font-mono)",
                fontVariantNumeric: "tabular-nums",
                color: "var(--color-ink)",
              }}
            >
              {valueText}
            </div>
          </section>

          {/* Verified badge — spot-check happens server-side later; today the
              claim is exactly "this number came from an executed query". */}
          <div
            style={{
              alignSelf: "flex-start",
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              border: "1px solid var(--color-success-dim)",
              background: "var(--color-success-dim)",
              borderRadius: "var(--radius-pill)",
              padding: "5px 12px",
              fontSize: "11.5px",
              fontWeight: 600,
              color: "var(--color-success)",
            }}
          >
            <span aria-hidden>✓</span>
            verified against database
            <span
              title="This number was traced to a query that actually ran against your data."
              style={{ fontWeight: 500, opacity: 0.75 }}
            >
              · traced to executed query
            </span>
          </div>

          {/* Producing query */}
          <section>
            <div style={LABEL}>
              Producing query{query ? ` · #${entry.query_index + 1}` : ""}
              {query && query.row_count > 0 ? ` · ${fmtNumber(query.row_count)} rows` : ""}
            </div>
            {query ? (
              <pre
                style={{
                  margin: 0,
                  border: "1px solid var(--color-border-subtle)",
                  borderRadius: "var(--radius-md)",
                  background: "var(--color-paper-2)",
                  padding: "12px 14px",
                  fontFamily: "var(--font-mono)",
                  fontSize: "11.5px",
                  lineHeight: 1.7,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  color: "var(--color-ink-dim)",
                }}
                dangerouslySetInnerHTML={{ __html: highlightSQL(query.sql) }}
              />
            ) : (
              <div
                style={{
                  fontSize: "12px",
                  color: "var(--color-ink-faint)",
                  border: "1px dashed var(--color-border)",
                  borderRadius: "var(--radius-md)",
                  padding: "10px 12px",
                }}
              >
                Query details unavailable for this metric (query #
                {entry.query_index} not in this payload).
              </div>
            )}
          </section>

          {/* Exact source row, when the backend provides per-query rows */}
          {row && (
            <section>
              <div style={LABEL}>Source row #{entry.row_index}</div>
              <div
                style={{
                  border: "1px solid var(--color-border-subtle)",
                  borderRadius: "var(--radius-md)",
                  background: "var(--color-paper-2)",
                  overflow: "hidden",
                }}
              >
                {Object.entries(row).map(([k, v], i) => (
                  <div
                    key={k}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: "var(--space-3)",
                      padding: i === 0 ? "10px 14px" : "10px 14px",
                      borderTop:
                        i === 0 ? "none" : "1px solid var(--color-border-subtle)",
                      fontSize: "12px",
                    }}
                  >
                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        color: "var(--color-ink-faint)",
                        flexShrink: 0,
                      }}
                    >
                      {k}
                    </span>
                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        color: "var(--color-ink)",
                        fontWeight: 600,
                        textAlign: "right",
                        wordBreak: "break-word",
                      }}
                    >
                      {v == null ? "—" : String(v)}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}
          {!row && entry.row_index != null && (
            <div
              style={{
                fontSize: "11px",
                color: "var(--color-ink-faint)",
                fontFamily: "var(--font-mono)",
              }}
            >
              Row-level detail not included in this payload (source row #
              {entry.row_index}).
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
