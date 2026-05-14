"use client";
import VegaChart from "./VegaChart";

interface RightPanelProps {
  title: string;
  vegaSpec: string | null;
  rows: Record<string, unknown>[];
  sql: string;
  sqlVisible: boolean;
  onToggleSql: () => void;
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

export default function RightPanel({
  title,
  vegaSpec,
  rows,
  sql,
  sqlVisible,
  onToggleSql,
}: RightPanelProps) {
  const rowColumns = rows.length > 0 ? Object.keys(rows[0]).slice(0, 6) : [];

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

      {/* Chart area */}
      <div
        style={{
          flex: 1,
          display: "grid",
          gridTemplateRows: rows.length > 0 ? "minmax(0, 1fr) 190px" : "1fr",
          padding: "24px",
          gap: "16px",
          overflow: "hidden",
        }}
      >
        {vegaSpec && rows.length > 0 ? (
          <div
            style={{
              width: "100%",
              height: "100%",
              minHeight: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <VegaChart spec={vegaSpec} />
          </div>
        ) : vegaSpec && rows.length === 0 ? (
          <div
            style={{
              alignSelf: "center",
              justifySelf: "center",
              color: "var(--text-secondary)",
              fontSize: "14px",
              textAlign: "center",
              border: "1px solid var(--border-subtle)",
              borderRadius: "8px",
              padding: "18px 22px",
              background: "var(--bg-panel)",
            }}
          >
            No rows returned for this question.
          </div>
        ) : (
          <p
            style={{
              color: "var(--text-muted)",
              fontSize: "14px",
              textAlign: "center",
            }}
          >
            Ask a question to see results
          </p>
        )}

        {rows.length > 0 && (
          <div
            style={{
              border: "1px solid var(--border-subtle)",
              borderRadius: "8px",
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
            <div style={{ overflow: "auto", maxHeight: "150px" }}>
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
