"use client";
import PipelinePanel from "./PipelinePanel";
import type { PipelineStageState } from "./PipelinePanel";

interface ArchitecturePanelProps {
  pipeline: Record<string, PipelineStageState>;
  isLoading: boolean;
  hasRun: boolean;
}

/**
 * Dedicated right column: the backend architecture diagram that lights up
 * live as a query runs. Fixed width, always visible, vertically scrollable
 * as stages fire. Persists after the query completes so the user can review
 * the path the system took.
 */
export default function ArchitecturePanel({
  pipeline,
  isLoading,
  hasRun,
}: ArchitecturePanelProps) {
  const firedCount = Object.keys(pipeline).length;

  return (
    <div
      style={{
        width: 260,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        borderLeft: "1px solid var(--color-border-subtle)",
        background: "var(--color-paper-2)",
        overflow: "hidden",
      }}
    >
      {/* Column header */}
      <div
        style={{
          padding: "14px 16px",
          borderBottom: "1px solid var(--color-border-subtle)",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <span
            className="status-dot"
            style={{
              background: isLoading
                ? "var(--color-accent)"
                : hasRun
                  ? "var(--color-success)"
                  : "var(--color-ink-faint)",
            }}
          />
          <span
            style={{
              fontSize: "12px",
              fontWeight: 700,
              color: "var(--color-ink)",
              letterSpacing: "0.02em",
            }}
          >
            System Architecture
          </span>
        </div>
        <div
          style={{
            fontSize: "10px",
            color: "var(--color-ink-faint)",
            marginTop: "4px",
            fontFamily: "var(--font-mono)",
          }}
        >
          {isLoading
            ? "processing…"
            : hasRun
              ? `${firedCount} stage${firedCount === 1 ? "" : "s"} executed`
              : "idle"}
        </div>
      </div>

      {/* Live pipeline diagram — scrolls if many stages */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          overscrollBehavior: "contain",
        }}
      >
        <PipelinePanel pipeline={pipeline} isLoading={isLoading} />
      </div>

      {/* Legend footer */}
      <div
        style={{
          padding: "10px 14px",
          borderTop: "1px solid var(--color-border-subtle)",
          display: "flex",
          gap: "12px",
          flexShrink: 0,
        }}
      >
        {[
          { color: "var(--color-accent)", label: "active" },
          { color: "var(--color-success)", label: "done" },
          { color: "var(--color-ink-faint)", label: "pending" },
        ].map((item) => (
          <div
            key={item.label}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "4px",
              fontSize: "9.5px",
              color: "var(--color-ink-faint)",
              fontFamily: "var(--font-mono)",
              textTransform: "capitalize",
            }}
          >
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: item.color,
                display: "inline-block",
              }}
            />
            {item.label}
          </div>
        ))}
      </div>
    </div>
  );
}
