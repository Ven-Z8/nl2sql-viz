/**
 * Answer metrics shape detection (Wave 4).
 *
 * The backend produces two metric shapes:
 *  - single-scalar: column-named stats ("Total Churned Accounts", "Avg LTV")
 *    traced at row 0 / row None of their result sets;
 *  - segmented: a grouped answer enumerates top categories ("Pro", "Basic")
 *    where every entry shares ONE query_index and cites a concrete,
 *    pairwise-distinct row_index into that query's rows.
 *
 * Callers branch on this shape — NOT on count — so e.g. two KPI columns
 * still render as big-number tiles while five segments render as a compact
 * chip row. Without contract-v2 provenance we conservatively report
 * "single" so styling degrades to the pre-Wave-3 look.
 */

import type { Metric, ProvenanceEntry } from "@/lib/types";

export function isSegmentedShape(
  metrics: Metric[] | undefined | null,
  provenance?: ProvenanceEntry[] | null
): boolean {
  if (!Array.isArray(metrics) || metrics.length < 2) return false;
  if (!Array.isArray(provenance) || provenance.length < 2) return false;

  // Group entries by producing query; a group is a segment set when every
  // member pinpoints its own concrete row (KPI-style answers cite row 0 for
  // every column; aggregate summaries cite no row at all — neither passes).
  const groups = new Map<number, ProvenanceEntry[]>();
  for (const p of provenance) {
    if (typeof p.query_index !== "number") continue;
    const list = groups.get(p.query_index);
    if (list) list.push(p);
    else groups.set(p.query_index, [p]);
  }
  for (const group of groups.values()) {
    if (group.length < 2) continue;
    const rowIndexes = group.map((e) => e.row_index);
    const allConcrete = rowIndexes.every((i) => i != null);
    const distinct = new Set(rowIndexes).size === rowIndexes.length;
    if (allConcrete && distinct) return true;
  }
  return false;
}
