"use client";
import { useMemo } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useChartPalette } from "@/lib/chartPalette";
import { isSegmentedShape } from "@/lib/answerShape";
import { fmtNumber, titleCase } from "@/lib/format";
import type { ChartHint, Metric, ProvenanceEntry, ResultRow } from "@/lib/types";

/**
 * THE chart renderer. One config-driven component consumes the backend's
 * chart_hint + result rows — there are no per-kind wrapper components and no
 * client-side column sniffing heuristics; when a hint is missing we fall
 * back to "first label column × first numeric column" as a plain bar chart.
 *
 * SVG presentation attributes can't resolve var(), so colors come pre-resolved
 * from lib/chartPalette.ts (recomputed on [data-theme] change → dark mode is
 * always correct). Tooltip/legend HTML uses CSS variables directly.
 */

interface DataChartProps {
  hint: ChartHint | null;
  rows: ResultRow[];
  rowCount: number | null;
  metrics: Metric[];
  /** Contract v2 provenance — used only to classify metric SHAPE
   *  (single-scalar vs segmented) for the KPI view. Optional; absent on
   *  older payloads, which then always render single-scalar styling. */
  provenance?: ProvenanceEntry[] | null;
}

const HISTOGRAM_BINS = 12;
const HORIZONTAL_LABEL_THRESHOLD = 14;
/** Cap on distinct color values a pivoted chart will plot (palette cycles). */
const MAX_PIVOT_SERIES = 12;

/** Kinds whose categories the backend asks us to order desc by y[0]. */
const DESC_SORT_KINDS: ReadonlySet<string> = new Set([
  "bar",
  "pie",
  "stacked_bar",
  "grouped_bar",
]);

// ── tooltip (HTML → safe for CSS vars) ──────────────────────────

/* eslint-disable @typescript-eslint/no-explicit-any */
function ChartTip({ active, payload, label, seriesOrder }: any) {
  if (!active || !payload || payload.length === 0) return null;
  // Multi-series tooltips read top-to-bottom in series order (matching the
  // legend), not in Recharts' default payload order.
  const ordered =
    Array.isArray(seriesOrder) && payload.length > 1
      ? [...payload].sort((a: any, b: any) => {
          const ia = seriesOrder.indexOf(a?.dataKey);
          const ib = seriesOrder.indexOf(b?.dataKey);
          return (ia === -1 ? Number.MAX_SAFE_INTEGER : ia) -
            (ib === -1 ? Number.MAX_SAFE_INTEGER : ib);
        })
      : payload;
  return (
    <div
      style={{
        background: "var(--color-paper-2)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-md)",
        boxShadow: "0 4px 16px color-mix(in srgb, var(--color-ink) 12%, transparent)",
        padding: "8px 12px",
        fontSize: "12px",
        maxWidth: 260,
      }}
    >
      {label != null && label !== "" && (
        <div
          style={{
            fontWeight: 600,
            color: "var(--color-ink)",
            marginBottom: 2,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {String(label)}
        </div>
      )}
      {ordered.map((entry: any, i: number) => (
        <div
          key={i}
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: 12,
            color: "var(--color-ink-dim)",
          }}
        >
          <span>{entry.name ? titleCase(String(entry.name)) : "Value"}</span>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontVariantNumeric: "tabular-nums",
              color: typeof entry.color === "string" ? entry.color : "var(--color-accent)",
              fontWeight: 600,
            }}
          >
            {fmtNumber(Number(entry.value))}
          </span>
        </div>
      ))}
    </div>
  );
}
const renderTip = (props: any) => <ChartTip {...props} />;

/** Element content lets us thread seriesOrder into ChartTip — Recharts
 *  clones the element with active/payload/label at hover time. */
function seriesTip(order: string[]) {
  return <ChartTip seriesOrder={order} />;
}

function pieLabel(p: any): string {
  const percent = typeof p?.percent === "number" ? p.percent : 0;
  return `${p?.name ?? ""}: ${(percent * 100).toFixed(0)}%`;
}
/* eslint-enable @typescript-eslint/no-explicit-any */

// ── data shaping (hint-driven, minimal fallbacks) ───────────────

interface PreparedSeries {
  xCol: string | null;
  yCols: string[];
  data: Record<string, unknown>[];
  /** Row count before the top_n slice — drives the "top N of M" footnote. */
  totalCount: number;
  /** hint.color when it exists in the rows, else null. */
  colorCol: string | null;
}

function prepare(hint: ChartHint | null, rows: ResultRow[]): PreparedSeries | null {
  if (rows.length === 0) return null;
  const columns = Object.keys(rows[0]);
  const numericCols = columns.filter((c) =>
    rows.some((r) => typeof r[c] === "number")
  );
  const labelCols = columns.filter((c) => !numericCols.includes(c));

  let xCol = hint?.x && columns.includes(hint.x) ? hint.x : null;
  let yCols = (hint?.y ?? []).filter((c) => columns.includes(c));

  if (!yCols.length) yCols = numericCols.slice(0, 3);
  if (!xCol) xCol = labelCols[0] ?? columns.find((c) => !yCols.includes(c)) ?? null;

  // Chronological ordering only when every x value parses as a date — and
  // chronological wins over the backend's desc-sort for categorical kinds
  // (a month axis should never read December-first).
  const data = [...rows];
  const chronological =
    !!xCol &&
    data.every((r) => !Number.isNaN(Date.parse(String(r[xCol!] ?? ""))));
  if (chronological) {
    data.sort(
      (a, b) => Date.parse(String(a[xCol!] ?? "")) - Date.parse(String(b[xCol!] ?? ""))
    );
  } else if (
    hint?.sort === "desc" &&
    !!hint.kind &&
    DESC_SORT_KINDS.has(hint.kind) &&
    yCols[0]
  ) {
    const measure = yCols[0];
    data.sort((a, b) => (Number(b[measure]) || 0) - (Number(a[measure]) || 0));
  }

  const topN =
    typeof hint?.top_n === "number" && Number.isFinite(hint.top_n) && hint.top_n > 0
      ? Math.floor(hint.top_n)
      : null;

  return {
    xCol,
    yCols,
    data: topN ? data.slice(0, topN) : data,
    totalCount: data.length,
    colorCol:
      hint?.color && columns.includes(hint.color) ? hint.color : null,
  };
}

/** Distinct color values in first-seen order, capped at MAX_PIVOT_SERIES. */
function collectColorSeries(rows: Record<string, unknown>[], colorCol: string): string[] {
  const seen: string[] = [];
  for (const r of rows) {
    const key = r[colorCol] == null ? "" : String(r[colorCol]);
    if (seen.includes(key)) continue;
    if (seen.length >= MAX_PIVOT_SERIES) break;
    seen.push(key);
  }
  return seen;
}

/**
 * Long-format temporal pivot (hint.color on line/area): rows are
 * (time_x, color_value, measure_value). One wide row per distinct x, one
 * property per color value; missing cells stay undefined so lines gap
 * instead of lying with zeros.
 */
function pivotLines(
  rows: Record<string, unknown>[],
  xCol: string | null,
  colorCol: string,
  valueCol: string
): { data: Record<string, unknown>[]; seriesKeys: string[] } {
  const seriesKeys = collectColorSeries(rows, colorCol);
  const byX = new Map<string, Record<string, unknown>>();
  rows.forEach((r, i) => {
    const cv = r[colorCol] == null ? "" : String(r[colorCol]);
    if (!seriesKeys.includes(cv)) return;
    const xv = xCol ? String(r[xCol] ?? "") : `#${i + 1}`;
    let bucket = byX.get(xv);
    if (!bucket) {
      bucket = { __x: xv };
      byX.set(xv, bucket);
    }
    const v = r[valueCol];
    if (v != null && v !== "" && Number.isFinite(Number(v))) {
      bucket[cv] = Number(v);
    }
  });
  return { data: [...byX.values()], seriesKeys };
}

/**
 * Long-format category pivot (hint.color on stacked/grouped bars): rows are
 * (x_cat, color_value, value). Each color value becomes its own Bar series;
 * missing cells fill 0 so stacks stay contiguous.
 */
function pivotBars(
  rows: Record<string, unknown>[],
  xCol: string | null,
  colorCol: string,
  valueCol: string
): { data: ({ name: string } & Record<string, unknown>)[]; seriesKeys: string[] } {
  const seriesKeys = collectColorSeries(rows, colorCol);
  const byX = new Map<string, { name: string } & Record<string, unknown>>();
  for (const r of rows) {
    const cv = r[colorCol] == null ? "" : String(r[colorCol]);
    if (!seriesKeys.includes(cv)) continue;
    const name = (xCol ? String(r[xCol] ?? "") : "").slice(0, 40);
    let bucket = byX.get(name);
    if (!bucket) {
      bucket = { name };
      byX.set(name, bucket);
    }
    bucket[cv] = Number(r[valueCol]) || 0;
  }
  return { data: [...byX.values()], seriesKeys };
}

function histogramData(column: string, rows: ResultRow[]) {
  const values = rows
    .map((r) => Number(r[column]))
    .filter((v) => Number.isFinite(v));
  if (values.length === 0) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = (max - min) / HISTOGRAM_BINS || 1;
  const integer = values.every((v) => Number.isInteger(v));
  const bins = Array.from({ length: HISTOGRAM_BINS }, (_, i) => {
    const lo = min + i * width;
    const hi = lo + width;
    return { lo, hi, count: 0 };
  });
  for (const v of values) {
    const idx = Math.min(
      HISTOGRAM_BINS - 1,
      Math.max(0, Math.floor((v - min) / width))
    );
    bins[idx].count += 1;
  }
  return bins.map((b) => ({
    name: integer
      ? `${Math.round(b.lo)}–${Math.round(b.hi)}`
      : `${b.lo.toFixed(1)}–${b.hi.toFixed(1)}`,
    value: b.count,
  }));
}

// ── shared axis bits ────────────────────────────────────────────

function CategoryXAxis({
  dataKey,
  palette,
  rotate,
}: {
  dataKey: string;
  palette: ReturnType<typeof useChartPalette>;
  rotate: boolean;
}) {
  return (
    <XAxis
      dataKey={dataKey}
      tick={{ fontSize: 11, fill: palette.axis }}
      angle={rotate ? -35 : 0}
      textAnchor={rotate ? "end" : "middle"}
      height={rotate ? 72 : 30}
      tickFormatter={(v: unknown) => String(v ?? "").slice(0, 24)}
    />
  );
}

function NumericYAxis({ palette }: { palette: ReturnType<typeof useChartPalette> }) {
  return (
    <YAxis
      tick={{ fontSize: 11, fill: palette.axis }}
      tickFormatter={(v: number) => fmtNumber(v)}
      width={56}
    />
  );
}

function Grid({ palette }: { palette: ReturnType<typeof useChartPalette> }) {
  return <CartesianGrid strokeDasharray="3 3" stroke={palette.grid} vertical={false} />;
}

// ── main component ──────────────────────────────────────────────

export default function DataChart({
  hint,
  rows,
  rowCount,
  metrics,
  provenance,
}: DataChartProps) {
  const palette = useChartPalette();

  const kind = hint?.kind ?? (metrics.length > 0 ? "kpi" : "bar");
  const prepared = useMemo(() => prepare(hint, rows), [hint, rows]);

  const truncated =
    rowCount != null && rows.length > 0 && rows.length < rowCount;

  // hint.top_n caps categories after the desc-sort — footnote the cut like
  // the backend row-preview cap above.
  const topN =
    typeof hint?.top_n === "number" && Number.isFinite(hint.top_n) && hint.top_n > 0
      ? Math.floor(hint.top_n)
      : null;
  const topTotal = prepared?.totalCount ?? rows.length;
  const topCut = topN != null && topTotal > topN;

  // ── KPI: reuse KpiCard2D's visual language, themed via CSS vars ──
  if (kind === "kpi") {
    if (metrics.length === 0) {
      return <ChartMessage text="No KPI metrics returned for this question." />;
    }
    // Segmented shape (grouped answers): category-labeled entries that all
    // cite rows of one query render as a compact chip row — label + value
    // pills — instead of N stacked big-number cards.
    if (isSegmentedShape(metrics, provenance)) {
      return (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "var(--space-2)",
            padding: "var(--space-5)",
            flex: 1,
            alignContent: "center",
            justifyContent: "center",
          }}
        >
          {metrics.slice(0, 12).map((m, i) => (
            <span
              key={`${m.label}-${i}`}
              title={`${m.label}: ${fmtNumber(m.value)}`}
              style={{
                display: "inline-flex",
                alignItems: "baseline",
                gap: "8px",
                border: "1px solid var(--color-border-subtle)",
                borderRadius: "var(--radius-pill)",
                background:
                  "linear-gradient(135deg, var(--color-accent-dim), transparent 70%), var(--color-paper-3)",
                padding: "6px 14px",
                animation: "fade-up var(--dur-med) var(--ease-out) both",
                animationDelay: `${i * 50}ms`,
              }}
            >
              <span
                style={{
                  fontSize: "12px",
                  fontWeight: 600,
                  color: "var(--color-ink-dim)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  maxWidth: 140,
                }}
              >
                {m.label}
              </span>
              <span
                style={{
                  fontSize: "15px",
                  fontWeight: 700,
                  fontFamily: "var(--font-mono)",
                  fontVariantNumeric: "tabular-nums",
                  letterSpacing: "-0.02em",
                  color: "var(--color-ink)",
                }}
              >
                {fmtNumber(m.value)}
                {m.unit && (
                  <span
                    style={{
                      fontSize: "10px",
                      color: "var(--color-ink-faint)",
                      marginLeft: "2px",
                      fontWeight: 500,
                    }}
                  >
                    {m.unit}
                  </span>
                )}
              </span>
            </span>
          ))}
        </div>
      );
    }
    return (
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
          gap: "var(--space-3)",
          padding: "var(--space-4)",
          flex: 1,
          alignContent: "center",
        }}
      >
        {metrics.slice(0, 8).map((m, i) => (
          <div
            key={`${m.label}-${i}`}
            style={{
              borderRadius: "var(--radius-md)",
              padding: "14px 16px",
              border: "1px solid var(--color-border-subtle)",
              background:
                "linear-gradient(135deg, var(--color-accent-dim), transparent 65%), var(--color-paper-3)",
              animation: "fade-up var(--dur-med) var(--ease-out) both",
              animationDelay: `${i * 70}ms`,
            }}
          >
            <div
              style={{
                fontSize: "10.5px",
                fontWeight: 600,
                color: "var(--color-ink-faint)",
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                marginBottom: "6px",
                fontFamily: "var(--font-mono)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {titleCase(m.label)}
            </div>
            <div
              style={{
                fontSize: i === 0 ? "32px" : "26px",
                fontWeight: 700,
                color: "var(--color-ink)",
                letterSpacing: "-0.03em",
                fontFamily: "var(--font-mono)",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {fmtNumber(m.value)}
              {m.unit && (
                <span
                  style={{
                    fontSize: "12px",
                    color: "var(--color-ink-dim)",
                    marginLeft: "4px",
                    fontWeight: 500,
                  }}
                >
                  {m.unit}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!prepared || prepared.yCols.length === 0) {
    return <ChartMessage text="No plottable data returned for this question." />;
  }

  // Rows exist but every plotted cell is null/empty — say so instead of
  // drawing a flat zero line the user would misread as real data.
  const hasPlotValues = prepared.data.some((r) =>
    prepared.yCols.some((c) => {
      const v = r[c];
      return v != null && v !== "" && Number.isFinite(Number(v));
    })
  );
  if (!hasPlotValues) {
    return (
      <ChartMessage text="Rows came back, but every plotted value is empty — nothing to draw." />
    );
  }

  const { xCol, yCols, data } = prepared;
  const header = hint?.title ?? (xCol ? `${titleCase(xCol)} by ${yCols.map(titleCase).join(", ")}` : null);

  const body = (() => {
    switch (kind) {
      case "line":
      case "area": {
        // hint.color pivots long-format rows into one series per color value.
        let seriesData: Record<string, unknown>[];
        let plotSeries: { key: string; name: string }[];
        if (prepared.colorCol) {
          const pivoted = pivotLines(data, xCol, prepared.colorCol, yCols[0]);
          seriesData = pivoted.data;
          plotSeries = pivoted.seriesKeys.map((k) => ({ key: k, name: titleCase(k) }));
        } else {
          seriesData = data.map((r, i) => ({
            __x: xCol ? String(r[xCol] ?? "") : `#${i + 1}`,
            ...Object.fromEntries(yCols.map((c) => [c, Number(r[c]) || 0])),
          }));
          plotSeries = yCols.map((c) => ({ key: c, name: titleCase(c) }));
        }
        const rotate = seriesData.length > 6;
        const Chart = kind === "line" ? LineChart : AreaChart;
        return (
          <ResponsiveContainer width="100%" height="100%">
            <Chart data={seriesData} margin={{ top: 12, right: 20, left: 0, bottom: 4 }}>
              <defs>
                {plotSeries.map((s, i) => (
                  <linearGradient key={s.key} id={`grad-${i}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={palette.series[i % palette.series.length]} stopOpacity={0.45} />
                    <stop offset="95%" stopColor={palette.series[i % palette.series.length]} stopOpacity={0.05} />
                  </linearGradient>
                ))}
              </defs>
              <Grid palette={palette} />
              <CategoryXAxis dataKey="__x" palette={palette} rotate={rotate} />
              <NumericYAxis palette={palette} />
              <Tooltip
                content={seriesTip(plotSeries.map((s) => s.key))}
                cursor={{ stroke: palette.axis, strokeDasharray: "3 3" }}
              />
              {plotSeries.length > 1 && (
                <Legend wrapperStyle={{ fontSize: "11px", color: "var(--color-ink-dim)" }} />
              )}
              {plotSeries.map((s, i) => {
                const color = palette.series[i % palette.series.length];
                return kind === "line" ? (
                  <Line
                    key={s.key}
                    type="monotone"
                    dataKey={s.key}
                    name={s.name}
                    stroke={color}
                    strokeWidth={2}
                    dot={seriesData.length <= 30 ? { r: 2.5, fill: color } : false}
                    activeDot={{ r: 5 }}
                  />
                ) : (
                  <Area
                    key={s.key}
                    type="monotone"
                    dataKey={s.key}
                    name={s.name}
                    stroke={color}
                    strokeWidth={2}
                    fill={`url(#grad-${i})`}
                  />
                );
              })}
            </Chart>
          </ResponsiveContainer>
        );
      }

      case "pie": {
        const labelCol = xCol ?? "__x";
        const valueCol = yCols[0];
        const pieData = data
          .map((r, i) => ({
            name: xCol ? String(r[labelCol] ?? `#${i + 1}`) : `#${i + 1}`,
            value: Math.abs(Number(r[valueCol]) || 0),
          }))
          .filter((d) => d.value > 0)
          .slice(0, 10);
        return (
          <ResponsiveContainer width="100%" height="100%">
            <PieChart margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
              <Tooltip content={renderTip} />
              <Legend wrapperStyle={{ fontSize: "11px", color: "var(--color-ink-dim)" }} />
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius="52%"
                outerRadius="80%"
                dataKey="value"
                labelLine={false}
                label={pieLabel}
              >
                {pieData.map((_, i) => (
                  <Cell key={i} fill={palette.series[i % palette.series.length]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        );
      }

      case "scatter": {
        const xNum = yCols.length >= 2 ? yCols[1] : yCols[0];
        const yNum = yCols[0];
        const scatterData = data
          .map((r) => ({
            x: Number(r[xNum]) || 0,
            y: Number(r[yNum]) || 0,
          }))
          .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
        return (
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 12, right: 20, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={palette.grid} />
              <XAxis
                type="number"
                dataKey="x"
                name={titleCase(xNum)}
                tick={{ fontSize: 11, fill: palette.axis }}
                tickFormatter={(v: number) => fmtNumber(v)}
              />
              <YAxis
                type="number"
                dataKey="y"
                name={titleCase(yNum)}
                tick={{ fontSize: 11, fill: palette.axis }}
                tickFormatter={(v: number) => fmtNumber(v)}
                width={56}
              />
              <Tooltip content={renderTip} cursor={{ strokeDasharray: "3 3" }} />
              {xNum !== yNum && (
                <Legend wrapperStyle={{ fontSize: "11px", color: "var(--color-ink-dim)" }} />
              )}
              <Scatter
                name={`${titleCase(yNum)} vs ${titleCase(xNum)}`}
                data={scatterData}
                fill={palette.series[1]}
                fillOpacity={0.75}
              />
            </ScatterChart>
          </ResponsiveContainer>
        );
      }

      case "histogram": {
        const col =
          (hint?.y ?? []).find((c) => data.some((r) => typeof r[c] === "number")) ??
          Object.keys(data[0]).find((c) => data.some((r) => typeof r[c] === "number"));
        if (!col) {
          return <ChartMessage text="No numeric column available to bin." />;
        }
        const bins = histogramData(col, data);
        return (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={bins} margin={{ top: 12, right: 20, left: 0, bottom: 4 }}>
              <Grid palette={palette} />
              <CategoryXAxis dataKey="name" palette={palette} rotate={false} />
              <NumericYAxis palette={palette} />
              <Tooltip content={renderTip} cursor={{ fill: palette.accentDim }} />
              <Bar dataKey="value" name={`Count of ${titleCase(col)}`} radius={[4, 4, 0, 0]} fill={palette.series[0]} />
            </BarChart>
          </ResponsiveContainer>
        );
      }

      // "bar" | "stacked_bar" | "grouped_bar" — vertical or horizontal chosen
      // by label length (no sniffing). Recharts groups multiple series side by
      // side by default (grouped_bar); stacked_bar adds stackId so the
      // series pile into one column per x value. hint.color pivots long-format
      // rows so each distinct color value becomes its own series.
      default: {
        const stacked = kind === "stacked_bar";
        let barData: ({ name: string } & Record<string, unknown>)[];
        let plotSeries: { key: string; name: string }[];
        if (prepared.colorCol) {
          const pivoted = pivotBars(data, xCol, prepared.colorCol, yCols[0]);
          barData = pivoted.data;
          plotSeries = pivoted.seriesKeys.map((k) => ({ key: k, name: titleCase(k) }));
        } else {
          barData = data.map((r, i) => ({
            name: xCol ? String(r[xCol] ?? `#${i + 1}`).slice(0, 40) : `#${i + 1}`,
            ...Object.fromEntries(yCols.map((c) => [c, Number(r[c]) || 0])),
          }));
          plotSeries = yCols.map((c) => ({ key: c, name: titleCase(c) }));
        }
        const horizontal =
          Math.max(...barData.map((d) => d.name.length), 0) > HORIZONTAL_LABEL_THRESHOLD;
        const categoryWidth = horizontal
          ? Math.min(220, Math.max(...barData.map((d) => d.name.length), 10) * 7 + 16)
          : undefined;

        return (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={barData}
              layout={horizontal ? "vertical" : "horizontal"}
              margin={{ top: 12, right: 24, left: horizontal ? 8 : 0, bottom: 4 }}
            >
              <Grid palette={palette} />
              {horizontal ? (
                <>
                  <XAxis
                    type="number"
                    tick={{ fontSize: 11, fill: palette.axis }}
                    tickFormatter={(v: number) => fmtNumber(v)}
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={categoryWidth}
                    tick={{ fontSize: 11, fill: palette.axis }}
                    interval={0}
                  />
                </>
              ) : (
                <>
                  <CategoryXAxis dataKey="name" palette={palette} rotate={barData.length > 6} />
                  <NumericYAxis palette={palette} />
                </>
              )}
              <Tooltip
                content={seriesTip(plotSeries.map((s) => s.key))}
                cursor={{ fill: palette.accentDim }}
              />
              {plotSeries.length > 1 && (
                <Legend wrapperStyle={{ fontSize: "11px", color: "var(--color-ink-dim)" }} />
              )}
              {plotSeries.map((s, i) => (
                <Bar
                  key={s.key}
                  dataKey={s.key}
                  name={s.name}
                  radius={horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]}
                  fill={palette.series[i % palette.series.length]}
                  stackId={stacked ? "stack" : undefined}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        );
      }
    }
  })();

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        flex: 1,
        minHeight: 0,
        padding: "var(--space-4)",
        gap: "var(--space-2)",
      }}
    >
      {(header || truncated || topCut) && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "var(--space-3)",
            flexShrink: 0,
          }}
        >
          <span
            style={{
              fontSize: "12px",
              fontWeight: 600,
              color: "var(--color-ink-dim)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {header}
          </span>
          {(truncated || topCut) && (
            <span
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-2)",
                flexShrink: 0,
              }}
            >
              {truncated && (
                <span
                  title="The backend preview caps result rows; totals above may be computed over the full set."
                  style={{
                    fontSize: "10px",
                    fontWeight: 600,
                    color: "var(--color-ink-dim)",
                    background: "var(--color-paper-3)",
                    border: "1px solid var(--color-border-subtle)",
                    borderRadius: "var(--radius-pill)",
                    padding: "2px 9px",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  showing first {rows.length} of {rowCount} rows
                </span>
              )}
              {topCut && topN != null && (
                <span
                  title={`Only the leading ${topN} categories (after descending sort) are plotted.`}
                  style={{
                    fontSize: "10px",
                    fontWeight: 600,
                    color: "var(--color-ink-dim)",
                    background: "var(--color-paper-3)",
                    border: "1px solid var(--color-border-subtle)",
                    borderRadius: "var(--radius-pill)",
                    padding: "2px 9px",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  top {topN} of {topTotal} · +{topTotal - topN} more
                </span>
              )}
            </span>
          )}
        </div>
      )}
      <div style={{ flex: 1, minHeight: 260 }}>{body}</div>
    </div>
  );
}

function ChartMessage({ text }: { text: string }) {
  return (
    <div
      style={{
        flex: 1,
        minHeight: 200,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: "13px",
        color: "var(--color-ink-faint)",
        textAlign: "center",
        padding: "var(--space-6)",
      }}
    >
      {text}
    </div>
  );
}
