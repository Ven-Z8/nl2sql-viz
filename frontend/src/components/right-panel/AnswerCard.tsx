"use client";
import { useMemo, useState } from "react";
import ProvenanceDrawer from "./ProvenanceDrawer";
import { isSegmentedShape } from "@/lib/answerShape";
import { fmtNumber, titleCase } from "@/lib/format";
import type {
  Answer,
  ProvenanceEntry,
  QueryEntry,
} from "@/lib/types";

interface AnswerCardProps {
  answer: Answer;
  /** Contract v2 provenance — null/absent on older payloads. */
  provenance?: ProvenanceEntry[] | null;
  /** Contract v2 query list; indexes provenance entries' query_index. */
  queries?: QueryEntry[];
}

/**
 * The grounded-answer narrative card. Deliberately does NOT render
 * answer.metrics — numeric metrics surface exactly once, in DataChart's KPI
 * view (de-duplication per the honest-states spec).
 *
 * When result.provenance is present, every cited number in the narrative
 * becomes a clickable citation that opens the ProvenanceDrawer showing which
 * executed query produced it. Without provenance, rendering is byte-for-byte
 * the pre-v2 card.
 */

// ── citation wrapping ───────────────────────────────────────────

type Part =
  | { kind: "text"; text: string }
  | { kind: "cite"; provIdx: number; text: string };

/** Textual forms under which a provenance value can appear in prose. */
function candidateForms(entry: ProvenanceEntry): string[] {
  const forms = new Set<string>();
  if (typeof entry.value === "number" && Number.isFinite(entry.value)) {
    forms.add(String(entry.value));
    forms.add(fmtNumber(entry.value));
    forms.add(
      entry.value.toLocaleString("en-US", { maximumFractionDigits: 2 })
    );
  } else if (typeof entry.value === "string") {
    const v = entry.value.trim();
    // Avoid matching single stray characters in prose.
    if (v.length >= 2) forms.add(v);
  }
  return [...forms].filter((f) => f.length > 0);
}

const WORD_CHAR = /[A-Za-z0-9_]/;
const DIGIT = /[0-9]/;
const NUM_JOINER = /[-/.:]/;
// "March 15, 2024" / "Jan 7" — a number right after a month name is a date,
// not one of our metrics.
const MONTH_BEFORE =
  /\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?,?\s*$/i;

/**
 * Boundary-safe occurrence test. A hit is rejected when it is part of a
 * larger token rather than a standalone value:
 *  - inside a word or longer digit run ("39" in "Q3-39" / "2019");
 *  - glued to letters ("39x", "x39");
 *  - a decimal fragment ("39" inside "39.5") or its whole side;
 *  - joined by -, /, . or : into a date/time run ("2024-01-15", "12:30");
 *  - a day-of-month directly following a month name ("March 15").
 */
function isSafeMatch(text: string, at: number, len: number): boolean {
  const before = at > 0 ? text[at - 1] : "";
  const after = at + len < text.length ? text[at + len] : "";
  if (before && WORD_CHAR.test(before)) return false;
  if (after && WORD_CHAR.test(after)) return false;
  if (after === "." && DIGIT.test(text[at + len + 1] ?? "")) return false; // "39.5"
  if (
    before &&
    NUM_JOINER.test(before) &&
    DIGIT.test(text[at - 2] ?? "")
  ) {
    return false; // "…-15", "12:30"
  }
  if (
    after &&
    NUM_JOINER.test(after) &&
    DIGIT.test(text[at + len + 1] ?? "")
  ) {
    return false; // "2024-…", "09:…"
  }
  if (MONTH_BEFORE.test(text.slice(Math.max(0, at - 16), at))) return false;
  return true;
}

function buildParts(text: string, provenance: ProvenanceEntry[]): Part[] {
  // form → indexes citing that form (provenance order preserved). Segmented
  // answers often repeat values across segments, so identical forms map to
  // several entries and get consumed in order of appearance below.
  const byForm = new Map<string, number[]>();
  provenance.forEach((p, i) => {
    for (const form of candidateForms(p)) {
      const list = byForm.get(form);
      if (list) {
        if (!list.includes(i)) list.push(i);
      } else {
        byForm.set(form, [i]);
      }
    }
  });
  if (byForm.size === 0) return [{ kind: "text", text }];

  // Longest-first so "$1,234.56" wins over "1,234".
  const forms = [...byForm.keys()].sort((a, b) => b.length - a.length);

  const parts: Part[] = [];
  const used = new Set<number>();
  let cursor = 0;
  while (cursor < text.length) {
    let bestForm: string | null = null;
    let bestAt = -1;
    for (const form of forms) {
      let at = text.indexOf(form, cursor);
      while (at !== -1 && !isSafeMatch(text, at, form.length)) {
        at = text.indexOf(form, at + 1);
      }
      if (at === -1) continue;
      if (
        bestForm === null ||
        at < bestAt ||
        (at === bestAt && form.length > bestForm.length)
      ) {
        bestForm = form;
        bestAt = at;
      }
      if (at === cursor) break; // longest match already found at cursor
    }
    if (bestForm === null || bestAt === -1) break;

    // The backend enumerates segments in the same order in prose and
    // provenance, so equal values map sequentially to their own rows.
    const idxs = byForm.get(bestForm)!;
    let provIdx = idxs.find((i) => !used.has(i));
    if (provIdx === undefined) provIdx = idxs[0];
    else used.add(provIdx);

    if (bestAt > cursor) parts.push({ kind: "text", text: text.slice(cursor, bestAt) });
    parts.push({ kind: "cite", provIdx, text: bestForm });
    cursor = bestAt + bestForm.length;
  }
  if (cursor < text.length) parts.push({ kind: "text", text: text.slice(cursor) });
  return parts;
}

// ── component ───────────────────────────────────────────────────

export default function AnswerCard({
  answer,
  provenance,
  queries = [],
}: AnswerCardProps) {
  const [activeProv, setActiveProv] = useState<number | null>(null);

  const hasProv = Array.isArray(provenance) && provenance.length > 0;

  // Shape branch (Wave 4): segmented grouped answers cite category values
  // ("Pro", "Basic") with concrete row indexes — the drawer then presents
  // the segment name prominently instead of a column-style metric label.
  const segmented = useMemo(
    () => isSegmentedShape(answer.metrics, provenance),
    [answer.metrics, provenance]
  );

  const textParts = useMemo(
    () => (hasProv ? buildParts(answer.text ?? "", provenance!) : null),
    [hasProv, answer.text, provenance]
  );

  const renderNarrative = () => {
    if (!answer.text) return null;
    if (!textParts) {
      return (
        <div
          style={{
            fontSize: "15px",
            fontWeight: 600,
            color: "var(--color-ink)",
            lineHeight: 1.5,
            letterSpacing: "-0.01em",
          }}
        >
          {answer.text}
        </div>
      );
    }
    return (
      <div
        style={{
          fontSize: "15px",
          fontWeight: 600,
          color: "var(--color-ink)",
          lineHeight: 1.7,
          letterSpacing: "-0.01em",
        }}
      >
        {textParts.map((part, i) =>
          part.kind === "text" ? (
            <span key={i}>{part.text}</span>
          ) : (
            <button
              key={i}
              type="button"
              onClick={() => setActiveProv(part.provIdx)}
              aria-haspopup="dialog"
              aria-expanded={activeProv === part.provIdx}
              title={`Show how “${provenance![part.provIdx].metric}” was computed`}
              style={{
                background: "none",
                border: "none",
                margin: 0,
                padding: "0",
                font: "inherit",
                fontWeight: 700,
                color: "var(--color-accent)",
                borderBottom: "2px dotted var(--color-accent)",
                cursor: "pointer",
                lineHeight: 1.5,
              }}
            >
              {part.text}
            </button>
          )
        )}
      </div>
    );
  };

  const renderKeyPoint = (kp: string, i: number) => {
    const parts = hasProv ? buildParts(kp, provenance!) : null;
    return (
      <div
        key={i}
        style={{ display: "flex", gap: "10px", alignItems: "flex-start", padding: "4px 0" }}
      >
        <span
          style={{
            fontSize: "12px",
            lineHeight: 1.5,
            color: "var(--color-accent)",
            fontWeight: 700,
            flexShrink: 0,
          }}
        >
          ▸
        </span>
        <span style={{ fontSize: "13px", lineHeight: 1.6, color: "var(--color-ink)" }}>
          {parts ? (
            parts.map((part, j) =>
              part.kind === "text" ? (
                <span key={j}>{part.text}</span>
              ) : (
                <button
                  key={j}
                  type="button"
                  onClick={() => setActiveProv(part.provIdx)}
                  aria-haspopup="dialog"
                  aria-expanded={activeProv === part.provIdx}
                  title={`Show how “${provenance![part.provIdx].metric}” was computed`}
                  style={{
                    background: "none",
                    border: "none",
                    margin: 0,
                    padding: "0",
                    font: "inherit",
                    color: "var(--color-accent)",
                    fontWeight: 700,
                    borderBottom: "2px dotted var(--color-accent)",
                    cursor: "pointer",
                    lineHeight: 1.5,
                  }}
                >
                  {part.text}
                </button>
              )
            )
          ) : (
            kp
          )}
        </span>
      </div>
    );
  };

  const activeQuery =
    activeProv != null && provenance?.[activeProv]
      ? (queries[provenance[activeProv].query_index] ?? null)
      : null;

  return (
    <div
      style={{
        border: "1px solid var(--color-accent-dim)",
        borderRadius: "var(--radius-lg)",
        background: "var(--color-paper-2)",
        padding: "var(--space-5) var(--space-6)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "3px",
          height: "100%",
          background: "var(--color-accent)",
        }}
      />
      <div
        style={{
          fontSize: "10.5px",
          fontWeight: 600,
          color: "var(--color-accent)",
          textTransform: "uppercase",
          letterSpacing: "0.1em",
          marginBottom: "var(--space-3)",
          fontFamily: "var(--font-mono)",
        }}
      >
        Grounded answer
      </div>

      {answer.key_points && answer.key_points.length > 0 && (
        <div
          style={{
            marginBottom: "var(--space-4)",
            padding: "12px 14px",
            borderRadius: "var(--radius-md)",
            background: "var(--color-paper-2)",
            border: "1px solid var(--color-border-subtle)",
          }}
        >
          {answer.key_points.map(renderKeyPoint)}
        </div>
      )}

      {renderNarrative()}

      {/* Citation chips — every traced metric stays reachable even when its
          value didn't appear verbatim in the prose. */}
      {hasProv && (
        <div
          style={{
            marginTop: "var(--space-4)",
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            gap: "6px",
          }}
        >
          <span
            style={{
              fontSize: "10px",
              fontWeight: 600,
              color: "var(--color-success)",
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              fontFamily: "var(--font-mono)",
              marginRight: "2px",
            }}
          >
            ✓ traced
          </span>
          {provenance!.map((p, i) => (
            <button
              key={`${p.metric}-${i}`}
              type="button"
              onClick={() => setActiveProv(i)}
              aria-haspopup="dialog"
              aria-expanded={activeProv === i}
              title="Show the executed query behind this number"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                background: "var(--color-paper-3)",
                border: "1px solid var(--color-border-subtle)",
                borderRadius: "var(--radius-pill)",
                padding: "3px 10px",
                fontSize: "11px",
                color: "var(--color-ink-dim)",
                fontFamily: "var(--font-mono)",
                cursor: "pointer",
                transition: "border-color var(--dur-fast) var(--ease-out)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "var(--color-accent)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "var(--color-border-subtle)";
              }}
            >
              <span>{titleCase(p.metric)}</span>
              <span style={{ fontWeight: 700, color: "var(--color-ink)" }}>
                {typeof p.value === "number" ? fmtNumber(p.value) : String(p.value)}
              </span>
            </button>
          ))}
        </div>
      )}

      {answer.sub_queries.length > 0 && (
        <div
          style={{
            marginTop: "var(--space-3)",
            display: "flex",
            flexWrap: "wrap",
            gap: "6px",
          }}
        >
          {answer.sub_queries.map((sq) => (
            <span
              key={sq.id}
              style={{
                fontSize: "11px",
                color: "var(--color-ink-dim)",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-pill)",
                padding: "3px 10px",
                fontFamily: "var(--font-mono)",
              }}
            >
              {sq.question}
            </span>
          ))}
        </div>
      )}

      {/* Provenance side drawer */}
      {activeProv != null && provenance?.[activeProv] && (
        <ProvenanceDrawer
          entry={provenance[activeProv]}
          query={activeQuery}
          variant={segmented ? "segment" : "metric"}
          onClose={() => setActiveProv(null)}
        />
      )}
    </div>
  );
}
