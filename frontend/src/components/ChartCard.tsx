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

const COLORS = ["#2f6bff", "#1a8f5b", "#b7791f", "#d1394b", "#7c5cff", "#0e9db8"];

type Series = { key: string; label?: string; color?: string };

export function ChartCard({
  title,
  sub,
  right,
  kind = "line",
  data,
  xKey,
  series,
  height = 260,
}: {
  title: ReactNode;
  sub?: ReactNode;
  right?: ReactNode;
  kind?: "line" | "bar" | "area";
  data: Record<string, unknown>[];
  xKey: string;
  series: Series[];
  height?: number;
}) {
  return (
    <Card title={title} sub={sub} right={right}>
      {!data || data.length === 0 ? (
        <EmptyState />
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          {kind === "bar" ? (
            <BarChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef0f4" />
              <XAxis dataKey={xKey} tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} width={64} />
              <Tooltip />
              {series.length > 1 && <Legend />}
              {series.map((s, i) => (
                <Bar
                  key={s.key}
                  dataKey={s.key}
                  name={s.label ?? s.key}
                  fill={s.color ?? COLORS[i % COLORS.length]}
                  radius={[3, 3, 0, 0]}
                />
              ))}
            </BarChart>
          ) : kind === "area" ? (
            <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef0f4" />
              <XAxis dataKey={xKey} tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} width={64} />
              <Tooltip />
              {series.length > 1 && <Legend />}
              {series.map((s, i) => (
                <Area
                  key={s.key}
                  dataKey={s.key}
                  name={s.label ?? s.key}
                  stroke={s.color ?? COLORS[i % COLORS.length]}
                  fill={s.color ?? COLORS[i % COLORS.length]}
                  fillOpacity={0.12}
                />
              ))}
            </AreaChart>
          ) : (
            <LineChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef0f4" />
              <XAxis dataKey={xKey} tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} width={64} />
              <Tooltip />
              {series.length > 1 && <Legend />}
              {series.map((s, i) => (
                <Line
                  key={s.key}
                  type="monotone"
                  dataKey={s.key}
                  name={s.label ?? s.key}
                  stroke={s.color ?? COLORS[i % COLORS.length]}
                  strokeWidth={2}
                  dot={false}
                />
              ))}
            </LineChart>
          )}
        </ResponsiveContainer>
      )}
    </Card>
  );
}
