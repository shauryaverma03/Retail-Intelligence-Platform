import { useState } from "react";
import { Card } from "../components/Card";
import { ChartCard } from "../components/ChartCard";
import { DataTable } from "../components/DataTable";
import { PageHeader } from "../components/Layout";
import { SqlBlock } from "../components/SqlBlock";
import { ErrorState, Loading } from "../components/States";
import { api } from "../api";
import { useApi } from "../hooks/useApi";

const TABS: { key: string; label: string }[] = [
  { key: "rfm", label: "RFM segments" },
  { key: "cohort", label: "Cohort retention" },
  { key: "at_risk", label: "At-risk customers" },
  { key: "churn", label: "Churn / inactivity" },
  { key: "repeat_by_channel", label: "Repeat rate by channel" },
  { key: "campaign_by_segment", label: "Campaign by segment" },
];

export function CustomerAnalytics() {
  const [tab, setTab] = useState("rfm");
  const { data, loading, error, reload } = useApi(() => api.customerAnalysis(tab), [tab]);

  return (
    <>
      <PageHeader title="Customer Analytics">
        RFM segmentation, cohort retention, churn/inactivity buckets, high-value
        identification and campaign performance by segment — each backed by a
        window-function SQL query you can inspect.
      </PageHeader>

      <div className="row" style={{ marginBottom: 16 }}>
        {TABS.map((t) => (
          <button
            key={t.key}
            className={tab === t.key ? "primary" : ""}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : !data?.ok ? (
        <ErrorState message={data?.error ?? "Failed to load analysis."} />
      ) : (
        <AnalysisView data={data} tab={tab} />
      )}
    </>
  );
}

function AnalysisView({ data, tab }: { data: any; tab: string }) {
  const rows: any[] = data.rows ?? [];
  const num = (v: any) => Number(v);

  const chart = (() => {
    if (tab === "rfm")
      return (
        <ChartCard
          title="Lifetime net by segment"
          kind="bar"
          data={rows.map((r) => ({ ...r, segment_lifetime_net: num(r.segment_lifetime_net) }))}
          xKey="segment"
          series={[{ key: "segment_lifetime_net", label: "Lifetime net", color: "#7c5cff" }]}
          height={280}
          yPrefix="₹"
          yCompact
        />
      );
    if (tab === "cohort")
      return (
        <ChartCard
          title="Retention by month offset"
          kind="line"
          data={rows.map((r) => ({
            cohort: r.cohort,
            m1: num(r.m1_pct),
            m3: num(r.m3_pct),
            m6: num(r.m6_pct),
            m12: num(r.m12_pct),
          }))}
          xKey="cohort"
          series={[
            { key: "m1", label: "M1 %" },
            { key: "m3", label: "M3 %" },
            { key: "m6", label: "M6 %" },
            { key: "m12", label: "M12 %" },
          ]}
        />
      );
    if (tab === "churn")
      return (
        <ChartCard
          title="Customers by recency bucket"
          kind="bar"
          data={rows.map((r) => ({ ...r, customers: num(r.customers) }))}
          xKey="recency_bucket"
          series={[{ key: "customers", label: "Customers" }]}
        />
      );
    if (tab === "repeat_by_channel")
      return (
        <ChartCard
          title="Repeat rate by acquisition channel"
          kind="bar"
          data={rows.map((r) => ({ ...r, repeat_rate_pct: num(r.repeat_rate_pct) }))}
          xKey="acquisition_channel"
          series={[{ key: "repeat_rate_pct", label: "Repeat rate %", color: "#12885a" }]}
        />
      );
    if (tab === "campaign_by_segment")
      return (
        <ChartCard
          title="Conversion revenue by segment"
          kind="bar"
          data={rows.map((r) => ({ ...r, revenue: num(r.revenue) }))}
          xKey="segment"
          series={[{ key: "revenue", label: "Revenue", color: "#0ea5a5" }]}
          yPrefix="₹"
          yCompact
        />
      );
    return null;
  })();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Card title={data.name}>
        <p className="muted" style={{ marginTop: 0 }}>{data.question}</p>
        <div className="row">
          {data.techniques?.map((t: string) => (
            <span key={t} className="pill info">{t}</span>
          ))}
          <span className="spacer" />
          <span className="pill">{data.row_count} rows</span>
          <span className="pill">{data.execution_ms} ms</span>
        </div>
      </Card>

      {chart}

      <Card title="Result">
        <DataTable columns={data.columns} rows={rows} maxRows={300} />
      </Card>

      <Card title="SQL">
        <SqlBlock sql={data.sql} />
      </Card>
    </div>
  );
}
