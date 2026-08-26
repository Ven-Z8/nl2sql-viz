"use client";
import { useMemo, useState } from "react";
import type { ResultRow } from "@/lib/types";

interface ResultTableProps {
  rows: ResultRow[];
}

type SortState = { key: string; dir: "asc" | "desc" } | null;

const MAX_COLUMNS = 6;

function compareValues(a: unknown, b: unknown): number {
  const na = Number(a);
  const nb = Number(b);
  if (!Number.isNaN(na) && !Number.isNaN(nb) && a !== "" && b !== "") {
    return na - nb;
  }
  return String(a ?? "").localeCompare(String(b ?? ""), undefined, {
    numeric: true,
    sensitivity: "base",
  });
}

/**
 * Sortable preview table. Click a column header to toggle asc/desc;
 * headers expose aria-sort for assistive tech.
 */
export default function ResultTable({ rows }: ResultTableProps) {
  const [sort, setSort] = useState<SortState>(null);

  const columns = useMemo(
    () => (rows.length > 0 ? Object.keys(rows[0]).slice(0, MAX_COLUMNS) : []),
    [rows]
  );

  const sorted = useMemo(() => {
    if (!sort || rows.length === 0) return rows;
    const { key, dir } = sort;
    const factor = dir === "asc" ? 1 : -1;
    return [...rows].sort(
      (a, b) => factor * compareValues(a[key], b[key])
    );
  }, [rows, sort]);

  if (rows.length === 0 || columns.length === 0) return null;

  const toggle = (key: string) =>
    setSort((prev) =>
      prev && prev.key === key
        ? { key, dir: prev.dir === "asc" ? "desc" : "asc" }
        : { key, dir: "asc" }
    );

  return (
    <div
      style={{
        border: "1px solid var(--color-border-subtle)",
        borderRadius: "var(--radius-lg)",
        background: "var(--color-paper-2)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "10px 14px",
          borderBottom: "1px solid var(--color-border-subtle)",
          color: "var(--color-ink-faint)",
          fontSize: "10.5px",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.1em",
          fontFamily: "var(--font-mono)",
        }}
      >
        Result Rows
      </div>
      <div style={{ overflow: "auto", maxHeight: "320px" }}>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontSize: "12.5px",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          <thead
            style={{
              position: "sticky",
              top: 0,
              background: "var(--color-paper-2)",
              zIndex: 1,
            }}
          >
            <tr>
              {columns.map((column) => {
                const isSorted = sort?.key === column;
                const ariaSort = isSorted
                  ? sort!.dir === "asc"
                    ? "ascending"
                    : "descending"
                  : "none";
                return (
                  <th
                    key={column}
                    aria-sort={ariaSort as "ascending" | "descending" | "none"}
                  >
                    <button
                      onClick={() => toggle(column)}
                      title={`Sort by ${column}`}
                      style={{
                        width: "100%",
                        display: "flex",
                        alignItems: "center",
                        gap: "5px",
                        padding: "9px 14px",
                        color: isSorted ? "var(--color-accent)" : "var(--color-ink-faint)",
                        textAlign: "left",
                        background: "none",
                        border: "none",
                        borderBottom: `1px solid ${isSorted ? "var(--color-accent-dim)" : "var(--color-border-subtle)"}`,
                        whiteSpace: "nowrap",
                        fontWeight: isSorted ? 700 : 500,
                        fontFamily: "var(--font-mono)",
                        fontSize: "11px",
                        cursor: "pointer",
                      }}
                    >
                      {column}
                      <span aria-hidden style={{ fontSize: "9px", opacity: isSorted ? 1 : 0.4 }}>
                        {isSorted ? (sort!.dir === "asc" ? "▲" : "▼") : "↕"}
                      </span>
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, index) => (
              <tr key={index}>
                {columns.map((column) => (
                  <td
                    key={column}
                    style={{
                      padding: "8px 14px",
                      color: "var(--color-ink-dim)",
                      borderBottom: "1px solid var(--color-border-subtle)",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {String(row[column] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
