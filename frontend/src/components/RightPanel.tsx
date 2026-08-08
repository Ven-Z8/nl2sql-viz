"use client";
import VegaChart from "./VegaChart";

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
}

function highlightSQL(sql: string): string {
  // COUNT/SUM/AVG/MIN/MAX omitted from keywords — covered by functions regex
  const keywords = /\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|HAVING|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AS|AND|OR|NOT|IN|LIKE|LIMIT|OFFSET|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|WITH|UNION|DISTINCT|CASE|WHEN|THEN|ELSE|END|NULL|IS|BY|ASC|DESC)\b/gi;
  const functions = /\b(count|sum|avg|min|max|coalesce|nullif|cast|extract|date_trunc|now|current_date|round|floor|ceil|abs|length|lower|upper|trim|substr|replace)\b/gi;
  // Identifiers and strings are replaced first as opaque tokens to prevent
  // subsequent keyword/function passes from matching inside their content.
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

export default function RightPanel({
  title,
  vegaSpec,
  rows,
  sql,
  sqlVisible,
  onToggleSql,
  queryType,
  answer,
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
        background: "var(--bg)",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "14px 24px",
          borderBottom: "1px solid var(--border-subtle)",
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
            color: title ? "var(--text-primary)" : "var(--text-muted)",
          }}
        >
          {title || "Results"}
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {queryType && (
            <span
              style={{
                fontSize: "11px",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                color: "var(--accent)",
                border: "1px solid var(--accent-dim)",
                borderRadius: "999px",
                padding: "2px 10px",
              }}
            >
              {queryType}
            </span>
          )}
          {rows.length > 0 && (
            <span style={{ color: "var(--text-secondary)", fontSize: "12px" }}>
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
                color: "var(--accent)",
                fontSize: "13px",
                fontWeight: 500,
                padding: "4px 8px",
                borderRadius: "4px",
              }}
            >
              SQL {sqlVisible ? "▴" : "▾"}
            </button>
          )}
        </div>
      </div>

      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          overflow: "auto",
          padding: "24px",
          gap: "16px",
        }}
      >
        {/* Grounded answer banner */}
        {answer && (
          <div
            style={{
              border: "1px solid var(--border-subtle)",
              borderRadius: "10px",
              background: "var(--bg-panel)",
              padding: "14px 18px",
            }}
          >
            <div
              style={{
                fontSize: "11px",
                fontWeight: 600,
                color: "var(--text-muted)",
                textTransform: "uppercase",
                letterSpacing: "0.06em",
                marginBottom: "6px",
              }}
            >
              Grounded answer
            </div>
            <div
              style={{
                fontSize: "15px",
                fontWeight: 600,
                color: "var(--text-primary)",
                lineHeight: 1.5,
              }}
            >
              {answer.text}
            </div>
            {answer.sub_queries.length > 0 && (
              <div
                style={{
                  marginTop: "8px",
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
                      color: "var(--text-secondary)",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "999px",
                      padding: "2px 8px",
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
        {isKpi && answer && answer.metrics.length > 0 && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: `repeat(${Math.min(answer.metrics.length, 4)}, minmax(0, 1fr))`,
              gap: "12px",
            }}
          >
            {answer.metrics.slice(0, 4).map((m) => (
              <div
                key={m.label}
                style={{
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "10px",
                  background: "var(--bg-panel)",
                  padding: "18px 20px",
                }}
              >
                <div
                  style={{
                    fontSize: "11px",
                    fontWeight: 600,
                    color: "var(--text-muted)",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    marginBottom: "8px",
                  }}
                >
                  {titleCase(m.label)}
                </div>
                <div
                  style={{
                    fontSize: "28px",
                    fontWeight: 700,
                    color: "var(--text-primary)",
                    letterSpacing: "-0.02em",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {formatValue(m.value)}
                  {m.unit && (
                    <span style={{ fontSize: "14px", color: "var(--text-secondary)", marginLeft: "4px" }}>
                      {m.unit}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Chart area */}
        {!isKpi && (
          <div
            style={{
              flex: 1,
              minHeight: "280px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              border: "1px solid var(--border-subtle)",
              borderRadius: "10px",
              background: "var(--bg-panel)",
              padding: "16px",
            }}
          >
            {vegaSpec ? (
              <div style={{ width: "100%", height: "100%", minHeight: 0 }}>
                <VegaChart spec={vegaSpec} />
              </div>
            ) : hasResult ? (
              <div
                style={{
                  color: "var(--text-secondary)",
                  fontSize: "14px",
                  textAlign: "center",
                }}
              >
                No rows returned for this question.
              </div>
            ) : (
              <p style={{ color: "var(--text-muted)", fontSize: "14px", textAlign: "center" }}>
                Ask a question to see results
              </p>
            )}
          </div>
        )}

        {/* Result rows table */}
        {rows.length > 0 && (
          <div
            style={{
              border: "1px solid var(--border-subtle)",
              borderRadius: "10px",
              background: "var(--bg-panel)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                padding: "8px 10px",
                borderBottom: "1px solid var(--border-subtle)",
                color: "var(--text-secondary)",
                fontSize: "11px",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
              }}
            >
              Result Rows
            </div>
            <div style={{ overflow: "auto", maxHeight: "220px" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
                <thead>
                  <tr>
                    {rowColumns.map((column) => (
                      <th
                        key={column}
                        style={{
                          padding: "8px 10px",
                          color: "var(--text-muted)",
                          textAlign: "left",
                          borderBottom: "1px solid var(--border-subtle)",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(0, 8).map((row, index) => (
                    <tr key={index}>
                      {rowColumns.map((column) => (
                        <td
                          key={column}
                          style={{
                            padding: "7px 10px",
                            color: "var(--text-secondary)",
                            borderBottom: "1px solid var(--border-subtle)",
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
            borderTop: "1px solid var(--border-subtle)",
            background: "var(--bg-panel)",
            padding: "12px 24px",
            maxHeight: "160px",
            overflowY: "auto",
            fontFamily: "'SF Mono', 'Fira Code', Menlo, Consolas, monospace",
            fontSize: "12px",
            lineHeight: "1.7",
            color: "var(--text-secondary)",
            whiteSpace: "pre-wrap",
          }}
          dangerouslySetInnerHTML={{ __html: highlightSQL(sql) }}
        />
      )}
    </div>
  );
}