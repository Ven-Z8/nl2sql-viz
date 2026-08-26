"use client";
import { useState } from "react";
import LogStream, { type LogEntry } from "./LogStream";
import CsvTab from "./left-panel/CsvTab";
import DbTab from "./left-panel/DbTab";
import HistoryList from "./left-panel/HistoryList";
import QueryComposer from "./left-panel/QueryComposer";
import SuggestedQuestions from "./left-panel/SuggestedQuestions";
import WorkspaceCard from "./left-panel/WorkspaceCard";
import { TAB } from "./left-panel/shared";
import type {
  CatalogItem,
  HistoryItem,
  SuggestedQuestion,
  UploadedDataset,
} from "@/lib/types";

export type { HistoryItem } from "@/lib/types";

interface LeftPanelProps {
  query: string;
  onQueryChange: (q: string) => void;
  onSubmit: () => void;
  isLoading: boolean;
  /** Socket open — gates the submit button honestly. */
  canRun: boolean;
  /** Contract v3 — composer hint while a thread is active. */
  composerPlaceholder?: string;
  datasetName: string;
  connectionLabel: string;
  suggestedQuestions: SuggestedQuestion[];
  logs: LogEntry[];
  history: HistoryItem[];
  onHistoryRerun: (q: string) => void;
  onAsk: (q: string) => void;
  domains: { id: string; name: string }[];
  activeDomain: string;
  onDomainChange: (d: string) => void;
  uploading: boolean;
  uploadedDataset: UploadedDataset | null;
  uploadError: string | null;
  onUpload: (file: File, domain: string) => void;
  samples: CatalogItem[];
  onLoadSample: (sampleId: string) => void;
  datasets: CatalogItem[];
  onLoadDataset: (datasetId: string) => void;
  onConnect: (dsn: string) => void;
}

/**
 * Thin shell composing the left column. All sections live in
 * components/left-panel/* — this file is layout + tab state only.
 * `activeDomain`/`onDomainChange` are retained as the workspace's declared
 * analysis domain surface.
 */
export default function LeftPanel({
  query,
  onQueryChange,
  onSubmit,
  isLoading,
  canRun,
  composerPlaceholder,
  datasetName,
  connectionLabel,
  suggestedQuestions,
  logs,
  history,
  onHistoryRerun,
  onAsk,
  domains,
  activeDomain,
  onDomainChange,
  uploading,
  uploadedDataset,
  uploadError,
  onUpload,
  samples,
  onLoadSample,
  datasets,
  onLoadDataset,
  onConnect,
}: LeftPanelProps) {
  const [activeTab, setActiveTab] = useState<"csv" | "db">("csv");

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
      <QueryComposer
        query={query}
        onQueryChange={onQueryChange}
        onSubmit={onSubmit}
        isLoading={isLoading}
        canRun={canRun}
        placeholder={composerPlaceholder}
      />

      {/* Scrollable content below the composer */}
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column" }}>
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
              color:
                activeTab === "csv" ? "var(--color-accent)" : "var(--color-ink-faint)",
              background:
                activeTab === "csv" ? "var(--color-accent-dim)" : "transparent",
            }}
          >
            CSV
          </button>
          <button
            onClick={() => setActiveTab("db")}
            style={{
              ...TAB,
              color:
                activeTab === "db" ? "var(--color-accent)" : "var(--color-ink-faint)",
              background:
                activeTab === "db" ? "var(--color-accent-dim)" : "transparent",
            }}
          >
            Databases
          </button>
        </div>

        {activeTab === "csv" ? (
          <CsvTab
            domains={domains}
            samples={samples}
            uploading={uploading}
            uploadError={uploadError}
            onLoadSample={onLoadSample}
            onUpload={(file, domain) => {
              onDomainChange(domain);
              onUpload(file, domain);
            }}
          />
        ) : (
          <DbTab
            datasets={datasets}
            uploading={uploading}
            uploadError={uploadError}
            onLoadDataset={onLoadDataset}
            onConnect={onConnect}
          />
        )}

        {/* Workspace */}
        <WorkspaceCard
          datasetName={datasetName}
          connectionLabel={connectionLabel}
          uploadedDataset={uploadedDataset}
        />

        {/* Curated questions — visible from first paint */}
        <SuggestedQuestions
          questions={suggestedQuestions}
          isLoading={isLoading}
          onAsk={onAsk}
        />

        {/* Activity */}
        <div
          style={{
            padding: "var(--space-4) var(--space-5)",
            borderBottom: "1px solid var(--color-border-subtle)",
          }}
        >
          <div
            style={{
              fontSize: "11px",
              fontWeight: 600,
              color: "var(--color-ink-faint)",
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              marginBottom: "var(--space-3)",
            }}
          >
            Activity
          </div>
          <LogStream logs={logs} />
        </div>

        {/* History — click re-runs */}
        <HistoryList history={history} onRerun={onHistoryRerun} />
      </div>
    </aside>
  );
}
