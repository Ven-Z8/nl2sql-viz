import { slugify } from "./format";
import type { ResultRow } from "./types";

/**
 * Serialize preview rows as RFC-4180 CSV. Fields containing commas, quotes
 * or newlines are quoted; embedded quotes are doubled.
 */
export function toCsv(
  rows: ResultRow[],
  columns?: string[]
): string {
  const cols =
    columns ?? (rows.length > 0 ? Object.keys(rows[0]) : []);
  const escape = (value: unknown): string => {
    let s: string;
    if (value == null) s = "";
    else if (typeof value === "object") s = JSON.stringify(value);
    else s = String(value);
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [
    cols.join(","),
    ...rows.map((r) => cols.map((c) => escape(r[c])).join(",")),
  ];
  return lines.join("\r\n");
}

/** Trigger a browser download of the current preview rows as CSV. */
export function downloadRowsCsv(
  rows: ResultRow[],
  title: string,
  columns?: string[]
): void {
  const csv = toCsv(rows, columns);
  const blob = new Blob([`\uFEFF${csv}`], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${slugify(title)}-${new Date()
    .toISOString()
    .slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
