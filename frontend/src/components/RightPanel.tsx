"use client";
import dynamic from "next/dynamic";

// vega-embed must never be evaluated during SSR — its module-level code
// (a Set-based expression guard) breaks the RSC serialization boundary.
const VegaChart = dynamic(() => import("./VegaChart"), { ssr: false });

interface Metric {
  label: string;
  value: number;
  unit: string;
}

interface Answer {
  text: string;
  metrics: Metric[];
  sub_queries: { id: string; question: string }[];
}

interface RightPanelProps {
  title: string;
  vegaSpec: string | null;
  rows: Record<string, unknown>[];
  sql: string;
  sqlVisible: boolean;
  onToggleSql: () => void;
  queryType: string | null;
  answer: Answer | null;
  isLoading: boolean;
}

function highlightSQL(sql: string): string {
  const keywords = /\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|HAVING|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AS|AND|OR|NOT|IN|LIKE|LIMIT|OFFSET|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|WITH|UNION|DISTINCT|CASE|WHEN|THEN|ELSE|END|NULL|IS|BY|ASC|DESC)\b/gi;
  const functions = /\b(count|sum|avg|min|max|coalesce|nullif|cast|extract|date_trunc|now|current_date|round|floor|ceil|abs|length|lower|upper|trim|substr|replace)\b/gi;
  const identifiers = /(`[^`]+`|"[^"]+")/g;
  const strings = /('(?:[^']|'')*')/g;
  const numbers = /\b(\d+(?:\.\d+)?)\b/g;

  return sql
    .replace(identifiers, '<span class="id">$1</span>')
    .replace(strings, '<span class="lit">$1</span>')
    .replace(numbers, '<span class="lit">$1</span>')
    .replace(functions, '<span class="fn">$&</span>')
    .replace(keywords, '<span class="kw">$&</span>');
}

function formatValue(value: number): string {
  if (Math.abs(value) >= 1000) {
    return value.toLocaleString("en-US", { maximumFractionDigits: 2 });
  }
  return String(Number(value.toFixed(2)));
}

function titleCase(label: string): string {
  return label.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const PANEL: React.CSSProperties = {
  border: "1px solid var(--color-border-subtle)",
  borderRadius: "var(--radius-lg)",
  background: "var(--color-paper-2)",
};

export default function RightPanel({
  title,
  vegaSpec,
  rows,
  sql,
  sqlVisible,
  onToggleSql,
  queryType,
  answer,
  isLoading,
}: RightPanelProps) {
  const rowColumns = rows.length > 0 ? Object.keys(rows[0]).slice(0, 6) : [];
  const isKpi = queryType === "kpi";
  const hasResult = Boolean(vegaSpec) || rows.length > 0;

  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        background: "var(--color-paper)",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "var(--space-4) var(--space-6)",
          borderBottom: "1px solid var(--color-border-subtle)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontSize: "14px",
            fontWeight: 600,
            letterSpacing: "-0.01em",
            color: title ? "var(--color-ink)" : "var(--color-ink-faint)",
          }}
        >
          {title || "Results"}
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
          {queryType && (
            <span
              style={{
                fontSize: "10.5px",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: "var(--color-accent)",
                border: "1px solid var(--color-accent-dim)",
                borderRadius: "var(--radius-pill)",
                padding: "3px 10px",
                fontFamily: "var(--font-mono)",
              }}
            >
              {queryType}
            </span>
          )}
          {rows.length > 0 && (
            <span
              style={{
                color: "var(--color-ink-dim)",
                fontSize: "12px",
                fontFamily: "var(--font-mono)",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {rows.length} rows
            </span>
          )}
          {sql && (
            <button
              onClick={onToggleSql}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                color: "var(--color-accent)",
                fontSize: "12.5px",
                fontWeight: 500,
                padding: "4px 8px",
                borderRadius: "var(--radius-sm)",
                fontFamily: "var(--font-mono)",
              }}
            >
              SQL {sqlVisible ? "▴" : "▾"}
            </button>
          )}
        </div>
      </div>

      <div
        className="stagger"
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          overflow: "auto",
          padding: "var(--space-6)",
          gap: "var(--space-5)",
        }}
      >
        {/* Loading skeletons */}
        {isLoading && (
          <>
            <div className="skeleton" style={{ height: "72px", width: "100%" }} />
            <div className="skeleton" style={{ height: 220, width: "100%" }} />
            <div className="skeleton" style={{ height: 120, width: "100%" }} />
          </>
        )}

        {/* Grounded answer banner */}
        {!isLoading && answer && (
          <div
            style={{
              border: "1px solid var(--color-accent-dim)",
              borderRadius: "var(--radius-lg)",
              background: "var(--color-paper-2)",
              padding: "var(--space-5) var(--space-6)",
              position: "relative",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "3px",
                height: "100%",
                background: "var(--color-accent)",
              }}
            />
            <div
              style={{
                fontSize: "10.5px",
                fontWeight: 600,
                color: "var(--color-accent)",
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                marginBottom: "var(--space-3)",
                fontFamily: "var(--font-mono)",
              }}
            >
              Grounded answer
            </div>

            {answer.metrics.length > 0 ? (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                  gap: "var(--space-3)",
                }}
              >
                {answer.metrics.map((m) => (
                  <div
                    key={m.label}
                    style={{
                      display: "flex",
                      alignItems: "baseline",
                      justifyContent: "space-between",
                      gap: "var(--space-3)",
                      padding: "10px 14px",
                      borderRadius: "var(--radius-md)",
                      background: "var(--color-paper-3)",
                      border: "1px solid var(--color-border-subtle)",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "12px",
                        color: "var(--color-ink-dim)",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {titleCase(m.label)}
                    </span>
                    <span
                      style={{
                        fontSize: "16px",
                        fontWeight: 700,
                        color: "var(--color-ink)",
                        fontFamily: "var(--font-mono)",
                        fontVariantNumeric: "tabular-nums",
                        letterSpacing: "-0.02em",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {formatValue(m.value)}
                      {m.unit && (
                        <span
                          style={{
                            fontSize: "11px",
                            color: "var(--color-ink-faint)",
                            marginLeft: "3px",
                            fontWeight: 500,
                          }}
                        >
                          {m.unit}
                        </span>
                      )}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div
                style={{
                  fontSize: "15px",
                  fontWeight: 600,
                  color: "var(--color-ink)",
                  lineHeight: 1.5,
                  letterSpacing: "-0.01em",
                }}
              >
                {answer.text}
              </div>
            )}

            {answer.sub_queries.length > 0 && (
              <div
                style={{
                  marginTop: "var(--space-3)",
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "6px",
                }}
              >
                {answer.sub_queries.map((sq) => (
                  <span
                    key={sq.id}
                    style={{
                      fontSize: "11px",
                      color: "var(--color-ink-dim)",
                      border: "1px solid var(--color-border)",
                      borderRadius: "var(--radius-pill)",
                      padding: "3px 10px",
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    {sq.question}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* KPI stat strip — big grounded numbers */}
        {!isLoading && isKpi && answer && answer.metrics.length > 0 && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: `repeat(${Math.min(answer.metrics.length, 4)}, minmax(0, 1fr))`,
              gap: "var(--space-4)",
            }}
          >
            {answer.metrics.slice(0, 4).map((m, i) => (
              <div
                key={m.label}
                style={{
                  border: "1px solid var(--color-border-subtle)",
                  borderRadius: "var(--radius-lg)",
                  background: "var(--color-paper-2)",
                  padding: "var(--space-5) var(--space-6)",
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
                    marginBottom: "var(--space-2)",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  {titleCase(m.label)}
                </div>
                <div
                  style={{
                    fontSize: i === 0 ? "34px" : "28px",
                    fontWeight: 700,
                    color: "var(--color-ink)",
                    letterSpacing: "-0.03em",
                    fontFamily: "var(--font-mono)",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {formatValue(m.value)}
                  {m.unit && (
                    <span
                      style={{
                        fontSize: "13px",
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
        )}

        {/* Chart area */}
        {!isLoading && !isKpi && (
          <div
            style={{
              flex: 1,
              minHeight: "300px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              border: "1px solid var(--color-border-subtle)",
              borderRadius: "var(--radius-xl)",
              background: "var(--color-paper-2)",
              padding: "var(--space-5)",
            }}
          >
            {vegaSpec ? (
              <div style={{ width: "100%", height: "100%", minHeight: 0 }}>
                <VegaChart spec={vegaSpec} />
              </div>
            ) : hasResult ? (
              <div
                style={{
                  color: "var(--color-ink-dim)",
                  fontSize: "14px",
                  textAlign: "center",
                }}
              >
                No rows returned for this question.
              </div>
            ) : (
              <div style={{ textAlign: "center", maxWidth: "320px" }}>
                <div
                  style={{
                    fontSize: "13px",
                    color: "var(--color-ink-faint)",
                    lineHeight: 1.6,
                  }}
                >
                  Ask a question to see results. Charts adapt to your data — trends,
                  breakdowns, comparisons, and KPIs.
                </div>
              </div>
            )}
          </div>
        )}

        {/* Result rows table */}
        {!isLoading && rows.length > 0 && (
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
                    {rowColumns.map((column) => (
                      <th
                        key={column}
                        style={{
                          padding: "9px 14px",
                          color: "var(--color-ink-faint)",
                          textAlign: "left",
                          borderBottom: "1px solid var(--color-border-subtle)",
                          whiteSpace: "nowrap",
                          fontWeight: 500,
                          fontFamily: "var(--font-mono)",
                          fontSize: "11px",
                        }}
                      >
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, index) => (
                    <tr key={index}>
                      {rowColumns.map((column) => (
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
        )}
      </div>

      {/* SQL panel */}
      {sqlVisible && sql && (
        <div
          style={{
            flexShrink: 0,
            borderTop: "1px solid var(--color-border-subtle)",
            background: "var(--color-paper-2)",
            padding: "14px var(--space-6)",
            maxHeight: "180px",
            overflowY: "auto",
            fontFamily: "var(--font-mono)",
            fontSize: "12px",
            lineHeight: "1.8",
            color: "var(--color-ink-dim)",
            whiteSpace: "pre-wrap",
          }}
          dangerouslySetInnerHTML={{ __html: highlightSQL(sql) }}
        />
      )}
    </div>
  );
}