"use client";
import { useEffect, useRef } from "react";

export type LogEntry = {
  time: string;
  icon: "done" | "run" | "sql";
  text: string;
  active?: boolean;
};

interface LogStreamProps {
  logs: LogEntry[];
}

const ICON: Record<LogEntry["icon"], { char: string; color: string }> = {
  done: { char: "✓", color: "var(--green)" },
  run:  { char: "⏳", color: "var(--accent)" },
  sql:  { char: "⬡", color: "var(--accent)" },
};

export default function LogStream({ logs }: LogStreamProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div
      style={{
        background: "var(--bg-log)",
        borderRadius: "6px",
        padding: "8px",
        height: "110px",
        overflowY: "auto",
        fontFamily: "'SF Mono', 'Fira Code', 'JetBrains Mono', Menlo, Consolas, monospace",
        fontSize: "11px",
        lineHeight: "1.7",
        color: "var(--text-secondary)",
      }}
    >
      {logs.length === 0 && (
        <span style={{ color: "var(--text-muted)" }}>Waiting for query…</span>
      )}
      {logs.map((entry, i) => {
        const ic = ICON[entry.icon];
        return (
          <div key={i} style={{ display: "flex", gap: "6px", alignItems: "flex-start" }}>
            <span style={{ color: "var(--text-muted)", flexShrink: 0 }}>{entry.time}</span>
            <span style={{ color: ic.color, flexShrink: 0 }}>{ic.char}</span>
            <span style={{ color: entry.active ? "var(--text-primary)" : undefined }}>
              {entry.text}
              {entry.active && (
                <span
                  style={{
                    display: "inline-block",
                    marginLeft: "2px",
                    color: "var(--accent)",
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
