import { useEffect, useState } from "react";

export type PipelineStageState = {
  status: "pending" | "active" | "done";
  detail: string;
  startedAt: number;
  durationMs: number;
};

export const PIPELINE_STAGES: { key: string; name: string; icon: string }[] = [
  { key: "schema", name: "Schema Introspection", icon: "▤" },
  { key: "link", name: "Schema Linking", icon: "⇄" },
  { key: "plan", name: "Query Planning", icon: "◫" },
  { key: "generate", name: "SQL Generation", icon: "⌘" },
  { key: "validate", name: "Schema Validation", icon: "✓" },
  { key: "cost", name: "Cost Gate", icon: "⚖" },
  { key: "execute", name: "Execution", icon: "▶" },
  { key: "narrative", name: "Narrative", icon: "✎" },
  { key: "viz", name: "Visualization", icon: "◔" },
];

interface PipelinePanelProps {
  pipeline: Record<string, PipelineStageState>;
  isLoading: boolean;
}

function fmtDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export default function PipelinePanel({ pipeline, isLoading }: PipelinePanelProps) {
  const [, tick] = useState(0);
  // Re-render every 250ms while a stage is active so the live timer moves
  useEffect(() => {
    if (!isLoading) return;
    const id = setInterval(() => tick((t) => t + 1), 250);
    return () => clearInterval(id);
  }, [isLoading]);

  const activeCount = Object.values(pipeline).filter((s) => s.status === "active").length;
  const doneCount = Object.values(pipeline).filter((s) => s.status === "done").length;

  return (
    <div
      style={{
        padding: "var(--space-4) var(--space-5)",
        borderBottom: "1px solid var(--color-border-subtle)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "var(--space-3)",
        }}
      >
        <span
          style={{
            fontSize: "11px",
            fontWeight: 600,
            color: "var(--color-ink-faint)",
            textTransform: "uppercase",
            letterSpacing: "0.1em",
          }}
        >
          Live Pipeline
        </span>
        {isLoading && (
          <span
            style={{
              fontSize: "10px",
              fontWeight: 600,
              color: "var(--color-accent)",
              fontFamily: "var(--font-mono)",
            }}
          >
            {activeCount > 0 ? `step ${doneCount + 1}/${PIPELINE_STAGES.length}` : "running…"}
          </span>
        )}
      </div>

      <div style={{ display: "flex", flexDirection: "column" }}>
        {PIPELINE_STAGES.map((stage, i) => {
          const state = pipeline[stage.key];
          const status = state?.status ?? "pending";
          const isActive = status === "active";
          const isDone = status === "done";
          const liveMs = isActive && state ? Date.now() - state.startedAt : 0;
          const duration = isDone && state ? state.durationMs : isActive ? liveMs : 0;

          const color = isDone
            ? "#4ade80"
            : isActive
              ? "var(--color-accent)"
              : "var(--color-ink-faint)";

          return (
            <div key={stage.key} style={{ display: "flex", gap: "12px" }}>
              {/* Connector column */}
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                <div
                  style={{
                    width: 26,
                    height: 26,
                    borderRadius: "50%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "12px",
                    border: `1.5px solid ${color}`,
                    color,
                    background: isActive
                      ? "color-mix(in srgb, var(--color-accent) 14%, transparent)"
                      : "transparent",
                    boxShadow: isActive ? `0 0 0 4px color-mix(in srgb, var(--color-accent) 12%, transparent)` : "none",
                    transition: "all var(--dur-fast) var(--ease-out)",
                  }}
                >
                  {isDone ? "✓" : stage.icon}
                </div>
                {i < PIPELINE_STAGES.length - 1 && (
                  <div
                    style={{
                      width: 2,
                      height: 22,
                      background: isDone ? "#4ade80" : "var(--color-border-subtle)",
                      transition: "background var(--dur-med) var(--ease-out)",
                    }}
                  />
                )}
              </div>

              {/* Stage body */}
              <div style={{ flex: 1, paddingBottom: "var(--space-3)" }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "baseline",
                    justifyContent: "space-between",
                    gap: "8px",
                  }}
                >
                  <span
                    style={{
                      fontSize: "12.5px",
                      fontWeight: isActive ? 700 : 600,
                      color: isActive ? "var(--color-ink)" : isDone ? "var(--color-ink)" : "var(--color-ink-faint)",
                    }}
                  >
                    {stage.name}
                  </span>
                  {duration > 0 && (
                    <span
                      style={{
                        fontSize: "10.5px",
                        fontFamily: "var(--font-mono)",
                        color: isActive ? "var(--color-accent)" : "var(--color-ink-faint)",
                      }}
                    >
                      {fmtDuration(duration)}
                    </span>
                  )}
                </div>
                {state?.detail && (
                  <div
                    style={{
                      fontSize: "11px",
                      color: "var(--color-ink-dim)",
                      marginTop: 2,
                      lineHeight: 1.4,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {state.detail}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}