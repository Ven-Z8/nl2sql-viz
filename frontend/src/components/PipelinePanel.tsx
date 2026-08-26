import { useEffect, useState } from "react";
import { titleCase } from "@/lib/format";

export type PipelineStageState = {
  status: "pending" | "active" | "done";
  detail: string;
  startedAt: number;
  durationMs: number;
  /** LLM tokens consumed up to this stage (only present on cost gate). */
  tokens?: number;
};

/**
 * The canonical pipeline — order matters. The linker lists every stage so
 * the architecture diagram reads top-to-bottom as the actual data flow.
 * Only stages that FIRED for the current query render (no showcase steps).
 */
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

/** Stages that fire mid-run but aren't canonical pipeline steps — e.g. the
 *  Wave-3 execute-inspect-refine loop. They render appended after the
 *  canonical flow; unknown keys fall back to a humanized key name. */
const EXTRA_STAGE_META: Record<string, { name: string; icon: string }> = {
  refine: { name: "Self-Correction", icon: "↻" },
  complexity: { name: "Complexity Classification", icon: "◔" },
};

/** Stages where the pipeline visibly tightens/corrects itself — tinted
 *  amber while active so users perceive the self-correction happening. */
const SELF_CORRECT_STAGES = new Set(["refine", "cost"]);

interface PipelineStageLike {
  key: string;
  name: string;
  icon: string;
}

interface PipelinePanelProps {
  pipeline: Record<string, PipelineStageState>;
  isLoading: boolean;
}

function fmtDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function fmtTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export default function PipelinePanel({ pipeline, isLoading }: PipelinePanelProps) {
  const [, tick] = useState(0);
  // Re-render every 200ms while a stage is active so the live timer moves
  useEffect(() => {
    if (!isLoading) return;
    const id = setInterval(() => tick((t) => t + 1), 200);
    return () => clearInterval(id);
  }, [isLoading]);

  // Only stages that actually fired for this query — canonical pipeline
  // order first, then any non-canonical stage that fired (refine loop,
  // complexity, …) in arrival order.
  const firedKnown = PIPELINE_STAGES.filter((s) => pipeline[s.key]);
  const extras: PipelineStageLike[] = Object.keys(pipeline)
    .filter((k) => !PIPELINE_STAGES.some((s) => s.key === k))
    .map((k) => ({
      key: k,
      name: EXTRA_STAGE_META[k]?.name ?? titleCase(k),
      icon: EXTRA_STAGE_META[k]?.icon ?? "•",
    }));
  const fired = [...firedKnown, ...extras];

  if (fired.length === 0) {
    return (
      <div
        style={{
          padding: "14px 16px",
          fontSize: "11px",
          color: "var(--color-ink-faint)",
          fontFamily: "var(--font-mono)",
        }}
      >
        Waiting for pipeline…
      </div>
    );
  }

  const doneCount = fired.filter((s) => pipeline[s.key]?.status === "done").length;

  return (
    <div style={{ padding: "12px 14px" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "10px",
        }}
      >
        <span
          style={{
            fontSize: "10px",
            fontWeight: 700,
            color: "var(--color-ink-faint)",
            textTransform: "uppercase",
            letterSpacing: "0.12em",
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
            {doneCount}/{fired.length}
          </span>
        )}
      </div>

      {/* Architecture flow */}
      <div style={{ display: "flex", flexDirection: "column" }}>
        {fired.map((stage, i) => {
          const state = pipeline[stage.key];
          if (!state) return null;
          const status = state.status;
          const isActive = status === "active";
          const isDone = status === "done";
          const liveMs = isActive ? Date.now() - state.startedAt : 0;
          const duration = isDone ? state.durationMs : isActive ? liveMs : 0;

          // Self-correction stages (refine / cost tightening) glow amber
          // while active; everything else keeps the accent/success scheme.
          const corrective = SELF_CORRECT_STAGES.has(stage.key);
          const liveColor =
            isActive && corrective ? "var(--color-warning)" : "var(--color-accent)";
          const dotColor = isDone
            ? "var(--color-success)"
            : isActive
              ? liveColor
              : "var(--color-ink-faint)";

          const isCost = stage.key === "cost";
          const showTokens = isCost && state.tokens != null && state.tokens > 0;

          return (
            <div key={stage.key} style={{ display: "flex", gap: "10px" }}>
              {/* Connector column — the "wire" */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  width: 22,
                }}
              >
                <div
                  style={{
                    width: 22,
                    height: 22,
                    borderRadius: "50%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "11px",
                    fontWeight: 700,
                    border: `1.5px solid ${dotColor}`,
                    color: dotColor,
                    background: isActive
                      ? `color-mix(in srgb, ${liveColor} 16%, transparent)`
                      : isDone
                        ? "color-mix(in srgb, var(--color-success) 12%, transparent)"
                        : "transparent",
                    boxShadow: isActive
                      ? `0 0 0 4px color-mix(in srgb, ${liveColor} 14%, transparent)`
                      : "none",
                    transition: "all var(--dur-fast) var(--ease-out)",
                    flexShrink: 0,
                  }}
                >
                  {isDone ? "✓" : stage.icon}
                </div>
                {i < fired.length - 1 && (
                  <div
                    style={{
                      width: 2,
                      minHeight: 20,
                      flex: 1,
                      background: isDone
                        ? "var(--color-success)"
                        : "var(--color-border-subtle)",
                      transition: "background var(--dur-med) var(--ease-out)",
                    }}
                  />
                )}
              </div>

              {/* Stage body */}
              <div style={{ flex: 1, paddingBottom: "12px", minWidth: 0 }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "baseline",
                    justifyContent: "space-between",
                    gap: "6px",
                  }}
                >
                  <span
                    style={{
                      fontSize: "12px",
                      fontWeight: isActive ? 700 : 600,
                      color: isActive
                        ? "var(--color-ink)"
                        : isDone
                          ? "var(--color-ink)"
                          : "var(--color-ink-faint)",
                    }}
                  >
                    {stage.name}
                  </span>
                  <span
                    style={{
                      fontSize: "10px",
                      fontFamily: "var(--font-mono)",
                      color: isActive ? liveColor : "var(--color-ink-faint)",
                      whiteSpace: "nowrap",
                      flexShrink: 0,
                    }}
                  >
                    {duration > 0 ? fmtDuration(duration) : isActive ? "…" : ""}
                  </span>
                </div>
                {state.detail && (
                  <div
                    style={{
                      fontSize: "10.5px",
                      color:
                        isActive && corrective
                          ? "var(--color-warning)"
                          : "var(--color-ink-dim)",
                      fontStyle: isActive && corrective ? "italic" : undefined,
                      marginTop: 2,
                      lineHeight: 1.35,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {state.detail}
                  </div>
                )}
                {showTokens && (
                  <div
                    style={{
                      marginTop: "5px",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "5px",
                      padding: "3px 8px",
                      borderRadius: "var(--radius-pill)",
                      background: "var(--color-accent-dim)",
                      fontSize: "10px",
                      fontWeight: 600,
                      color: "var(--color-accent)",
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    <span style={{ fontSize: "9px" }}>⛁</span>
                    {fmtTokens(state.tokens!)} tokens
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
