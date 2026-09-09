export function StatTile({
  label,
  value,
  hint,
  delta,
}: {
  label: string;
  value: string | number | null | undefined;
  hint?: string;
  delta?: number | null;
}) {
  const shown =
    value === null || value === undefined || value === ""
      ? "—"
      : typeof value === "number"
        ? value.toLocaleString()
        : value;
  return (
    <div className="card stat">
      <div className="label">{label}</div>
      <div className="value">{shown}</div>
      {delta !== undefined && delta !== null && !Number.isNaN(delta) && (
        <div className={`hint delta ${delta >= 0 ? "up" : "down"}`}>
          {delta >= 0 ? "▲" : "▼"} {Math.abs(delta).toFixed(1)}% vs prior 30d
        </div>
      )}
      {hint && <div className="hint">{hint}</div>}
    </div>
  );
}
