import { useState } from "react";

const KEYWORDS =
  /\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|HAVING|LIMIT|OFFSET|JOIN|LEFT|RIGHT|INNER|OUTER|FULL|CROSS|LATERAL|ON|USING|AS|WITH|AND|OR|NOT|IN|IS|NULL|CASE|WHEN|THEN|ELSE|END|OVER|PARTITION BY|FILTER|DISTINCT|UNION|ALL|BETWEEN|INTERVAL|DESC|ASC|NULLS|FIRST|LAST|WITHIN GROUP)\b/gi;
const FUNCS =
  /\b(count|sum|avg|min|max|round|coalesce|nullif|date_trunc|to_char|generate_series|percentile_cont|ntile|lag|lead|row_number|rank|dense_rank|array_agg|extract|age|make_interval|greatest|least|now)\b/gi;

function highlight(sql: string): string {
  let out = sql
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  out = out.replace(/(--[^\n]*)/g, '<span class="com">$1</span>');
  out = out.replace(/('(?:[^']|'')*')/g, '<span class="str">$1</span>');
  out = out.replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="num">$1</span>');
  out = out.replace(FUNCS, '<span class="fn">$1</span>');
  out = out.replace(KEYWORDS, '<span class="kw">$1</span>');
  return out;
}

export function SqlBlock({ sql }: { sql: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  };
  return (
    <div style={{ position: "relative" }}>
      <button
        onClick={copy}
        style={{ position: "absolute", top: 8, right: 8, padding: "4px 10px", fontSize: 12 }}
      >
        {copied ? "Copied" : "Copy"}
      </button>
      <pre className="sql" dangerouslySetInnerHTML={{ __html: highlight(sql.trim()) }} />
    </div>
  );
}
