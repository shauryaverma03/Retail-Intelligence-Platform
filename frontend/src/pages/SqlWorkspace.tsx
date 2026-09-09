import { useMemo, useState } from "react";
import { Card } from "../components/Card";
import { DataTable } from "../components/DataTable";
import { PageHeader } from "../components/Layout";
import { SqlBlock } from "../components/SqlBlock";
import { ErrorState, Loading } from "../components/States";
import { api } from "../api";
import { useApi, useAction } from "../hooks/useApi";
import { useSession } from "../session";

export function SqlWorkspace() {
  const { data: catalog, loading, error, reload } = useApi(() => api.catalog(), []);
  const { session, refresh: refreshSession } = useSession();
  const [sql, setSql] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const run = useAction(api.runQuery);

  const queries: any[] = catalog?.queries ?? [];
  const history: any[] = session?.recent_queries ?? [];
  const active = useMemo(
    () => queries.find((q) => q.id === selected) ?? null,
    [queries, selected],
  );

  const pickCatalog = (q: any) => {
    setSelected(q.id);
    setSql(q.sql);
    run.setData(null);
  };

  const execute = async (mode: "catalog" | "custom") => {
    if (mode === "catalog" && selected) {
      await run.run({ query_id: selected, explain: true });
    } else {
      setSelected(null);
      await run.run({ sql, explain: true });
    }
    refreshSession(); // pull the updated session query history
  };

  const res = run.data;

  return (
    <>
      <PageHeader title="SQL Analytics Workspace">
        Pick a reviewed analytical question or write your own. Custom SQL is
        parsed, restricted to a table allow-list, and executed read-only with a
        statement timeout. Queries you run are saved to this session.
      </PageHeader>

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorState message={error} onRetry={reload} />
      ) : (
        <div className="grid" style={{ gridTemplateColumns: "300px 1fr", gap: 16 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <Card title="Question catalog" sub={`${queries.length}`}>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {queries.map((q) => (
                  <button
                    key={q.id}
                    onClick={() => pickCatalog(q)}
                    className={selected === q.id ? "primary" : ""}
                    style={{ textAlign: "left", padding: "8px 10px" }}
                  >
                    <div style={{ fontWeight: 650 }}>{q.name}</div>
                    <div
                      className={selected === q.id ? "" : "muted"}
                      style={{ fontSize: 12, fontWeight: 400 }}
                    >
                      {q.question}
                    </div>
                  </button>
                ))}
              </div>
            </Card>

            <Card title="Session history" sub={`${history.length}`}>
              {history.length === 0 ? (
                <p className="muted" style={{ margin: 0, fontSize: 13 }}>
                  Queries you run this session show up here. Click one to reload it.
                </p>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {history.map((h) => (
                    <button
                      key={h.id}
                      onClick={() => {
                        setSelected(null);
                        setSql(h.sql);
                        run.setData(null);
                      }}
                      style={{ textAlign: "left", padding: "7px 9px" }}
                      title={h.sql}
                    >
                      <div className="mono" style={{ fontSize: 11.5, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {h.sql.replace(/\s+/g, " ").slice(0, 60)}
                      </div>
                      <div className="row" style={{ gap: 5, marginTop: 3 }}>
                        <span className={`pill ${h.ok ? "" : "bad"}`} style={{ fontSize: 10 }}>{h.source}</span>
                        {h.ok ? (
                          <span className="pill" style={{ fontSize: 10 }}>{h.row_count} rows · {h.execution_ms} ms</span>
                        ) : (
                          <span className="pill bad" style={{ fontSize: 10 }}>rejected</span>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </Card>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {active && (
              <Card title={active.name}>
                <p className="muted" style={{ marginTop: 0 }}>{active.question}</p>
                <div className="row" style={{ marginBottom: 8 }}>
                  {active.techniques?.map((t: string) => (
                    <span key={t} className="pill info">{t}</span>
                  ))}
                </div>
              </Card>
            )}

            <Card
              title="Editor"
              right={
                <div className="row">
                  <button onClick={() => execute(selected ? "catalog" : "custom")} className="primary" disabled={run.loading || !sql.trim()}>
                    {run.loading ? "Running…" : "Run"}
                  </button>
                </div>
              }
            >
              <textarea
                value={sql}
                onChange={(e) => {
                  setSql(e.target.value);
                  setSelected(null);
                }}
                placeholder="SELECT ... FROM orders WHERE status = 'completed' ..."
                spellCheck={false}
              />
              <p className="muted" style={{ margin: "8px 0 0" }}>
                Allowed tables: customers, products, campaigns, orders, order_items,
                campaign_events, etl_runs. Single SELECT only.
              </p>
            </Card>

            {run.error && <ErrorState message={run.error} />}

            {res && !res.ok && (
              <Card title="Query rejected">
                <p className="pill bad" style={{ display: "inline-block" }}>not executed</p>
                <p className="mono" style={{ marginTop: 10 }}>{res.error}</p>
              </Card>
            )}

            {res && res.ok && (
              <>
                <Card
                  title="Result"
                  right={
                    <div className="row">
                      <span className="pill">{res.row_count} rows</span>
                      <span className="pill">{res.execution_ms} ms</span>
                      <span className="pill info">{res.source}</span>
                      {res.truncated && <span className="pill warn">truncated</span>}
                    </div>
                  }
                >
                  <DataTable columns={res.columns} rows={res.rows} />
                </Card>

                <Card title="Executed SQL">
                  <SqlBlock sql={res.sql} />
                  {res.tables?.length > 0 && (
                    <p className="muted" style={{ marginTop: 8 }}>
                      Tables referenced: {res.tables.join(", ")}
                    </p>
                  )}
                </Card>

                {(res.plan_meta || res.plan) && (
                  <Card title="Query plan" sub="EXPLAIN (ANALYZE, BUFFERS)">
                    {res.plan_meta && (
                      <div className="grid cols-4">
                        <PlanStat label="Planning" value={`${res.plan_meta.planning_ms ?? "—"} ms`} />
                        <PlanStat label="Execution" value={`${res.plan_meta.execution_ms ?? "—"} ms`} />
                        <PlanStat label="Top node" value={res.plan_meta.top_node ?? "—"} />
                        <PlanStat label="Rows" value={res.plan_meta.actual_rows ?? "—"} />
                      </div>
                    )}
                    <details style={{ marginTop: 12 }}>
                      <summary className="muted">Raw plan JSON</summary>
                      <pre className="sql" style={{ marginTop: 8 }}>
                        {JSON.stringify(res.plan, null, 2)}
                      </pre>
                    </details>
                    {res.plan_error && <p className="mono">{res.plan_error}</p>}
                  </Card>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

function PlanStat({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="card stat" style={{ padding: 12 }}>
      <div className="label">{label}</div>
      <div className="value" style={{ fontSize: "1.05rem" }}>{String(value)}</div>
    </div>
  );
}
