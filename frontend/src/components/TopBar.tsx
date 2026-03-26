interface TopBarProps {
  connected: boolean;
}

export default function TopBar({ connected }: TopBarProps) {
  return (
    <header
      style={{
        background: "var(--bg-panel)",
        borderBottom: "1px solid var(--border-subtle)",
        padding: "0 20px",
        height: "48px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexShrink: 0,
      }}
    >
      {/* Logo */}
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <span
          style={{
            fontSize: "20px",
            background: "linear-gradient(135deg, var(--accent), var(--accent-deep))",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}
        >
          ⬡
        </span>
        <span
          style={{
            fontWeight: 600,
            fontSize: "15px",
            color: "var(--text-primary)",
            letterSpacing: "-0.01em",
          }}
        >
          DataLens AI
        </span>
      </div>

      {/* Status pill */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          padding: "4px 10px",
          borderRadius: "999px",
          background: connected ? "#0d2b14" : "var(--bg-input)",
          border: `1px solid ${connected ? "#238636" : "var(--border)"}`,
          fontSize: "12px",
          color: connected ? "var(--green)" : "var(--text-muted)",
        }}
      >
        <span
          style={{
            width: "6px",
            height: "6px",
            borderRadius: "50%",
            background: connected ? "var(--green)" : "var(--text-muted)",
            flexShrink: 0,
          }}
        />
        {connected ? "Connected" : "Disconnected"}
      </div>
    </header>
  );
}
