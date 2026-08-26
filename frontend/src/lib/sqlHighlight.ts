/**
 * Lightweight SQL syntax highlighting for the read-only SQL panel.
 * Produces HTML using the .kw/.fn/.id/.lit classes defined in globals.css.
 * Input is escaped first, so this is safe for dangerouslySetInnerHTML.
 */

const KEYWORDS =
  /\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|HAVING|JOIN|LEFT|RIGHT|INNER|OUTER|ON|AS|AND|OR|NOT|IN|LIKE|LIMIT|OFFSET|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|WITH|UNION|DISTINCT|CASE|WHEN|THEN|ELSE|END|NULL|IS|BY|ASC|DESC)\b/gi;
const FUNCTIONS =
  /\b(count|sum|avg|min|max|coalesce|nullif|cast|extract|date_trunc|now|current_date|round|floor|ceil|abs|length|lower|upper|trim|substr|replace)\b/gi;
const IDENTIFIERS = /(`[^`]+`|"[^"]+")/g;
const STRINGS = /('(?:[^']|'')*')/g;
const NUMBERS = /\b(\d+(?:\.\d+)?)\b/g;

function escapeHtml(sql: string): string {
  return sql
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function highlightSQL(sql: string): string {
  return escapeHtml(sql)
    .replace(IDENTIFIERS, '<span class="id">$1</span>')
    .replace(STRINGS, '<span class="lit">$1</span>')
    .replace(NUMBERS, '<span class="lit">$1</span>')
    .replace(FUNCTIONS, '<span class="fn">$&</span>')
    .replace(KEYWORDS, '<span class="kw">$&</span>');
}
