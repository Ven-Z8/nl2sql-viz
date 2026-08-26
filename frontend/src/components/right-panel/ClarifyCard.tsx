"use client";
import type { PendingClarify } from "@/hooks/useQueryStream";

interface ClarifyCardProps {
  clarify: PendingClarify;
  /** Called with the picked option's index → clarification_response. */
  onRespond: (choice: number) => void;
}

/**
 * Inline card for the contract-v2 `clarify` event. The pipeline is paused
 * server-side until the user picks an option (or the ~120s server timeout
 * fires) — the composer is disabled while this is visible.
 */
export default function ClarifyCard({ clarify, onRespond }: ClarifyCardProps) {
  return (
    <div
      role="status"
      style={{
        border: "1px solid var(--color-accent-dim)",
        borderRadius: "var(--radius-lg)",
        background: "var(--color-accent-dim)",
        padding: "var(--space-4) var(--space-5)",
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-3)",
        animation: "fade-up var(--dur-med) var(--ease-out) both",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <span aria-hidden style={{ color: "var(--color-accent)", fontSize: "14px" }}>
          ◈
        </span>
        <span
          style={{
            fontSize: "10.5px",
            fontWeight: 600,
            color: "var(--color-accent)",
            textTransform: "uppercase",
            letterSpacing: "0.1em",
            fontFamily: "var(--font-mono)",
          }}
        >
          Quick question before I continue
        </span>
      </div>

      <div
        style={{
          fontSize: "14px",
          fontWeight: 600,
          lineHeight: 1.5,
          color: "var(--color-ink)",
        }}
      >
        {clarify.question}
      </div>

      {clarify.options.length > 0 && (
        <div
          role="group"
          aria-label="Clarification options"
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "8px",
          }}
        >
          {clarify.options.map((opt, i) => (
            <button
              key={i}
              type="button"
              onClick={() => onRespond(i)}
              title={`Continue with “${opt}”`}
              style={{
                background: "var(--color-paper)",
                border: "1px solid var(--color-border)",
                borderRadius: "var(--radius-pill)",
                padding: "7px 16px",
                fontSize: "12.5px",
                fontWeight: 600,
                color: "var(--color-ink)",
                cursor: "pointer",
                transition:
                  "border-color var(--dur-fast) var(--ease-out), background var(--dur-fast) var(--ease-out)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "var(--color-accent)";
                e.currentTarget.style.background = "var(--color-paper-2)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "var(--color-border)";
                e.currentTarget.style.background = "var(--color-paper)";
              }}
            >
              {opt}
            </button>
          ))}
        </div>
      )}

      <div
        style={{
          fontSize: "11px",
          color: "var(--color-ink-faint)",
          fontFamily: "var(--font-mono)",
        }}
      >
        Pick one to continue · the request times out server-side after ~2 minutes
      </div>
    </div>
  );
}
