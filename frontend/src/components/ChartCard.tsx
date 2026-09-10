import type { ReactNode } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "./Card";
import { EmptyState } from "./States";

// fixed categorical order — never cycled (see dataviz)
const COLORS = ["#2f6bff", "#0ea5a5", "#7c5cff", "#d98a0b", "#12885a", "#d1394b"];
const AXIS = "#8b96ad";
const GRID = "#eaeef4";

type Series = { key: string; label?: string; color?: string };

const tooltipStyle = {
  borderRadius: 10,
  border: "1px solid #e4e8ef",
  boxShadow: "0 8px 24px -8px rgba(18,26,45,.22)",
  fontSize: 12,
};

const compact = (v: number) => {
  const a = Math.abs(v);
  if (a >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (a >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `${(v / 1e3).toFixed(0)}k`;
  return `${v}`;
};

export function ChartCard({
  title,
  sub,
  right,
  kind = "line",
  data,
  xKey,
  series,
  height = 260,
  yPrefix = "",
  yCompact = false,
}: {
  title: ReactNode;
  sub?: ReactNode;
  right?: ReactNode;
  kind?: "line" | "bar" | "area";
  data: Record<string, unknown>[];
  xKey: string;
  series: Series[];
  height?: number;
  yPrefix?: string;
  yCompact?: boolean;
}) {
  const colorAt = (s: Series, i: number) => s.color ?? COLORS[i % COLORS.length];
  const gid = (k: string) => `grad-${String(title).replace(/\W/g, "")}-${k}`;
  const yFmt = yCompact
    ? (v: number) => `${yPrefix}${compact(v)}`
    : (v: number) => `${yPrefix}${v.toLocaleString()}`;

  return (
    <Card title={title} sub={sub} right={right}>
      {!data || data.length === 0 ? (
        <EmptyState />
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          {kind === "bar" ? (
            <BarChart data={data} margin={{ top: 6, right: 10, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
              <XAxis dataKey={xKey} tick={{ fontSize: 11, fill: AXIS }} tickLine={false} axisLine={{ stroke: GRID }} />
              <YAxis tick={{ fontSize: 11, fill: AXIS }} width={58} tickLine={false} axisLine={false} tickFormatter={yFmt} />
              <Tooltip cursor={{ fill: "rgba(47,107,255,.06)" }} contentStyle={tooltipStyle} />
              {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
              {series.map((s, i) => (
                <Bar
                  key={s.key}
                  dataKey={s.key}
                  name={s.label ?? s.key}
                  fill={colorAt(s, i)}
                  radius={[5, 5, 0, 0]}
                  maxBarSize={46}
                  isAnimationActive={false}
                />
              ))}
            </BarChart>
          ) : kind === "area" ? (
            <AreaChart data={data} margin={{ top: 6, right: 10, bottom: 4, left: 0 }}>
              <defs>
                {series.map((s, i) => (
                  <linearGradient key={s.key} id={gid(s.key)} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={colorAt(s, i)} stopOpacity={0.28} />
                    <stop offset="100%" stopColor={colorAt(s, i)} stopOpacity={0.02} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
              <XAxis dataKey={xKey} tick={{ fontSize: 11, fill: AXIS }} tickLine={false} axisLine={{ stroke: GRID }} />
              <YAxis tick={{ fontSize: 11, fill: AXIS }} width={58} tickLine={false} axisLine={false} tickFormatter={yFmt} />
              <Tooltip contentStyle={tooltipStyle} />
              {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
              {series.map((s, i) => (
                <Area
                  key={s.key}
                  type="monotone"
                  dataKey={s.key}
                  name={s.label ?? s.key}
                  stroke={colorAt(s, i)}
                  strokeWidth={2}
                  fill={`url(#${gid(s.key)})`}
                  dot={false}
                  activeDot={{ r: 4, strokeWidth: 2 }}
                  isAnimationActive={false}
                />
              ))}
            </AreaChart>
          ) : (
            <LineChart data={data} margin={{ top: 6, right: 10, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
              <XAxis dataKey={xKey} tick={{ fontSize: 11, fill: AXIS }} tickLine={false} axisLine={{ stroke: GRID }} />
              <YAxis tick={{ fontSize: 11, fill: AXIS }} width={58} tickLine={false} axisLine={false} tickFormatter={yFmt} />
              <Tooltip contentStyle={tooltipStyle} />
              {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
              {series.map((s, i) => (
                <Line
                  key={s.key}
                  type="monotone"
                  dataKey={s.key}
                  name={s.label ?? s.key}
                  stroke={colorAt(s, i)}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, strokeWidth: 2 }}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          )}
        </ResponsiveContainer>
      )}
    </Card>
  );
}
