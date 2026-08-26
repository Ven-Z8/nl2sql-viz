"use client";
import { useState } from "react";
import { DatasetCard, SECTION_LABEL } from "./shared";
import type { CatalogItem } from "@/lib/types";

interface DbTabProps {
  datasets: CatalogItem[];
  uploading: boolean;
  uploadError: string | null;
  onLoadDataset: (id: string) => void;
  onConnect: (dsn: string) => void;
}

/** Databases tab: multi-table relational datasets + bring-your-own DSN. */
export default function DbTab({
  datasets,
  uploading,
  uploadError,
  onLoadDataset,
  onConnect,
}: DbTabProps) {
  const [dsnInput, setDsnInput] = useState("");

  return (
    <div
      style={{
        padding: "var(--space-4) var(--space-5)",
        borderBottom: "1px solid var(--color-border-subtle)",
      }}
    >
      <div style={SECTION_LABEL}>Relational databases</div>
      <p
        style={{
          fontSize: "12px",
          color: "var(--color-ink-dim)",
          lineHeight: 1.5,
          marginBottom: "var(--space-3)",
        }}
      >
        Complex multi-table databases with relationships — ready to query.
      </p>
      {datasets.length === 0 && (
        <p style={{ fontSize: "12.5px", color: "var(--color-ink-faint)" }}>
          No databases available.
        </p>
      )}
      {datasets.map((d) => (
        <DatasetCard key={d.id} item={d} disabled={uploading} onLoad={onLoadDataset} />
      ))}

      <div style={{ marginTop: "var(--space-4)" }}>
        <div style={SECTION_LABEL}>Connect your own</div>
        <p
          style={{
            fontSize: "12px",
            color: "var(--color-ink-dim)",
            lineHeight: 1.5,
            marginBottom: "var(--space-3)",
          }}
        >
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
          onClick={() => onConnect(dsnInput)}
          disabled={uploading || !dsnInput.trim()}
          style={{
            marginTop: "var(--space-2)",
            width: "100%",
            padding: "8px",
            borderRadius: "var(--radius-md)",
            background:
              uploading || !dsnInput.trim()
                ? "var(--color-paper-3)"
                : "var(--color-accent)",
            border: "none",
            color:
              uploading || !dsnInput.trim()
                ? "var(--color-ink-faint)"
                : "var(--color-on-accent)",
            fontSize: "12.5px",
            fontWeight: 600,
            cursor: uploading || !dsnInput.trim() ? "not-allowed" : "pointer",
          }}
        >
          {uploading ? "Connecting…" : "Connect"}
        </button>
        {uploadError && (
          <div
            style={{
              fontSize: "11.5px",
              color: "var(--color-danger)",
              lineHeight: 1.4,
              marginTop: "var(--space-2)",
            }}
          >
            {uploadError}
          </div>
        )}
      </div>
    </div>
  );
}
