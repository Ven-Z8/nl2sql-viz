interface TopBarProps {
  connected: boolean;
}

export default function TopBar({ connected }: TopBarProps) {
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

      {/* Status pill */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          padding: "5px 12px",
          borderRadius: "var(--radius-pill)",
          background: connected ? "var(--color-success-dim)" : "var(--color-paper-3)",
          border: `1px solid ${connected ? "var(--color-success-dim)" : "var(--color-border)"}`,
          fontSize: "12px",
          fontWeight: 500,
          color: connected ? "var(--color-success)" : "var(--color-ink-faint)",
          transition: "background var(--dur-fast) var(--ease-out)",
        }}
      >
        <span
          className="status-dot"
          style={{
            background: connected ? "var(--color-success)" : "var(--color-ink-faint)",
          }}
        />
        {connected ? "Connected" : "Disconnected"}
      </div>
    </header>
  );
}