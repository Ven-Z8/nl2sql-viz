"use client";
import VegaChart from "./VegaChart";

interface RightPanelProps {
  title: string;
  vegaSpec: string | null;
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
  sql,
  sqlVisible,
  onToggleSql,
}: RightPanelProps) {
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

      {/* Chart area */}
      <div
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "24px",
          overflow: "hidden",
        }}
      >
        {vegaSpec ? (
          <div style={{ width: "100%", maxWidth: "600px" }}>
            <VegaChart spec={vegaSpec} />
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
