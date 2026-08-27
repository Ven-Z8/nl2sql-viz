"use client";
import { useEffect, useState } from "react";
import type { WsStatus } from "@/lib/ws";

interface TopBarProps {
  status: WsStatus;
}

const STATUS_META: Record<
  WsStatus,
  { label: string; color: string; bg: string; border: string; dot: string }
> = {
  open: {
    label: "Connected",
    color: "var(--color-success)",
    bg: "var(--color-success-dim)",
    border: "var(--color-success-dim)",
    dot: "var(--color-success)",
  },
  connecting: {
    label: "Connecting…",
    color: "var(--color-accent)",
    bg: "var(--color-accent-dim)",
    border: "var(--color-accent-dim)",
    dot: "var(--color-accent)",
  },
  retrying: {
    label: "Reconnecting…",
    color: "var(--color-accent)",
    bg: "var(--color-accent-dim)",
    border: "var(--color-accent-dim)",
    dot: "var(--color-accent)",
  },
  closed: {
    label: "Disconnected",
    color: "var(--color-ink-faint)",
    bg: "var(--color-paper-3)",
    border: "var(--color-border)",
    dot: "var(--color-ink-faint)",
  },
};

export default function TopBar({ status }: TopBarProps) {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const meta = STATUS_META[status];

  return (
    <header
      style={{
        background: "var(--color-paper-2)",
        borderBottom: "1px solid var(--color-border-subtle)",
        padding: "0 var(--space-6)",
        height: "56px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexShrink: 0,
      }}
    >
      {/* Wordmark */}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
        <span
          style={{
            width: "26px",
            height: "26px",
            borderRadius: "8px",
            background: "var(--color-accent-dim)",
            border: "1px solid var(--color-accent-dim)",
            display: "grid",
            placeItems: "center",
            color: "var(--color-accent)",
            fontSize: "13px",
            fontWeight: 700,
            fontFamily: "var(--font-mono)",
          }}
        >
          ◈
        </span>
        <span
          style={{
            fontWeight: 600,
            fontSize: "15px",
            color: "var(--color-ink)",
            letterSpacing: "-0.02em",
          }}
        >
          DataLens
          <span style={{ color: "var(--color-accent)" }}> AI</span>
        </span>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
        {/* Theme toggle */}
        <button
          onClick={() => setTheme((t) => (t === "light" ? "dark" : "light"))}
          title="Toggle theme"
          style={{
            background: "var(--color-paper-3)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-pill)",
            padding: "5px 12px",
            fontSize: "12px",
            fontWeight: 500,
            color: "var(--color-ink-dim)",
            cursor: "pointer",
            transition: "background var(--dur-fast) var(--ease-out)",
          }}
        >
          {theme === "light" ? "◐ Dark" : "◐ Light"}
        </button>

        {/* Status pill — reflects the real WS lifecycle */}
        <div
          title={
            status === "retrying"
              ? "Demo backend warming up — pick a dataset or ask a question to continue."
              : undefined
          }
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "5px 12px",
            borderRadius: "var(--radius-pill)",
            background: meta.bg,
            border: `1px solid ${meta.border}`,
            fontSize: "12px",
            fontWeight: 500,
            color: meta.color,
            transition: "background var(--dur-fast) var(--ease-out)",
          }}
        >
          <span className="status-dot" style={{ background: meta.dot }} />
          {meta.label}
        </div>
      </div>
    </header>
  );
}
