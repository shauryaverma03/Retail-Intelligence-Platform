import { useCountUp } from "../hooks/useCountUp";

interface Props {
  label: string;
  value: string | number | null | undefined;
  hint?: string;
  delta?: number | null;
  accent?: string;
}

/** Parse "₹41,184" / "35.7%" / "1,234" into prefix + number + suffix + decimals. */
function parseValue(v: string) {
  const m = v.match(/^(\D*?)(-?[\d,]*\.?\d+)(.*)$/);
  if (!m) return null;
  const num = Number(m[2].replace(/,/g, ""));
  if (Number.isNaN(num)) return null;
  const decimals = m[2].includes(".") ? m[2].split(".")[1].length : 0;
  return { prefix: m[1], num, suffix: m[3], decimals };
}

export function StatTile({ label, value, hint, delta, accent }: Props) {
  const parsed =
    typeof value === "number"
      ? { prefix: "", num: value, suffix: "", decimals: value % 1 === 0 ? 0 : 2 }
      : typeof value === "string"
        ? parseValue(value)
        : null;

  const animated = useCountUp(parsed?.num);
  const shown =
    value === null || value === undefined || value === ""
      ? "—"
      : parsed
        ? `${parsed.prefix}${animated.toLocaleString(undefined, {
            minimumFractionDigits: parsed.decimals,
            maximumFractionDigits: parsed.decimals,
          })}${parsed.suffix}`
        : String(value);

  return (
    <div
      className="card stat"
      style={accent ? ({ "--accent": accent } as React.CSSProperties) : undefined}
    >
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
