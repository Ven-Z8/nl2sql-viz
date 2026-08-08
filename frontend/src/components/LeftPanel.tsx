"use client";
import { useRef, useState } from "react";
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
  domains: { id: string; name: string }[];
  activeDomain: string;
  onDomainChange: (d: string) => void;
  uploading: boolean;
  uploadedDataset: {
    table_name: string;
    row_count: number;
    columns: string[];
    domain: string;
  } | null;
  uploadError: string | null;
  onUpload: (file: File, domain: string) => void;
  samples: { id: string; name: string; domain: string; description: string }[];
  onLoadSample: (sampleId: string) => void;
  onConnect: (dsn: string) => void;
}

const SECTION_LABEL: React.CSSProperties = {
  fontSize: "11px",
  fontWeight: 600,
  color: "var(--color-ink-faint)",
  textTransform: "uppercase",
  letterSpacing: "0.1em",
  marginBottom: "var(--space-3)",
};

const TAB: React.CSSProperties = {
  flex: 1,
  padding: "7px 0",
  borderRadius: "var(--radius-sm)",
  border: "none",
  background: "transparent",
  fontSize: "12px",
  fontWeight: 600,
  cursor: "pointer",
  transition: "background var(--dur-fast) var(--ease-out), color var(--dur-fast)",
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
  domains,
  activeDomain,
  onDomainChange,
  uploading,
  uploadedDataset,
  uploadError,
  onUpload,
  samples,
  onLoadSample,
  onConnect,
}: LeftPanelProps) {
  const [activeTab, setActiveTab] = useState<"csv" | "db">("csv");
  const [showUpload, setShowUpload] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadDomain, setUploadDomain] = useState("general");
  const [dsnInput, setDsnInput] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      if (query.trim() && !isLoading) onSubmit();
    }
  };

  const handleUploadClick = () => {
    if (!selectedFile) {
      fileInputRef.current?.click();
      return;
    }
    onUpload(selectedFile, uploadDomain);
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
      {/* Query composer — always pinned at top */}
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
          onClick={() => onSubmit()}
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
              : "var(--color-on-accent)",
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

      {/* Scrollable content below the composer */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Data source tabs: CSV | Databases */}
        <div
          style={{
            padding: "var(--space-4) var(--space-5) 0",
            display: "flex",
            gap: "4px",
            background: "var(--color-paper-3)",
            borderBottom: "1px solid var(--color-border-subtle)",
          }}
        >
          <button
            onClick={() => setActiveTab("csv")}
            style={{
              ...TAB,
              color: activeTab === "csv" ? "var(--color-accent)" : "var(--color-ink-faint)",
              background: activeTab === "csv" ? "var(--color-accent-dim)" : "transparent",
            }}
          >
            CSV
          </button>
          <button
            onClick={() => setActiveTab("db")}
            style={{
              ...TAB,
              color: activeTab === "db" ? "var(--color-accent)" : "var(--color-ink-faint)",
              background: activeTab === "db" ? "var(--color-accent-dim)" : "transparent",
            }}
          >
            Databases
          </button>
        </div>

        {/* CSV tab: samples + upload */}
        {activeTab === "csv" && (
          <div
            style={{
              padding: "var(--space-4) var(--space-5)",
              borderBottom: "1px solid var(--color-border-subtle)",
            }}
          >
            <div style={SECTION_LABEL}>Sample datasets</div>
            {samples.length === 0 && (
              <p style={{ fontSize: "12.5px", color: "var(--color-ink-faint)" }}>
                No samples available.
              </p>
            )}
            {samples.map((s) => (
              <button
                key={s.id}
                onClick={() => onLoadSample(s.id)}
                disabled={uploading}
                style={{
                  width: "100%",
                  textAlign: "left",
                  padding: "10px 12px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--color-border-subtle)",
                  background: "var(--color-paper-3)",
                  color: "var(--color-ink)",
                  marginBottom: "var(--space-2)",
                  cursor: uploading ? "not-allowed" : "pointer",
                  opacity: uploading ? 0.55 : 1,
                  transition: "border-color var(--dur-fast) var(--ease-out)",
                }}
                onMouseEnter={(e) => {
                  if (!uploading) {
                    (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--color-accent-dim)";
                  }
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--color-border-subtle)";
                }}
              >
                <span
                  style={{
                    display: "block",
                    fontSize: "12.5px",
                    fontWeight: 600,
                    marginBottom: "2px",
                  }}
                >
                  {s.name}
                </span>
                <span
                  style={{
                    display: "block",
                    fontSize: "11px",
                    color: "var(--color-ink-dim)",
                    lineHeight: 1.4,
                  }}
                >
                  {s.description}
                </span>
                <span
                  style={{
                    display: "inline-block",
                    marginTop: "4px",
                    fontSize: "10px",
                    fontWeight: 600,
                    color: "var(--color-accent)",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  {s.domain} · load →
                </span>
              </button>
            ))}

            <button
              onClick={() => setShowUpload((v) => !v)}
              style={{
                marginTop: "var(--space-2)",
                width: "100%",
                padding: "8px",
                borderRadius: "var(--radius-md)",
                background: "var(--color-paper-3)",
                border: "1px dashed var(--color-border)",
                color: "var(--color-accent)",
                fontSize: "12.5px",
                fontWeight: 500,
                cursor: "pointer",
                transition: "border-color var(--dur-fast) var(--ease-out)",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--color-accent-dim)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--color-border)";
              }}
            >
              {showUpload ? "Hide upload" : "Upload your own CSV →"}
            </button>

            {showUpload && (
              <div
                style={{
                  marginTop: "var(--space-3)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "var(--space-2)",
                }}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv"
                  style={{ display: "none" }}
                  onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  style={{
                    padding: "8px 10px",
                    borderRadius: "var(--radius-md)",
                    background: "var(--color-paper-3)",
                    border: "1px solid var(--color-border)",
                    color: selectedFile ? "var(--color-ink)" : "var(--color-ink-faint)",
                    fontSize: "12px",
                    textAlign: "left",
                    cursor: "pointer",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {selectedFile ? selectedFile.name : "Choose a .csv file…"}
                </button>
                <select
                  value={uploadDomain}
                  onChange={(e) => setUploadDomain(e.target.value)}
                  style={{
                    padding: "8px 10px",
                    borderRadius: "var(--radius-md)",
                    background: "var(--color-paper-3)",
                    border: "1px solid var(--color-border)",
                    color: "var(--color-ink)",
                    fontSize: "12px",
                    fontFamily: "inherit",
                    outline: "none",
                  }}
                >
                  <option value="" disabled>
                    Domain (guides analysis)
                  </option>
                  {domains.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
                <button
                  onClick={handleUploadClick}
                  disabled={uploading || !selectedFile}
                  style={{
                    padding: "8px",
                    borderRadius: "var(--radius-md)",
                    background: uploading || !selectedFile
                      ? "var(--color-paper-3)"
                      : "var(--color-accent)",
                    border: "none",
                    color: uploading || !selectedFile ? "var(--color-ink-faint)" : "var(--color-on-accent)",
                    fontSize: "12.5px",
                    fontWeight: 600,
                    cursor: uploading || !selectedFile ? "not-allowed" : "pointer",
                  }}
                >
                  {uploading ? "Uploading…" : "Upload & analyze"}
                </button>
                {uploadError && (
                  <div style={{ fontSize: "11.5px", color: "var(--color-danger)", lineHeight: 1.4 }}>
                    {uploadError}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Databases tab: connect */}
        {activeTab === "db" && (
          <div
            style={{
              padding: "var(--space-4) var(--space-5)",
              borderBottom: "1px solid var(--color-border-subtle)",
            }}
          >
            <div style={SECTION_LABEL}>Connect a database</div>
            <p style={{ fontSize: "12px", color: "var(--color-ink-dim)", lineHeight: 1.5, marginBottom: "var(--space-3)" }}>
              Connect a Postgres database to query it with natural language.
            </p>
            <input
              value={dsnInput}
              onChange={(e) => setDsnInput(e.target.value)}
              placeholder="postgresql://user:pass@host:5432/db"
              style={{
                width: "100%",
                padding: "10px 12px",
                borderRadius: "var(--radius-md)",
                background: "var(--color-paper-3)",
                border: "1px solid var(--color-border)",
                color: "var(--color-ink)",
                fontSize: "12px",
                fontFamily: "var(--font-mono)",
                outline: "none",
                boxSizing: "border-box",
              }}
            />
            <button
              onClick={() => onConnect(dsnInput.trim())}
              disabled={uploading || !dsnInput.trim()}
              style={{
                marginTop: "var(--space-2)",
                width: "100%",
                padding: "8px",
                borderRadius: "var(--radius-md)",
                background: uploading || !dsnInput.trim()
                  ? "var(--color-paper-3)"
                  : "var(--color-accent)",
                border: "none",
                color: uploading || !dsnInput.trim() ? "var(--color-ink-faint)" : "var(--color-on-accent)",
                fontSize: "12.5px",
                fontWeight: 600,
                cursor: uploading || !dsnInput.trim() ? "not-allowed" : "pointer",
              }}
            >
              {uploading ? "Connecting…" : "Connect"}
            </button>
            {uploadError && (
              <div style={{ fontSize: "11.5px", color: "var(--color-danger)", lineHeight: 1.4, marginTop: "var(--space-2)" }}>
                {uploadError}
              </div>
            )}
          </div>
        )}

        {/* Workspace */}
        <div
          style={{
            padding: "var(--space-4) var(--space-5)",
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
          {uploadedDataset && (
            <div
              style={{
                marginTop: "var(--space-3)",
                padding: "10px 12px",
                borderRadius: "var(--radius-md)",
                background: "var(--color-accent-dim)",
                border: "1px solid var(--color-accent-dim)",
                fontSize: "12px",
                color: "var(--color-ink)",
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: "2px" }}>
                {uploadedDataset.table_name}
              </div>
              <div
                style={{
                  fontSize: "11px",
                  color: "var(--color-ink-dim)",
                  fontFamily: "var(--font-mono)",
                }}
              >
                {uploadedDataset.row_count.toLocaleString()} rows · {uploadedDataset.columns.length} cols ·{" "}
                {uploadedDataset.domain}
              </div>
            </div>
          )}
        </div>

        {/* Suggested questions — appear after loading a dataset */}
        {suggestedQuestions.length > 0 && (
          <div
            style={{
              padding: "var(--space-4) var(--space-5)",
              borderBottom: "1px solid var(--color-border-subtle)",
            }}
          >
            <div style={SECTION_LABEL}>Suggested Analysis</div>
            {suggestedQuestions.map((item) => (
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
                  transition: "transform var(--dur-fast) var(--ease-out), border-color var(--dur-fast)",
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
        )}

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
        <div style={{ padding: "var(--space-4) var(--space-5)" }}>
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
      </div>
    </aside>
  );
}
