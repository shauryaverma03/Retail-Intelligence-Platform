import { Card } from "./Card";

export interface Rec {
  id?: string;
  title?: string;
  priority?: string;
  finding: string;
  evidence: string;
  recommendation: string;
  expected_impact: string;
  next_step: string;
}

export function RecommendationCard({ rec }: { rec: Rec }) {
  return (
    <Card
      className="rec"
      title={rec.title ?? "Recommendation"}
      right={
        rec.priority ? (
          <span className={`pill ${rec.priority === "high" ? "bad" : "warn"}`}>
            {rec.priority} priority
          </span>
        ) : null
      }
    >
      <dl className="rec-grid">
        <dt>Finding</dt>
        <dd>{rec.finding}</dd>
        <dt>Evidence</dt>
        <dd className="mono">{rec.evidence}</dd>
        <dt>Recommendation</dt>
        <dd>{rec.recommendation}</dd>
        <dt>Expected impact</dt>
        <dd>{rec.expected_impact}</dd>
        <dt>Next step</dt>
        <dd>{rec.next_step}</dd>
      </dl>
    </Card>
  );
}
