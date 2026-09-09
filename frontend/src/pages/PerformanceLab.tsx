import { useState } from "react";
import { Card } from "../components/Card";
import { ChartCard } from "../components/ChartCard";
import { DataTable } from "../components/DataTable";
import { PageHeader } from "../components/Layout";
import { SqlBlock } from "../components/SqlBlock";
import { ErrorState, Loading } from "../components/States";
import { api } from "../api";
import { useAction, useApi } from "../hooks/useApi";

export function PerformanceLab() {
  const { data, loading, error, reload } = useApi(() => api.scenarios(), []);
  const bench = useAction(api.benchmark);
  const scaling = useAction(api.scalingBenchmark);
  const [openId, setOpenId] = useState<string | null>(null);

  if (loading) return <Loading />;
  if (error) return <ErrorState message={error} onRetry={reload} />;

  const scenarios: any[] = data?.scenarios ?? [];
  const r = bench.data;

  return (
    <>
      <PageHeader title="Query Performance Lab">
        Each scenario runs a real before/after benchmark against the live
        database: <span className="mono">EXPLAIN (ANALYZE, BUFFERS)</span> is
        executed on both states (one cold run discarded). Numbers below come
        straight from the planner.
      </PageHeader>

      <div className="grid" style={{ gap: 12 }}>
        {scenarios.map((s) => (
          <Card
            key={s.id}
            title={s.title}
            sub={s.category}
            right={
              <div className="row">
                {!s.available && <span className="pill warn">unavailable</span>}
                <button
                  className="primary"
                  disabled={bench.loading || !s.available}
                  onClick={() => {
                    setOpenId(s.id);
                    bench.run(s.id);
                  }}
                >
                  {bench.loading && openId === s.id ? "Benchmarking…" : "Run benchmark"}
                </button>
              </div>
            }
          >
            <p style={{ marginTop: 0 }}>{s.problem}</p>
            <p className="muted"><b>Technique:</b> {s.technique}</p>
            {!s.available && <p className="mono">{s.unavailable_reason}</p>}

            {openId === s.id && bench.error && <ErrorState message={bench.error} />}

            {openId === s.id && r && r.scenario_id === s.id && (
              <BenchmarkResult r={r} />
            )}
          </Card>
        ))}
      </div>

      <Card
        title="Dataset-size scaling benchmark"
        sub="same query, growing time window, with vs without the supporting index"
        right={
          <button className="primary" disabled={scaling.loading} onClick={() => scaling.run()}>
            {scaling.loading ? "Running…" : "Run scaling benchmark"}
          </button>
        }
        className=""
      >
        {scaling.error && <ErrorState message={scaling.error} />}
        {scaling.data && <ScalingResult data={scaling.data} />}
        {!scaling.data && !scaling.loading && (
          <p className="muted">
            Runs the conversion-revenue query over 30 / 180 / 730 / 3650 day
            windows, first with the index dropped then recreated, and reports
            EXPLAIN ANALYZE timing + buffers for all eight runs.
          </p>
        )}
      </Card>
    </>
  );
}

function BenchmarkResult({ r }: { r: any }) {
  const c = r.comparison;
  return (
    <div style={{ marginTop: 14 }}>
      <div className="grid cols-4" style={{ marginBottom: 12 }}>
        <Stat label="Before" value={`${c.execution_ms_before?.toFixed(1)} ms`} />
        <Stat label="After" value={`${c.execution_ms_after?.toFixed(1)} ms`} win />
        <Stat label="Speedup" value={c.speedup_x ? `${c.speedup_x}×` : "—"} win />
        <Stat label="Buffer reduction" value={c.buffer_reduction_x ? `${c.buffer_reduction_x}×` : "—"} />
      </div>

      <div className="row" style={{ marginBottom: 12 }}>
        {c.seq_scan_removed && <span className="pill ok">Seq Scan removed</span>}
        {c.became_index_only && <span className="pill ok">Now Index Only Scan</span>}
        {c.partitions_pruned_after > 0 && (
          <span className="pill ok">{c.partitions_pruned_after} partitions pruned</span>
        )}
        <span className="pill">buffers {c.buffers_before} → {c.buffers_after}</span>
      </div>

      <div className="bench-cols">
        <div className="bench-col">
          <h4>Before</h4>
          <SqlBlock sql={r.query_before} />
          <PlanFacts p={r.before} />
        </div>
        <div className="bench-col">
          <h4>After</h4>
          <SqlBlock sql={r.query_after} />
          <PlanFacts p={r.after} />
        </div>
      </div>

      <p className="muted" style={{ marginTop: 12 }}><b>Takeaway:</b> {r.takeaway}</p>

      <details style={{ marginTop: 8 }}>
        <summary className="muted">Raw EXPLAIN JSON (before / after)</summary>
        <div className="bench-cols" style={{ marginTop: 8 }}>
          <pre className="sql">{JSON.stringify(r.before.plan, null, 2)}</pre>
          <pre className="sql">{JSON.stringify(r.after.plan, null, 2)}</pre>
        </div>
      </details>
    </div>
  );
}

function PlanFacts({ p }: { p: any }) {
  return (
    <dl className="kv" style={{ marginTop: 10 }}>
      <dt>Execution</dt><dd className="mono">{p.execution_ms?.toFixed?.(2)} ms</dd>
      <dt>Scan types</dt><dd className="mono">{(p.scan_types ?? []).join(", ") || "—"}</dd>
      <dt>Buffers (hit+read)</dt><dd className="mono">{p.buffers_total}</dd>
      <dt>Rows</dt><dd className="mono">{p.actual_rows}</dd>
      <dt>Total cost</dt><dd className="mono">{p.total_cost}</dd>
    </dl>
  );
}

function ScalingResult({ data }: { data: any }) {
  const rows = data.windows_days.map((d: number, i: number) => ({
    window_days: d,
    with_index_ms: data.results.with_index[i]?.execution_ms,
    without_index_ms: data.results.without_index[i]?.execution_ms,
    rows_returned: data.results.with_index[i]?.rows_returned,
  }));
  return (
    <div style={{ marginTop: 10 }}>
      <ChartCard
        title="Execution time vs window size"
        kind="line"
        data={rows}
        xKey="window_days"
        series={[
          { key: "without_index_ms", label: "no index (ms)", color: "#d1394b" },
          { key: "with_index_ms", label: "with index (ms)", color: "#1a8f5b" },
        ]}
      />
      <div style={{ marginTop: 12 }}>
        <DataTable
          columns={["window_days", "without_index_ms", "with_index_ms", "rows_returned"]}
          rows={rows}
        />
      </div>
      <p className="muted" style={{ marginTop: 8 }}>{data.note}</p>
    </div>
  );
}

function Stat({ label, value, win }: { label: string; value: string; win?: boolean }) {
  return (
    <div className="card stat" style={{ padding: 12 }}>
      <div className="label">{label}</div>
      <div className={`metric-big ${win ? "win" : ""}`}>{value}</div>
    </div>
  );
}
