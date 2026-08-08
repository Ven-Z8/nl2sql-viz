"use client";
import LogStream, { LogEntry } from "./LogStream";

export type HistoryItem = { query: string; timestamp: string };
export type SuggestedQuestion = { id: string; question: string; category: string };

interface LeftPanelProps {
  query: string;
  onQueryChange: (q: string) => void;
  onSubmit: () => void;
  isLoading: boolean;
  datasetName: string;
  connectionLabel: string;
  suggestedQuestions: SuggestedQuestion[];
  logs: LogEntry[];
  history: HistoryItem[];
  activeHistoryIndex: number | null;
  onHistoryClick: (q: string) => void;
  onSuggestedQuestionClick: (q: string) => void;
}

const SECTION_LABEL: React.CSSProperties = {
  fontSize: "11px",
  fontWeight: 600,
  color: "var(--color-ink-faint)",
  textTransform: "uppercase",
  letterSpacing: "0.1em",
  marginBottom: "var(--space-3)",
};

export default function LeftPanel({
  query,
  onQueryChange,
  onSubmit,
  isLoading,
  datasetName,
  connectionLabel,
  suggestedQuestions,
  logs,
  history,
  activeHistoryIndex,
  onHistoryClick,
  onSuggestedQuestionClick,
}: LeftPanelProps) {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      if (query.trim() && !isLoading) onSubmit();
    }
  };

  return (
    <aside
      style={{
        width: "300px",
        flexShrink: 0,
        background: "var(--color-paper-2)",
        borderRight: "1px solid var(--color-border-subtle)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* Workspace */}
      <div
        style={{
          padding: "var(--space-5) var(--space-5) var(--space-4)",
          borderBottom: "1px solid var(--color-border-subtle)",
        }}
      >
        <div style={SECTION_LABEL}>Workspace</div>
        <div
          style={{
            fontSize: "14px",
            fontWeight: 600,
            color: "var(--color-ink)",
            letterSpacing: "-0.01em",
          }}
        >
          {datasetName || "Postgres Workspace"}
        </div>
        <div
          style={{
            fontSize: "12px",
            color: "var(--color-ink-dim)",
            marginTop: "4px",
            fontFamily: "var(--font-mono)",
          }}
        >
          {connectionLabel}
        </div>
      </div>

      {/* Query composer */}
      <div
        style={{
          padding: "var(--space-5)",
          borderBottom: "1px solid var(--color-border-subtle)",
        }}
      >
        <textarea
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          placeholder="Ask a question about your data…"
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
          disabled={isLoading || !query.trim()}
          style={{
            marginTop: "var(--space-3)",
            width: "100%",
            padding: "10px",
            borderRadius: "var(--radius-md)",
            background: isLoading || !query.trim()
              ? "var(--color-paper-3)"
              : "var(--color-accent)",
            border: "none",
            color: isLoading || !query.trim()
              ? "var(--color-ink-faint)"
              : "oklch(18% 0.02 80)",
            fontSize: "13px",
            fontWeight: 600,
            letterSpacing: "-0.01em",
            cursor: isLoading || !query.trim() ? "not-allowed" : "pointer",
            transition: "transform var(--dur-fast) var(--ease-out), opacity var(--dur-fast)",
          }}
          onMouseDown={(e) => {
            if (query.trim() && !isLoading) {
              (e.currentTarget as HTMLButtonElement).style.transform = "scale(0.98)";
            }
          }}
          onMouseUp={(e) => {
            (e.currentTarget as HTMLButtonElement).style.transform = "scale(1)";
          }}
        >
          {isLoading ? "Running…" : "Ask DataLens →"}
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

      {/* Suggested questions */}
      <div
        style={{
          padding: "var(--space-4) var(--space-5)",
          borderBottom: "1px solid var(--color-border-subtle)",
        }}
      >
        <div style={SECTION_LABEL}>Suggested Analysis</div>
        {suggestedQuestions.length === 0 && (
          <p style={{ fontSize: "12.5px", color: "var(--color-ink-faint)", lineHeight: 1.5 }}>
            Connect a database or configure demo mode to see sample questions.
          </p>
        )}
        {suggestedQuestions.map((item, i) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onSuggestedQuestionClick(item.question)}
            disabled={isLoading}
            style={{
              width: "100%",
              textAlign: "left",
              padding: "10px 12px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--color-border-subtle)",
              background: "var(--color-paper-3)",
              color: "var(--color-ink)",
              marginBottom: "var(--space-2)",
              cursor: isLoading ? "not-allowed" : "pointer",
              opacity: isLoading ? 0.55 : 1,
              transition:
                "transform var(--dur-fast) var(--ease-out), border-color var(--dur-fast), opacity var(--dur-fast)",
            }}
            onMouseEnter={(e) => {
              if (!isLoading) {
                (e.currentTarget as HTMLButtonElement).style.transform = "translateY(-1px)";
                (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--color-accent-dim)";
              }
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.transform = "translateY(0)";
              (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--color-border-subtle)";
            }}
          >
            <span
              style={{
                display: "block",
                fontSize: "10px",
                fontWeight: 600,
                color: "var(--color-accent)",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                marginBottom: "3px",
              }}
            >
              {item.category}
            </span>
            <span style={{ display: "block", fontSize: "12.5px", lineHeight: 1.45 }}>
              {item.question}
            </span>
          </button>
        ))}
      </div>

      {/* Activity */}
      <div
        style={{
          padding: "var(--space-4) var(--space-5)",
          borderBottom: "1px solid var(--color-border-subtle)",
        }}
      >
        <div style={SECTION_LABEL}>Activity</div>
        <LogStream logs={logs} />
      </div>

      {/* History */}
      <div style={{ flex: 1, overflowY: "auto", padding: "var(--space-4) var(--space-5)" }}>
        <div style={SECTION_LABEL}>History</div>
        {history.length === 0 && (
          <p style={{ fontSize: "12.5px", color: "var(--color-ink-faint)" }}>No queries yet.</p>
        )}
        {history.map((item, i) => {
          const isActive = i === activeHistoryIndex;
          return (
            <div
              key={i}
              onClick={() => onHistoryClick(item.query)}
              style={{
                padding: "10px 12px",
                borderRadius: "var(--radius-md)",
                marginBottom: "4px",
                cursor: "pointer",
                background: isActive ? "var(--color-accent-dim)" : "transparent",
                border: `1px solid ${isActive ? "var(--color-accent-dim)" : "transparent"}`,
                transition: "background var(--dur-fast) var(--ease-out)",
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLDivElement).style.background = "var(--color-paper-3)";
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLDivElement).style.background = "transparent";
                }
              }}
            >
              <div
                style={{
                  fontSize: "12.5px",
                  color: "var(--color-ink)",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {item.query}
              </div>
              <div
                style={{
                  fontSize: "11px",
                  color: "var(--color-ink-faint)",
                  marginTop: "3px",
                  fontFamily: "var(--font-mono)",
                }}
              >
                {item.timestamp}
              </div>
            </div>
          );
        })}
      </div>
    </aside>
  );
}