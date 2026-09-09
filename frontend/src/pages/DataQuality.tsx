import { Card } from "../components/Card";
import { DataTable } from "../components/DataTable";
import { PageHeader } from "../components/Layout";
import { ErrorState, Loading } from "../components/States";
import { StatTile } from "../components/StatTile";
import { api } from "../api";
import { useApi } from "../hooks/useApi";

const statusPill = (s: string) =>
  s === "pass" ? "pill ok" : s === "warn" ? "pill warn" : "pill bad";

export function DataQuality() {
  const { data, loading, error, reload } = useApi(() => api.dataQuality(), []);

  if (loading) return <Loading label="Running data-quality checks…" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return <ErrorState message="No data." onRetry={reload} />;

  const s = data.summary;

  return (
    <>
      <PageHeader title="Data Quality" right={<button onClick={() => reload()}>Re-run</button>}>
        {data.checks.length} SQL checks across completeness, uniqueness, validity,
        integrity, timeliness and pipeline status. Ran in {data.elapsed_ms} ms.
      </PageHeader>

      <div className="grid cols-4">
        <StatTile label="Health score" value={`${s.health_score}%`} />
        <StatTile label="Passed" value={s.passed} />
        <StatTile label="Failed" value={s.failed} />
        <StatTile label="Warnings" value={s.warnings} />
      </div>

      <div className="grid" style={{ gap: 12, marginTop: 16 }}>
        {data.checks.map((c: any) => (
          <Card
            key={c.id}
            title={c.title}
            sub={c.category}
            right={
              <div className="row">
                <span className="pill">{c.severity}</span>
                <span className={statusPill(c.status)}>{c.status.toUpperCase()}</span>
              </div>
            }
          >
            <div className="row" style={{ marginBottom: 8 }}>
              <span className="pill">
                metric: <b style={{ marginLeft: 4 }}>{String(c.metric)}</b>
              </span>
              <span className="pill">threshold: {String(c.threshold)}</span>
            </div>
            {Array.isArray(c.detail) && c.detail.length > 0 && (
              <details>
                <summary className="muted">Detail ({c.detail.length} rows)</summary>
                <div style={{ marginTop: 8 }}>
                  <DataTable columns={Object.keys(c.detail[0])} rows={c.detail} maxRows={20} />
                </div>
              </details>
            )}
          </Card>
        ))}
      </div>

      <p className="muted" style={{ marginTop: 16 }}>{data.note}</p>
    </>
  );
}
