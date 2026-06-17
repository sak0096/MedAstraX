interface ModelLimitationsPanelProps {
  priorityRuleDescription?: string;
}

export function ModelLimitationsPanel({ priorityRuleDescription }: ModelLimitationsPanelProps) {
  return (
    <section className="panel study-limitations">
      <h2>Data and model information</h2>
      <ul className="limitations-list">
        <li>Beneficiary records are CMS synthetic data for research only — not real patients.</li>
        <li>Risk scores reflect a frozen XGBoost model trained on administrative claims features.</li>
        <li>SHAP attributions describe model behavior, not clinical causality.</li>
        <li>Generated summaries and query interpretations may be incomplete or incorrect.</li>
        <li>Administrative claims do not capture full clinical context or social determinants.</li>
      </ul>
      {priorityRuleDescription ? (
        <div className="priority-rule-box">
          <h3>Operational outreach priority rule</h3>
          <p>{priorityRuleDescription}</p>
        </div>
      ) : null}
    </section>
  );
}
