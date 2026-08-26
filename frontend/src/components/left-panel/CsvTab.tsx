"use client";
import { useRef, useState } from "react";
import { DatasetCard, DOMAIN_SELECT, SECTION_LABEL } from "./shared";
import type { CatalogItem } from "@/lib/types";

interface CsvTabProps {
  domains: { id: string; name: string }[];
  samples: CatalogItem[];
  uploading: boolean;
  uploadError: string | null;
  onLoadSample: (id: string) => void;
  onUpload: (file: File, domain: string) => void;
}

/** CSV tab: sample datasets + own-file upload. */
export default function CsvTab({
  domains,
  samples,
  uploading,
  uploadError,
  onLoadSample,
  onUpload,
}: CsvTabProps) {
  const [showUpload, setShowUpload] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadDomain, setUploadDomain] = useState("general");
  const [sampleDomain, setSampleDomain] = useState("all");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const filteredSamples =
    sampleDomain === "all"
      ? samples
      : samples.filter((s) => s.domain === sampleDomain);

  return (
    <div
      style={{
        padding: "var(--space-4) var(--space-5)",
        borderBottom: "1px solid var(--color-border-subtle)",
      }}
    >
      <div style={SECTION_LABEL}>Sample datasets</div>
      <select
        value={sampleDomain}
        onChange={(e) => setSampleDomain(e.target.value)}
        style={{ ...DOMAIN_SELECT, marginBottom: "var(--space-3)" }}
      >
        <option value="all">All domains</option>
        {domains.map((d) => (
          <option key={d.id} value={d.id}>
            {d.name}
          </option>
        ))}
      </select>
      {filteredSamples.length === 0 && (
        <p style={{ fontSize: "12.5px", color: "var(--color-ink-faint)" }}>
          No datasets for this domain yet.
        </p>
      )}
      {filteredSamples.map((s) => (
        <DatasetCard
          key={s.id}
          item={s}
          disabled={uploading}
          onLoad={onLoadSample}
        />
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
          (e.currentTarget as HTMLButtonElement).style.borderColor =
            "var(--color-accent-dim)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.borderColor =
            "var(--color-border)";
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
            style={DOMAIN_SELECT}
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
            onClick={() => selectedFile && onUpload(selectedFile, uploadDomain)}
            disabled={uploading || !selectedFile}
            style={{
              padding: "8px",
              borderRadius: "var(--radius-md)",
              background:
                uploading || !selectedFile
                  ? "var(--color-paper-3)"
                  : "var(--color-accent)",
              border: "none",
              color:
                uploading || !selectedFile
                  ? "var(--color-ink-faint)"
                  : "var(--color-on-accent)",
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
  );
}
