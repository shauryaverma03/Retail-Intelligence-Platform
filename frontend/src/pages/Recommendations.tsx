import { PageHeader } from "../components/Layout";
import { RecommendationCard } from "../components/RecommendationCard";
import { ErrorState, Loading } from "../components/States";
import { api } from "../api";
import { useApi } from "../hooks/useApi";

export function Recommendations() {
  const { data, loading, error, reload } = useApi(() => api.recommendations(), []);

  if (loading) return <Loading label="Deriving recommendations from live SQL…" />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!data) return <ErrorState message="No recommendations." onRetry={reload} />;

  return (
    <>
      <PageHeader title="Business Recommendations" right={<button onClick={() => reload()}>Refresh</button>}>
        {data.count} recommendations. Each is generated from a query run during
        this request — the numbers in “Evidence” are real. Computed in{" "}
        {data.elapsed_ms} ms.
      </PageHeader>

      <div className="grid" style={{ gap: 14 }}>
        {data.recommendations.map((r: any) => (
          <RecommendationCard key={r.id} rec={r} />
        ))}
      </div>

      <p className="muted" style={{ marginTop: 16 }}>{data.note}</p>
    </>
  );
}
