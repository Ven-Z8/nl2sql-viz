"use client";

interface QueryComposerProps {
  query: string;
  onQueryChange: (q: string) => void;
  onSubmit: () => void;
  isLoading: boolean;
  /** True only when the socket is open — submit stays honest otherwise. */
  canRun: boolean;
  /** Contract v3 — "Ask a follow-up…" while a thread is active. */
  placeholder?: string;
}

export default function QueryComposer({
  query,
  onQueryChange,
  onSubmit,
  isLoading,
  canRun,
  placeholder = "Ask a question about your data…",
}: QueryComposerProps) {
  const disabled = isLoading || !query.trim() || !canRun;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      if (!disabled) onSubmit();
    }
  };

  return (
    <div
      style={{
        padding: "var(--space-5)",
        borderBottom: "1px solid var(--color-border-subtle)",
        flexShrink: 0,
        background: "var(--color-paper-2)",
      }}
    >
      <textarea
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={isLoading}
        placeholder={placeholder}
        style={{
          width: "100%",
          height: "84px",
          background: "var(--color-paper-3)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-md)",
          padding: "12px 14px",
          fontSize: "13.5px",
          lineHeight: 1.5,
          color: "var(--color-ink)",
          resize: "none",
          outline: "none",
          fontFamily: "inherit",
          transition: "border-color var(--dur-fast) var(--ease-out)",
        }}
        onFocus={(e) => {
          e.target.style.borderColor = "var(--color-accent)";
        }}
        onBlur={(e) => {
          e.target.style.borderColor = "var(--color-border)";
        }}
      />
      <button
        onClick={onSubmit}
        disabled={disabled}
        title={
          !canRun && !isLoading
            ? "Waiting for the backend connection…"
            : undefined
        }
        style={{
          marginTop: "var(--space-3)",
          width: "100%",
          padding: "10px",
          borderRadius: "var(--radius-md)",
          background: disabled ? "var(--color-paper-3)" : "var(--color-accent)",
          border: "none",
          color: disabled ? "var(--color-ink-faint)" : "var(--color-on-accent)",
          fontSize: "13px",
          fontWeight: 600,
          letterSpacing: "-0.01em",
          cursor: disabled ? "not-allowed" : "pointer",
          transition:
            "transform var(--dur-fast) var(--ease-out), opacity var(--dur-fast)",
        }}
        onMouseDown={(e) => {
          if (!disabled) {
            (e.currentTarget as HTMLButtonElement).style.transform = "scale(0.98)";
          }
        }}
        onMouseUp={(e) => {
          (e.currentTarget as HTMLButtonElement).style.transform = "scale(1)";
        }}
      >
        {isLoading ? "Running…" : !canRun ? "Connecting…" : "Ask DataLens →"}
      </button>
      <div
        style={{
          fontSize: "11px",
          color: "var(--color-ink-faint)",
          marginTop: "var(--space-2)",
          textAlign: "right",
          fontFamily: "var(--font-mono)",
        }}
      >
        ⌘↵ to run
      </div>
    </div>
  );
}
