"use client";
import { useEffect, useRef } from "react";

export type LogEntry = {
  time: string;
  icon: "done" | "run" | "sql";
  text: string;
  active?: boolean;
  /** Self-correction events (refine loop / cost tightening) get a subtle
   *  amber tint so the pipeline visibly corrects itself. Unknown/absent
   *  tones render exactly as before. */
  tone?: "selfcorrect";
};

interface LogStreamProps {
  logs: LogEntry[];
}

const ICON: Record<LogEntry["icon"], { char: string; color: string }> = {
  done: { char: "✓", color: "var(--color-success)" },
  run:  { char: "◈", color: "var(--color-accent)" },
  sql:  { char: "›", color: "var(--color-accent)" },
};

export default function LogStream({ logs }: LogStreamProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div
      style={{
        background: "var(--color-paper)",
        borderRadius: "var(--radius-md)",
        border: "1px solid var(--color-border-subtle)",
        padding: "10px",
        height: "120px",
        overflowY: "auto",
        fontFamily: "var(--font-mono)",
        fontSize: "11px",
        lineHeight: "1.8",
        color: "var(--color-ink-dim)",
      }}
    >
      {logs.length === 0 && (
        <span style={{ color: "var(--color-ink-faint)" }}>Waiting for query…</span>
      )}
      {logs.map((entry, i) => {
        const ic = ICON[entry.icon];
        const selfCorrect = entry.tone === "selfcorrect";
        return (
          <div
            key={i}
            style={{
              display: "flex",
              gap: "8px",
              alignItems: "flex-start",
              animation: "fade-up var(--dur-fast) var(--ease-out) both",
            }}
          >
            <span style={{ color: "var(--color-ink-faint)", flexShrink: 0 }}>{entry.time}</span>
            <span
              style={{
                color: selfCorrect ? "var(--color-warning)" : ic.color,
                flexShrink: 0,
              }}
            >
              {ic.char}
            </span>
            <span
              style={{
                color:
                  entry.active && !selfCorrect
                    ? "var(--color-ink)"
                    : selfCorrect
                      ? "var(--color-warning)"
                      : "var(--color-ink-dim)",
                fontStyle: selfCorrect ? "italic" : undefined,
                wordBreak: "break-word",
              }}
            >
              {entry.text}
              {entry.active && (
                <span
                  style={{
                    display: "inline-block",
                    marginLeft: "3px",
                    color: "var(--color-accent)",
                    animation: "blink 1s step-end infinite",
                  }}
                >
                  ▋
                </span>
              )}
            </span>
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}