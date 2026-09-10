import { Card } from "../components/Card";
import { ChartCard } from "../components/ChartCard";
import { DataTable } from "../components/DataTable";
import { PageHeader } from "../components/Layout";
import { ErrorState, SkeletonDashboard } from "../components/States";
import { StatTile } from "../components/StatTile";
import { api } from "../api";
import { useApi } from "../hooks/useApi";

const money = (v: unknown) =>
  v === null || v === undefined ? "—" : `₹${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const pct = (v: unknown) => (v === null || v === undefined ? "—" : `${Number(v).toFixed(1)}%`);

export function Dashboard() {
  const { data, loading, error, reload } = useApi(() => api.dashboard(), []);

  if (loading) return <SkeletonDashboard />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return <ErrorState message="No dashboard data." onRetry={reload} />;

  const k = data.kpis ?? {};
  const cc = data.campaign_conversion ?? {};
  const ar = data.at_risk ?? {};
  const trend = (data.revenue_trend ?? []).map((r: any) => ({
    ...r,
    net_revenue: Number(r.net_revenue),
  }));
  const segs = data.segment_performance ?? [];

  return (
    <>
      <PageHeader
        title="Business Dashboard"
        right={<button onClick={() => reload()}>Refresh</button>}
      >
        Every figure is computed live via SQL. Built in {data.build_ms} ms
        {data.cached ? " (cached)" : ""}.
      </PageHeader>

      <div className="grid cols-4 stagger">
        <StatTile accent="#2f6bff" label="Total customers" value={k.total_customers} hint={`${k.buyers?.toLocaleString()} have purchased`} />
        <StatTile accent="#0ea5a5" label="Avg order value" value={money(k.avg_order_value)} hint={`${k.completed_orders?.toLocaleString()} completed orders`} />
        <StatTile accent="#7c5cff" label="Net revenue (30d)" value={money(k.net_revenue_30d)} delta={k.revenue_mom_growth_pct} />
        <StatTile accent="#12885a" label="Repeat purchase rate" value={pct(k.repeat_purchase_rate_pct)} hint={`${k.repeat_buyers?.toLocaleString()} of ${k.buyers?.toLocaleString()} buyers`} />
        <StatTile accent="#12885a" label="90-day retention" value={pct(k.retention_rate_pct)} hint={`${k.retained?.toLocaleString()} of ${k.prior_window_buyers?.toLocaleString()} prior-window buyers`} />
        <StatTile accent="#2f6bff" label="Active customers (90d)" value={k.active_customers_90d} />
        <StatTile accent="#d98a0b" label="Campaign conversion" value={pct(cc.conversion_rate_pct)} hint={`${cc.conversions?.toLocaleString()} converts / ${cc.sent?.toLocaleString()} sent`} />
        <StatTile accent="#d1394b" label="Revenue at risk" value={money(ar.lifetime_net_at_risk)} hint={`${ar.at_risk_customers?.toLocaleString()} lapsing high-value customers`} />
      </div>

      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <ChartCard
          title="Net revenue trend"
          sub="last 12 months, completed orders"
          kind="area"
          data={trend}
          xKey="month"
          series={[{ key: "net_revenue", label: "Net revenue" }]}
          yPrefix="₹"
          yCompact
        />
        <ChartCard
          title="Orders per month"
          sub="last 12 months"
          kind="bar"
          data={trend}
          xKey="month"
          series={[{ key: "orders", label: "Orders", color: "#0ea5a5" }]}
          yCompact
        />
      </div>

      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <ChartCard
          title="Customer segment value"
          sub="RFM segment lifetime net"
          kind="bar"
          data={segs.map((s: any) => ({ ...s, segment_lifetime_net: Number(s.segment_lifetime_net) }))}
          xKey="segment"
          series={[{ key: "segment_lifetime_net", label: "Lifetime net", color: "#7c5cff" }]}
          height={280}
          yPrefix="₹"
          yCompact
        />
        <Card title="Segment performance" sub="RFM">
          <DataTable
            columns={["segment", "customers", "avg_orders", "avg_lifetime_net", "segment_lifetime_net"]}
            rows={segs}
          />
        </Card>
      </div>

      <Card title="Data freshness">
        <dl className="kv">
          <dt>Latest order</dt>
          <dd className="mono">{String(data.data_freshness?.latest_order ?? "—")}</dd>
          <dt>Order lag</dt>
          <dd className="mono">{String(data.data_freshness?.order_lag ?? "—")}</dd>
          <dt>Last successful ETL</dt>
          <dd className="mono">{String(data.data_freshness?.last_successful_etl ?? "—")}</dd>
        </dl>
        <p className="muted" style={{ marginTop: 10 }}>{data.note}</p>
      </Card>
    </>
  );
}
