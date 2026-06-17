import type { OutreachRecommendation } from "../types";

interface OutreachRecommendationPanelProps {
  recommendation: OutreachRecommendation | null;
  loading: boolean;
}

export function OutreachRecommendationPanel({
  recommendation,
  loading,
}: OutreachRecommendationPanelProps) {
  if (loading) {
    return <p className="detail-loading">Loading AI outreach recommendation…</p>;
  }
  if (!recommendation) return null;

  return (
    <section className="study-recommendation">
      <h4>AI outreach recommendation</h4>
      <p className="panel-subtitle">{recommendation.rationale}</p>
      <ol>
        {recommendation.recommended_ranking.map((caseId) => (
          <li key={caseId}>
            <strong>{caseId}</strong>
            <span className="priority-score">
              Priority score: {recommendation.priority_scores[caseId]?.toFixed(1) ?? "—"}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
