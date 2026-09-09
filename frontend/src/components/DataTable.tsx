import { EmptyState } from "./States";

function isNumeric(v: unknown) {
  return typeof v === "number" || (typeof v === "string" && v !== "" && !Number.isNaN(Number(v)));
}

function fmt(v: unknown) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return v.toLocaleString(undefined, { maximumFractionDigits: 4 });
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export function DataTable({
  columns,
  rows,
  maxRows = 200,
}: {
  columns: string[];
  rows: Record<string, unknown>[];
  maxRows?: number;
}) {
  if (!rows || rows.length === 0) return <EmptyState message="Query returned no rows." />;
  const cols = columns?.length ? columns : Object.keys(rows[0]);
  const shown = rows.slice(0, maxRows);
  const numericCols = new Set(
    cols.filter((c) => shown.every((r) => r[c] === null || isNumeric(r[c]))),
  );

  return (
    <>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c} className={numericCols.has(c) ? "num" : ""}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((r, i) => (
              <tr key={i}>
                {cols.map((c) => (
                  <td key={c} className={numericCols.has(c) ? "num" : ""}>
                    {fmt(r[c])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > maxRows && (
        <p className="muted" style={{ marginTop: 8 }}>
          Showing first {maxRows} of {rows.length.toLocaleString()} rows.
        </p>
      )}
    </>
  );
}
