"use client";
import { SECTION_LABEL } from "./shared";
import type { UploadedDataset } from "@/lib/types";

export default function WorkspaceCard({
  datasetName,
  connectionLabel,
  uploadedDataset,
}: {
  datasetName: string;
  connectionLabel: string;
  uploadedDataset: UploadedDataset | null;
}) {
  return (
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
            {uploadedDataset.row_count.toLocaleString()} rows ·{" "}
            {uploadedDataset.columns.length} cols · {uploadedDataset.domain}
          </div>
        </div>
      )}
    </div>
  );
}
