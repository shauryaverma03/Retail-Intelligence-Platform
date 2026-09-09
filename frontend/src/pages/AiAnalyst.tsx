import { useState } from "react";
import { Card } from "../components/Card";
import { DataTable } from "../components/DataTable";
import { PageHeader } from "../components/Layout";
import { RecommendationCard } from "../components/RecommendationCard";
import { SqlBlock } from "../components/SqlBlock";
import { ErrorState } from "../components/States";
import { api } from "../api";
import { useAction, useApi } from "../hooks/useApi";

export function AiAnalyst({ meta }: { meta: any }) {
  const { data: examples } = useApi(() => api.aiExamples(), []);
  const [q, setQ] = useState("");
  const ask = useAction(api.ask);
  const r = ask.data;

  const submit = (question?: string) => {
    const value = question ?? q;
    if (!value.trim()) return;
    setQ(value);
    ask.run(value, true);
  };

  return (
    <>
      <PageHeader title="AI Analyst">
        Ask a business question in plain English. The workflow: generate SQL →
        validate against the read-only guard → run it → summarise the{" "}
        <i>actual</i> rows → give a recommendation. Numbers are never invented.
      </PageHeader>

      <Card
        title="Ask a question"
        right={
          <span className={`pill ${meta?.ai_enabled ? "ok" : "warn"}`}>
            {meta?.ai_enabled ? `LLM: ${meta.ai_model}` : "rule-based fallback (no API key)"}
          </span>
        }
      >
        <textarea
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="e.g. Which campaigns have the best return on ad spend?"
          style={{ minHeight: 80 }}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") submit();
          }}
        />
        <div className="row" style={{ marginTop: 10 }}>
          <button className="primary" onClick={() => submit()} disabled={ask.loading || !q.trim()}>
            {ask.loading ? "Thinking…" : "Ask"}
          </button>
          <span className="muted">⌘/Ctrl + Enter</span>
        </div>
        <div className="row" style={{ marginTop: 12 }}>
          {(examples?.examples ?? []).map((ex: string) => (
            <button key={ex} style={{ fontSize: 12, padding: "5px 9px" }} onClick={() => submit(ex)}>
              {ex}
            </button>
          ))}
        </div>
      </Card>

      {ask.error && <ErrorState message={ask.error} />}

      {r && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 16 }}>
          {!r.ok ? (
            <Card title="Could not answer">
              <p className="mono">{r.error}</p>
              {r.validation_error && (
                <p className="mono">Guard rejection: {r.validation_error}</p>
              )}
              {r.sql && <SqlBlock sql={r.sql} />}
            </Card>
          ) : (
            <>
              <Card
                title="Answer"
                right={
                  <div className="row">
                    <span className="pill info">{r.engine}</span>
                    {r.summary_engine && <span className="pill">{r.summary_engine} summary</span>}
                    <span className="pill">{r.row_count} rows</span>
                    <span className="pill">{r.execution_ms} ms</span>
                  </div>
                }
              >
                <p style={{ fontSize: 15 }}>{r.summary}</p>
                <p className="muted">{r.disclaimer}</p>
              </Card>

              {r.recommendation && (
                <RecommendationCard
                  rec={{ title: "Recommendation", ...r.recommendation }}
                />
              )}

              <Card title="Generated SQL" sub={r.sql_valid ? "validated · read-only" : "invalid"}>
                <SqlBlock sql={r.sql} />
                {r.tables?.length > 0 && (
                  <p className="muted" style={{ marginTop: 8 }}>Tables: {r.tables.join(", ")}</p>
                )}
              </Card>

              <Card title="Result rows">
                <DataTable columns={r.columns} rows={r.rows} maxRows={200} />
              </Card>
            </>
          )}
        </div>
      )}
    </>
  );
}
