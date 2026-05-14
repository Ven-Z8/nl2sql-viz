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
        width: "280px",
        flexShrink: 0,
        background: "var(--bg-panel)",
        borderRight: "1px solid var(--border-subtle)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--border-subtle)" }}>
        <div
          style={{
            fontSize: "11px",
            fontWeight: 600,
            color: "var(--text-muted)",
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            marginBottom: "8px",
          }}
        >
          Workspace
        </div>
        <div style={{ fontSize: "13px", color: "var(--text-primary)", fontWeight: 600 }}>
          {datasetName || "Postgres Workspace"}
        </div>
        <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "4px" }}>
          {connectionLabel}
        </div>
      </div>

      <div style={{ padding: "16px", borderBottom: "1px solid var(--border-subtle)" }}>
        <textarea
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          placeholder="Ask a question about your data…"
          style={{
            width: "100%",
            height: "72px",
            background: "var(--bg-input)",
            border: "1px solid var(--border)",
            borderRadius: "6px",
            padding: "8px 10px",
            fontSize: "13px",
            color: "var(--text-primary)",
            resize: "none",
            outline: "none",
            fontFamily: "inherit",
            boxSizing: "border-box",
            transition: "border-color 0.15s, box-shadow 0.15s",
          }}
          onFocus={(e) => {
            e.target.style.borderColor = "var(--accent)";
            e.target.style.boxShadow = "0 0 0 3px var(--accent-glow)";
          }}
          onBlur={(e) => {
            e.target.style.borderColor = "var(--border)";
            e.target.style.boxShadow = "none";
          }}
        />
        <button
          onClick={onSubmit}
          disabled={isLoading || !query.trim()}
          style={{
            marginTop: "8px",
            width: "100%",
            padding: "8px",
            background: isLoading || !query.trim()
              ? "var(--bg-input)"
              : "linear-gradient(90deg, var(--accent), var(--accent-deep))",
            border: "none",
            borderRadius: "6px",
            color: isLoading || !query.trim() ? "var(--text-muted)" : "#fff",
            fontSize: "13px",
            fontWeight: 500,
            cursor: isLoading || !query.trim() ? "not-allowed" : "pointer",
            transition: "opacity 0.15s",
          }}
        >
          {isLoading ? "Running…" : "Ask DataLens →"}
        </button>
      </div>

      <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border-subtle)" }}>
        <div
          style={{
            fontSize: "11px",
            fontWeight: 600,
            color: "var(--text-muted)",
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            marginBottom: "8px",
          }}
        >
          Suggested Analysis
        </div>
        {suggestedQuestions.length === 0 && (
          <p style={{ fontSize: "12px", color: "var(--text-muted)" }}>
            Connect a database or configure demo mode to see sample questions.
          </p>
        )}
        {suggestedQuestions.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onSuggestedQuestionClick(item.question)}
            disabled={isLoading}
            style={{
              width: "100%",
              textAlign: "left",
              padding: "8px 10px",
              borderRadius: "6px",
              border: "1px solid var(--border-subtle)",
              background: "var(--bg-log)",
              color: "var(--text-primary)",
              marginBottom: "6px",
              cursor: isLoading ? "not-allowed" : "pointer",
              opacity: isLoading ? 0.6 : 1,
            }}
          >
            <span
              style={{
                display: "block",
                fontSize: "10px",
                color: "var(--accent)",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                marginBottom: "3px",
              }}
            >
              {item.category}
            </span>
            <span style={{ display: "block", fontSize: "12px", lineHeight: 1.35 }}>
              {item.question}
            </span>
          </button>
        ))}
      </div>

      {/* Activity log section */}
      <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border-subtle)" }}>
        <div
          style={{
            fontSize: "11px",
            fontWeight: 600,
            color: "var(--text-muted)",
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            marginBottom: "8px",
          }}
        >
          Activity
        </div>
        <LogStream logs={logs} />
      </div>

      {/* History section */}
      <div style={{ flex: 1, overflowY: "auto", padding: "12px 16px" }}>
        <div
          style={{
            fontSize: "11px",
            fontWeight: 600,
            color: "var(--text-muted)",
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            marginBottom: "8px",
          }}
        >
          History
        </div>
        {history.length === 0 && (
          <p style={{ fontSize: "12px", color: "var(--text-muted)" }}>No queries yet.</p>
        )}
        {history.map((item, i) => {
          const isActive = i === activeHistoryIndex;
          return (
            <div
              key={i}
              onClick={() => onHistoryClick(item.query)}
              style={{
                padding: "8px 10px",
                borderRadius: "6px",
                marginBottom: "4px",
                cursor: "pointer",
                background: isActive ? "var(--accent-hist)" : "transparent",
                border: `1px solid ${isActive ? "var(--accent-dim)" : "transparent"}`,
                transition: "background 0.1s",
              }}
              onMouseEnter={(e) => {
                if (!isActive)
                  (e.currentTarget as HTMLDivElement).style.background = "var(--bg-input)";
              }}
              onMouseLeave={(e) => {
                if (!isActive)
                  (e.currentTarget as HTMLDivElement).style.background = "transparent";
              }}
            >
              <div
                style={{
                  fontSize: "12px",
                  color: "var(--text-primary)",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {item.query}
              </div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
                {item.timestamp}
              </div>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
