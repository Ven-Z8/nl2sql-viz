"use client";
import { SECTION_LABEL } from "./shared";
import type { HistoryItem } from "@/lib/types";

/**
 * Query history. Clicking an entry RE-RUNS the question end-to-end
 * (not just a textarea refill).
 */
export default function HistoryList({
  history,
  onRerun,
}: {
  history: HistoryItem[];
  onRerun: (q: string) => void;
}) {
  return (
    <div style={{ padding: "var(--space-4) var(--space-5)" }}>
      <div style={SECTION_LABEL}>History</div>
      {history.length === 0 && (
        <p style={{ fontSize: "12.5px", color: "var(--color-ink-faint)" }}>
          No queries yet.
        </p>
      )}
      {history.map((item, i) => (
        <button
          key={i}
          onClick={() => onRerun(item.query)}
          title="Run this question again"
          style={{
            display: "block",
            width: "100%",
            textAlign: "left",
            padding: "10px 12px",
            borderRadius: "var(--radius-md)",
            marginBottom: "4px",
            cursor: "pointer",
            background: "transparent",
            border: "1px solid transparent",
            transition: "background var(--dur-fast) var(--ease-out)",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background =
              "var(--color-paper-3)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "transparent";
          }}
        >
          <div
            style={{
              fontSize: "12.5px",
              color: "var(--color-ink)",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {item.query}
          </div>
          <div
            style={{
              fontSize: "11px",
              color: "var(--color-ink-faint)",
              marginTop: "3px",
              fontFamily: "var(--font-mono)",
            }}
          >
            {item.timestamp}
          </div>
        </button>
      ))}
    </div>
  );
}
